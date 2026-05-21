# git hook integration - install/uninstall graph post-commit and post-checkout hooks
from __future__ import annotations
import configparser
import re
import sys
from pathlib import Path

_HOOK_MARKER = "# graph-hook-start"
_HOOK_MARKER_END = "# graph-hook-end"
_CHECKOUT_MARKER = "# graph-checkout-hook-start"
_CHECKOUT_MARKER_END = "# graph-checkout-hook-end"

_PYTHON_DETECT = """\
# Detect the correct Python interpreter (handles pipx, venv, system installs)
GRAPH_BIN=$(command -v graph 2>/dev/null)
if [ -n "$GRAPH_BIN" ]; then
    case "$GRAPH_BIN" in
        *.exe) _SHEBANG="" ;;
        *)     _SHEBANG=$(head -1 "$GRAPH_BIN" | sed 's/^#![[:space:]]*//') ;;
    esac
    case "$_SHEBANG" in
        */env\\ *) GRAPH_PYTHON="${_SHEBANG#*/env }" ;;
        *)         GRAPH_PYTHON="$_SHEBANG" ;;
    esac
    # Allowlist: only keep characters valid in a filesystem path to prevent
    # injection if the shebang contains shell metacharacters
    case "$GRAPH_PYTHON" in
        *[!a-zA-Z0-9/_.@-]*) GRAPH_PYTHON="" ;;
    esac
    if [ -n "$GRAPH_PYTHON" ] && ! "$GRAPH_PYTHON" -c "import graph" 2>/dev/null; then
        GRAPH_PYTHON=""
    fi
fi
# Fall back: try python3, then python (Windows has no python3 shim)
if [ -z "$GRAPH_PYTHON" ]; then
    if command -v python3 >/dev/null 2>&1 && python3 -c "import graph" 2>/dev/null; then
        GRAPH_PYTHON="python3"
    elif command -v python >/dev/null 2>&1 && python -c "import graph" 2>/dev/null; then
        GRAPH_PYTHON="python"
    else
        exit 0
    fi
fi
"""

_HOOK_SCRIPT = """\
# graph-hook-start
# Auto-rebuilds the knowledge graph after each commit (code files only, no LLM needed).
# Installed by: graph hook install

# Skip during rebase/merge/cherry-pick to avoid blocking --continue with unstaged changes
GIT_DIR=$(git rev-parse --git-dir 2>/dev/null)
[ -d "$GIT_DIR/rebase-merge" ] && exit 0
[ -d "$GIT_DIR/rebase-apply" ] && exit 0
[ -f "$GIT_DIR/MERGE_HEAD" ] && exit 0
[ -f "$GIT_DIR/CHERRY_PICK_HEAD" ] && exit 0

CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || git diff --name-only HEAD 2>/dev/null)
if [ -z "$CHANGED" ]; then
    exit 0
fi

""" + _PYTHON_DETECT + """
export GRAPH_CHANGED="$CHANGED"

# Run rebuild detached so git commit returns immediately.
# Full repo rebuilds can take hours; blocking the post-commit hook stalls the shell.
_GRAPH_LOG="${HOME}/.cache/graph-rebuild.log"
mkdir -p "$(dirname "$_GRAPH_LOG")"
echo "[graph hook] launching background rebuild (log: $_GRAPH_LOG)"
nohup $GRAPH_PYTHON -c "
import os, signal, sys
from pathlib import Path

changed_raw = os.environ.get('GRAPH_CHANGED', '')
changed = [Path(f.strip()) for f in changed_raw.strip().splitlines() if f.strip()]

if not changed:
    sys.exit(0)

print(f'[graph hook] {len(changed)} file(s) changed - rebuilding graph...')

try:
    from graph.watch import _rebuild_code, _apply_resource_limits
    _apply_resource_limits()
    _timeout = int(os.environ.get('GRAPH_REBUILD_TIMEOUT', '600'))
    if _timeout > 0 and hasattr(signal, 'SIGALRM'):
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError(f'graph rebuild exceeded {_timeout}s')))
        signal.alarm(_timeout)
    _force = os.environ.get('GRAPH_FORCE', '').lower() in ('1', 'true', 'yes')
    _rebuild_code(Path('.'), changed_paths=changed, force=_force)
except TimeoutError as exc:
    print(f'[graph hook] {exc}')
    sys.exit(1)
except Exception as exc:
    print(f'[graph hook] Rebuild failed: {exc}')
    sys.exit(1)
" > "$_GRAPH_LOG" 2>&1 < /dev/null &
disown 2>/dev/null || true
# graph-hook-end
"""


_CHECKOUT_SCRIPT = """\
# graph-checkout-hook-start
# Auto-rebuilds the knowledge graph (code only) when switching branches.
# Installed by: graph hook install

PREV_HEAD=$1
NEW_HEAD=$2
BRANCH_SWITCH=$3

# Only run on branch switches, not file checkouts
if [ "$BRANCH_SWITCH" != "1" ]; then
    exit 0
fi

# Only run if graph-out/ exists (graph has been built before)
if [ ! -d "graph-out" ]; then
    exit 0
fi

# Skip during rebase/merge/cherry-pick
GIT_DIR=$(git rev-parse --git-dir 2>/dev/null)
[ -d "$GIT_DIR/rebase-merge" ] && exit 0
[ -d "$GIT_DIR/rebase-apply" ] && exit 0
[ -f "$GIT_DIR/MERGE_HEAD" ] && exit 0
[ -f "$GIT_DIR/CHERRY_PICK_HEAD" ] && exit 0

""" + _PYTHON_DETECT + """
_GRAPH_LOG="${HOME}/.cache/graph-rebuild.log"
mkdir -p "$(dirname "$_GRAPH_LOG")"
echo "[graph] Branch switched - launching background rebuild (log: $_GRAPH_LOG)"
nohup $GRAPH_PYTHON -c "
from graph.watch import _rebuild_code, _apply_resource_limits
from pathlib import Path
import os, signal, sys
try:
    _apply_resource_limits()
    _timeout = int(os.environ.get('GRAPH_REBUILD_TIMEOUT', '600'))
    if _timeout > 0 and hasattr(signal, 'SIGALRM'):
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError(f'graph rebuild exceeded {_timeout}s')))
        signal.alarm(_timeout)
    _force = os.environ.get('GRAPH_FORCE', '').lower() in ('1', 'true', 'yes')
    # post-checkout: branch switch can touch arbitrary files; full rebuild path
    # (no changed_paths) is correct here. The flock inside _rebuild_code still
    # prevents pile-ups when commit + checkout fire back-to-back.
    _rebuild_code(Path('.'), force=_force)
except TimeoutError as exc:
    print(f'[graph] {exc}')
    sys.exit(1)
except Exception as exc:
    print(f'[graph] Rebuild failed: {exc}')
    sys.exit(1)
" > "$_GRAPH_LOG" 2>&1 < /dev/null &
disown 2>/dev/null || true
# graph-checkout-hook-end
"""


def _git_root(path: Path) -> Path | None:
    """Walk up to find .git directory."""
    current = path.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _hooks_dir(root: Path) -> Path:
    """Return the git hooks directory, respecting core.hooksPath if set (e.g. Husky)."""
    try:
        cfg = configparser.RawConfigParser()
        cfg.read(root / ".git" / "config", encoding="utf-8")
        # configparser lowercases option names; git's hooksPath becomes hookspath
        custom = cfg.get("core", "hookspath", fallback="").strip()
        if custom:
            p = Path(custom).expanduser()
            if not p.is_absolute():
                p = root / p
            # Validate the resolved path stays within the repository root
            # to prevent supply-chain attacks via malicious core.hooksPath values
            try:
                p.resolve().relative_to(root.resolve())
            except ValueError:
                pass  # Path escapes repo root; fall through to default .git/hooks
            else:
                p.mkdir(parents=True, exist_ok=True)
                return p
    except (configparser.Error, OSError) as exc:
        # Narrow the exception (PR747-NEW-2): a bare `except Exception: pass`
        # was hiding tampering signals (corrupt .git/config, permission flips
        # by another tool). Surface them on stderr instead of silently
        # falling through to the default hooks directory.
        print(
            f"[graph hooks] could not read core.hooksPath from "
            f"{root / '.git' / 'config'}: {exc}",
            file=sys.stderr,
        )
    # In a linked worktree .git is a file not a directory, so constructing
    # root/.git/hooks directly fails. Ask git for the real hooks path instead.
    # NOTE: do NOT pass --path-format=absolute — added in git 2.31; older git
    # echoes it back as a literal argument, contaminating stdout and causing a
    # phantom directory to be created (#907). git -C <root> already returns an
    # absolute path for worktree/external-gitdir cases, and a path relative to
    # <root> for normal repos — anchoring on root covers both.
    import subprocess as _sp
    try:
        res = _sp.run(
            ["git", "-C", str(root), "rev-parse", "--git-path", "hooks"],
            capture_output=True, text=True,
        )
        raw = res.stdout.strip()
        # A valid hooks path can never contain newlines or NUL. Their presence
        # means git echoed an unrecognised flag back (old git behaviour).
        if res.returncode == 0 and raw and not any(c in raw for c in ("\n", "\r", "\x00")):
            d = (root / raw).resolve()
            d.mkdir(parents=True, exist_ok=True)
            return d
    except (OSError, FileNotFoundError):
        pass
    d = root / ".git" / "hooks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _install_hook(hooks_dir: Path, name: str, script: str, marker: str) -> str:
    """Install a single git hook, appending if an existing hook is present."""
    hook_path = hooks_dir / name
    if hook_path.exists():
        content = hook_path.read_text(encoding="utf-8")
        if marker in content:
            return f"already installed at {hook_path}"
        hook_path.write_text(content.rstrip() + "\n\n" + script, encoding="utf-8", newline="\n")
        return f"appended to existing {name} hook at {hook_path}"
    hook_path.write_text("#!/bin/sh\n" + script, encoding="utf-8", newline="\n")
    hook_path.chmod(0o755)
    return f"installed at {hook_path}"


def _uninstall_hook(hooks_dir: Path, name: str, marker: str, marker_end: str) -> str:
    """Remove graph section from a git hook using start/end markers."""
    hook_path = hooks_dir / name
    if not hook_path.exists():
        return f"no {name} hook found - nothing to remove."
    content = hook_path.read_text(encoding="utf-8")
    if marker not in content:
        return f"graph hook not found in {name} - nothing to remove."
    new_content = re.sub(
        rf"{re.escape(marker)}.*?{re.escape(marker_end)}\n?",
        "",
        content,
        flags=re.DOTALL,
    ).strip()
    if not new_content or new_content in ("#!/bin/bash", "#!/bin/sh"):
        hook_path.unlink()
        return f"removed {name} hook at {hook_path}"
    hook_path.write_text(new_content + "\n", encoding="utf-8", newline="\n")
    return f"graph removed from {name} at {hook_path} (other hook content preserved)"


def install(path: Path = Path(".")) -> str:
    """Install graph post-commit and post-checkout hooks in the nearest git repo."""
    root = _git_root(path)
    if root is None:
        raise RuntimeError(f"No git repository found at or above {path.resolve()}")

    hooks_dir = _hooks_dir(root)

    commit_msg = _install_hook(hooks_dir, "post-commit", _HOOK_SCRIPT, _HOOK_MARKER)
    checkout_msg = _install_hook(hooks_dir, "post-checkout", _CHECKOUT_SCRIPT, _CHECKOUT_MARKER)

    return f"post-commit: {commit_msg}\npost-checkout: {checkout_msg}"


def uninstall(path: Path = Path(".")) -> str:
    """Remove graph post-commit and post-checkout hooks."""
    root = _git_root(path)
    if root is None:
        raise RuntimeError(f"No git repository found at or above {path.resolve()}")

    hooks_dir = _hooks_dir(root)
    commit_msg = _uninstall_hook(hooks_dir, "post-commit", _HOOK_MARKER, _HOOK_MARKER_END)
    checkout_msg = _uninstall_hook(hooks_dir, "post-checkout", _CHECKOUT_MARKER, _CHECKOUT_MARKER_END)

    return f"post-commit: {commit_msg}\npost-checkout: {checkout_msg}"


def status(path: Path = Path(".")) -> str:
    """Check if graph hooks are installed."""
    root = _git_root(path)
    if root is None:
        return "Not in a git repository."
    hooks_dir = _hooks_dir(root)

    def _check(name: str, marker: str) -> str:
        p = hooks_dir / name
        if not p.exists():
            return "not installed"
        return "installed" if marker in p.read_text(encoding="utf-8") else "not installed (hook exists but graph not found)"

    commit = _check("post-commit", _HOOK_MARKER)
    checkout = _check("post-checkout", _CHECKOUT_MARKER)
    return f"post-commit: {commit}\npost-checkout: {checkout}"

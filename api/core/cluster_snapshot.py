"""On-demand Kubernetes cluster inventory (read-only snapshot)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.core.pkb_storage import project_dir


def snapshot_path(project_id: str) -> Path:
    return project_dir(project_id) / "cluster_snapshot.json"


def load_snapshot(project_id: str) -> dict[str, Any] | None:
    p = snapshot_path(project_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_snapshot(project_id: str, data: dict[str, Any]) -> Path:
    p = snapshot_path(project_id)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def _kubectl_json(args: list[str], kubeconfig: str | None) -> Any:
    cmd = ["kubectl", *args, "-o", "json"]
    if kubeconfig:
        cmd.extend(["--kubeconfig", kubeconfig])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout or "kubectl failed")
    return json.loads(proc.stdout)


def capture_cluster_snapshot(
    project_id: str,
    *,
    kubeconfig: str | None = None,
    context: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """List deployments, services, ingresses via kubectl (read-only)."""
    ns_flag = ["-n", namespace] if namespace else ["--all-namespaces"]
    ctx_flag = ["--context", context] if context else []

    resources: list[dict[str, Any]] = []
    for kind in ("deployments", "services", "ingresses"):
        try:
            data = _kubectl_json(
                ["get", kind, *ns_flag, *ctx_flag],
                kubeconfig,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "kubectl not found. Install kubectl and configure cluster access."
            ) from None
        items = data.get("items") or []
        for item in items:
            meta = item.get("metadata") or {}
            spec = item.get("spec") or {}
            name = meta.get("name", "")
            ns = meta.get("namespace", namespace or "default")
            labels = meta.get("labels") or {}
            rid = f"{kind}/{ns}/{name}"
            resources.append({
                "id": rid,
                "kind": kind.rstrip("s") if kind.endswith("s") else kind,
                "name": name,
                "namespace": ns,
                "labels": labels,
                "source": "cluster_snapshot",
                "selector": (spec.get("selector") or {}).get("matchLabels"),
                "ports": [p.get("port") for p in (spec.get("ports") or []) if isinstance(p, dict)],
            })

    cluster_name = context or "default"
    try:
        cmd = ["kubectl", "config", "current-context"]
        if kubeconfig:
            cmd.extend(["--kubeconfig", kubeconfig])
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if proc.returncode == 0 and proc.stdout.strip():
            cluster_name = context or proc.stdout.strip()
    except Exception:
        pass

    snapshot = {
        "project_id": project_id,
        "cluster": cluster_name,
        "context": context,
        "namespace_filter": namespace,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "resource_count": len(resources),
        "resources": resources,
    }
    save_snapshot(project_id, snapshot)
    return snapshot


def compute_drift(
    static_labels: set[str],
    snapshot: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Compare declared infra names (from cd graph) vs running cluster resources."""
    if not snapshot:
        return []
    running = {
        (r.get("name") or "").lower(): r
        for r in snapshot.get("resources", [])
        if r.get("name")
    }
    drift: list[dict[str, Any]] = []
    for name in sorted(static_labels):
        key = name.lower()
        if key in running:
            drift.append({
                "resource": name,
                "declared": True,
                "running": True,
                "status": "matched",
            })
        else:
            drift.append({
                "resource": name,
                "declared": True,
                "running": False,
                "status": "not_deployed",
            })
    for key, r in running.items():
        if key not in {n.lower() for n in static_labels}:
            drift.append({
                "resource": r.get("name"),
                "declared": False,
                "running": True,
                "status": "undeclared_running",
            })
    return drift[:100]

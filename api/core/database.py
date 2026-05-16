"""SQLite database for graph job metadata."""
from __future__ import annotations
import sqlite3
import threading
from pathlib import Path
from api.config import DB_PATH

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS graphs (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            source_path TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            backend     TEXT,
            -- role classifies what this graph represents:
            -- source | test | ci | cd
            graph_role  TEXT NOT NULL DEFAULT 'source',
            project_id  TEXT,
            node_count  INTEGER DEFAULT 0,
            edge_count  INTEGER DEFAULT 0,
            community_count INTEGER DEFAULT 0,
            error       TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Migration: add graph_role/project_id if they don't exist yet
        -- (no-op when column already present; SQLite ignores duplicate ADD COLUMN
        --  only if we catch the error — handled in Python below)

        CREATE TABLE IF NOT EXISTS projects (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS policies (
            id          TEXT PRIMARY KEY,
            graph_id    TEXT NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            rules_yaml  TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS memory_items (
            id          TEXT PRIMARY KEY,
            graph_id    TEXT NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
            source_type TEXT NOT NULL,
            source_ref  TEXT NOT NULL,
            content     TEXT,
            status      TEXT NOT NULL DEFAULT 'pending',
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    # Safe column migrations for existing DBs
    for col, defn in [
        ("graph_role", "TEXT NOT NULL DEFAULT 'source'"),
        ("project_id",  "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE graphs ADD COLUMN {col} {defn}")
        except Exception:
            pass  # column already exists
    conn.commit()


def upsert_graph(graph_id: str, **fields) -> None:
    conn = get_conn()
    fields["updated_at"] = "datetime('now')"
    set_clause = ", ".join(f"{k} = :{k}" for k in fields if k != "updated_at")
    set_clause += ", updated_at = datetime('now')"
    conn.execute(
        f"UPDATE graphs SET {set_clause} WHERE id = :id",
        {"id": graph_id, **fields},
    )
    conn.commit()


def insert_graph(
    graph_id: str,
    name: str,
    source_path: str,
    backend: str,
    graph_role: str = "source",
    project_id: str | None = None,
) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO graphs
           (id, name, source_path, backend, status, graph_role, project_id)
           VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
        (graph_id, name, source_path, backend, graph_role, project_id),
    )
    conn.commit()


def get_graph(graph_id: str) -> sqlite3.Row | None:
    conn = get_conn()
    return conn.execute("SELECT * FROM graphs WHERE id = ?", (graph_id,)).fetchone()


def list_graphs(project_id: str | None = None) -> list[sqlite3.Row]:
    conn = get_conn()
    if project_id:
        return conn.execute(
            "SELECT * FROM graphs WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    return conn.execute("SELECT * FROM graphs ORDER BY created_at DESC").fetchall()


def get_graph_for_project_role(project_id: str, graph_role: str) -> sqlite3.Row | None:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM graphs WHERE project_id = ? AND graph_role = ? LIMIT 1",
        (project_id, graph_role),
    ).fetchone()


def delete_graph_row(graph_id: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM graphs WHERE id = ?", (graph_id,))
    conn.commit()


def delete_project_cascade(project_id: str) -> list[str]:
    """Delete project and all its graphs. Returns deleted graph ids."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id FROM graphs WHERE project_id = ?", (project_id,)
    ).fetchall()
    graph_ids = [r["id"] for r in rows]
    for gid in graph_ids:
        conn.execute("DELETE FROM graphs WHERE id = ?", (gid,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    return graph_ids


# ── Project CRUD ──────────────────────────────────────────────────────────────

def insert_project(project_id: str, name: str, description: str = "") -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO projects (id, name, description) VALUES (?, ?, ?)",
        (project_id, name, description),
    )
    conn.commit()


def get_project(project_id: str) -> sqlite3.Row | None:
    conn = get_conn()
    return conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()


def list_projects() -> list[sqlite3.Row]:
    conn = get_conn()
    return conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()


def update_project(project_id: str, **fields) -> None:
    conn = get_conn()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    set_clause += ", updated_at = datetime('now')"
    conn.execute(
        f"UPDATE projects SET {set_clause} WHERE id = ?",
        (*fields.values(), project_id),
    )
    conn.commit()


def delete_project(project_id: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()


def get_project_graphs(project_id: str) -> list[sqlite3.Row]:
    """Return all graphs associated with a project, ordered by role."""
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM graphs WHERE project_id = ? ORDER BY graph_role, created_at",
        (project_id,),
    ).fetchall()


def assign_graph_to_project(graph_id: str, project_id: str, graph_role: str | None = None) -> None:
    """Attach graph to project. Caller must enforce project-scope rules."""
    conn = get_conn()
    if graph_role:
        conn.execute(
            "UPDATE graphs SET project_id = ?, graph_role = ?, updated_at = datetime('now') WHERE id = ?",
            (project_id, graph_role, graph_id),
        )
    else:
        conn.execute(
            "UPDATE graphs SET project_id = ?, updated_at = datetime('now') WHERE id = ?",
            (project_id, graph_id),
        )
    conn.commit()

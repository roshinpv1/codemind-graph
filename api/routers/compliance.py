"""CodeMind Compliance — topology-aware compliance intelligence (PII, GDPR, HIPAA, PCI)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.core import engine, database

router = APIRouter(prefix="/graphs/{graph_id}/compliance", tags=["Compliance"])

# Keyword sets for data classification
_PII_KEYWORDS = frozenset({"email", "phone", "address", "ssn", "dob", "name", "user_id", "passport", "national_id", "pii", "personal"})
_PHI_KEYWORDS = frozenset({"patient", "diagnosis", "medication", "health", "medical", "mrn", "phi", "clinical", "prescription"})
_PCI_KEYWORDS = frozenset({"card", "credit", "cvv", "pan", "payment", "billing", "cardholder", "stripe", "checkout"})

_STANDARDS = {
    "gdpr": _PII_KEYWORDS,
    "hipaa": _PHI_KEYWORDS,
    "pci": _PCI_KEYWORDS,
}


class AuditBoundaryRequest(BaseModel):
    boundary_name: str
    included_paths: list[str]  # source_file path fragments that are in scope


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")


def _classify_node(G, nid: str) -> list[str]:
    label = (G.nodes[nid].get("label") or "").lower()
    src = (G.nodes[nid].get("source_file") or "").lower()
    text = label + " " + src
    tags = []
    if any(kw in text for kw in _PII_KEYWORDS):
        tags.append("pii")
    if any(kw in text for kw in _PHI_KEYWORDS):
        tags.append("phi")
    if any(kw in text for kw in _PCI_KEYWORDS):
        tags.append("pci")
    return tags


@router.get("/pii-flows", response_model=list[dict], summary="All PII propagation paths in the graph")
def pii_flows(graph_id: str, standard: str = "gdpr"):
    """
    Trace how PII (or PHI/PCI) data propagates through the call graph.
    standard: gdpr | hipaa | pci
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    keywords = _STANDARDS.get(standard.lower(), _PII_KEYWORDS)
    sensitive_nodes = [
        nid for nid in G.nodes()
        if any(kw in (G.nodes[nid].get("label") or "").lower() or kw in (G.nodes[nid].get("source_file") or "").lower()
               for kw in keywords)
    ]
    result = []
    for nid in sensitive_nodes[:30]:
        node_ids, edges = engine.bfs(G, [nid], depth=3)
        node_ids.discard(nid)
        result.append({
            "pii_node": nid,
            "pii_label": G.nodes[nid].get("label", nid),
            "source_file": G.nodes[nid].get("source_file", ""),
            "classification": _classify_node(G, nid),
            "propagates_to": [
                {"id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
                for n in list(node_ids)[:10]
            ],
            "propagation_count": len(node_ids),
        })
    return sorted(result, key=lambda x: x["propagation_count"], reverse=True)


@router.get("/audit-boundary", response_model=dict, summary="What's in scope for a given regulation")
def audit_boundary(graph_id: str, standard: str = "gdpr"):
    """Return all nodes that handle regulated data for a given compliance standard."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    keywords = _STANDARDS.get(standard.lower(), _PII_KEYWORDS)
    in_scope = []
    out_of_scope_count = 0
    for nid, data in G.nodes(data=True):
        tags = _classify_node(G, nid)
        if standard.lower() in ("gdpr", "all") and "pii" in tags:
            in_scope.append({"id": nid, "label": data.get("label", nid), "source_file": data.get("source_file", ""), "tags": tags})
        elif standard.lower() == "hipaa" and "phi" in tags:
            in_scope.append({"id": nid, "label": data.get("label", nid), "source_file": data.get("source_file", ""), "tags": tags})
        elif standard.lower() == "pci" and "pci" in tags:
            in_scope.append({"id": nid, "label": data.get("label", nid), "source_file": data.get("source_file", ""), "tags": tags})
        else:
            out_of_scope_count += 1
    return {
        "standard": standard,
        "in_scope_count": len(in_scope),
        "out_of_scope_count": out_of_scope_count,
        "in_scope_nodes": in_scope[:100],
    }


@router.get("/violations", response_model=list[dict], summary="Policy violations by compliance standard")
def compliance_violations(graph_id: str, standard: str = "gdpr"):
    """
    Detect nodes that handle regulated data but propagate it to unclassified nodes —
    a proxy for uncontrolled data egress.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    keywords = _STANDARDS.get(standard.lower(), _PII_KEYWORDS)
    sensitive_set = {
        nid for nid in G.nodes()
        if any(kw in (G.nodes[nid].get("label") or "").lower() for kw in keywords)
    }
    violations = []
    for u, v, data in G.edges(data=True):
        if u in sensitive_set and v not in sensitive_set:
            v_tags = _classify_node(G, v)
            if not v_tags:
                violations.append({
                    "standard": standard,
                    "sensitive_node": u,
                    "sensitive_label": G.nodes[u].get("label", u),
                    "receiving_node": v,
                    "receiving_label": G.nodes[v].get("label", v),
                    "receiving_file": G.nodes[v].get("source_file", ""),
                    "relation": data.get("relation", ""),
                    "risk": "Regulated data flows to unclassified node — potential uncontrolled egress",
                })
    return violations[:100]


@router.get("/lineage", response_model=dict, summary="Full data lineage for a PII node")
def data_lineage(graph_id: str, node: str, depth: int = 4):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, node)
    if not matches:
        return {"node": node, "lineage": [], "message": "Node not found"}
    nid = matches[0]
    fwd_ids, fwd_edges = engine.bfs(G, [nid], depth)
    rev = G.reverse() if G.is_directed() else G
    rev_ids, _ = engine.bfs(rev, [nid], depth=2)
    fwd_ids.discard(nid)
    rev_ids.discard(nid)
    return {
        "node": {"id": nid, "label": G.nodes[nid].get("label", nid), "classification": _classify_node(G, nid)},
        "data_sources": [{"id": n, "label": G.nodes[n].get("label", n)} for n in rev_ids if n in G],
        "data_destinations": [{"id": n, "label": G.nodes[n].get("label", n), "classification": _classify_node(G, n)} for n in fwd_ids if n in G],
        "unclassified_destinations": [n for n in fwd_ids if not _classify_node(G, n) and n in G],
    }


@router.get("/evidence", response_model=dict, summary="Export compliance evidence package")
def compliance_evidence(graph_id: str, standard: str = "gdpr"):
    """Generate a structured compliance evidence package with graph provenance."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    keywords = _STANDARDS.get(standard.lower(), _PII_KEYWORDS)
    sensitive = [nid for nid in G.nodes() if any(kw in (G.nodes[nid].get("label") or "").lower() for kw in keywords)]
    violations_count = sum(
        1 for u, v in G.edges()
        if u in sensitive and not _classify_node(G, v)
    )
    evidence = {
        "standard": standard.upper(),
        "graph_id": graph_id,
        "total_nodes": G.number_of_nodes(),
        "regulated_nodes": len(sensitive),
        "potential_violations": violations_count,
        "compliance_status": "REVIEW_REQUIRED" if violations_count > 0 else "PASS",
        "regulated_node_samples": [
            {"id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
            for n in sensitive[:20]
        ],
    }
    return evidence

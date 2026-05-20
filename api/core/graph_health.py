"""Fast graph health metrics — safe for large code graphs (no unbounded simple_cycles)."""
from __future__ import annotations

import re

import networkx as nx

# Conservative: likely framework entry / plugin surfaces
_SAFE_NAME = re.compile(
    r"(Plugin|Handler|Adapter|Middleware|Controller|Route|__init__|main|index|app)\b",
    re.I,
)
_DYNAMIC_LOAD = re.compile(r"importlib|__import__|getattr\s*\(", re.I)

# Above this size, use SCC-based cycle proxy instead of enumerating simple cycles.
_SIMPLE_CYCLE_NODE_LIMIT = 1_500
_SIMPLE_CYCLE_MAX = 200


def count_circular_dependencies(G: nx.Graph) -> tuple[int, bool]:
    """
    Return (count, approximate).
    For large graphs uses strongly connected components (size > 1) as a cycle proxy.
    """
    if G.number_of_nodes() == 0:
        return 0, False
    if not G.is_directed():
        return 0, False

    n = G.number_of_nodes()
    if n > _SIMPLE_CYCLE_NODE_LIMIT:
        sccs = [c for c in nx.strongly_connected_components(G) if len(c) > 1]
        return len(sccs), True

    try:
        count = 0
        for _ in nx.simple_cycles(G):
            count += 1
            if count >= _SIMPLE_CYCLE_MAX:
                return _SIMPLE_CYCLE_MAX, True
        return count, False
    except Exception:
        sccs = [c for c in nx.strongly_connected_components(G) if len(c) > 1]
        return len(sccs), True


def dead_code_candidates(G: nx.Graph, *, limit: int = 500) -> list[dict]:
    """Nodes with no incoming references — likely dead or entry-only code."""
    result: list[dict] = []
    for n, data in G.nodes(data=True):
        if not _is_trackable_code_node(data):
            continue
        if G.is_directed():
            in_deg = G.in_degree(n)
            out_deg = G.out_degree(n)
        else:
            in_deg = G.degree(n)
            out_deg = in_deg
        if in_deg != 0:
            continue
        result.append({
            "id": n,
            "label": data.get("label", n),
            "source_file": data.get("source_file", ""),
            "out_degree": out_deg,
        })
        if len(result) >= limit:
            break
    return sorted(result, key=lambda x: (x.get("source_file") or "", x.get("label") or ""))


def _is_trackable_code_node(data: dict) -> bool:
    ft = (data.get("file_type") or "").lower()
    if ft in ("code", "function", "class", "method", "module", "file"):
        return True
    if ft in ("doc", "rationale", "concept", "directory"):
        return False
    return bool(data.get("source_file"))


def dead_code_node_ids(G: nx.Graph, *, limit: int = 5_000) -> list[str]:
    return [r["id"] for r in dead_code_candidates(G, limit=limit)]


def _dead_code_confidence(data: dict, out_degree: int) -> float:
    label = (data.get("label") or "")
    sf = (data.get("source_file") or "")
    score = 0.55
    if out_degree == 0:
        score += 0.25
    elif out_degree <= 1:
        score += 0.1
    if _SAFE_NAME.search(label) or _SAFE_NAME.search(sf):
        score -= 0.35
    if _DYNAMIC_LOAD.search(label):
        score -= 0.2
    if len(label) <= 3 or label in (".push()", ".call()", ".slice()"):
        score -= 0.4
    return max(0.1, min(1.0, round(score, 2)))


def classify_dead_code(G: nx.Graph, *, limit: int = 500) -> list[dict]:
    """Dead-code candidates with confidence tier for UI and agents."""
    raw = dead_code_candidates(G, limit=limit)
    out: list[dict] = []
    for item in raw:
        nid = item["id"]
        data = G.nodes[nid] if nid in G else {}
        conf = _dead_code_confidence(data, int(item.get("out_degree") or 0))
        tier = "safe_to_remove" if conf >= 0.7 else "review_first" if conf >= 0.45 else "uncertain"
        out.append({
            **item,
            "confidence": conf,
            "tier": tier,
            "tier_label": {
                "safe_to_remove": "Likely safe to remove",
                "review_first": "Review before removing",
                "uncertain": "Uncertain",
            }.get(tier, tier),
        })
    out.sort(key=lambda x: (-x["confidence"], x.get("source_file") or "", x.get("label") or ""))
    return out


def sample_cycles_for_display(
    G: nx.Graph,
    *,
    max_samples: int = 20,
) -> tuple[list[list[str]], bool]:
    """
    Return (list of node-id cycles/groups, approximate).
    Large graphs: one representative path per cyclic strongly connected component.
    """
    if G.number_of_nodes() == 0 or not G.is_directed():
        return [], False

    n = G.number_of_nodes()
    if n <= _SIMPLE_CYCLE_NODE_LIMIT:
        out: list[list[str]] = []
        try:
            for i, cycle in enumerate(nx.simple_cycles(G)):
                out.append(cycle)
                if i >= max_samples - 1:
                    return out, False
        except Exception:
            pass
        if out:
            return out, False

    out = []
    for scc in nx.strongly_connected_components(G):
        if len(scc) < 2:
            continue
        hubs = sorted(scc, key=lambda node: G.degree(node), reverse=True)[: min(8, len(scc))]
        out.append(hubs)
        if len(out) >= max_samples:
            break
    return out, True


def structural_architecture_findings(G: nx.Graph) -> list[dict]:
    """Built-in architecture signals (no custom policy YAML required)."""
    findings: list[dict] = []
    if G.number_of_nodes() == 0:
        return findings

    degrees = [G.degree(n) for n in G.nodes()]
    avg_deg = sum(degrees) / len(degrees) if degrees else 0
    for nid, data in G.nodes(data=True):
        d = G.degree(nid)
        if d > avg_deg * 5 and d > 20:
            findings.append({
                "rule": "hub_concentration",
                "severity": "warning",
                "source": nid,
                "source_label": data.get("label", nid),
                "target": "",
                "target_label": "",
                "relation": "",
                "message": f"Highly connected component ({d} links vs avg {avg_deg:.0f}) — change-risk hotspot",
            })

    cycle_count, approx = count_circular_dependencies(G)
    if cycle_count > 0:
        label = "cyclic_dependency_groups" if approx else "circular_dependencies"
        findings.append({
            "rule": label,
            "severity": "warning",
            "source": "",
            "source_label": "",
            "target": "",
            "target_label": "",
            "relation": "",
            "message": (
                f"{cycle_count} {'cyclic dependency group(s)' if approx else 'circular dependency chain(s)'} detected"
            ),
        })

    communities = None
    try:
        from api.core import engine
        communities = engine.communities_from_graph(G)
    except Exception:
        communities = {}

    for cid, members in (communities or {}).items():
        if len(members) < 3:
            continue
        member_set = set(members)
        external = sum(1 for n in members for nb in G.neighbors(n) if nb not in member_set)
        intra = sum(1 for n in members for nb in G.neighbors(n) if nb in member_set)
        if intra > 0 and external / max(intra, 1) > 3:
            hub = max(members, key=lambda n: G.degree(n), default=members[0])
            findings.append({
                "rule": "cross_area_coupling",
                "severity": "info",
                "source": hub,
                "source_label": G.nodes[hub].get("label", hub),
                "target": "",
                "target_label": "",
                "relation": "",
                "message": f"Product area has high outward coupling (external/internal ratio {external / max(intra, 1):.1f})",
            })

    dead = dead_code_candidates(G, limit=1)
    dead_n = len(dead_code_candidates(G, limit=500))
    if dead_n > 0:
        findings.append({
            "rule": "unreferenced_code",
            "severity": "info",
            "source": dead[0]["id"] if dead else "",
            "source_label": dead[0].get("label", "") if dead else "",
            "target": "",
            "target_label": "",
            "relation": "",
            "message": f"{dead_n}+ components with no incoming references (possible dead or entry-only code)",
        })

    return findings[:25]

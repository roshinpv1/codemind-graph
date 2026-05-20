# Functional coverage in CodeMind — expected vs actual

This document explains **how CodeMind calculates “functional coverage”**: what counts as **expected** (the denominator), what counts as **actual** (the numerator), and how application code and test code are combined. It reflects the implementation in `api/routers/coverage.py`, `api/core/cross_graph.py`, and `api/core/project_synthesis.py` (and the project endpoint in `api/routers/projects.py` where noted).

---

## 1. What functional coverage means here

**Functional coverage** is **not** line coverage, branch coverage, or “did pytest execute this bytecode.” It is a **static analysis** over a **knowledge graph** built from your repository:

| Idea | Meaning |
|------|--------|
| **Expected (denominator)** | “How many **functional entry points** did we find in production code?” |
| **Actual (numerator)** | “How many of those entry points appear **exercised by tests** according to our graph rules?” |
| **Percentage** | `actual / expected × 100` (see exact formula below) |

An **entry point** is meant to approximate **user-facing or externally invocable surface area**: handlers, CLI commands, public interfaces — not every private helper.

**Unit coverage** (same router family) is separate: it counts raw production nodes reachable from tests. This document focuses on **functional** mode only.

---

## 2. Big picture — two numbers

```
expected  = number of nodes classified as functional entry points  (on application graph)
actual    = number of those entry points that are "covered"
gap       = expected − actual
pct       = round(actual / max(expected, 1) × 100, 1)
```

- **Expected** is entirely determined by `_functional_entry_points(G)` on the **application** graph (merged app repo graph(s)).
- **Actual** is the size of the set of entry-point node IDs that are covered by **either** (or both) of:
  1. **In-graph reachability** — BFS from test nodes inside the same graph as the app.
  2. **Cross-graph label matching** — symbols in a separate **test-role** graph that match entry-point labels on the app graph.

```
actually_covered = covered_in_graph ∪ covered_cross
```

---

## 3. Inputs: production graph and roles

### 3.1 Single-repository graph (`GET /graphs/{id}/coverage/...`)

- One graph file is loaded: all nodes and edges from that ingest.
- **Expected** entry points come from this graph’s **production** nodes only.
- **Actual** uses:
  - Test nodes in **this same graph**, BFS outward; **no** cross-graph pass (there is only one graph).

### 3.2 Project with multiple repositories

Two code paths matter:

**A — Project synthesis / PKB** (`synthesize_project` in `api/core/project_synthesis.py`)

- **Application graphs:** `application_graphs(loadable)` prefers `graph_role=ci`, then `source`, with a legacy fallback when app was only under `test`.
- Multiple ready application graphs are **composed** with `networkx.compose` into one `G_source`.
- **Test graphs for cross-repo matching:** `coverage_test_graphs(loadable)` — graphs with `graph_role=test` that are **not** the same graph IDs as the chosen application graphs (avoids treating the app as its own test repo).

**B — Project coverage API** (`GET /projects/{id}/coverage` in `api/routers/projects.py`)

- Currently groups graphs by role using **`source`** and **`test`** slots specifically (see implementation). If your app lives only under **`ci`**, this endpoint may not match synthesis behavior until aligned with `application_graphs()`.
- Otherwise the **math** is the same: merge source-side graphs, compute entry points, then in-graph BFS + cross-graph match against `test` role graphs.

When reading this doc, treat **“application graph”** as the merged graph used for `_functional_entry_points` (synthesis: CI/source; project route: historically `source`).

---

## 4. Node classification (before entry points)

Every node has metadata (e.g. `source_file`, `label`, `file_type`). Classification drives who is “production” vs “test” vs “file container.”

### 4.1 Test node (`_is_test_node`)

A node is **test** if **either**:

1. **`source_file`** matches `_TEST_FILE_PAT`, e.g. paths containing:
   - `test_`, `_test.`, `.test.`, `.spec.`, `spec_`, `tests/`, `__tests__/`, `conftest`, `fixtures/`, `e2e/`, `integration/test`, …  
2. **`label`** matches `_TEST_LABEL_PAT`, e.g. names starting with `test_`, `it_`, `describe_`, `should_`, `given_`, `when_`, `then_`, setup/teardown/before/after/fixture prefixes, …

Test nodes **never** appear in the entry-point candidate set as production.

### 4.2 Production node (`_is_prod_node`)

A node is **production** if:

- It is **not** a test node, **and**
- `file_type` is one of `code`, `document`, `concept`, `None`, or `""`

So odd file types may be excluded from prod.

### 4.3 Container node (`_is_container_node`)

If the node **`label`** looks like a **file path** ending in common extensions (`.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.rb`, `.java`, `.go`, …), it is treated as a **file-level container**, not a callable unit.

Container nodes are **excluded** from the production set used for entry-point detection.

---

## 5. Expected coverage — functional entry points

### 5.1 Definition

**Expected count** = `len(entry_points)` where `entry_points = _functional_entry_points(G)`.

`G` must be the **application** graph (possibly merged).

### 5.2 Production-only in-degree (“who in prod calls this?”)

For each production node `v`, we count **how many other production nodes** have a **coverage-relevant edge** **into** `v`:

- Edges `(u, v)` with `u ∈ prod_ids` and `v ∈ prod_ids`.
- Edge relation `rel` must be in `_COVERAGE_RELS` **or** be empty (`rel` missing/`""` still counts as traversable in many cases).

```text
_COVERAGE_RELS = {
  "calls", "imports", "imports_from", "uses", "references", "inherits"
}
```

This count is stored per node as **`prod_in_degree`** (conceptually: incoming edges from production along those relations).

**Test callers are ignored** for this in-degree: a symbol only called from tests can still look like “nothing in prod calls it” from production’s perspective.

### 5.3 Three rules — ANY rule qualifies a node as an entry point

For each **non-container production** node with a **non-empty `label`**:

| Rule | Condition (simplified) | Intuition |
|------|------------------------|-----------|
| **1 — Zero production in-degree + outgoing** | `prod_in_degree == 0` **and** `out_degree ≥ 1` | Nothing in prod “calls” it, but it calls other code → surface like handler/CLI that starts a chain. |
| **2 — Public-interface file** | `source_file` matches `_ENTRY_FILE_PAT` | Path suggests routes, API, CLI, main, server, workers, etc. |
| **3 — “Public” symbol with connections** | Label does **not** match `_PRIVATE_PAT` (`^_` single underscore) **and** `total degree ≥ 2` **and** not a container | Heuristic for exported / wired symbols. |

If **any** of rules 1–3 is true, the node is an entry point.

**`entry_type` label on the payload** (first match wins in code order):

- `api_handler` if rule 2
- else `public_entry` if rule 1 (`is_zero_in`)
- else `public_symbol` (rule 3)

**Important:** Rule 3 can add **many** nodes that are not strictly “user-facing.” Rule 2 can add everything in a coarse path. So **expected** is **heuristic**, not a formal API catalog.

### 5.4 Stored metadata per entry point

Each entry point record includes fields such as:

- `id`, `label`, `source_file`, `module`
- `degree`, `out_degree`, `prod_in_degree`
- Flags: `is_api_file`, `is_zero_in`, `is_public`
- `entry_type` as above

---

## 6. Actual coverage — strategy 1: in-graph BFS

**Goal:** Starting from **test** nodes in the **same** graph `G`, walk **outward** along edges whose relation is in `_COVERAGE_RELS` or empty/unset (same as BFS for coverage).

Algorithm: `_bfs_from(G, test_ids)`  
- Start set = all node IDs where `_is_test_node(data)` is true.  
- Queue BFS; for each neighbor, if not visited and edge is coverage-relevant, enqueue.

**Covered entry points (in-graph):**

```text
covered_in_graph = { nid | nid ∈ entry_points and nid ∈ reachable_from_tests }
```

**Meaning:** Some test file’s graph node can reach the entry-point node through call/import/use/… edges inside **one** combined graph (typical **monorepo** where app + tests were ingested together).

**If there are no test nodes:** `reachable` is empty; in-graph contributes nothing.

---

## 7. Actual coverage — strategy 2: cross-graph label matching

**When:** Project (or synthesis) loads a **separate** graph `G_test` built from a **test** repository.

**Function:** `cross_graph_match_entry_points(G_source, G_test, entry_pts)`

### 7.1 Index application entry points by label

For each entry point:

```text
key = ep["label"].strip().lower().rstrip("()")
entry_index[key] = entry_point_node_id
```

If two entry points normalize to the same key, **the later one wins** in the dict (implementation detail).

### 7.2 Collect test-side symbols

Build a set `test_labels`:

1. Every **test graph node** with a non-empty label — normalized the same way: `strip().lower().rstrip("()")`.
2. For every edge `(u, v)` in `G_test`, if the edge’s `relation` is in `_COVERAGE_RELS` or empty, add **both** endpoints’ labels (same normalization).

### 7.3 Match

```text
covered_cross = { entry_index[l] | l ∈ test_labels and l ∈ entry_index }
```

**Meaning:** If the **exact normalized symbol string** appears on the test graph (as a node label or on an endpoint of a coverage-relevant edge), we treat the corresponding **application** entry point as covered — **even though** there is no single shared graph edge from test repo to app repo.

This is **nominal** coverage (name equality), not proof of runtime execution or correct assertions.

---

## 8. Combined actual and percentage

```text
actually_covered = covered_in_graph ∪ covered_cross
coverage_gap     = set(entry_points) − actually_covered
functional_coverage_pct = round(len(actually_covered) / max(len(entry_points), 1) × 100, 1)
```

Project API may also report:

- `covered_by_in_graph_tests` — count of `covered_in_graph`
- `covered_by_cross_graph` — count of `covered_cross - covered_in_graph` (cross adds beyond what in-graph already saw)

---

## 9. Where this interacts with the product

| Surface | Uses functional % / gaps? |
|--------|---------------------------|
| `GET /graphs/{id}/coverage/summary` | Yes — single graph |
| `GET /graphs/{id}/coverage/functional` | Detail rows per entry point |
| `GET /projects/{id}/coverage` | Project — in-graph + cross (see role caveats above) |
| `synthesize_project` / PKB | Same math on `application_graphs` + `coverage_test_graphs` — drives `functional_coverage_pct`, capabilities `covered`, coverage-gap **findings** |

---

## 10. Limitations and interpretation

1. **Graph quality:** Wrong or missing `calls`/`imports` edges → wrong reachability. Wrong direction → tests never “reach” prod.
2. **Heuristic entry points:** Rules 2 and 3 can **inflate expected**; rule 1 can **miss** dynamic entry (factories, reflection, plugins).
3. **Cross-graph = string match:** Renamed APIs, different languages’ naming, wrappers, or aliases → **false gaps** or **false coverage** if names collide.
4. **BFS is not execution:** Reaching a node only means the graph says tests link to it; not that behavior is asserted.
5. **Monorepo vs polyrepo:** Monorepos lean on **in-graph BFS**; separate test repos lean on **cross-graph labels**. Using only app ingest with tests elsewhere and **no** test graph → actual may be **under-reported**.
6. **Role alignment:** Synthesis uses **CI/source** for app; the project coverage route historically keyed on **source + test** — verify your project setup matches the code path you rely on.

---

## 11. Quick reference — formulas

| Name | Formula |
|------|--------|
| Expected count | `|_functional_entry_points(G_app)|` |
| In-graph actual set | `{ ep ∈ entry_points : ep ∈ BFS_from(test_nodes) }` |
| Cross actual set | `{ ep_id : normalize(label) ∈ test_labels }` |
| Total actual set | `in_graph ∪ cross` |
| Percentage | `round(|total actual| / max(|expected|, 1) × 100, 1)` |

---

## 12. Code pointers

| Topic | Location |
|-------|----------|
| Entry points, test/prod/container, BFS | `api/routers/coverage.py` |
| Cross-graph match | `api/core/cross_graph.py` |
| Application vs test graph selection (synthesis) | `api/core/project_roles.py` — `application_graphs`, `coverage_test_graphs` |
| PKB functional % | `api/core/project_synthesis.py` |
| HTTP project coverage | `api/routers/projects.py` — `project_coverage` |

---

*Last updated to match the repository implementation as of the doc author revision; if APIs change, prefer the source files above.*

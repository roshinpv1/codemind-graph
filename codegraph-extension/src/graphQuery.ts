import * as fs from 'fs';

export interface GraphNode {
    id: string;
    label?: string;
    source_file?: string;
    source_location?: string;
    community?: string | number;
    file_type?: string;
    [key: string]: any;
}

export interface GraphLink {
    source: string;
    target: string;
    relation?: string;
    confidence?: string;
    context?: string;
    [key: string]: any;
}

export interface GraphData {
    directed?: boolean;
    multigraph?: boolean;
    graph?: any;
    nodes: GraphNode[];
    links?: GraphLink[];
    edges?: GraphLink[]; // standard networkx alternate
}

function stripDiacritics(text: string): string {
    return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

export class GraphQueryEngine {
    private nodes: GraphNode[] = [];
    private links: GraphLink[] = [];
    private nodeMap = new Map<string, GraphNode>();
    private adjacencyList = new Map<string, Set<string>>();
    private edgeMap = new Map<string, GraphLink>();
    private nodeDegrees = new Map<string, number>();

    constructor(graphPath: string) {
        if (!fs.existsSync(graphPath)) {
            return;
        }
        try {
            const raw = fs.readFileSync(graphPath, 'utf8');
            const data: GraphData = JSON.parse(raw);
            this.nodes = data.nodes || [];
            this.links = data.links || data.edges || [];
            this.initialize();
        } catch (e) {
            console.error("Failed to load or parse graph.json:", e);
        }
    }

    private initialize() {
        for (const node of this.nodes) {
            this.nodeMap.set(node.id, node);
            this.adjacencyList.set(node.id, new Set<string>());
            this.nodeDegrees.set(node.id, 0);
        }

        for (const link of this.links) {
            const src = typeof link.source === 'string' ? link.source : (link.source as any).id;
            const tgt = typeof link.target === 'string' ? link.target : (link.target as any).id;
            
            if (this.nodeMap.has(src) && this.nodeMap.has(tgt)) {
                this.adjacencyList.get(src)!.add(tgt);
                this.adjacencyList.get(tgt)!.add(src); // treat as undirected for traversal

                // Keep track of direct edge details
                const edgeKey = `${src}->${tgt}`;
                this.edgeMap.set(edgeKey, link);
            }
        }

        // Calculate degrees
        for (const [nodeId, neighbors] of this.adjacencyList.entries()) {
            this.nodeDegrees.set(nodeId, neighbors.size);
        }
    }

    public isLoaded(): boolean {
        return this.nodes.length > 0;
    }

    public getStats() {
        const confs = this.links.map(l => l.confidence || "EXTRACTED");
        const total = confs.length || 1;
        const extracted = confs.filter(c => c === "EXTRACTED").length;
        const inferred = confs.filter(c => c === "INFERRED").length;
        const ambiguous = confs.filter(c => c === "AMBIGUOUS").length;

        // Calculate community count
        const communities = new Set<string>();
        for (const n of this.nodes) {
            if (n.community !== undefined && n.community !== null) {
                communities.add(String(n.community));
            }
        }

        return {
            nodeCount: this.nodes.length,
            edgeCount: this.links.length,
            communityCount: communities.size,
            extractedPct: Math.round((extracted / total) * 100),
            inferredPct: Math.round((inferred / total) * 100),
            ambiguousPct: Math.round((ambiguous / total) * 100)
        };
    }

    private computeIDF(terms: string[]): Map<string, number> {
        const idf = new Map<string, number>();
        const N = this.nodes.length || 1;

        for (const term of terms) {
            let df = 0;
            for (const node of this.nodes) {
                const label = stripDiacritics(node.label || node.id || "").toLowerCase();
                if (label.includes(term)) {
                    df++;
                }
            }
            idf.set(term, Math.log(1 + N / (1 + df)));
        }

        return idf;
    }

    private scoreNodes(terms: string[]): { score: number, id: string }[] {
        const scored: { score: number, id: string }[] = [];
        const normTerms = terms.map(t => stripDiacritics(t).toLowerCase());
        const idf = this.computeIDF(normTerms);

        const EXACT_MATCH_BONUS = 1000.0;
        const PREFIX_MATCH_BONUS = 100.0;
        const SUBSTRING_MATCH_BONUS = 1.0;
        const SOURCE_MATCH_BONUS = 0.5;

        for (const node of this.nodes) {
            const normLabel = stripDiacritics(node.label || node.id || "").toLowerCase();
            const bareLabel = normLabel.replace(/\(\)$/, "");
            const source = (node.source_file || "").toLowerCase();
            const nodeId = node.id.toLowerCase();
            let score = 0.0;

            for (const t of normTerms) {
                const w = idf.get(t) ?? 1.0;

                if (t === normLabel || t === bareLabel || t === nodeId) {
                    score += EXACT_MATCH_BONUS * w;
                } else if (normLabel.startsWith(t) || bareLabel.startsWith(t) || nodeId.startsWith(t)) {
                    score += PREFIX_MATCH_BONUS * w;
                } else if (normLabel.includes(t) || nodeId.includes(t)) {
                    score += SUBSTRING_MATCH_BONUS * w;
                }

                if (source.includes(t)) {
                    score += SOURCE_MATCH_BONUS * w;
                }
            }

            if (score > 0) {
                scored.push({ score, id: node.id });
            }
        }

        return scored.sort((a, b) => b.score - a.score);
    }

    private pickSeeds(scored: { score: number, id: string }[], maxK = 3, gapRatio = 0.2): string[] {
        if (scored.length === 0) {
            return [];
        }
        const topScore = scored[0].score;
        const seeds: string[] = [];

        for (const item of scored.slice(0, maxK)) {
            if (seeds.length > 0 && item.score < topScore * gapRatio) {
                break;
            }
            seeds.push(item.id);
        }


        return seeds;
    }

    private getHubThreshold(): number {
        const degrees = Array.from(this.nodeDegrees.values()).sort((a, b) => a - b);
        if (degrees.length === 0) {
            return 50;
        }
        const p99Idx = Math.floor(degrees.length * 0.99);
        const p99 = degrees[p99Idx];
        return Math.max(50, p99);
    }

    public queryGraph(question: string, options: { mode?: 'bfs' | 'dfs', depth?: number, tokenBudget?: number } = {}): string {
        const mode = options.mode || 'bfs';
        const depth = options.depth || 3;
        const tokenBudget = options.tokenBudget || 2000;

        const terms = question.split(/\s+/).map(t => t.trim()).filter(t => t.length > 2);
        if (terms.length === 0) {
            return "Query is too short or has no keywords.";
        }

        const scored = this.scoreNodes(terms);
        const startNodes = this.pickSeeds(scored);
        if (startNodes.length === 0) {
            return "No matching concepts or symbols found in the graph.";
        }

        const hubThreshold = this.getHubThreshold();
        const visited = new Set<string>(startNodes);
        const edgesSeen: [string, string][] = [];

        if (mode === 'bfs') {
            let frontier = new Set<string>(startNodes);
            for (let d = 0; d < depth; d++) {
                const nextFrontier = new Set<string>();
                for (const node of frontier) {
                    // Hub pruning
                    if (!startNodes.includes(node) && (this.nodeDegrees.get(node) || 0) >= hubThreshold) {
                        continue;
                    }
                    const neighbors = this.adjacencyList.get(node);
                    if (neighbors) {
                        for (const n of neighbors) {
                            if (!visited.has(n)) {
                                nextFrontier.add(n);
                                visited.add(n);
                                edgesSeen.push([node, n]);
                            }
                        }
                    }
                }
                frontier = nextFrontier;
            }
        } else {
            // DFS traversal
            const stack: { id: string, depth: number }[] = startNodes.map(id => ({ id, depth: 0 })).reverse();
            while (stack.length > 0) {
                const { id, depth: d } = stack.pop()!;
                if (d > depth) {
                    continue;
                }
                // Hub pruning
                if (!startNodes.includes(id) && (this.nodeDegrees.get(id) || 0) >= hubThreshold) {
                    continue;
                }
                const neighbors = this.adjacencyList.get(id);
                if (neighbors) {
                    for (const n of neighbors) {
                        if (!visited.has(n)) {
                            visited.add(n);
                            stack.push({ id: n, depth: d + 1 });
                            edgesSeen.push([id, n]);
                        }
                    }
                }
            }
        }

        const startLabels = startNodes.map(id => this.nodeMap.get(id)?.label || id);
        let header = `Traversal: ${mode.toUpperCase()} depth=${depth} | Start: [${startLabels.join(', ')}] | ${visited.size} nodes found\n\n`;

        return header + this.renderSubgraph(visited, edgesSeen, tokenBudget, startNodes);
    }

    private renderSubgraph(nodes: Set<string>, edges: [string, string][], tokenBudget: number, seeds: string[]): string {
        const charBudget = tokenBudget * 3;
        const lines: string[] = [];
        
        const seedSet = new Set<string>(seeds);
        const ordered = [
            ...seeds.filter(id => nodes.has(id)),
            ...Array.from(nodes).filter(id => !seedSet.has(id)).sort((a, b) => (this.nodeDegrees.get(b) || 0) - (this.nodeDegrees.get(a) || 0))
        ];

        for (const nid of ordered) {
            const d = this.nodeMap.get(nid);
            if (d) {
                const label = d.label || nid;
                const src = d.source_file || '';
                const loc = d.source_location || '';
                const comm = d.community !== undefined ? String(d.community) : '';
                lines.push(`NODE ${label} [src=${src} loc=${loc} community=${comm}]`);
            }
        }

        for (const [u, v] of edges) {
            if (nodes.has(u) && nodes.has(v)) {
                // Find relation details
                const fwd = this.edgeMap.get(`${u}->${v}`);
                const rev = this.edgeMap.get(`${v}->${u}`);
                const link = fwd || rev;
                if (link) {
                    const relation = link.relation || 'connects';
                    const confidence = link.confidence || 'EXTRACTED';
                    const context = link.context ? ` context=${link.context}` : '';
                    const uLabel = this.nodeMap.get(u)?.label || u;
                    const vLabel = this.nodeMap.get(v)?.label || v;
                    lines.push(`EDGE ${uLabel} --${relation} [${confidence}${context}]--> ${vLabel}`);
                }
            }
        }

        let output = lines.join('\n');
        if (output.length > charBudget) {
            const cutAt = output.substring(0, charBudget).lastIndexOf('\n');
            const finalCut = cutAt > 0 ? cutAt : charBudget;
            const shownCount = output.substring(0, finalCut).split('\nNODE ').length;
            const totalNodes = lines.filter(l => l.startsWith('NODE ')).length;
            const cutCount = totalNodes - shownCount;
            output = output.substring(0, finalCut) + `\n... (truncated — ${cutCount} more nodes cut by ~${tokenBudget}-token budget.)`;
        }
        return output;
    }

    public getNodeDetails(labelOrId: string): string {
        const term = stripDiacritics(labelOrId).toLowerCase();
        let matchedNode: GraphNode | undefined;
        
        // Exact match
        for (const n of this.nodes) {
            const normLabel = stripDiacritics(n.label || '').toLowerCase();
            if (n.id.toLowerCase() === term || normLabel === term) {
                matchedNode = n;
                break;
            }
        }

        // Substring match
        if (!matchedNode) {
            for (const n of this.nodes) {
                const normLabel = stripDiacritics(n.label || '').toLowerCase();
                if (n.id.toLowerCase().includes(term) || normLabel.includes(term)) {
                    matchedNode = n;
                    break;
                }
            }
        }

        if (!matchedNode) {
            return `No node matching '${labelOrId}' found.`;
        }

        const id = matchedNode.id;
        const degree = this.nodeDegrees.get(id) || 0;
        return [
            `Node: ${matchedNode.label || id}`,
            `  ID: ${id}`,
            `  Source: ${matchedNode.source_file || ''} ${matchedNode.source_location || ''}`,
            `  Type: ${matchedNode.file_type || ''}`,
            `  Community: ${matchedNode.community !== undefined ? String(matchedNode.community) : ''}`,
            `  Degree: ${degree}`
        ].join('\n');
    }

    public getNeighbors(labelOrId: string, relationFilter = ''): string {
        const term = stripDiacritics(labelOrId).toLowerCase();
        let matchedId = '';

        for (const n of this.nodes) {
            const normLabel = stripDiacritics(n.label || '').toLowerCase();
            if (n.id.toLowerCase() === term || normLabel === term) {
                matchedId = n.id;
                break;
            }
        }

        if (!matchedId) {
            for (const n of this.nodes) {
                const normLabel = stripDiacritics(n.label || '').toLowerCase();
                if (n.id.toLowerCase().includes(term) || normLabel.includes(term)) {
                    matchedId = n.id;
                    break;
                }
            }
        }

        if (!matchedId) {
            return `No node matching '${labelOrId}' found.`;
        }

        const lines: string[] = [`Neighbors of ${this.nodeMap.get(matchedId)?.label || matchedId}:`];
        const filter = relationFilter.toLowerCase();

        for (const link of this.links) {
            const src = typeof link.source === 'string' ? link.source : (link.source as any).id;
            const tgt = typeof link.target === 'string' ? link.target : (link.target as any).id;

            if (src === matchedId) {
                const rel = link.relation || '';
                if (filter && !rel.toLowerCase().includes(filter)) continue;
                const tgtLabel = this.nodeMap.get(tgt)?.label || tgt;
                lines.push(`  --> ${tgtLabel} [${rel}] [${link.confidence || 'EXTRACTED'}]`);
            } else if (tgt === matchedId) {
                const rel = link.relation || '';
                if (filter && !rel.toLowerCase().includes(filter)) continue;
                const srcLabel = this.nodeMap.get(src)?.label || src;
                lines.push(`  <-- ${srcLabel} [${rel}] [${link.confidence || 'EXTRACTED'}]`);
            }
        }

        return lines.join('\n');
    }

    public shortestPath(sourceQuery: string, targetQuery: string, maxHops = 8): string {
        const srcTerms = sourceQuery.split(/\s+/).map(t => t.trim()).filter(t => t.length > 2);
        const tgtTerms = targetQuery.split(/\s+/).map(t => t.trim()).filter(t => t.length > 2);

        const srcScored = this.scoreNodes(srcTerms);
        const tgtScored = this.scoreNodes(tgtTerms);

        if (srcScored.length === 0) {
            return `No node matching source '${sourceQuery}' found.`;
        }
        if (tgtScored.length === 0) {
            return `No node matching target '${targetQuery}' found.`;
        }

        const srcId = srcScored[0].id;
        const tgtId = tgtScored[0].id;

        if (srcId === tgtId) {
            return `'${sourceQuery}' and '${targetQuery}' both resolved to the same node '${srcId}'.`;
        }

        // BFS pathfinding (undirected)
        const queue: string[][] = [[srcId]];
        const visited = new Set<string>([srcId]);
        let foundPath: string[] | null = null;

        while (queue.length > 0) {
            const path = queue.shift()!;
            const node = path[path.length - 1];

            if (node === tgtId) {
                foundPath = path;
                break;
            }

            if (path.length - 1 >= maxHops) {
                continue;
            }

            const neighbors = this.adjacencyList.get(node);
            if (neighbors) {
                for (const neighbor of neighbors) {
                    if (!visited.has(neighbor)) {
                        visited.add(neighbor);
                        queue.push([...path, neighbor]);
                    }
                }
            }
        }

        if (!foundPath) {
            const srcLabel = this.nodeMap.get(srcId)?.label || srcId;
            const tgtLabel = this.nodeMap.get(tgtId)?.label || tgtId;
            return `No path found between '${srcLabel}' and '${tgtLabel}'.`;
        }

        const segments: string[] = [];
        for (let i = 0; i < foundPath.length - 1; i++) {
            const u = foundPath[i];
            const v = foundPath[i + 1];
            const fwd = this.edgeMap.get(`${u}->${v}`);
            const rev = this.edgeMap.get(`${v}->${u}`);
            const link = fwd || rev;
            const rel = link?.relation || 'connects';
            const conf = link?.confidence ? ` [${link.confidence}]` : '';

            if (i === 0) {
                segments.push(this.nodeMap.get(u)?.label || u);
            }

            if (fwd) {
                segments.push(`--${rel}${conf}--> ${this.nodeMap.get(v)?.label || v}`);
            } else {
                segments.push(`<--${rel}${conf}-- ${this.nodeMap.get(v)?.label || v}`);
            }
        }

        const hops = foundPath.length - 1;
        return `Shortest path (${hops} hops):\n  ` + segments.join(' ');
    }
}

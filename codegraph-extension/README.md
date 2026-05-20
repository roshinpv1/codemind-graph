# CodeGraph VS Code Extension

CodeGraph is a zero-dependency, self-contained codebase knowledge graph assistant. It maps your files, classes, methods, imports, and relationships into a local knowledge graph using tree-sitter.

Once generated, CodeGraph registers language model tools directly with VS Code Copilot. This allows Copilot to query your codebase's architecture and connections dynamically, returning precise, context-optimized subgraphs to answer your questions while using up to **90% fewer tokens** than traditional grep/full-file ingestion.

## Features

- **VS Code Copilot Integration**: Automatically registers graph querying tools with Copilot Chat.
- **`@codegraph` Chat Participant**: Interact with your graph directly in the chat panel.
- **Zero Configuration**: Bundles the parser engine and pre-compiles all dependencies inside the extension. Only system Python 3.10+ is required on your machine.
- **Incremental Background Watcher**: Auto-updates the graph in real-time when you save any file (sub-second AST-only updates, completely offline, zero LLM cost).
- **TypeScript Query Engine**: Direct TS implementation reads `graphify-out/graph.json` to execute BFS/DFS traversals and shortest paths in sub-milliseconds.

## Usage

### commands
- **`/build`**: Build the initial graph for the workspace.
- **`/update`**: Run an incremental update on the workspace.
- **`/explain <symbol>`**: Explain a class, function, or file and its neighbors.
- **`/path <source> to <target>`**: Find the shortest relationship path between two concepts.
- **`/query <question>`**: Query the graph for a specific question.

### Copilot Integration
Once the extension is active, Copilot will automatically call CodeGraph's tools under the hood when you ask questions like:
- *"Where is auth handled in this project?"*
- *"How does the router connect to the database connection pool?"*
- *"Explain the architecture of the codebase."*

import * as vscode from 'vscode';
import * as path from 'path';
import { checkPythonVersion, runBundledPython, ensureDependencies, getPythonPath } from './utils';
import { GraphQueryEngine } from './graphQuery';
import * as fs from 'fs';

let queryEngine: GraphQueryEngine | null = null;
let watcher: vscode.FileSystemWatcher | null = null;

function getGraphPath(workspaceRoot: string): string {
    return path.join(workspaceRoot, 'graph-out', 'graph.json');
}

function loadQueryEngine(workspaceRoot: string) {
    const graphPath = getGraphPath(workspaceRoot);
    queryEngine = new GraphQueryEngine(graphPath);
    console.log(`Loaded GraphQueryEngine for path: ${graphPath}. Success: ${queryEngine.isLoaded()}`);
}

export async function activate(context: vscode.ExtensionContext) {
    console.log('CodeGraph extension is now active!');

    // Get workspace root
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        console.log("No workspace folder open. CodeGraph active with limited functionality.");
        return;
    }
    const workspaceRoot = workspaceFolders[0].uri.fsPath;

    // Verify Python version
    const pythonOk = await checkPythonVersion();
    if (!pythonOk) {
        vscode.window.showWarningMessage(
            "CodeGraph requires Python 3.10+ to build/update graphs. Please verify your system Python installation or update the 'codegraph.pythonPath' setting."
        );
    }

    // Resolve global storage dependencies path (cross-platform self-contained installation)
    const storageDepsPath = path.join(context.globalStorageUri.fsPath, 'dependencies');
    const treeSitterMarker = path.join(storageDepsPath, 'tree_sitter');

    if (!fs.existsSync(treeSitterMarker)) {
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Setting up CodeGraph",
            cancellable: false
        }, async (progress) => {
            progress.report({ message: "Installing platform-native Python dependencies..." });
            // Ensure globalStorage directory exists
            fs.mkdirSync(storageDepsPath, { recursive: true });
            const success = await ensureDependencies(getPythonPath(), storageDepsPath);
            if (success) {
                vscode.window.showInformationMessage("CodeGraph ready!");
            } else {
                vscode.window.showErrorMessage("Failed to setup CodeGraph python dependencies. Check console logs.");
            }
        });
    }

    // Load graph query engine
    loadQueryEngine(workspaceRoot);

    // Watch for graph.json changes to hot-reload the graph
    const graphRelativePattern = new vscode.RelativePattern(workspaceRoot, 'graph-out/graph.json');
    watcher = vscode.workspace.createFileSystemWatcher(graphRelativePattern);
    watcher.onDidChange(() => {
        console.log("graph.json changed on disk. Reloading GraphQueryEngine.");
        loadQueryEngine(workspaceRoot);
    });
    watcher.onDidCreate(() => {
        console.log("graph.json created on disk. Loading GraphQueryEngine.");
        loadQueryEngine(workspaceRoot);
    });
    watcher.onDidDelete(() => {
        console.log("graph.json deleted on disk. Clearing GraphQueryEngine.");
        queryEngine = null;
    });

    // Auto-update graph on document save
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument(async (document) => {
            const config = vscode.workspace.getConfiguration('codegraph');
            const autoUpdate = config.get<boolean>('autoUpdate', true);
            if (!autoUpdate) {
                return;
            }

            // Exclude node_modules, .git, etc.
            const filePath = document.uri.fsPath;
            if (filePath.includes('node_modules') || filePath.includes('.git') || filePath.includes('graph-out')) {
                return;
            }

            // Run AST update command in background
            console.log(`Auto-updating graph for saved file: ${filePath}`);
            const result = await runBundledPython(context.extensionPath, ['update', workspaceRoot], workspaceRoot, storageDepsPath);
            if (result.code !== 0) {
                console.error(`Auto-update failed with exit code ${result.code}:`, result.stderr);
            } else {
                console.log("Auto-update finished successfully.");
            }
        })
    );

    // Register Chat Participant
    const participant = vscode.chat.createChatParticipant('codegraph.chat', async (request, _contextChat, response, _token) => {
        const command = request.command;
        const prompt = request.prompt.trim();

        if (!queryEngine || !queryEngine.isLoaded()) {
            response.markdown("No knowledge graph found. Run `@codegraph /build` to map your project into a knowledge graph.");
            return;
        }

        if (command === 'build') {
            response.progress("Extracting code structure and building knowledge graph (this may take a few seconds)...");
            const result = await runBundledPython(context.extensionPath, ['extract', '.'], workspaceRoot, storageDepsPath);
            if (result.code === 0) {
                response.markdown("### CodeGraph Built Successfully\nInteractive visualization and reports are available in the `graph-out/` folder.");
            } else {
                response.markdown(`### Build Failed\nExit code: ${result.code}\nError: ${result.stderr}`);
            }
            return;
        }

        if (command === 'update') {
            response.progress("Running incremental update...");
            const result = await runBundledPython(context.extensionPath, ['update', '.'], workspaceRoot, storageDepsPath);
            if (result.code === 0) {
                response.markdown("### CodeGraph Updated Successfully");
            } else {
                response.markdown(`### Update Failed\nExit code: ${result.code}\nError: ${result.stderr}`);
            }
            return;
        }

        if (command === 'path') {
            const parts = prompt.split(/\s+to\s+|\s+and\s+/i);
            if (parts.length < 2) {
                response.markdown("Please specify two symbols, e.g. `auth to database` or `UserService and DatabasePool`.");
                return;
            }
            const source = parts[0].trim();
            const target = parts[1].trim();
            response.markdown(queryEngine.shortestPath(source, target));
            return;
        }

        if (command === 'explain') {
            if (!prompt) {
                response.markdown("Please specify a symbol or file name to explain, e.g. `UserService`.");
                return;
            }
            const details = queryEngine.getNodeDetails(prompt);
            const neighbors = queryEngine.getNeighbors(prompt);
            response.markdown(`### Concept Details\n${details}\n\n### Relationships\n${neighbors}`);
            return;
        }

        // Default query / search command
        if (!prompt) {
            response.markdown("Welcome to CodeGraph! Try `@codegraph /query what connects UserService to database` or `@codegraph /explain UserService`.");
            return;
        }

        response.progress("Searching knowledge graph...");
        const answer = queryEngine.queryGraph(prompt);
        response.markdown(answer);
    });

    context.subscriptions.push(participant);

    // Register VS Code Language Model Tools
    context.subscriptions.push(
        vscode.lm.registerTool('codegraph_query', {
            async prepareInvocation(options: vscode.LanguageModelToolInvocationPrepareOptions<any>) {
                return { invocationMessage: `Searching CodeGraph for: "${options.input.question}"` };
            },
            async invoke(options: vscode.LanguageModelToolInvocationOptions<any>, _token: vscode.CancellationToken) {
                const question = options.input.question;
                if (!queryEngine || !queryEngine.isLoaded()) {
                    return new vscode.LanguageModelToolResult([
                        new vscode.LanguageModelTextPart("No knowledge graph available. The graph must be built first.")
                    ]);
                }
                const result = queryEngine.queryGraph(question);
                return new vscode.LanguageModelToolResult([
                    new vscode.LanguageModelTextPart(result)
                ]);
            }
        })
    );

    context.subscriptions.push(
        vscode.lm.registerTool('codegraph_path', {
            async prepareInvocation(options: vscode.LanguageModelToolInvocationPrepareOptions<any>) {
                return { invocationMessage: `Finding path from "${options.input.source}" to "${options.input.target}"` };
            },
            async invoke(options: vscode.LanguageModelToolInvocationOptions<any>, _token: vscode.CancellationToken) {
                const source = options.input.source;
                const target = options.input.target;
                if (!queryEngine || !queryEngine.isLoaded()) {
                    return new vscode.LanguageModelToolResult([
                        new vscode.LanguageModelTextPart("No knowledge graph available.")
                    ]);
                }
                const result = queryEngine.shortestPath(source, target);
                return new vscode.LanguageModelToolResult([
                    new vscode.LanguageModelTextPart(result)
                ]);
            }
        })
    );

    context.subscriptions.push(
        vscode.lm.registerTool('codegraph_explain', {
            async prepareInvocation(options: vscode.LanguageModelToolInvocationPrepareOptions<any>) {
                return { invocationMessage: `Explaining symbol: "${options.input.symbol}"` };
            },
            async invoke(options: vscode.LanguageModelToolInvocationOptions<any>, _token: vscode.CancellationToken) {
                const symbol = options.input.symbol;
                if (!queryEngine || !queryEngine.isLoaded()) {
                    return new vscode.LanguageModelToolResult([
                        new vscode.LanguageModelTextPart("No knowledge graph available.")
                    ]);
                }
                const details = queryEngine.getNodeDetails(symbol);
                const neighbors = queryEngine.getNeighbors(symbol);
                const result = `Symbol Details:\n${details}\n\nConnected Relationships:\n${neighbors}`;
                return new vscode.LanguageModelToolResult([
                    new vscode.LanguageModelTextPart(result)
                ]);
            }
        })
    );
}

export function deactivate() {
    if (watcher) {
        watcher.dispose();
    }
}

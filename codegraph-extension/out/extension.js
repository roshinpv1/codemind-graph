"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const utils_1 = require("./utils");
const graphQuery_1 = require("./graphQuery");
const fs = __importStar(require("fs"));
let queryEngine = null;
let watcher = null;
function getGraphPath(workspaceRoot) {
    return path.join(workspaceRoot, 'graphify-out', 'graph.json');
}
function loadQueryEngine(workspaceRoot) {
    const graphPath = getGraphPath(workspaceRoot);
    queryEngine = new graphQuery_1.GraphQueryEngine(graphPath);
    console.log(`Loaded GraphQueryEngine for path: ${graphPath}. Success: ${queryEngine.isLoaded()}`);
}
async function activate(context) {
    console.log('CodeGraph extension is now active!');
    // Get workspace root
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        console.log("No workspace folder open. CodeGraph active with limited functionality.");
        return;
    }
    const workspaceRoot = workspaceFolders[0].uri.fsPath;
    // Verify Python version
    const pythonOk = await (0, utils_1.checkPythonVersion)();
    if (!pythonOk) {
        vscode.window.showWarningMessage("CodeGraph requires Python 3.10+ to build/update graphs. Please verify your system Python installation or update the 'codegraph.pythonPath' setting.");
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
            const success = await (0, utils_1.ensureDependencies)((0, utils_1.getPythonPath)(), storageDepsPath);
            if (success) {
                vscode.window.showInformationMessage("CodeGraph ready!");
            }
            else {
                vscode.window.showErrorMessage("Failed to setup CodeGraph python dependencies. Check console logs.");
            }
        });
    }
    // Load graph query engine
    loadQueryEngine(workspaceRoot);
    // Watch for graph.json changes to hot-reload the graph
    const graphRelativePattern = new vscode.RelativePattern(workspaceRoot, 'graphify-out/graph.json');
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
    context.subscriptions.push(vscode.workspace.onDidSaveTextDocument(async (document) => {
        const config = vscode.workspace.getConfiguration('codegraph');
        const autoUpdate = config.get('autoUpdate', true);
        if (!autoUpdate) {
            return;
        }
        // Exclude node_modules, .git, etc.
        const filePath = document.uri.fsPath;
        if (filePath.includes('node_modules') || filePath.includes('.git') || filePath.includes('graphify-out')) {
            return;
        }
        // Run AST update command in background
        console.log(`Auto-updating graph for saved file: ${filePath}`);
        const result = await (0, utils_1.runBundledPython)(context.extensionPath, ['update', workspaceRoot], workspaceRoot, storageDepsPath);
        if (result.code !== 0) {
            console.error(`Auto-update failed with exit code ${result.code}:`, result.stderr);
        }
        else {
            console.log("Auto-update finished successfully.");
        }
    }));
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
            const result = await (0, utils_1.runBundledPython)(context.extensionPath, ['extract', '.'], workspaceRoot, storageDepsPath);
            if (result.code === 0) {
                response.markdown("### CodeGraph Built Successfully\nInteractive visualization and reports are available in the `graphify-out/` folder.");
            }
            else {
                response.markdown(`### Build Failed\nExit code: ${result.code}\nError: ${result.stderr}`);
            }
            return;
        }
        if (command === 'update') {
            response.progress("Running incremental update...");
            const result = await (0, utils_1.runBundledPython)(context.extensionPath, ['update', '.'], workspaceRoot, storageDepsPath);
            if (result.code === 0) {
                response.markdown("### CodeGraph Updated Successfully");
            }
            else {
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
    context.subscriptions.push(vscode.lm.registerTool('codegraph_query', {
        async prepareInvocation(options) {
            return { invocationMessage: `Searching CodeGraph for: "${options.input.question}"` };
        },
        async invoke(options, _token) {
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
    }));
    context.subscriptions.push(vscode.lm.registerTool('codegraph_path', {
        async prepareInvocation(options) {
            return { invocationMessage: `Finding path from "${options.input.source}" to "${options.input.target}"` };
        },
        async invoke(options, _token) {
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
    }));
    context.subscriptions.push(vscode.lm.registerTool('codegraph_explain', {
        async prepareInvocation(options) {
            return { invocationMessage: `Explaining symbol: "${options.input.symbol}"` };
        },
        async invoke(options, _token) {
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
    }));
}
function deactivate() {
    if (watcher) {
        watcher.dispose();
    }
}
//# sourceMappingURL=extension.js.map
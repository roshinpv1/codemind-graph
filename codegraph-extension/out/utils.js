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
exports.getPythonPath = getPythonPath;
exports.checkPythonVersion = checkPythonVersion;
exports.runBundledPython = runBundledPython;
exports.ensureDependencies = ensureDependencies;
const vscode = __importStar(require("vscode"));
const child_process_1 = require("child_process");
const path = __importStar(require("path"));
let activePythonPath = null;
function getPythonPath() {
    if (activePythonPath) {
        return activePythonPath;
    }
    const config = vscode.workspace.getConfiguration('codegraph');
    return config.get('pythonPath') || 'python3';
}
function testPython(executable) {
    return new Promise((resolve) => {
        (0, child_process_1.exec)(`"${executable}" --version`, (err, stdout, stderr) => {
            if (err) {
                resolve(false);
                return;
            }
            const output = (stdout || stderr || '').trim();
            console.log(`Testing python executable "${executable}":`, output);
            const match = output.match(/Python\s+([0-9]+)\.([0-9]+)/i);
            if (match) {
                const major = parseInt(match[1], 10);
                const minor = parseInt(match[2], 10);
                if (major > 3 || (major === 3 && minor >= 10)) {
                    resolve(true);
                    return;
                }
            }
            resolve(false);
        });
    });
}
async function checkPythonVersion() {
    const configured = getPythonPath();
    // 1. Try configured python command
    let ok = await testPython(configured);
    if (ok) {
        activePythonPath = configured;
        return true;
    }
    // 2. Try common fallbacks (e.g. on Windows default is often 'python')
    const alternates = configured === 'python3' ? ['python', 'python.exe'] : ['python3'];
    for (const alt of alternates) {
        ok = await testPython(alt);
        if (ok) {
            console.log(`CodeGraph: configured '${configured}' failed, but fallback '${alt}' succeeded.`);
            activePythonPath = alt;
            return true;
        }
    }
    return false;
}
function runBundledPython(extensionPath, args, cwd, storageDepsPath) {
    const python = getPythonPath();
    const pythonDir = path.join(extensionPath, 'python');
    const pathSeparator = process.platform === 'win32' ? ';' : ':';
    const pythonPathEnv = [pythonDir, storageDepsPath].filter(Boolean).join(pathSeparator);
    // We add the bundled python directory to PYTHONPATH so python can resolve "graph"
    const env = {
        ...process.env,
        PYTHONPATH: pythonPathEnv,
        GRAPH_OUT: path.join(cwd, 'graph-out')
    };
    return new Promise((resolve) => {
        const fullArgs = ['-m', 'graph', ...args];
        console.log(`Executing: ${python} ${fullArgs.join(' ')}`);
        (0, child_process_1.execFile)(python, fullArgs, { cwd, env }, (err, stdout, stderr) => {
            resolve({
                stdout: stdout || '',
                stderr: stderr || '',
                code: err ? (typeof err.code === 'number' ? err.code : 1) : 0
            });
        });
    });
}
function ensureDependencies(python, targetPath, outputChannel) {
    return new Promise((resolve) => {
        // Run pip install inside targetPath
        const args = [
            '-m',
            'pip',
            'install',
            '--target',
            targetPath,
            'networkx',
            'datasketch',
            'rapidfuzz',
            'tree-sitter==0.23.2',
            'tree-sitter-python',
            'tree-sitter-javascript',
            'tree-sitter-typescript',
            'tree-sitter-go',
            'tree-sitter-rust',
            'tree-sitter-java',
            'tree-sitter-c',
            'tree-sitter-cpp'
        ];
        const cmdStr = `${python} ${args.join(' ')}`;
        console.log(`Installing dependencies using: ${cmdStr}`);
        if (outputChannel) {
            outputChannel.appendLine(`[INFO] Starting CodeGraph dependencies installation...`);
            outputChannel.appendLine(`[INFO] Command: ${cmdStr}`);
        }
        const child = (0, child_process_1.execFile)(python, args);
        if (child.stdout && outputChannel) {
            child.stdout.on('data', (data) => {
                outputChannel.append(data.toString());
            });
        }
        if (child.stderr && outputChannel) {
            child.stderr.on('data', (data) => {
                outputChannel.append(data.toString());
            });
        }
        child.on('close', (code) => {
            if (code !== 0) {
                console.error(`Dependency installation failed with exit code: ${code}`);
                if (outputChannel) {
                    outputChannel.appendLine(`\n[ERROR] Dependency installation failed with exit code: ${code}`);
                }
                resolve(false);
            }
            else {
                if (outputChannel) {
                    outputChannel.appendLine(`\n[SUCCESS] Dependencies installed successfully.`);
                }
                resolve(true);
            }
        });
    });
}
//# sourceMappingURL=utils.js.map
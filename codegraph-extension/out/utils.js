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
function getPythonPath() {
    const config = vscode.workspace.getConfiguration('codegraph');
    return config.get('pythonPath') || 'python3';
}
async function checkPythonVersion() {
    const python = getPythonPath();
    return new Promise((resolve) => {
        (0, child_process_1.exec)(`"${python}" --version`, (err, stdout, stderr) => {
            if (err) {
                console.error("Failed to run python executable:", python, err);
                resolve(false);
                return;
            }
            const output = (stdout || stderr || '').trim();
            console.log("Python version check output:", output);
            // Verify Python >= 3.10
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
function runBundledPython(extensionPath, args, cwd, storageDepsPath) {
    const python = getPythonPath();
    const pythonDir = path.join(extensionPath, 'python');
    const pathSeparator = process.platform === 'win32' ? ';' : ':';
    const pythonPathEnv = [pythonDir, storageDepsPath].filter(Boolean).join(pathSeparator);
    // We add the bundled python directory to PYTHONPATH so python can resolve "graphify"
    const env = {
        ...process.env,
        PYTHONPATH: pythonPathEnv,
        GRAPHIFY_OUT: path.join(cwd, 'graphify-out')
    };
    return new Promise((resolve) => {
        const fullArgs = ['-m', 'graphify', ...args];
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
function ensureDependencies(python, targetPath) {
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
        console.log(`Installing dependencies using: ${python} ${args.join(' ')}`);
        (0, child_process_1.execFile)(python, args, (err) => {
            if (err) {
                console.error("Dependency installation failed:", err);
                resolve(false);
            }
            else {
                resolve(true);
            }
        });
    });
}
//# sourceMappingURL=utils.js.map
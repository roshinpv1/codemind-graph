import * as vscode from 'vscode';
import { exec, execFile } from 'child_process';
import * as path from 'path';

let activePythonPath: string | null = null;

export function getPythonPath(): string {
    if (activePythonPath) {
        return activePythonPath;
    }
    const config = vscode.workspace.getConfiguration('codegraph');
    return config.get<string>('pythonPath') || 'python3';
}

function testPython(executable: string): Promise<boolean> {
    return new Promise((resolve) => {
        exec(`"${executable}" --version`, (err, stdout, stderr) => {
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

export async function checkPythonVersion(): Promise<boolean> {
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


export interface ExecResult {
    stdout: string;
    stderr: string;
    code: number;
}

export function runBundledPython(
    extensionPath: string,
    args: string[],
    cwd: string,
    storageDepsPath?: string
): Promise<ExecResult> {
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
        
        execFile(python, fullArgs, { cwd, env }, (err, stdout, stderr) => {
            resolve({
                stdout: stdout || '',
                stderr: stderr || '',
                code: err ? (typeof err.code === 'number' ? err.code : 1) : 0
            });
        });
    });
}

export function ensureDependencies(
    python: string,
    targetPath: string
): Promise<boolean> {
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
        execFile(python, args, (err) => {
            if (err) {
                console.error("Dependency installation failed:", err);
                resolve(false);
            } else {
                resolve(true);
            }
        });
    });
}



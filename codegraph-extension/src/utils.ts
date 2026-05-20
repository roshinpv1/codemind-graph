import * as vscode from 'vscode';
import { exec, execFile } from 'child_process';
import * as path from 'path';

export function getPythonPath(): string {
    const config = vscode.workspace.getConfiguration('codegraph');
    return config.get<string>('pythonPath') || 'python3';
}

export async function checkPythonVersion(): Promise<boolean> {
    const python = getPythonPath();
    return new Promise((resolve) => {
        exec(`"${python}" --version`, (err, stdout, stderr) => {
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
    
    // We add the bundled python directory to PYTHONPATH so python can resolve "graphify"
    const env = {
        ...process.env,
        PYTHONPATH: pythonPathEnv,
        GRAPHIFY_OUT: path.join(cwd, 'graphify-out')
    };

    return new Promise((resolve) => {
        const fullArgs = ['-m', 'graphify', ...args];
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



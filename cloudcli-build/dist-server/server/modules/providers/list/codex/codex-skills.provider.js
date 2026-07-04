import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { SkillsProvider } from '../../../../modules/providers/shared/skills/skills.provider.js';
const hasGitMarker = async (dirPath) => {
    try {
        const gitMarkerStats = await fs.stat(path.join(dirPath, '.git'));
        return gitMarkerStats.isDirectory() || gitMarkerStats.isFile();
    }
    catch {
        return false;
    }
};
const findTopmostGitRoot = async (startPath) => {
    let currentPath = path.resolve(startPath);
    let topmostGitRoot = null;
    while (true) {
        if (await hasGitMarker(currentPath)) {
            topmostGitRoot = currentPath;
        }
        const parentPath = path.dirname(currentPath);
        if (parentPath === currentPath) {
            break;
        }
        currentPath = parentPath;
    }
    return topmostGitRoot;
};
const addUniqueSource = (sources, seenRootDirs, source) => {
    const normalizedRootDir = path.resolve(source.rootDir);
    if (seenRootDirs.has(normalizedRootDir)) {
        return;
    }
    seenRootDirs.add(normalizedRootDir);
    sources.push({ ...source, rootDir: normalizedRootDir });
};
export class CodexSkillsProvider extends SkillsProvider {
    constructor() {
        super('codex');
    }
    async getSkillSources(workspacePath) {
        const sources = [];
        const seenRootDirs = new Set();
        const repoRoot = await findTopmostGitRoot(workspacePath);
        addUniqueSource(sources, seenRootDirs, {
            scope: 'repo',
            rootDir: path.join(workspacePath, '.agents', 'skills'),
            commandPrefix: '$',
        });
        if (repoRoot) {
            // Codex checks repository skills at the launch folder, one folder above it,
            // and the topmost git root; these can collapse to the same directory.
            addUniqueSource(sources, seenRootDirs, {
                scope: 'repo',
                rootDir: path.join(path.dirname(workspacePath), '.agents', 'skills'),
                commandPrefix: '$',
            });
            addUniqueSource(sources, seenRootDirs, {
                scope: 'repo',
                rootDir: path.join(repoRoot, '.agents', 'skills'),
                commandPrefix: '$',
            });
        }
        addUniqueSource(sources, seenRootDirs, {
            scope: 'user',
            rootDir: path.join(os.homedir(), '.agents', 'skills'),
            commandPrefix: '$',
        });
        addUniqueSource(sources, seenRootDirs, {
            scope: 'admin',
            rootDir: path.join('/etc', 'codex', 'skills'),
            commandPrefix: '$',
        });
        addUniqueSource(sources, seenRootDirs, {
            scope: 'system',
            rootDir: path.join(os.homedir(), '.codex', 'skills', '.system'),
            commandPrefix: '$',
        });
        return sources;
    }
}
//# sourceMappingURL=codex-skills.provider.js.map
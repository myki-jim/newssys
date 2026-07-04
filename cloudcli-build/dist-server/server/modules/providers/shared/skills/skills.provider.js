import path from 'node:path';
import { findProviderSkillMarkdownFiles, readProviderSkillMarkdownDefinition, } from '../../../../shared/utils.js';
const resolveWorkspacePath = (workspacePath) => path.resolve(workspacePath ?? process.cwd());
/**
 * Shared skills provider for provider-specific skill source discovery.
 */
export class SkillsProvider {
    provider;
    constructor(provider) {
        this.provider = provider;
    }
    async listSkills(options) {
        const workspacePath = resolveWorkspacePath(options?.workspacePath);
        const sources = await this.getSkillSources(workspacePath);
        const skills = [];
        for (const source of sources) {
            const skillFiles = await findProviderSkillMarkdownFiles(source.rootDir, {
                recursive: source.recursive,
            });
            for (const skillPath of skillFiles) {
                try {
                    const definition = await readProviderSkillMarkdownDefinition(skillPath);
                    const command = source.commandForSkill
                        ? source.commandForSkill(definition.name)
                        : `${source.commandPrefix ?? '/'}${definition.name}`;
                    skills.push({
                        provider: this.provider,
                        name: definition.name,
                        description: definition.description,
                        command,
                        scope: source.scope,
                        sourcePath: skillPath,
                        pluginName: source.pluginName,
                        pluginId: source.pluginId,
                    });
                }
                catch {
                    // A malformed or unreadable skill markdown file should not hide other valid skills.
                }
            }
        }
        return skills;
    }
}
//# sourceMappingURL=skills.provider.js.map
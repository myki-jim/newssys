import { providerRegistry } from '../../../modules/providers/provider.registry.js';
export const providerSkillsService = {
    /**
     * Lists normalized skills visible to one provider.
     */
    async listProviderSkills(providerName, options) {
        const provider = providerRegistry.resolveProvider(providerName);
        return provider.skills.listSkills(options);
    },
};
//# sourceMappingURL=skills.service.js.map
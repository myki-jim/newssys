/**
 * Centralized Model Definitions
 * Single source of truth for all supported AI models
 */
/**
 * OSINT Models
 */
export const CLAUDE_MODELS = {
    OPTIONS: [
        { value: "deepseek-v4-pro", label: "DeepSeek V4 Flash" },
    ],
    DEFAULT: "deepseek-v4-pro",
};
/**
 * Ordered provider registry.
 */
export const PROVIDERS = [
    { id: "claude", name: "OSINT AI", models: CLAUDE_MODELS },
];
//# sourceMappingURL=modelConstants.js.map
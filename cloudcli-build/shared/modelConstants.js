/**
 * Centralized Model Definitions
 * Single source of truth for all supported AI models
 */

/**
 * OSINT Models
 */
export const CLAUDE_MODELS = {
  OPTIONS: [
    { value: "deepseek-v4-flash", label: "DeepSeek V4 Flash" },
  ],

  DEFAULT: "deepseek-v4-flash",
};

/**
 * Ordered provider registry.
 */
export const PROVIDERS = [
  { id: "claude", name: "OSINT AI", models: CLAUDE_MODELS },
];

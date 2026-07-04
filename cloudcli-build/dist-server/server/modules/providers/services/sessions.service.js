import fsp from 'node:fs/promises';
import path from 'node:path';
import { projectsDb, sessionsDb } from '../../../modules/database/index.js';
import { providerRegistry } from '../../../modules/providers/provider.registry.js';
import { AppError } from '../../../shared/utils.js';
/**
 * Removes one file if it exists.
 */
async function removeFileIfExists(filePath) {
    try {
        await fsp.unlink(filePath);
        return true;
    }
    catch (error) {
        const code = error.code;
        if (code === 'ENOENT') {
            return false;
        }
        throw error;
    }
}
/**
 * Archive rows need a stable project label even when the owning project is not
 * part of the active sidebar payload. This lightweight resolver keeps the
 * archive API self-contained while still matching the project's stored display
 * name when one exists.
 */
function resolveProjectDisplayName(projectPath, customProjectName) {
    const trimmedCustomName = typeof customProjectName === 'string' ? customProjectName.trim() : '';
    if (trimmedCustomName.length > 0) {
        return trimmedCustomName;
    }
    if (!projectPath) {
        return 'Unknown Project';
    }
    return path.basename(projectPath) || projectPath;
}
/**
 * Application service for provider-backed session message operations.
 *
 * Callers pass a provider id and this service resolves the concrete provider
 * class, keeping normalization/history call sites decoupled from implementation
 * file layout.
 */
export const sessionsService = {
    /**
     * Lists provider ids that can load session history and normalize live messages.
     */
    listProviderIds() {
        return providerRegistry.listProviders().map((provider) => provider.id);
    },
    /**
     * Normalizes one provider-native event into frontend session message events.
     */
    normalizeMessage(providerName, raw, sessionId) {
        return providerRegistry.resolveProvider(providerName).sessions.normalizeMessage(raw, sessionId);
    },
    /**
     * Fetches persisted history by session id.
     *
     * Provider and provider-specific lookup hints are resolved from the indexed
     * session metadata in the database.
     */
    fetchHistory(sessionId, options = {}) {
        const session = sessionsDb.getSessionById(sessionId);
        if (!session) {
            throw new AppError(`Session "${sessionId}" was not found.`, {
                code: 'SESSION_NOT_FOUND',
                statusCode: 404,
            });
        }
        const provider = session.provider;
        return providerRegistry.resolveProvider(provider).sessions.fetchHistory(sessionId, {
            limit: options.limit ?? null,
            offset: options.offset ?? 0,
            projectPath: session.project_path ?? '',
        });
    },
    /**
     * Returns archived sessions with enough project metadata for the sidebar to
     * group, filter, open, and restore them without a per-row follow-up query.
     */
    listArchivedSessions() {
        const archivedSessions = sessionsDb.getArchivedSessions();
        const projectCache = new Map();
        return archivedSessions.map((session) => {
            const projectPath = session.project_path?.trim() ? session.project_path : null;
            let project = null;
            if (projectPath) {
                if (!projectCache.has(projectPath)) {
                    projectCache.set(projectPath, projectsDb.getProjectPath(projectPath));
                }
                project = projectCache.get(projectPath) ?? null;
            }
            return {
                sessionId: session.session_id,
                provider: session.provider,
                projectId: project?.project_id ?? null,
                projectPath,
                projectDisplayName: resolveProjectDisplayName(projectPath, project?.custom_project_name),
                sessionTitle: session.custom_name?.trim() || session.session_id,
                createdAt: session.created_at ?? null,
                updatedAt: session.updated_at ?? null,
                lastActivity: session.updated_at ?? session.created_at ?? null,
                isProjectArchived: Boolean(project?.isArchived),
            };
        });
    },
    /**
     * Archives or permanently deletes one persisted session row by id.
     *
     * Soft-delete mirrors the project behavior by toggling `isArchived` so the
     * row disappears from active lists but remains restorable. Force-delete
     * optionally removes the transcript file before deleting the database row.
     */
    async deleteOrArchiveSessionById(sessionId, options = {}) {
        const session = sessionsDb.getSessionById(sessionId);
        if (!session) {
            throw new AppError(`Session "${sessionId}" was not found.`, {
                code: 'SESSION_NOT_FOUND',
                statusCode: 404,
            });
        }
        if (!options.force) {
            sessionsDb.updateSessionIsArchived(sessionId, true);
            return {
                sessionId,
                action: 'archived',
                deletedFromDisk: false,
            };
        }
        let removedFromDisk = false;
        if (options.deletedFromDisk && session.jsonl_path) {
            removedFromDisk = await removeFileIfExists(session.jsonl_path);
        }
        const deleted = sessionsDb.deleteSessionById(sessionId);
        if (!deleted) {
            throw new AppError(`Session "${sessionId}" was not found.`, {
                code: 'SESSION_NOT_FOUND',
                statusCode: 404,
            });
        }
        return {
            sessionId,
            action: 'deleted',
            deletedFromDisk: removedFromDisk,
        };
    },
    /**
     * Restores one archived session back into the active sidebar lists.
     */
    restoreSessionById(sessionId) {
        const session = sessionsDb.getSessionById(sessionId);
        if (!session) {
            throw new AppError(`Session "${sessionId}" was not found.`, {
                code: 'SESSION_NOT_FOUND',
                statusCode: 404,
            });
        }
        sessionsDb.updateSessionIsArchived(sessionId, false);
        return { sessionId, isArchived: false };
    },
    /**
     * Renames one session by id without requiring the caller to pass provider.
     */
    renameSessionById(sessionId, summary) {
        const session = sessionsDb.getSessionById(sessionId);
        if (!session) {
            throw new AppError(`Session "${sessionId}" was not found.`, {
                code: 'SESSION_NOT_FOUND',
                statusCode: 404,
            });
        }
        sessionsDb.updateSessionCustomName(sessionId, summary);
        return { sessionId, summary };
    },
};
//# sourceMappingURL=sessions.service.js.map
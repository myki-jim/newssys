import { getConnection } from '../../../modules/database/connection.js';
import { projectsDb } from '../../../modules/database/repositories/projects.db.js';
import { normalizeProjectPath } from '../../../shared/utils.js';
function normalizeTimestamp(value) {
    if (!value)
        return null;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return null;
    }
    return parsed.toISOString();
}
function normalizeProjectPathForProvider(provider, projectPath) {
    void provider;
    return normalizeProjectPath(projectPath);
}
export const sessionsDb = {
    createSession(sessionId, provider, projectPath, customName, createdAt, updatedAt, jsonlPath) {
        const db = getConnection();
        const createdAtValue = normalizeTimestamp(createdAt);
        const updatedAtValue = normalizeTimestamp(updatedAt);
        const normalizedProjectPath = normalizeProjectPathForProvider(provider, projectPath);
        // First, ensure the project path is recorded in the projects table,
        // since it's a foreign key in the sessions table.
        projectsDb.createProjectPath(normalizedProjectPath);
        db.prepare(`INSERT INTO sessions (session_id, provider, custom_name, project_path, jsonl_path, isArchived, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, 0, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP))
       ON CONFLICT(session_id) DO UPDATE SET
         provider = excluded.provider,
         updated_at = excluded.updated_at,
         project_path = excluded.project_path,
         jsonl_path = excluded.jsonl_path,
         isArchived = 0,
         custom_name = COALESCE(excluded.custom_name, sessions.custom_name)`).run(sessionId, provider, customName ?? null, normalizedProjectPath, jsonlPath ?? null, createdAtValue, updatedAtValue);
        return sessionId;
    },
    updateSessionCustomName(sessionId, customName) {
        const db = getConnection();
        db.prepare(`UPDATE sessions
       SET custom_name = ?
       WHERE session_id = ?`).run(customName, sessionId);
    },
    getSessionById(sessionId) {
        const db = getConnection();
        const row = db
            .prepare(`SELECT session_id, provider, project_path, jsonl_path, custom_name, isArchived, created_at, updated_at
         FROM sessions
         WHERE session_id = ?
         ORDER BY updated_at DESC
         LIMIT 1`)
            .get(sessionId);
        return row ?? null;
    },
    getAllSessions() {
        const db = getConnection();
        return db
            .prepare(`SELECT session_id, provider, project_path, jsonl_path, custom_name, isArchived, created_at, updated_at
         FROM sessions
         WHERE isArchived = 0`)
            .all();
    },
    /**
     * Archived rows are intentionally queried separately so the caller can render
     * them in a dedicated view without reintroducing them into active session lists.
     */
    getArchivedSessions() {
        const db = getConnection();
        return db
            .prepare(`SELECT session_id, provider, project_path, jsonl_path, custom_name, isArchived, created_at, updated_at
         FROM sessions
         WHERE isArchived = 1
         ORDER BY datetime(COALESCE(updated_at, created_at)) DESC, session_id DESC`)
            .all();
    },
    getSessionsByProjectPath(projectPath) {
        const db = getConnection();
        const normalizedProjectPath = normalizeProjectPath(projectPath);
        return db
            .prepare(`SELECT session_id, provider, project_path, jsonl_path, custom_name, isArchived, created_at, updated_at
         FROM sessions
         WHERE project_path = ?
           AND isArchived = 0`)
            .all(normalizedProjectPath);
    },
    /**
     * Permanent project deletion must see every session row for the path,
     * including archived ones, so their transcript files can be cleaned up.
     */
    getSessionsByProjectPathIncludingArchived(projectPath) {
        const db = getConnection();
        const normalizedProjectPath = normalizeProjectPath(projectPath);
        return db
            .prepare(`SELECT session_id, provider, project_path, jsonl_path, custom_name, isArchived, created_at, updated_at
         FROM sessions
         WHERE project_path = ?`)
            .all(normalizedProjectPath);
    },
    getSessionsByProjectPathPage(projectPath, limit, offset) {
        const db = getConnection();
        const normalizedProjectPath = normalizeProjectPath(projectPath);
        return db
            .prepare(`SELECT session_id, provider, project_path, jsonl_path, custom_name, isArchived, created_at, updated_at
         FROM sessions
         WHERE project_path = ?
           AND isArchived = 0
         ORDER BY datetime(COALESCE(updated_at, created_at)) DESC, session_id DESC
         LIMIT ? OFFSET ?`)
            .all(normalizedProjectPath, limit, offset);
    },
    countSessionsByProjectPath(projectPath) {
        const db = getConnection();
        const normalizedProjectPath = normalizeProjectPath(projectPath);
        const row = db
            .prepare(`SELECT COUNT(*) AS count
         FROM sessions
         WHERE project_path = ?
           AND isArchived = 0`)
            .get(normalizedProjectPath);
        return Number(row?.count ?? 0);
    },
    deleteSessionsByProjectPath(projectPath) {
        const db = getConnection();
        const normalizedProjectPath = normalizeProjectPath(projectPath);
        db.prepare(`DELETE FROM sessions WHERE project_path = ?`).run(normalizedProjectPath);
    },
    getSessionName(sessionId, provider) {
        const db = getConnection();
        const row = db
            .prepare(`SELECT custom_name
         FROM sessions
         WHERE session_id = ? AND provider = ?`)
            .get(sessionId, provider);
        return row?.custom_name ?? null;
    },
    /**
     * Soft-delete and restore both use the same flag update so callers keep the
     * row, metadata, and file path intact while toggling visibility.
     */
    updateSessionIsArchived(sessionId, isArchived) {
        const db = getConnection();
        db.prepare(`UPDATE sessions
       SET isArchived = ?
       WHERE session_id = ?`).run(isArchived ? 1 : 0, sessionId);
    },
    deleteSessionById(sessionId) {
        const db = getConnection();
        return db.prepare('DELETE FROM sessions WHERE session_id = ?').run(sessionId).changes > 0;
    },
};
//# sourceMappingURL=sessions.db.js.map
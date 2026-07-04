import express from 'express';
import { providerAuthService } from '../../modules/providers/services/provider-auth.service.js';
import { providerMcpService } from '../../modules/providers/services/mcp.service.js';
import { providerSkillsService } from '../../modules/providers/services/skills.service.js';
import { sessionConversationsSearchService } from '../../modules/providers/services/session-conversations-search.service.js';
import { sessionsService } from '../../modules/providers/services/sessions.service.js';
import { AppError, asyncHandler, createApiSuccessResponse } from '../../shared/utils.js';
const router = express.Router();
const readPathParam = (value, name) => {
    if (typeof value === 'string') {
        return value;
    }
    if (Array.isArray(value) && typeof value[0] === 'string') {
        return value[0];
    }
    throw new AppError(`${name} path parameter is invalid.`, {
        code: 'INVALID_PATH_PARAMETER',
        statusCode: 400,
    });
};
const normalizeProviderParam = (value) => readPathParam(value, 'provider').trim().toLowerCase();
const SESSION_ID_PATTERN = /^[a-zA-Z0-9._-]{1,120}$/;
const parseSessionId = (value) => {
    const sessionId = readPathParam(value, 'sessionId').trim();
    if (!SESSION_ID_PATTERN.test(sessionId)) {
        throw new AppError('Invalid sessionId.', {
            code: 'INVALID_SESSION_ID',
            statusCode: 400,
        });
    }
    return sessionId;
};
const readOptionalQueryString = (value) => {
    if (typeof value !== 'string') {
        return undefined;
    }
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : undefined;
};
const parseOptionalBooleanQuery = (value, name) => {
    if (value === undefined) {
        return undefined;
    }
    const normalized = readOptionalQueryString(value);
    if (!normalized) {
        return undefined;
    }
    if (normalized === 'true') {
        return true;
    }
    if (normalized === 'false') {
        return false;
    }
    throw new AppError(`${name} must be "true" or "false".`, {
        code: 'INVALID_QUERY_PARAMETER',
        statusCode: 400,
    });
};
const parseMcpScope = (value) => {
    if (value === undefined) {
        return undefined;
    }
    const normalized = readOptionalQueryString(value);
    if (!normalized) {
        return undefined;
    }
    if (normalized === 'user' || normalized === 'local' || normalized === 'project') {
        return normalized;
    }
    throw new AppError(`Unsupported MCP scope "${normalized}".`, {
        code: 'INVALID_MCP_SCOPE',
        statusCode: 400,
    });
};
const parseMcpTransport = (value) => {
    const normalized = readOptionalQueryString(value);
    if (!normalized) {
        throw new AppError('transport is required.', {
            code: 'MCP_TRANSPORT_REQUIRED',
            statusCode: 400,
        });
    }
    if (normalized === 'stdio' || normalized === 'http' || normalized === 'sse') {
        return normalized;
    }
    throw new AppError(`Unsupported MCP transport "${normalized}".`, {
        code: 'INVALID_MCP_TRANSPORT',
        statusCode: 400,
    });
};
const parseMcpUpsertPayload = (payload) => {
    if (!payload || typeof payload !== 'object') {
        throw new AppError('Request body must be an object.', {
            code: 'INVALID_REQUEST_BODY',
            statusCode: 400,
        });
    }
    const body = payload;
    const name = readOptionalQueryString(body.name);
    if (!name) {
        throw new AppError('name is required.', {
            code: 'MCP_NAME_REQUIRED',
            statusCode: 400,
        });
    }
    const transport = parseMcpTransport(body.transport);
    const scope = parseMcpScope(body.scope);
    const workspacePath = readOptionalQueryString(body.workspacePath);
    return {
        name,
        transport,
        scope,
        workspacePath,
        command: readOptionalQueryString(body.command),
        args: Array.isArray(body.args) ? body.args.filter((entry) => typeof entry === 'string') : undefined,
        env: typeof body.env === 'object' && body.env !== null
            ? Object.fromEntries(Object.entries(body.env).filter((entry) => typeof entry[1] === 'string'))
            : undefined,
        cwd: readOptionalQueryString(body.cwd),
        url: readOptionalQueryString(body.url),
        headers: typeof body.headers === 'object' && body.headers !== null
            ? Object.fromEntries(Object.entries(body.headers).filter((entry) => typeof entry[1] === 'string'))
            : undefined,
        envVars: Array.isArray(body.envVars)
            ? body.envVars.filter((entry) => typeof entry === 'string')
            : undefined,
        bearerTokenEnvVar: readOptionalQueryString(body.bearerTokenEnvVar),
        envHttpHeaders: typeof body.envHttpHeaders === 'object' && body.envHttpHeaders !== null
            ? Object.fromEntries(Object.entries(body.envHttpHeaders).filter((entry) => typeof entry[1] === 'string'))
            : undefined,
    };
};
const parseProvider = (value) => {
    const normalized = normalizeProviderParam(value);
    if (normalized === 'claude' || normalized === 'codex' || normalized === 'cursor' || normalized === 'gemini') {
        return normalized;
    }
    throw new AppError(`Unsupported provider "${normalized}".`, {
        code: 'UNSUPPORTED_PROVIDER',
        statusCode: 400,
    });
};
const parseSessionRenameSummary = (payload) => {
    if (!payload || typeof payload !== 'object') {
        throw new AppError('Request body must be an object.', {
            code: 'INVALID_REQUEST_BODY',
            statusCode: 400,
        });
    }
    const body = payload;
    const summary = typeof body.summary === 'string' ? body.summary.trim() : '';
    if (!summary) {
        throw new AppError('Summary is required.', {
            code: 'INVALID_SESSION_SUMMARY',
            statusCode: 400,
        });
    }
    if (summary.length > 500) {
        throw new AppError('Summary must not exceed 500 characters.', {
            code: 'INVALID_SESSION_SUMMARY',
            statusCode: 400,
        });
    }
    return summary;
};
const parseSessionSearchQuery = (value) => {
    const query = readOptionalQueryString(value) ?? '';
    if (query.length < 2) {
        throw new AppError('Query must be at least 2 characters', {
            code: 'INVALID_SEARCH_QUERY',
            statusCode: 400,
        });
    }
    return query;
};
const parseSessionSearchLimit = (value) => {
    const raw = readOptionalQueryString(value);
    if (!raw) {
        return 50;
    }
    const parsed = Number.parseInt(raw, 10);
    if (Number.isNaN(parsed)) {
        throw new AppError('limit must be a valid integer.', {
            code: 'INVALID_QUERY_PARAMETER',
            statusCode: 400,
        });
    }
    return Math.max(1, Math.min(parsed, 100));
};
router.get('/:provider/auth/status', asyncHandler(async (req, res) => {
    const provider = parseProvider(req.params.provider);
    const status = await providerAuthService.getProviderAuthStatus(provider);
    res.json(createApiSuccessResponse(status));
}));
// ----------------- Skills routes -----------------
router.get('/:provider/skills', asyncHandler(async (req, res) => {
    const provider = parseProvider(req.params.provider);
    const workspacePath = readOptionalQueryString(req.query.workspacePath);
    const skills = await providerSkillsService.listProviderSkills(provider, { workspacePath });
    res.json(createApiSuccessResponse({ provider, skills }));
}));
// ----------------- MCP routes -----------------
router.get('/:provider/mcp/servers', asyncHandler(async (req, res) => {
    const provider = parseProvider(req.params.provider);
    const workspacePath = readOptionalQueryString(req.query.workspacePath);
    const scope = parseMcpScope(req.query.scope);
    if (scope) {
        const servers = await providerMcpService.listProviderMcpServersForScope(provider, scope, { workspacePath });
        res.json(createApiSuccessResponse({ provider, scope, servers }));
        return;
    }
    const groupedServers = await providerMcpService.listProviderMcpServers(provider, { workspacePath });
    res.json(createApiSuccessResponse({ provider, scopes: groupedServers }));
}));
router.post('/:provider/mcp/servers', asyncHandler(async (req, res) => {
    const provider = parseProvider(req.params.provider);
    const payload = parseMcpUpsertPayload(req.body);
    const server = await providerMcpService.upsertProviderMcpServer(provider, payload);
    res.status(201).json(createApiSuccessResponse({ server }));
}));
router.delete('/:provider/mcp/servers/:name', asyncHandler(async (req, res) => {
    const provider = parseProvider(req.params.provider);
    const scope = parseMcpScope(req.query.scope);
    const workspacePath = readOptionalQueryString(req.query.workspacePath);
    const result = await providerMcpService.removeProviderMcpServer(provider, {
        name: readPathParam(req.params.name, 'name'),
        scope,
        workspacePath,
    });
    res.json(createApiSuccessResponse(result));
}));
router.post('/mcp/servers/global', asyncHandler(async (req, res) => {
    const payload = parseMcpUpsertPayload(req.body);
    if (payload.scope === 'local') {
        throw new AppError('Global MCP add supports only "user" or "project" scopes.', {
            code: 'INVALID_GLOBAL_MCP_SCOPE',
            statusCode: 400,
        });
    }
    const results = await providerMcpService.addMcpServerToAllProviders({
        ...payload,
        scope: payload.scope === 'user' ? 'user' : 'project',
    });
    res.status(201).json(createApiSuccessResponse({ results }));
}));
// ----------------- Session routes -----------------
router.get('/sessions/archived', asyncHandler(async (_req, res) => {
    const sessions = sessionsService.listArchivedSessions();
    res.json(createApiSuccessResponse({ sessions }));
}));
router.delete('/sessions/:sessionId', asyncHandler(async (req, res) => {
    const sessionId = parseSessionId(req.params.sessionId);
    const force = parseOptionalBooleanQuery(req.query.force, 'force') ?? false;
    const deletedFromDisk = parseOptionalBooleanQuery(req.query.deletedFromDisk, 'deletedFromDisk') ?? force;
    const result = await sessionsService.deleteOrArchiveSessionById(sessionId, {
        force,
        deletedFromDisk,
    });
    res.json(createApiSuccessResponse(result));
}));
router.post('/sessions/:sessionId/restore', asyncHandler(async (req, res) => {
    const sessionId = parseSessionId(req.params.sessionId);
    const result = sessionsService.restoreSessionById(sessionId);
    res.json(createApiSuccessResponse(result));
}));
router.put('/sessions/:sessionId', asyncHandler(async (req, res) => {
    const sessionId = parseSessionId(req.params.sessionId);
    const summary = parseSessionRenameSummary(req.body);
    const result = sessionsService.renameSessionById(sessionId, summary);
    res.json(createApiSuccessResponse(result));
}));
router.get('/sessions/:sessionId/messages', asyncHandler(async (req, res) => {
    const sessionId = parseSessionId(req.params.sessionId);
    const limitRaw = readOptionalQueryString(req.query.limit);
    const offsetRaw = readOptionalQueryString(req.query.offset);
    let limit = null;
    if (limitRaw !== undefined) {
        const parsedLimit = Number.parseInt(limitRaw, 10);
        if (Number.isNaN(parsedLimit) || parsedLimit < 0) {
            throw new AppError('limit must be a non-negative integer.', {
                code: 'INVALID_QUERY_PARAMETER',
                statusCode: 400,
            });
        }
        limit = parsedLimit;
    }
    let offset = 0;
    if (offsetRaw !== undefined) {
        const parsedOffset = Number.parseInt(offsetRaw, 10);
        if (Number.isNaN(parsedOffset) || parsedOffset < 0) {
            throw new AppError('offset must be a non-negative integer.', {
                code: 'INVALID_QUERY_PARAMETER',
                statusCode: 400,
            });
        }
        offset = parsedOffset;
    }
    const result = await sessionsService.fetchHistory(sessionId, {
        limit,
        offset,
    });
    res.json(result);
}));
router.get('/search/sessions', asyncHandler(async (req, res) => {
    const query = parseSessionSearchQuery(req.query.q);
    const limit = parseSessionSearchLimit(req.query.limit);
    res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
    });
    let closed = false;
    const abortController = new AbortController();
    req.on('close', () => {
        closed = true;
        abortController.abort();
    });
    try {
        await sessionConversationsSearchService.search({
            query,
            limit,
            signal: abortController.signal,
            onProgress: ({ projectResult, totalMatches, scannedProjects, totalProjects }) => {
                if (closed) {
                    return;
                }
                if (projectResult) {
                    res.write(`event: result\ndata: ${JSON.stringify({ projectResult, totalMatches, scannedProjects, totalProjects })}\n\n`);
                    return;
                }
                res.write(`event: progress\ndata: ${JSON.stringify({ totalMatches, scannedProjects, totalProjects })}\n\n`);
            },
        });
        if (!closed) {
            res.write('event: done\ndata: {}\n\n');
        }
    }
    catch (error) {
        console.error('Error searching conversations:', error);
        if (!closed) {
            res.write(`event: error\ndata: ${JSON.stringify({ error: 'Search failed' })}\n\n`);
        }
    }
    finally {
        if (!closed) {
            res.end();
        }
    }
}));
export default router;
//# sourceMappingURL=provider.routes.js.map
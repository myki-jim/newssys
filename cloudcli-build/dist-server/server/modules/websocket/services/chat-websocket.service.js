import { connectedClients } from '../../../modules/websocket/services/websocket-state.service.js';
import { WebSocketWriter } from '../../../modules/websocket/services/websocket-writer.service.js';
import { createNormalizedMessage, parseIncomingJsonObject } from '../../../shared/utils.js';
const DEFAULT_PROVIDER = 'claude';
/**
 * Normalizes potentially invalid provider names coming from websocket payloads.
 */
function readProvider(value) {
    if (value === 'claude' || value === 'cursor' || value === 'codex' || value === 'gemini') {
        return value;
    }
    return DEFAULT_PROVIDER;
}
/**
 * Extracts the authenticated request user id in the formats currently produced
 * by platform and OSS auth code paths.
 */
function readRequestUserId(request) {
    const user = request?.user;
    if (!user) {
        return null;
    }
    if (typeof user.id === 'string' || typeof user.id === 'number') {
        return user.id;
    }
    if (typeof user.userId === 'string' || typeof user.userId === 'number') {
        return user.userId;
    }
    return null;
}
/**
 * Handles authenticated chat websocket messages used by the main chat panel.
 */
export function handleChatConnection(ws, request, dependencies) {
    console.log('[INFO] Chat WebSocket connected');
    connectedClients.add(ws);
    const writer = new WebSocketWriter(ws, readRequestUserId(request));
    ws.on('message', async (rawMessage) => {
        try {
            const parsed = parseIncomingJsonObject(rawMessage);
            if (!parsed) {
                throw new Error('Invalid websocket payload');
            }
            const data = parsed;
            const messageType = data.type;
            if (!messageType) {
                throw new Error('Message type is required');
            }
            if (messageType === 'claude-command') {
                await dependencies.queryClaudeSDK(data.command ?? '', data.options, writer);
                return;
            }
            if (messageType === 'cursor-command') {
                await dependencies.spawnCursor(data.command ?? '', data.options, writer);
                return;
            }
            if (messageType === 'codex-command') {
                await dependencies.queryCodex(data.command ?? '', data.options, writer);
                return;
            }
            if (messageType === 'gemini-command') {
                await dependencies.spawnGemini(data.command ?? '', data.options, writer);
                return;
            }
            if (messageType === 'cursor-resume') {
                await dependencies.spawnCursor('', {
                    sessionId: data.sessionId,
                    resume: true,
                    cwd: data.options?.cwd,
                }, writer);
                return;
            }
            if (messageType === 'abort-session') {
                const provider = readProvider(data.provider);
                const sessionId = typeof data.sessionId === 'string' ? data.sessionId : '';
                let success = false;
                if (provider === 'cursor') {
                    success = dependencies.abortCursorSession(sessionId);
                }
                else if (provider === 'codex') {
                    success = dependencies.abortCodexSession(sessionId);
                }
                else if (provider === 'gemini') {
                    success = dependencies.abortGeminiSession(sessionId);
                }
                else {
                    success = await dependencies.abortClaudeSDKSession(sessionId);
                }
                writer.send(createNormalizedMessage({
                    kind: 'complete',
                    exitCode: success ? 0 : 1,
                    aborted: true,
                    success,
                    sessionId,
                    provider,
                }));
                return;
            }
            if (messageType === 'claude-permission-response') {
                if (typeof data.requestId === 'string' && data.requestId.length > 0) {
                    dependencies.resolveToolApproval(data.requestId, {
                        allow: Boolean(data.allow),
                        updatedInput: data.updatedInput,
                        message: typeof data.message === 'string' ? data.message : undefined,
                        rememberEntry: data.rememberEntry,
                    });
                }
                return;
            }
            if (messageType === 'cursor-abort') {
                const sessionId = typeof data.sessionId === 'string' ? data.sessionId : '';
                const success = dependencies.abortCursorSession(sessionId);
                writer.send(createNormalizedMessage({
                    kind: 'complete',
                    exitCode: success ? 0 : 1,
                    aborted: true,
                    success,
                    sessionId,
                    provider: 'cursor',
                }));
                return;
            }
            if (messageType === 'check-session-status') {
                const provider = readProvider(data.provider);
                const sessionId = typeof data.sessionId === 'string' ? data.sessionId : '';
                let isActive = false;
                if (provider === 'cursor') {
                    isActive = dependencies.isCursorSessionActive(sessionId);
                }
                else if (provider === 'codex') {
                    isActive = dependencies.isCodexSessionActive(sessionId);
                }
                else if (provider === 'gemini') {
                    isActive = dependencies.isGeminiSessionActive(sessionId);
                }
                else {
                    isActive = dependencies.isClaudeSDKSessionActive(sessionId);
                    if (isActive) {
                        dependencies.reconnectSessionWriter(sessionId, ws);
                    }
                }
                writer.send({
                    type: 'session-status',
                    sessionId,
                    provider,
                    isProcessing: isActive,
                });
                return;
            }
            if (messageType === 'get-pending-permissions') {
                const sessionId = typeof data.sessionId === 'string' ? data.sessionId : '';
                if (sessionId && dependencies.isClaudeSDKSessionActive(sessionId)) {
                    const pending = dependencies.getPendingApprovalsForSession(sessionId);
                    writer.send({
                        type: 'pending-permissions-response',
                        sessionId,
                        data: pending,
                    });
                }
                return;
            }
            if (messageType === 'get-active-sessions') {
                writer.send({
                    type: 'active-sessions',
                    sessions: {
                        claude: dependencies.getActiveClaudeSDKSessions(),
                        cursor: dependencies.getActiveCursorSessions(),
                        codex: dependencies.getActiveCodexSessions(),
                        gemini: dependencies.getActiveGeminiSessions(),
                    },
                });
            }
        }
        catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            console.error('[ERROR] Chat WebSocket error:', message);
            writer.send({
                type: 'error',
                error: message,
            });
        }
    });
    ws.on('close', () => {
        console.log('[INFO] Chat client disconnected');
        connectedClients.delete(ws);
    });
}
//# sourceMappingURL=chat-websocket.service.js.map
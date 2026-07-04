import { WebSocketServer } from 'ws';
import { handleChatConnection } from '../../../modules/websocket/services/chat-websocket.service.js';
import { verifyWebSocketClient } from '../../../modules/websocket/services/websocket-auth.service.js';
import { handlePluginWsProxy } from '../../../modules/websocket/services/plugin-websocket-proxy.service.js';
import { handleShellConnection } from '../../../modules/websocket/services/shell-websocket.service.js';
/**
 * Creates and wires the server-wide websocket gateway used for chat, shell, and
 * plugin proxy routes.
 */
export function createWebSocketServer(server, dependencies) {
    const wss = new WebSocketServer({
        server,
        verifyClient: ((info) => verifyWebSocketClient(info, dependencies.verifyClient)),
    });
    wss.on('connection', (ws, request) => {
        const incomingRequest = request;
        const url = incomingRequest.url ?? '/';
        const pathname = new URL(url, 'http://localhost').pathname;
        if (pathname === '/shell') {
            handleShellConnection(ws, dependencies.shell);
            return;
        }
        if (pathname === '/ws') {
            handleChatConnection(ws, incomingRequest, dependencies.chat);
            return;
        }
        if (pathname.startsWith('/plugin-ws/')) {
            handlePluginWsProxy(ws, pathname, dependencies.getPluginPort);
            return;
        }
        console.log('[WARN] Unknown WebSocket path:', pathname);
        ws.close();
    });
    return wss;
}
//# sourceMappingURL=websocket-server.service.js.map
(function() {
    'use strict';

    const TERMINAL_WS_URL = `ws://${window.location.host}/api/terminal/ws`;

    class TerminalPanel {
        constructor(container) {
            this.container = container;
            this.terminal = null;
            this.websocket = null;
            this.sessionId = null;
            this.fitAddon = null;
            this.connected = false;
            this.reconnectAttempts = 0;
            this.maxReconnectAttempts = 5;
        }

        async init() {
            const terminalContainer = document.createElement('div');
            terminalContainer.className = 'terminal-container';
            this.container.appendChild(terminalContainer);

            await this.loadXterm();

            this.terminal = new Terminal({
                theme: {
                    background: '#0a0a1a',
                    foreground: '#e0e0e0',
                    cursor: '#4fc3f7',
                    cursorAccent: '#0a0a1a',
                    selection: 'rgba(79, 195, 247, 0.3)',
                    black: '#0a0a1a',
                    red: '#ef5350',
                    green: '#66bb6a',
                    yellow: '#ffa726',
                    blue: '#42a5f5',
                    magenta: '#ab47bc',
                    cyan: '#26c6da',
                    white: '#e0e0e0',
                    brightBlack: '#546e7a',
                    brightRed: '#e57373',
                    brightGreen: '#81c784',
                    brightYellow: '#ffb74d',
                    brightBlue: '#64b5f6',
                    brightMagenta: '#ce93d8',
                    brightCyan: '#4dd0e1',
                    brightWhite: '#ffffff',
                },
                fontFamily: "'SF Mono', 'Cascadia Code', 'Fira Code', monospace",
                fontSize: 14,
                lineHeight: 1.2,
                cursorBlink: true,
                cursorStyle: 'block',
                scrollback: 10000,
                allowTransparency: true,
            });

            this.fitAddon = new FitAddon.FitAddon();
            this.terminal.loadAddon(this.fitAddon);

            this.terminal.open(terminalContainer);

            const webLinksAddon = new WebLinksAddon.WebLinksAddon();
            this.terminal.loadAddon(webLinksAddon);

            this.terminal.onData((data) => {
                this.sendInput(data);
            });

            this.terminal.onResize(({ cols, rows }) => {
                this.sendResize(cols, rows);
            });

            this.connect();

            setTimeout(() => {
                this.fit();
            }, 100);
        }

        async loadXterm() {
            if (window.Terminal && window.FitAddon && window.WebLinksAddon) {
                return;
            }

            const scripts = [
                {
                    src: 'https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js',
                    integrity: 'sha384-Y7EI+h6ReVW7G2im4DQHRt6dyZZqQrLK3nsVMjT5DtS4vT3g5Tmfu0c05Ij3oE5Mf'
                },
                {
                    src: 'https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.min.js',
                    integrity: 'sha384-PBzYfo5NuCZhXe+QqAuVcN3aW5eq8LZJQKvzVqbw3PhgH96zlJ5CkF+PO8xbVw6E'
                },
                {
                    src: 'https://cdn.jsdelivr.net/npm/xterm-addon-web-links@0.9.0/lib/xterm-addon-web-links.min.js',
                    integrity: 'sha384-PGQLzQ3hgxf5h1HYh+L5t0CqBu8Pag8f4E4Y1L+WPZ+3ugnq+e8qJ5L4Q2ANd1F'
                },
            ];

            const styles = [
                'https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css',
            ];

            for (const href of styles) {
                if (!document.querySelector(`link[href="${href}"]`)) {
                    const link = document.createElement('link');
                    link.rel = 'stylesheet';
                    link.href = href;
                    link.crossOrigin = 'anonymous';
                    document.head.appendChild(link);
                }
            }

            for (const scriptInfo of scripts) {
                if (!document.querySelector(`script[src="${scriptInfo.src}"]`)) {
                    await new Promise((resolve, reject) => {
                        const script = document.createElement('script');
                        script.src = scriptInfo.src;
                        script.integrity = scriptInfo.integrity;
                        script.crossOrigin = 'anonymous';
                        script.onload = resolve;
                        script.onerror = () => {
                            console.error(`Failed to load script: ${scriptInfo.src}`);
                            reject(new Error(`Failed to load ${scriptInfo.src}`));
                        };
                        document.head.appendChild(script);
                    });
                }
            }
        }

        connect() {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                return;
            }

            this.terminal.write('\x1b[33mConnecting to terminal...\x1b[0m\r\n');

            try {
                this.websocket = new WebSocket(TERMINAL_WS_URL);
            } catch (e) {
                this.terminal.write(`\x1b[31mFailed to create WebSocket: ${e}\x1b[0m\r\n`);
                this.scheduleReconnect();
                return;
            }

            this.websocket.onopen = () => {
                this.connected = true;
                this.reconnectAttempts = 0;
                this.terminal.write('\x1b[32mConnected!\x1b[0m\r\n');
                this.createSession();
            };

            this.websocket.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    this.handleMessage(msg);
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };

            this.websocket.onclose = (event) => {
                this.connected = false;
                if (!event.wasClean) {
                    this.terminal.write('\r\n\x1b[33mConnection closed unexpectedly.\x1b[0m\r\n');
                    this.scheduleReconnect();
                } else {
                    this.terminal.write('\r\n\x1b[33mConnection closed.\x1b[0m\r\n');
                }
            };

            this.websocket.onerror = (error) => {
                this.terminal.write('\r\n\x1b[31mWebSocket error.\x1b[0m\r\n');
            };
        }

        createSession() {
            const cols = this.terminal.cols || 80;
            const rows = this.terminal.rows || 24;

            this.send({
                type: 'create',
                cols: cols,
                rows: rows,
            });
        }

        handleMessage(msg) {
            switch (msg.type) {
                case 'created':
                    this.sessionId = msg.session_id;
                    this.terminal.write(`\x1b[32mSession created: ${msg.session_id.substring(0, 8)}...\x1b[0m\r\n`);
                    this.terminal.write(`\x1b[90mShell: ${msg.shell}\x1b[0m\r\n`);
                    this.fit();
                    break;

                case 'output':
                    if (msg.data) {
                        this.terminal.write(msg.data);
                    }
                    break;

                case 'exit':
                    this.terminal.write(`\r\n\x1b[33mProcess exited with code ${msg.code}\x1b[0m\r\n`);
                    this.sessionId = null;
                    break;

                case 'error':
                    this.terminal.write(`\r\n\x1b[31mError: ${msg.message}\x1b[0m\r\n`);
                    break;

                case 'pong':
                    break;
            }
        }

        send(data) {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify(data));
            }
        }

        sendInput(data) {
            if (!this.sessionId) return;
            this.send({
                type: 'input',
                session_id: this.sessionId,
                data: data,
            });
        }

        sendResize(cols, rows) {
            if (!this.sessionId) return;
            this.send({
                type: 'resize',
                session_id: this.sessionId,
                cols: cols,
                rows: rows,
            });
        }

        scheduleReconnect() {
            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                this.terminal.write(`\x1b[31mMax reconnect attempts reached.\x1b[0m\r\n`);
                return;
            }

            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

            this.terminal.write(`\x1b[33mReconnecting in ${delay / 1000}s...\x1b[0m\r\n`);

            setTimeout(() => {
                this.connect();
            }, delay);
        }

        fit() {
            if (this.fitAddon && this.terminal) {
                try {
                    this.fitAddon.fit();
                } catch (e) {
                }
            }
        }

        destroy() {
            if (this.websocket) {
                this.websocket.close();
                this.websocket = null;
            }
            if (this.terminal) {
                this.terminal.dispose();
                this.terminal = null;
            }
        }
    }

    window.TerminalPanel = TerminalPanel;
})();

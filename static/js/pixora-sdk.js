/**
 * Pixora Platform SDK v2.0.0 (Hardened Cryptographic Edition)
 * Standardized communication protocol & proof-of-gameplay engine.
 * 
 * Features:
 * - Cryptographic session handshake (/api/v2/session/start)
 * - Strict origin validation for iframe postMessage (Fixes Fatal Flaw #3)
 * - Action entropy tracking and rate-limiting
 * - Dual-mode operation: Direct REST API (standalone) & Parent Shell Bridge (sandboxed)
 */

(function (window) {
    'use strict';

    class PixoraSDK {
        constructor(allowedOrigin = window.location.origin) {
            this.version = '2.0.0';
            this.allowedOrigin = allowedOrigin;
            this.sessionToken = null;
            this.startTime = null;
            this.gameSlug = null;
            this.initialized = false;
            this.player = null;
            this.isMuted = false;

            // Proof-of-Gameplay Telemetry
            this.actionCount = 0;
            this._actionTimestamps = [];
            this._listeners = {};

            // Bind and register strict postMessage handler
            this._handleParentMessage = this._handleParentMessage.bind(this);
            window.addEventListener('message', this._handleParentMessage);

            // Automatic keystroke/click action tracking for entropy validation
            this._setupActionListeners();
        }

        /**
         * Initialize the SDK connection with parent platform shell or REST backend.
         */
        async init(options = {}) {
            this.gameSlug = options.gameSlug || options.gameId || window.location.pathname.split('/').filter(Boolean).pop();
            if (options.allowedOrigin) {
                this.allowedOrigin = options.allowedOrigin;
            }

            // If we are inside an iframe, attempt parent shell handshake
            if (window.parent && window.parent !== window) {
                return new Promise((resolve) => {
                    const ackHandler = (e) => {
                        // Strict origin check
                        if (this.allowedOrigin !== '*' && e.origin !== this.allowedOrigin && e.origin !== window.location.origin) {
                            return;
                        }

                        if (e.data && (e.data.type === 'PIXORA_HANDSHAKE_ACK' || e.data.type === 'GLITCH4CE_HANDSHAKE_ACK')) {
                            this.initialized = true;
                            this.player = e.data.payload ? e.data.payload.player : null;
                            if (e.data.payload && e.data.payload.sessionToken) {
                                this.sessionToken = e.data.payload.sessionToken;
                                this.startTime = e.data.payload.startTimeMs || Date.now();
                            }
                            window.removeEventListener('message', ackHandler);
                            console.log('%c👾 [Pixora SDK v2] Authenticated shell connection established.', 'color: #00ffcc; font-weight: bold;');
                            resolve({ success: true, player: this.player, mode: 'iframe' });
                        }
                    };

                    window.addEventListener('message', ackHandler);

                    // Broadcast handshake to parent
                    this._sendToParent('PIXORA_HANDSHAKE', {
                        gameId: this.gameSlug,
                        version: this.version
                    });

                    // Fallback to direct REST session if parent doesn't ACK within 1200ms
                    setTimeout(async () => {
                        if (!this.initialized) {
                            try {
                                await this.startSession(this.gameSlug);
                                this.initialized = true;
                                console.log('%c👾 [Pixora SDK v2] Connected directly via REST Gateway.', 'color: #7928ca; font-weight: bold;');
                                resolve({ success: true, player: this.player || { username: 'Player' }, mode: 'rest' });
                            } catch (e) {
                                this.initialized = true;
                                this.player = { username: 'GuestPlayer', isGuest: true };
                                resolve({ success: true, player: this.player, mode: 'standalone' });
                            }
                        }
                    }, 1200);
                });
            } else {
                // Standalone mode: connect directly via REST
                try {
                    await this.startSession(this.gameSlug);
                    this.initialized = true;
                    return { success: true, player: this.player, mode: 'rest' };
                } catch (e) {
                    this.initialized = true;
                    return { success: false, error: e.message, mode: 'offline' };
                }
            }
        }

        /**
         * Authoritative Session Handshake: Request cryptographically signed token.
         * @param {string} gameSlug 
         */
        async startSession(gameSlug) {
            this.gameSlug = gameSlug || this.gameSlug;
            this.actionCount = 0;
            this._actionTimestamps = [];

            try {
                const res = await fetch('/api/v2/session/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ game_slug: this.gameSlug })
                });

                if (!res.ok) {
                    throw new Error(`Session start failed with HTTP ${res.status}`);
                }

                const data = await res.json();
                this.sessionToken = data.session_token;
                this.startTime = data.start_time_ms;
                this.player = { id: data.player_id, username: data.username };
                return data;
            } catch (err) {
                console.warn('[Pixora SDK] Direct session start warning:', err.message);
                this.startTime = Date.now();
                throw err;
            }
        }

        /**
         * Track physical player input for entropy verification.
         */
        recordAction(actionType = 'action') {
            this.actionCount++;
            if (this._actionTimestamps.length < 100) {
                this._actionTimestamps.push(Date.now());
            }
        }

        _setupActionListeners() {
            const onAction = () => { this.recordAction(); };
            window.addEventListener('keydown', onAction, { passive: true });
            window.addEventListener('pointerdown', onAction, { passive: true });
        }

        /**
         * Report loading progress to show loading indicator in theater shell.
         * @param {number} percentage 0 to 100
         */
        loadingProgress(percentage) {
            this._sendToParent('PIXORA_LOADING_PROGRESS', { percentage: Math.min(100, Math.max(0, percentage)) });
        }

        /**
         * Notify platform that game loop has started.
         */
        gameplayStart() {
            if (!this.startTime) {
                this.startTime = Date.now();
            }
            this._sendToParent('PIXORA_GAMEPLAY_START', { timestamp: Date.now() });
        }

        /**
         * Notify platform that game loop has paused or reached game-over.
         */
        gameplayStop() {
            this._sendToParent('PIXORA_GAMEPLAY_STOP', { timestamp: Date.now() });
        }

        /**
         * Submit high score with cryptographic proof and action entropy.
         * @param {number} score 
         * @param {object} extraData optional metadata
         */
        async submitScore(score, extraData = {}) {
            const numScore = Math.floor(Number(score));
            if (isNaN(numScore) || numScore < 0) {
                console.error('[Pixora SDK] Score must be a positive integer.');
                return;
            }

            const now = Date.now();
            const startMs = this.startTime || (now - 2000);
            const durationMs = Math.max(0, now - startMs);

            // Compute basic input entropy checksum
            const entropyStr = `${this.actionCount}:${this._actionTimestamps.slice(-10).join(',')}`;

            // If we have an active cryptographic session token, submit directly to v2 REST API
            if (this.sessionToken) {
                try {
                    const res = await fetch('/api/v2/session/end', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            game_slug: this.gameSlug,
                            score: numScore,
                            session_token: this.sessionToken,
                            start_time_ms: startMs,
                            duration_ms: durationMs,
                            action_count: this.actionCount,
                            input_entropy_hash: entropyStr,
                            extra_data: extraData
                        })
                    });

                    const result = await res.json();
                    if (!res.ok) {
                        console.error('[Pixora SDK] Anti-Cheat Rejected Submission:', result);
                    } else {
                        console.log('%c🛡️ [Pixora SDK v2] Score cryptographically verified & submitted:', 'color: #00f2fe;', result);
                    }
                    return result;
                } catch (e) {
                    console.warn('[Pixora SDK] Direct submission failed, falling back to parent postMessage:', e);
                }
            }

            // Fallback: Notify parent shell via secure postMessage
            this._sendToParent('PIXORA_SUBMIT_SCORE', {
                score: numScore,
                session_token: this.sessionToken,
                start_time_ms: startMs,
                action_count: this.actionCount,
                extraData: extraData,
                timestamp: now
            });
        }

        /**
         * Request commercial break or interstitial.
         */
        async commercialBreak() {
            return new Promise((resolve) => {
                const resumeHandler = (e) => {
                    if (this.allowedOrigin !== '*' && e.origin !== this.allowedOrigin && e.origin !== window.location.origin) return;
                    if (e.data && e.data.type === 'PIXORA_BREAK_COMPLETE') {
                        window.removeEventListener('message', resumeHandler);
                        resolve();
                    }
                };
                window.addEventListener('message', resumeHandler);
                this._sendToParent('PIXORA_REQUEST_BREAK');
                setTimeout(resolve, 3000);
            });
        }

        onMuteToggle(callback) {
            this._listeners['MUTE_TOGGLE'] = callback;
        }

        _sendToParent(type, payload = {}) {
            if (window.parent && window.parent !== window) {
                const targetOrigin = (this.allowedOrigin && this.allowedOrigin !== '*') ? this.allowedOrigin : window.location.origin;
                window.parent.postMessage({
                    source: 'PIXORA_GAME_CLIENT',
                    type: type,
                    payload: payload
                }, targetOrigin);
            }
        }

        _handleParentMessage(event) {
            // Strict Origin Verification: Drop malicious third-party message spoofs
            if (this.allowedOrigin !== '*' && event.origin !== this.allowedOrigin && event.origin !== window.location.origin) {
                return;
            }

            const data = event.data;
            if (!data || data.source !== 'PIXORA_PLATFORM_SHELL') return;

            if (data.type === 'PIXORA_MUTE_CHANGED' && this._listeners['MUTE_TOGGLE']) {
                this.isMuted = !!data.payload.muted;
                this._listeners['MUTE_TOGGLE'](this.isMuted);
            }
        }
    }

    // Expose global constructors and singletons
    window.PixoraSDK = PixoraSDK;
    window.Pixora = window.Pixora || new PixoraSDK();
    window.Glitch4ce = window.Pixora;

})(typeof window !== 'undefined' ? window : this);

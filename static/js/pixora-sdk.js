/**
 * Pixora Platform SDK v1.0.0
 * Standardized communication protocol between sandboxed games and the Pixora platform.
 * Inspired by PokiSDK / CrazyGames SDK.
 */

(function (window) {
    'use strict';

    class PixoraSDK {
        constructor() {
            this.version = '1.0.0';
            this.initialized = false;
            this.gameId = null;
            this.player = null;
            this.sessionToken = null;
            this.isMuted = false;

            // Internal event callbacks
            this._listeners = {};

            this._handleParentMessage = this._handleParentMessage.bind(this);
            window.addEventListener('message', this._handleParentMessage);
        }

        /**
         * Initialize the SDK connection with parent platform shell.
         */
        async init(options = {}) {
            return new Promise((resolve) => {
                this.gameId = options.gameId || window.location.pathname.split('/').filter(Boolean).pop();

                // Listen for handshake ack from parent portal
                const ackHandler = (e) => {
                    if (e.data && e.data.type === 'PIXORA_HANDSHAKE_ACK') {
                        this.initialized = true;
                        this.player = e.data.payload.player;
                        this.sessionToken = e.data.payload.sessionToken;
                        window.removeEventListener('message', ackHandler);
                        console.log('%c👾 [Pixora SDK] Connected to Platform shell.', 'color: #00ffcc; font-weight: bold;');
                        resolve({ success: true, player: this.player });
                    }
                };

                window.addEventListener('message', ackHandler);

                // Broadcast handshake
                this._sendToParent('PIXORA_HANDSHAKE', {
                    gameId: this.gameId,
                    version: this.version
                });

                // Fallback timeout if game is running standalone (e.g. direct asset preview)
                setTimeout(() => {
                    if (!this.initialized) {
                        this.initialized = true;
                        this.player = { username: 'GuestPlayer', isGuest: true };
                        console.warn('[Pixora SDK] Standalone/Offline mode initialized.');
                        resolve({ success: true, player: this.player, standalone: true });
                    }
                }, 1200);
            });
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
            this._sendToParent('PIXORA_GAMEPLAY_START', { timestamp: Date.now() });
        }

        /**
         * Notify platform that game loop has paused or player reached game-over.
         */
        gameplayStop() {
            this._sendToParent('PIXORA_GAMEPLAY_STOP', { timestamp: Date.now() });
        }

        /**
         * Submit high score to server leaderboard.
         * @param {number} score 
         * @param {object} extraData optional level or stats
         */
        submitScore(score, extraData = {}) {
            if (typeof score !== 'number' || isNaN(score)) {
                console.error('[Pixora SDK] Score must be a valid number.');
                return;
            }

            this._sendToParent('PIXORA_SUBMIT_SCORE', {
                score: Math.floor(score),
                extraData: extraData,
                timestamp: Date.now()
            });
        }

        /**
         * Request interstitial commercial / break.
         */
        async commercialBreak() {
            return new Promise((resolve) => {
                const resumeHandler = (e) => {
                    if (e.data && e.data.type === 'PIXORA_BREAK_COMPLETE') {
                        window.removeEventListener('message', resumeHandler);
                        resolve();
                    }
                };
                window.addEventListener('message', resumeHandler);
                this._sendToParent('PIXORA_REQUEST_BREAK');
                // Auto resume if no response after 3s
                setTimeout(resolve, 3000);
            });
        }

        /**
         * Toggle platform audio mute.
         */
        onMuteToggle(callback) {
            this._listeners['MUTE_TOGGLE'] = callback;
        }

        _sendToParent(type, payload = {}) {
            if (window.parent && window.parent !== window) {
                window.parent.postMessage({
                    source: 'PIXORA_GAME_CLIENT',
                    type: type,
                    payload: payload
                }, '*');
            }
        }

        _handleParentMessage(event) {
            const data = event.data;
            if (!data || data.source !== 'PIXORA_PLATFORM_SHELL') return;

            if (data.type === 'PIXORA_MUTE_CHANGED' && this._listeners['MUTE_TOGGLE']) {
                this.isMuted = !!data.payload.muted;
                this._listeners['MUTE_TOGGLE'](this.isMuted);
            }
        }
    }

    // Expose global singleton
    // Aliases for compatibility
    window.Pixora = window.Pixora || new PixoraSDK();
    window.Glitch4ce = window.Pixora;

})(window);

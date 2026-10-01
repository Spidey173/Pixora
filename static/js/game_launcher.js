/**
 * Pixora Game Launcher & Telemetry Helper Module
 */
const GlitchLauncher = {
  /**
   * Request fullscreen container view
   */
  toggleFullscreen(elementId = null) {
    const el = elementId ? document.getElementById(elementId) : document.documentElement;
    if (!document.fullscreenElement) {
      if (el.requestFullscreen) el.requestFullscreen();
      else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
      else if (el.msRequestFullscreen) el.msRequestFullscreen();
    } else {
      if (document.exitFullscreen) document.exitFullscreen();
    }
  },

  /**
   * Log game start telemetry
   */
  logStart(gameName) {
    if (!gameName) return;
    return fetch(`/start_game/${encodeURIComponent(gameName)}`, {
      method: 'POST'
    }).catch(err => console.log('Game start telemetry log failed:', err));
  },

  /**
   * Log game completion telemetry
   */
  logEnd(gameName) {
    if (!gameName) return;
    return fetch(`/end_game/${encodeURIComponent(gameName)}`, {
      method: 'POST'
    }).catch(err => console.log('Game end telemetry log failed:', err));
  },

  /**
   * Submit player high score to telemetry API
   */
  submitScore(gameName, score) {
    if (!gameName || score === undefined || score === null) return;
    return fetch('/api/score/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game_name: gameName, score: Math.floor(score) })
    }).then(res => res.json())
      .catch(err => console.log('Score submit failed:', err));
  }
};

window.GlitchLauncher = GlitchLauncher;

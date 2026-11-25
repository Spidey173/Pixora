/**
 * Pixora 2.0 API Client
 */

export const PixoraAPI = {
  async startSession(gameSlug: string) {
    const res = await fetch('/api/v2/session/start', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game_slug: gameSlug }),
    });
    if (!res.ok) throw new Error('Failed to initiate cryptographic session');
    return res.json();
  },

  async submitScore(payload: {
    game_slug: string;
    score: number;
    session_token: string;
    start_time_ms: number;
    action_count?: number;
  }) {
    const res = await fetch('/api/v2/session/end', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return res.json();
  },

  async getPresence(gameSlug: string): Promise<number> {
    try {
      const res = await fetch(`/api/v2/presence/${encodeURIComponent(gameSlug)}`);
      const data = await res.json();
      return data.presence || 1;
    } catch {
      return 1;
    }
  },
};


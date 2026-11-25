/**
 * Pixora 2.0 API Client
 */

export interface LeaderboardEntry {
  player_id: number;
  username: string;
  score: number;
  achieved_at?: string;
}

export interface LeaderboardData {
  game_name: string;
  leaderboard: LeaderboardEntry[];
  user_best?: number | null;
  world_record?: {
    score: number;
    username: string;
  } | null;
}

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

  async getLeaderboard(gameSlug: string): Promise<LeaderboardData> {
    const res = await fetch(`/api/leaderboard/${encodeURIComponent(gameSlug)}`, {
      credentials: 'include',
    });
    if (!res.ok) throw new Error('Failed to fetch leaderboard');
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


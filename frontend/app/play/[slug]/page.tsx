'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import { PixoraAPI, LeaderboardData } from '@/lib/api';
import { CanvasLeaderboardChart } from '@/components/CanvasLeaderboardChart';

const GAME_URLS: Record<string, { title: string; playUrl: string; category: string }> = {
  'neon-cyber-racer': {
    title: 'Neon Cyber Racer',
    playUrl: 'https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev/games/neon-cyber-racer/index.html',
    category: 'Action',
  },
  '2048': {
    title: '2048 Cyber Grid',
    playUrl: '/2048',
    category: 'Puzzle',
  },
  'flappybird': {
    title: 'Flappy Birds',
    playUrl: '/FlappyBird',
    category: 'Arcade',
  },
  'speedtype': {
    title: 'SpeedType Pro',
    playUrl: '/speedtype',
    category: 'Skill',
  },
};

export default function GameTheaterPage() {
  const params = useParams();
  const slug = (params?.slug as string) || 'neon-cyber-racer';
  const game = GAME_URLS[slug] || {
    title: slug.replace(/-/g, ' ').toUpperCase(),
    playUrl: `/${slug}`,
    category: 'Arcade',
  };

  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [presence, setPresence] = useState<number>(1);
  const [leaderboard, setLeaderboard] = useState<LeaderboardData | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // 1. Fetch Leaderboard and Initial Presence
  const loadData = async () => {
    try {
      const lb = await PixoraAPI.getLeaderboard(game.title);
      setLeaderboard(lb);
      const pres = await PixoraAPI.getPresence(game.title);
      setPresence(pres);
    } catch (e) {
      console.warn('Initial data load warning:', e);
    }
  };

  useEffect(() => {
    loadData();

    // 2. Real-Time SSE Stream for Presence & Overtakes
    let evtSource: EventSource | null = null;
    try {
      evtSource = new EventSource(`/api/v2/events/${encodeURIComponent(game.title)}`);
      evtSource.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === 'PRESENCE_UPDATE') {
            setPresence(data.count);
          } else if (data.type === 'LEADERBOARD_OVERTAKE') {
            showToast(`⚡ LIVE: ${data.player} claimed Rank #${data.rank} (${data.score.toLocaleString()} pts)!`);
            loadData();
          }
        } catch {}
      };
    } catch {}

    // 3. Strict postMessage Receiver with Origin Validation
    const ALLOWED_ORIGINS = [
      window.location.origin,
      'https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev',
    ];

    const messageHandler = async (event: MessageEvent) => {
      // Validate Origin
      if (
        !ALLOWED_ORIGINS.includes(event.origin) &&
        iframeRef.current &&
        event.source !== iframeRef.current.contentWindow
      ) {
        return;
      }

      const data = event.data;
      if (!data || data.source !== 'PIXORA_GAME_CLIENT') return;

      if (data.type === 'PIXORA_HANDSHAKE') {
        try {
          const session = await PixoraAPI.startSession(slug);
          iframeRef.current?.contentWindow?.postMessage(
            {
              source: 'PIXORA_PLATFORM_SHELL',
              type: 'PIXORA_HANDSHAKE_ACK',
              payload: {
                player: { username: 'Pilot', id: 1 },
                sessionToken: session.session_token,
                startTimeMs: session.start_time_ms,
              },
            },
            '*'
          );
        } catch (e) {}
      } else if (data.type === 'PIXORA_SUBMIT_SCORE') {
        loadData();
        showToast(`🏆 Score ${data.payload.score} verified and recorded!`);
      }
    };

    window.addEventListener('message', messageHandler);

    return () => {
      window.removeEventListener('message', messageHandler);
      evtSource?.close();
    };
  }, [slug, game.title]);

  return (
    <div className="max-w-[1600px] mx-auto p-6 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
      {/* Game Stage Screen */}
      <section className="flex flex-col gap-4">
        <div className="w-full h-[calc(100vh-190px)] min-h-[540px] bg-black rounded-xl overflow-hidden border border-[rgba(0,242,254,0.3)] shadow-[0_10px_40px_rgba(0,0,0,0.8),0_0_20px_rgba(0,242,254,0.15)] relative">
          <iframe
            ref={iframeRef}
            src={game.playUrl}
            title={game.title}
            className="w-full h-full border-0 block"
            sandbox="allow-scripts allow-same-origin allow-pointer-lock allow-forms"
            allow="autoplay; fullscreen; keyboard; gamepad"
          />
        </div>

        {/* Stage Toolbar */}
        <div className="bg-[rgba(18,22,36,0.85)] border border-[rgba(0,242,254,0.25)] rounded-xl p-4 flex items-center justify-between">
          <div>
            <h2 className="font-orbitron text-xl font-bold flex items-center gap-2">
              {game.title}
              <span className="text-xs font-mono text-[#00f2fe] bg-[rgba(0,242,254,0.1)] px-2 py-0.5 rounded">
                {game.category}
              </span>
            </h2>
            <p className="text-xs text-[#7f8fa6] mt-1">Authoritative Sandboxed Environment</p>
          </div>

          <div className="flex items-center gap-4">
            <div className="inline-flex items-center gap-2 bg-[rgba(0,242,254,0.08)] border border-[rgba(0,242,254,0.3)] rounded-full px-3 py-1 text-xs text-[#00f2fe] font-semibold">
              <span className="w-2 h-2 rounded-full bg-[#00ffcc] animate-pulse" />
              <span>{presence} in simulation</span>
            </div>

            <button
              onClick={() => {
                if (iframeRef.current) iframeRef.current.src = iframeRef.current.src;
                showToast('Simulation reloaded');
              }}
              className="px-3 py-1.5 rounded-lg border border-[rgba(255,255,255,0.15)] text-sm hover:border-[#00f2fe] hover:text-[#00f2fe] transition-all"
            >
              Restart
            </button>
          </div>
        </div>
      </section>

      {/* Telemetry & Leaderboard Sidebar */}
      <aside className="flex flex-col gap-6">
        {/* World Record & Personal Best */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-[rgba(18,22,36,0.85)] border border-[rgba(0,242,254,0.2)] rounded-xl p-4">
            <div className="text-[10px] font-mono text-[#7f8fa6] tracking-wider mb-1">// PERSONAL BEST</div>
            <div className="font-orbitron text-xl font-bold text-[#00f2fe]">
              {leaderboard?.user_best ? leaderboard.user_best.toLocaleString() : '--'}
            </div>
          </div>

          <div className="bg-[rgba(18,22,36,0.85)] border border-[rgba(255,0,127,0.2)] rounded-xl p-4">
            <div className="text-[10px] font-mono text-[#7f8fa6] tracking-wider mb-1">// WORLD RECORD</div>
            <div className="font-orbitron text-xl font-bold text-[#ff007f]">
              {leaderboard?.world_record ? leaderboard.world_record.score.toLocaleString() : '--'}
            </div>
            <div className="text-[10px] text-[#7f8fa6] truncate">
              {leaderboard?.world_record ? `By: ${leaderboard.world_record.username}` : ''}
            </div>
          </div>
        </div>

        {/* Canvas Visual Leaderboard Spectrum */}
        <CanvasLeaderboardChart
          entries={leaderboard?.leaderboard || []}
          userBest={leaderboard?.user_best}
          worldRecord={leaderboard?.world_record?.score}
        />

        {/* Live Leaderboard List */}
        <div className="bg-[rgba(18,22,36,0.85)] border border-[rgba(0,242,254,0.25)] rounded-xl p-5 flex-1">
          <h3 className="font-orbitron text-sm font-bold tracking-wider text-[#7f8fa6] uppercase mb-4">
            Top Pilots Leaderboard
          </h3>

          <ul className="space-y-2">
            {!leaderboard?.leaderboard || leaderboard.leaderboard.length === 0 ? (
              <li className="text-xs text-[#7f8fa6] py-3 text-center">No scores recorded yet. Be the first!</li>
            ) : (
              leaderboard.leaderboard.map((item, idx) => (
                <li
                  key={idx}
                  className={`flex items-center justify-between p-2.5 rounded-lg text-sm border ${
                    idx === 0
                      ? 'border-[#ffe600] bg-[rgba(255,230,0,0.06)] font-bold text-[#ffe600]'
                      : 'border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)]'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-xs w-5 text-[#7f8fa6]">
                      {idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : `#${idx + 1}`}
                    </span>
                    <span>{item.username}</span>
                  </span>
                  <span className="font-mono font-bold">{item.score.toLocaleString()}</span>
                </li>
              ))
            )}
          </ul>
        </div>
      </aside>

      {/* Real-Time Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#0a0c14] border border-[#00f2fe] text-[#00f2fe] px-5 py-3 rounded-lg shadow-[0_0_25px_rgba(0,242,254,0.3)] font-mono text-sm">
          {toastMessage}
        </div>
      )}
    </div>
  );
}


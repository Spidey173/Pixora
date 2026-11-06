'use client';

import React from 'react';

const FEATURED_GAMES = [
  {
    slug: 'neon-cyber-racer',
    title: 'Neon Cyber Racer',
    category: 'Action',
    desc: 'Flagship Phaser 3 arcade racer. Dodge obstacles, drift at relativistic speed, and stream assets at microsecond latency.',
    playUrl: 'https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev/games/neon-cyber-racer/index.html',
    tag: 'FLAGSHIP',
    color: '#00f2fe',
  },
  {
    slug: '2048',
    title: '2048 Cyber Grid',
    category: 'Puzzle',
    desc: 'Slide numerical blocks across the neon matrix. Synthesize the elusive 2048 singularity.',
    playUrl: '/2048',
    tag: 'VERIFIED',
    color: '#7928ca',
  },
  {
    slug: 'flappybird',
    title: 'Flappy Birds',
    category: 'Arcade',
    desc: 'Pilot an autonomous aerial drone through treacherous data conduit pillars without crashing.',
    playUrl: '/FlappyBird',
    tag: 'VERIFIED',
    color: '#ff007f',
  },
  {
    slug: 'speedtype',
    title: 'SpeedType Pro',
    category: 'Skill',
    desc: 'High-velocity typing simulator for elite hackers. Overclock your keystroke speed and accuracy.',
    playUrl: '/speedtype',
    tag: 'VERIFIED',
    color: '#ffe600',
  },
];

export default function HomePage() {
  return (
    <div className="max-w-7xl mx-auto px-6 py-12">
      {/* Hero Header */}
      <section className="text-center py-12 border-b border-[rgba(0,242,254,0.15)] mb-12">
        <div className="inline-flex items-center gap-2 bg-[rgba(0,242,254,0.08)] border border-[rgba(0,242,254,0.3)] rounded-full px-4 py-1 text-xs text-[#00f2fe] font-semibold mb-6">
          <span className="w-2 h-2 rounded-full bg-[#00ffcc] animate-ping" />
          FASTAPI + REDIS STREAMS + CRYPTOGRAPHIC ANTI-CHEAT
        </div>
        <h1 className="font-orbitron text-4xl sm:text-6xl font-black mb-6 tracking-tight">
          HIGH-THROUGHPUT <span className="neon-text-gradient">GAMING ENGINE</span>
        </h1>
        <p className="text-[#7f8fa6] text-lg max-w-2xl mx-auto leading-relaxed">
          Sub-5ms telemetry ingestion, HMAC-SHA256 session signatures, and sub-millisecond Redis Sorted Set leaderboards.
        </p>
      </section>

      {/* 4 Polished Games Showcase */}
      <section id="games">
        <div className="flex items-center justify-between mb-8">
          <h2 className="font-orbitron text-2xl font-bold tracking-wide">
            VERIFIED FLIGHT SIMULATIONS
          </h2>
          <span className="text-xs text-[#7f8fa6] font-mono">// 4 AUTHORITATIVE RUNTIMES</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {FEATURED_GAMES.map((game) => (
            <div
              key={game.slug}
              className="bg-[rgba(18,22,36,0.85)] border border-[rgba(0,242,254,0.2)] rounded-xl p-5 flex flex-col justify-between hover:border-[#00f2fe] hover:shadow-[0_0_20px_rgba(0,242,254,0.2)] transition-all group"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono uppercase text-[#00f2fe] bg-[rgba(0,242,254,0.1)] px-2 py-0.5 rounded">
                    {game.category}
                  </span>
                  <span className="text-[10px] font-mono font-bold text-[#ff007f] border border-[rgba(255,0,127,0.3)] px-1.5 py-0.5 rounded">
                    {game.tag}
                  </span>
                </div>
                <h3 className="font-orbitron text-lg font-bold group-hover:text-[#00f2fe] transition-colors mb-2">
                  {game.title}
                </h3>
                <p className="text-xs text-[#7f8fa6] leading-relaxed mb-6">
                  {game.desc}
                </p>
              </div>

              <a
                href={`/play/${game.slug}`}
                className="w-full text-center py-2.5 rounded-lg bg-[rgba(0,242,254,0.1)] border border-[rgba(0,242,254,0.4)] text-[#00f2fe] font-bold text-sm tracking-wide group-hover:bg-[#00f2fe] group-hover:text-black transition-all shadow-[0_0_10px_rgba(0,242,254,0.1)]"
              >
                LAUNCH SIMULATION →
              </a>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}


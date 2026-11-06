import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Pixora 2.0 | Real-Time High-Throughput Gaming Engine',
  description: 'Cryptographic Anti-Cheat, Sub-Millisecond Redis Leaderboards & Sandboxed Gameplay',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;800;900&family=Rajdhani:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-rajdhani bg-[#0a0c14] text-[#f0f4fc] antialiased">
        <header className="sticky top-0 z-50 h-16 border-b border-[rgba(0,242,254,0.2)] bg-[rgba(10,12,20,0.92)] backdrop-blur-md px-6 flex items-center justify-between">
          <a href="/" className="flex items-center gap-3">
            <span className="font-orbitron text-xl font-black tracking-wider neon-text-gradient">
              PIXORA 2.0
            </span>
            <span className="bg-[rgba(0,242,254,0.15)] text-[#00f2fe] text-xs font-semibold px-2 py-0.5 rounded border border-[rgba(0,242,254,0.3)]">
              TIER S
            </span>
          </a>

          <div className="flex items-center gap-4 text-sm font-semibold">
            <a
              href="/#games"
              className="text-[#7f8fa6] hover:text-[#00f2fe] transition-colors"
            >
              GAMES
            </a>
            <a
              href="/#leaderboard"
              className="text-[#7f8fa6] hover:text-[#ff007f] transition-colors"
            >
              HALL OF FAME
            </a>
          </div>
        </header>

        <main>{children}</main>

        <footer className="mt-20 border-t border-[rgba(0,242,254,0.15)] py-8 text-center text-sm text-[#7f8fa6]">
          <p>© 2026 Pixora 2.0 Engine. Authoritative Cryptographic Anti-Cheat & Redis Streams Ingestion.</p>
        </footer>
      </body>
    </html>
  );
}


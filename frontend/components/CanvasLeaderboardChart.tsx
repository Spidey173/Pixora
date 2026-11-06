'use client';

import React, { useEffect, useRef } from 'react';
import { LeaderboardEntry } from '@/lib/api';

interface CanvasLeaderboardChartProps {
  entries: LeaderboardEntry[];
  userBest?: number | null;
  worldRecord?: number | null;
}

export const CanvasLeaderboardChart: React.FC<CanvasLeaderboardChartProps> = ({
  entries,
  userBest,
  worldRecord,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Retina display scaling
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    if (!entries || entries.length === 0) {
      ctx.fillStyle = '#7f8fa6';
      ctx.font = '12px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('Awaiting telemetry score stream...', width / 2, height / 2);
      return;
    }

    // Grid lines
    ctx.strokeStyle = 'rgba(0, 242, 254, 0.08)';
    ctx.lineWidth = 1;
    for (let y = 20; y < height - 20; y += 25) {
      ctx.beginPath();
      ctx.moveTo(40, y);
      ctx.lineTo(width - 20, y);
      ctx.stroke();
    }

    const maxScore = Math.max(
      ...entries.map((e) => e.score),
      worldRecord || 0,
      userBest || 0,
      10
    );

    const paddingLeft = 45;
    const paddingBottom = 25;
    const chartWidth = width - paddingLeft - 20;
    const chartHeight = height - paddingBottom - 20;

    const barWidth = Math.min(28, (chartWidth / Math.max(entries.length, 5)) * 0.7);
    const spacing = chartWidth / Math.max(entries.length, 1);

    // Draw bars for Top Pilots
    entries.slice(0, 10).forEach((item, index) => {
      const x = paddingLeft + index * spacing + spacing / 2 - barWidth / 2;
      const barHeight = (item.score / maxScore) * chartHeight;
      const y = height - paddingBottom - barHeight;

      // Cyberpunk Gradient
      const grad = ctx.createLinearGradient(0, y, 0, height - paddingBottom);
      if (index === 0) {
        grad.addColorStop(0, '#ffe600');
        grad.addColorStop(1, 'rgba(255, 230, 0, 0.15)');
      } else {
        grad.addColorStop(0, '#00f2fe');
        grad.addColorStop(1, 'rgba(0, 242, 254, 0.15)');
      }

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barHeight, [4, 4, 0, 0]);
      ctx.fill();

      // Top Rank Glow
      if (index === 0) {
        ctx.strokeStyle = '#ffe600';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // X-Axis Rank Label
      ctx.fillStyle = index === 0 ? '#ffe600' : '#7f8fa6';
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`#${index + 1}`, x + barWidth / 2, height - 8);
    });

    // Draw Personal Best Horizontal Threshold Line
    if (userBest && userBest > 0) {
      const pbY = height - paddingBottom - (userBest / maxScore) * chartHeight;
      ctx.strokeStyle = 'rgba(0, 242, 254, 0.7)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(paddingLeft, pbY);
      ctx.lineTo(width - 20, pbY);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = '#00f2fe';
      ctx.font = '9px monospace';
      ctx.textAlign = 'left';
      ctx.fillText('PB', 10, pbY + 3);
    }
  }, [entries, userBest, worldRecord]);

  return (
    <div className="w-full bg-[rgba(10,12,20,0.6)] border border-[rgba(0,242,254,0.15)] rounded-xl p-3">
      <div className="text-[10px] font-mono text-[#7f8fa6] tracking-wider mb-2 flex items-center justify-between">
        <span>// SCORE VELOCITY SPECTRUM</span>
        <span className="text-[#00f2fe]">TOP 10 PILOTS</span>
      </div>
      <canvas ref={canvasRef} className="w-full h-36 block" />
    </div>
  );
};


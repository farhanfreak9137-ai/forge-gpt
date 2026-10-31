import React, { useEffect, useMemo, useState } from 'react';
import { create } from 'zustand';

interface CelebrateState {
  count: number;
  celebrate: () => void;
}

export const useCelebration = create<CelebrateState>((set) => ({
  count: 0,
  celebrate: () => set((s) => ({ count: s.count + 1 })),
}));

const COLORS = ['#8b5cf6', '#10b981', '#38bdf8', '#f43f5e', '#fbbf24', '#f472b6'];

/** Mounted once in the app shell. Call `useCelebration().celebrate()` to throw confetti. */
export const ConfettiHost: React.FC = () => {
  const count = useCelebration((s) => s.count);
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (!count) return;
    setActive(count);
    const t = setTimeout(() => setActive(0), 2600);
    return () => clearTimeout(t);
  }, [count]);

  const pieces = useMemo(
    () =>
      active
        ? Array.from({ length: 48 }, (_, i) => ({
            id: i,
            color: COLORS[i % COLORS.length],
            dx: Math.round((Math.random() - 0.5) * 900),
            dy: Math.round(260 + Math.random() * 560),
            rot: Math.round((Math.random() - 0.5) * 1080),
            dur: (1.6 + Math.random() * 0.9).toFixed(2),
            delay: (Math.random() * 0.15).toFixed(2),
          }))
        : [],
    [active],
  );

  if (!active) return null;
  return (
    <div aria-hidden className="pointer-events-none fixed inset-x-0 top-[28%] z-[80] h-0">
      {pieces.map((p) => (
        <span
          key={p.id}
          className="confetti-piece"
          style={
            {
              background: p.color,
              '--dx': `${p.dx}px`,
              '--dy': `${p.dy}px`,
              '--rot': `${p.rot}deg`,
              '--dur': `${p.dur}s`,
              animationDelay: `${p.delay}s`,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
};

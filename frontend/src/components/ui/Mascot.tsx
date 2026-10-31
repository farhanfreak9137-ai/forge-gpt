import React from 'react';
import { cn } from '../../lib/cn';

export type Mood = 'idle' | 'thinking' | 'happy' | 'alert' | 'sleeping';

const GLOW = 'rgb(var(--glow))';
const SCREEN = '#0b1020';

/** "Forge", the friendly little robot. Its face shows what the agent is up to. */
export const Mascot: React.FC<{ mood?: Mood; size?: number; className?: string; label?: string }> = ({
  mood = 'idle',
  size = 40,
  className,
  label,
}) => {
  const motion = mood === 'happy' ? 'mascot-bounce' : mood === 'alert' ? 'mascot-shake' : mood === 'sleeping' ? '' : 'mascot-float';
  const stroke = { stroke: GLOW, strokeWidth: 2.6, strokeLinecap: 'round' as const, fill: 'none' };

  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={cn('mascot-svg shrink-0', className)}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <g className={motion}>
        {/* antenna */}
        <line x1="32" y1="7" x2="32" y2="15" stroke="rgb(var(--brand-400))" strokeWidth="2.5" strokeLinecap="round" />
        <circle
          cx="32"
          cy="6"
          r="3.2"
          fill={mood === 'alert' ? '#fbbf24' : GLOW}
          className={mood === 'thinking' || mood === 'alert' ? 'mascot-pulse' : undefined}
        />
        {/* ears */}
        <rect x="2.5" y="28" width="6" height="13" rx="3" fill="rgb(var(--brand-600))" />
        <rect x="55.5" y="28" width="6" height="13" rx="3" fill="rgb(var(--brand-600))" />
        {/* head */}
        <rect x="8" y="14" width="48" height="42" rx="15" fill="rgb(var(--brand-500))" />
        <path d="M14 22 Q20 16.5 30 16.5" stroke="#fff" strokeOpacity="0.35" strokeWidth="2.4" strokeLinecap="round" fill="none" />
        {/* face screen */}
        <rect x="14" y="21" width="36" height="28" rx="11" fill={SCREEN} />

        {/* eyes */}
        {(mood === 'idle' || mood === 'thinking' || mood === 'alert') && (
          <g className={mood === 'idle' ? 'mascot-blink' : mood === 'thinking' ? 'mascot-look' : undefined}>
            <ellipse cx="25" cy={mood === 'thinking' ? 31 : 32} rx={mood === 'alert' ? 4 : 3.2} ry={mood === 'alert' ? 5 : 4.2} fill={GLOW} />
            <ellipse cx="39" cy={mood === 'thinking' ? 31 : 32} rx={mood === 'alert' ? 4 : 3.2} ry={mood === 'alert' ? 5 : 4.2} fill={GLOW} />
          </g>
        )}
        {mood === 'happy' && (
          <>
            <path d="M21 34 Q25 27.5 29 34" {...stroke} />
            <path d="M35 34 Q39 27.5 43 34" {...stroke} />
            <circle cx="19" cy="41" r="2.6" fill="#fb7185" fillOpacity="0.55" />
            <circle cx="45" cy="41" r="2.6" fill="#fb7185" fillOpacity="0.55" />
          </>
        )}
        {mood === 'sleeping' && (
          <>
            <path d="M21.5 33 H28.5" {...stroke} />
            <path d="M35.5 33 H42.5" {...stroke} />
          </>
        )}

        {/* mouth */}
        {mood === 'idle' && <path d="M27.5 41 Q32 45 36.5 41" {...stroke} strokeWidth={2.2} />}
        {mood === 'thinking' && <path d="M28.5 42 H35.5" {...stroke} strokeWidth={2.2} />}
        {mood === 'happy' && <path d="M26 40 Q32 48.5 38 40 Z" fill={GLOW} stroke={GLOW} strokeWidth="1.6" strokeLinejoin="round" />}
        {mood === 'alert' && <ellipse cx="32" cy="42.5" rx="2.6" ry="3" fill={GLOW} />}
        {mood === 'sleeping' && <path d="M29 42 Q32 44 35 42" {...stroke} strokeWidth={2} />}

        {mood === 'sleeping' && (
          <>
            <text x="48" y="14" fontSize="10" fontWeight="700" fill={GLOW} className="mascot-zzz">
              z
            </text>
            <text x="54" y="8" fontSize="7" fontWeight="700" fill={GLOW} className="mascot-zzz" style={{ animationDelay: '1.1s' }}>
              z
            </text>
          </>
        )}
      </g>
    </svg>
  );
};

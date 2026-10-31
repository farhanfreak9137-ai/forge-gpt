import React, { useEffect, useId, useRef, useState } from 'react';
import { cn } from '../../lib/cn';

export interface MenuItem {
  label: string;
  icon?: React.ReactNode;
  onSelect: () => void;
  danger?: boolean;
  disabled?: boolean;
  hint?: string;
}

/** Small accessible dropdown menu: Esc / outside click closes, arrow keys move. */
export const Menu: React.FC<{
  trigger: (props: { onClick: () => void; 'aria-haspopup': 'menu'; 'aria-expanded': boolean; 'aria-controls': string }) => React.ReactNode;
  items: MenuItem[];
  align?: 'left' | 'right';
}> = ({ trigger, items, align = 'right' }) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        rootRef.current?.querySelector<HTMLElement>('button')?.focus();
      }
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    listRef.current?.querySelector<HTMLElement>('button:not([disabled])')?.focus();
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const onListKey = (e: React.KeyboardEvent) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const buttons = Array.from(listRef.current?.querySelectorAll<HTMLElement>('button:not([disabled])') ?? []);
    const idx = buttons.indexOf(document.activeElement as HTMLElement);
    const next = e.key === 'ArrowDown' ? (idx + 1) % buttons.length : (idx - 1 + buttons.length) % buttons.length;
    buttons[next]?.focus();
  };

  return (
    <div ref={rootRef} className="relative">
      {trigger({ onClick: () => setOpen((o) => !o), 'aria-haspopup': 'menu', 'aria-expanded': open, 'aria-controls': id })}
      {open && (
        <div
          ref={listRef}
          id={id}
          role="menu"
          onKeyDown={onListKey}
          className={cn(
            'absolute z-40 mt-2 min-w-[14rem] rounded-xl border border-slate-700 bg-slate-900 p-1 shadow-2xl animate-fade-in',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {items.map((item) => (
            <button
              key={item.label}
              role="menuitem"
              type="button"
              disabled={item.disabled}
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={cn(
                'flex w-full items-start gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors disabled:opacity-50',
                item.danger ? 'text-rose-300 hover:bg-rose-500/10' : 'text-slate-200 hover:bg-slate-800',
              )}
            >
              {item.icon && <span className="mt-0.5 shrink-0">{item.icon}</span>}
              <span className="min-w-0">
                <span className="block">{item.label}</span>
                {item.hint && <span className="block text-xs text-slate-500">{item.hint}</span>}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

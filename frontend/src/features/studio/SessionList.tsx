import React, { useMemo, useState } from 'react';
import { EllipsisVertical, MessageSquare, Plus, RefreshCw, Search, Trash2, Eraser } from 'lucide-react';
import { cn } from '../../lib/cn';
import { dateGroup } from '../../lib/format';
import { StudioChatSession } from '../../types';
import { Button, IconButton, Menu } from '../../components/ui';

const GROUP_ORDER = ['Today', 'Yesterday', 'Previous 7 days', 'Previous 30 days', 'Older'];

export const SessionList: React.FC<{
  sessions: StudioChatSession[];
  activeId: string | null;
  syncing: boolean;
  loading: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string, title: string) => void;
  onSync: () => void;
  onPrune: () => void;
}> = ({ sessions, activeId, syncing, loading, onSelect, onNew, onDelete, onSync, onPrune }) => {
  const [query, setQuery] = useState('');

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = sessions
      .filter((s) => !q || (s.title || '').toLowerCase().includes(q))
      .sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''));
    const map = new Map<string, StudioChatSession[]>();
    for (const s of filtered) {
      const g = dateGroup(s.updated_at);
      map.set(g, [...(map.get(g) ?? []), s]);
    }
    return GROUP_ORDER.filter((g) => map.has(g)).map((g) => ({ name: g, items: map.get(g)! }));
  }, [sessions, query]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-slate-800 p-3">
        <Button variant="primary" size="sm" className="flex-1" icon={<Plus className="h-4 w-4" />} onClick={onNew}>
          New chat
        </Button>
        <Menu
          trigger={(p) => (
            <IconButton label="Chat list options" {...p}>
              <EllipsisVertical className="h-4 w-4" />
            </IconButton>
          )}
          items={[
            {
              label: syncing ? 'Syncing…' : 'Sync with ChatGPT',
              icon: <RefreshCw className="h-4 w-4" />,
              hint: 'Import conversations from your Edge session',
              onSelect: onSync,
              disabled: syncing,
            },
            {
              label: 'Clean up old chats…',
              icon: <Eraser className="h-4 w-4" />,
              hint: 'Delete empty chats and keep the 10 newest',
              onSelect: onPrune,
              danger: true,
            },
          ]}
        />
      </div>

      <div className="px-3 pt-3">
        <label className="relative block">
          <span className="sr-only">Search chats</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats"
            className="h-9 w-full rounded-lg border border-slate-800 bg-slate-900 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 focus-visible:border-brand-500"
          />
        </label>
      </div>

      <nav aria-label="Chats" className="mt-2 flex-1 space-y-4 overflow-y-auto px-2 pb-3">
        {loading && sessions.length === 0 ? (
          <div className="space-y-2 px-1 pt-2" aria-hidden>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded-lg bg-slate-800/60" />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-slate-400">{query ? 'No chats match your search.' : 'No chats yet. Start one above.'}</p>
        ) : (
          groups.map((g) => (
            <div key={g.name}>
              <h3 className="px-2 pb-1 pt-2 text-xs font-medium text-slate-500">{g.name}</h3>
              <ul className="space-y-0.5">
                {g.items.map((s) => {
                  const active = s.id === activeId;
                  const title = s.title || 'Untitled chat';
                  return (
                    <li key={s.id} className="group relative">
                      <button
                        type="button"
                        onClick={() => onSelect(s.id)}
                        aria-current={active ? 'true' : undefined}
                        className={cn(
                          'flex w-full items-center gap-2 rounded-lg py-2 pl-2.5 pr-9 text-left text-sm transition-colors',
                          active ? 'bg-slate-800 font-medium text-white' : 'text-slate-300 hover:bg-slate-900 hover:text-slate-50',
                        )}
                      >
                        <MessageSquare className={cn('h-4 w-4 shrink-0', active ? 'text-brand-400' : 'text-slate-500')} aria-hidden />
                        <span className="truncate">{title}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(s.id, title)}
                        aria-label={`Delete chat: ${title}`}
                        title="Delete chat"
                        className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-slate-400 opacity-0 transition hover:bg-slate-700 hover:text-rose-300 focus-visible:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))
        )}
      </nav>
    </div>
  );
};

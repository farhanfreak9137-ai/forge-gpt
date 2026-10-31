import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bot,
  CornerDownLeft,
  FolderGit2,
  LayoutDashboard,
  ListChecks,
  MessageSquarePlus,
  Moon,
  Monitor,
  OctagonAlert,
  ScrollText,
  Search,
  Settings,
  Sun,
} from 'lucide-react';
import { api } from '../../services/api';
import { cn } from '../../lib/cn';
import { ACCENTS, useTheme } from '../../lib/theme';
import { usePalette } from '../../lib/palette';
import { relativeTime } from '../../lib/format';
import { Task } from '../../types';
import { useAppStore } from '../../stores/useAppStore';
import { useEmergencyStop } from './Navbar';

interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: React.ReactNode;
  keywords?: string;
  run: () => void;
}

const ICON = 'h-4 w-4';

export const CommandPalette: React.FC = () => {
  const { open, setOpen } = usePalette();
  const navigate = useNavigate();
  const { setMode, setAccent } = useTheme();
  const stop = useEmergencyStop();
  const setActiveTask = useAppStore((s) => s.setActiveTask);
  const [query, setQuery] = useState('');
  const [index, setIndex] = useState(0);
  const [recent, setRecent] = useState<Task[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Ctrl/Cmd + K toggles the palette from anywhere
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen(!usePalette.getState().open);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setOpen]);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setIndex(0);
    api
      .getTasks()
      .then((t) => setRecent([...t].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5)))
      .catch(() => setRecent([]));
    setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const go = (to: string) => () => navigate(to);
    return [
      { id: 'go-studio', group: 'Go to', label: 'Agent Studio', hint: 'Chat with the agent', icon: <Bot className={ICON} />, run: go('/'), keywords: 'chat home' },
      { id: 'go-overview', group: 'Go to', label: 'Overview', icon: <LayoutDashboard className={ICON} />, run: go('/overview'), keywords: 'dashboard' },
      { id: 'go-projects', group: 'Go to', label: 'Projects', icon: <FolderGit2 className={ICON} />, run: go('/projects') },
      { id: 'go-tasks', group: 'Go to', label: 'Tasks', icon: <ListChecks className={ICON} />, run: go('/workspace'), keywords: 'workspace' },
      { id: 'go-activity', group: 'Go to', label: 'Activity', icon: <ScrollText className={ICON} />, run: go('/activity'), keywords: 'log events audit' },
      { id: 'go-settings', group: 'Go to', label: 'Settings', icon: <Settings className={ICON} />, run: go('/settings') },
      { id: 'new-chat', group: 'Actions', label: 'Start a new chat', icon: <MessageSquarePlus className={ICON} />, run: go('/?new=1'), keywords: 'conversation' },
      {
        id: 'estop',
        group: 'Actions',
        label: stop.active ? 'Resume the agent' : 'Emergency stop',
        hint: stop.active ? 'Allow commands and file changes again' : 'Block all commands and file changes now',
        icon: <OctagonAlert className={ICON} />,
        run: () => void stop.toggle(),
        keywords: 'halt pause kill',
      },
      { id: 'theme-light', group: 'Appearance', label: 'Light theme', icon: <Sun className={ICON} />, run: () => setMode('light'), keywords: 'bright day' },
      { id: 'theme-dark', group: 'Appearance', label: 'Dark theme', icon: <Moon className={ICON} />, run: () => setMode('dark'), keywords: 'night' },
      { id: 'theme-system', group: 'Appearance', label: 'Match my device', icon: <Monitor className={ICON} />, run: () => setMode('system'), keywords: 'system auto theme' },
      ...ACCENTS.map<Command>((a) => ({
        id: `accent-${a.value}`,
        group: 'Appearance',
        label: `${a.label} accent colour`,
        icon: <span className="h-3.5 w-3.5 rounded-full" style={{ background: a.swatch }} />,
        run: () => setAccent(a.value),
        keywords: 'color theme',
      })),
      ...recent.map<Command>((t) => ({
        id: `task-${t.id}`,
        group: 'Recent tasks',
        label: t.title,
        hint: relativeTime(t.created_at),
        icon: <ListChecks className={ICON} />,
        run: async () => {
          try {
            setActiveTask(await api.getTask(t.id));
            navigate('/workspace');
          } catch {
            /* the task may have been deleted */
          }
        },
      })),
    ];
  }, [navigate, recent, setAccent, setMode, setActiveTask, stop.active, stop.toggle]);

  const results = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (words.length === 0) return commands;
    return commands.filter((c) => {
      const hay = `${c.label} ${c.group} ${c.keywords ?? ''}`.toLowerCase();
      return words.every((w) => hay.includes(w));
    });
  }, [commands, query]);

  useEffect(() => setIndex(0), [query]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${index}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [index]);

  if (!open) return null;

  const close = () => setOpen(false);
  const runAt = (i: number) => {
    const cmd = results[i];
    if (!cmd) return;
    close();
    cmd.run();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      runAt(index);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'Tab') {
      e.preventDefault();
    }
  };

  let lastGroup = '';
  return (
    <div
      className="fixed inset-0 z-[65] flex items-start justify-center bg-black/60 p-4 pt-[12vh] backdrop-blur-sm animate-fade-in"
      onMouseDown={(e) => e.target === e.currentTarget && close()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onKeyDown={onKeyDown}
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl animate-pop-in"
      >
        <div className="flex items-center gap-3 border-b border-slate-800 px-4">
          <Search className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
          <input
            ref={inputRef}
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-list"
            aria-activedescendant={results[index] ? `palette-${results[index].id}` : undefined}
            aria-label="Type a command or search"
            placeholder="Where do you want to go, or what do you want to do?"
            className="h-14 w-full bg-transparent text-base text-slate-100 placeholder:text-slate-500 focus-visible:outline-none"
          />
          <kbd className="hidden shrink-0 rounded-md border border-slate-700 px-1.5 py-0.5 text-xs text-slate-400 sm:block">Esc</kbd>
        </div>
        <ul id="palette-list" role="listbox" ref={listRef} className="max-h-[50vh] overflow-y-auto p-2">
          {results.length === 0 && <li className="px-3 py-10 text-center text-sm text-slate-400">Nothing matches “{query}”. Try a page name like “settings”.</li>}
          {results.map((c, i) => {
            const header = c.group !== lastGroup ? c.group : null;
            lastGroup = c.group;
            return (
              <React.Fragment key={c.id}>
                {header && <li role="presentation" className="px-3 pb-1 pt-3 text-xs font-medium text-slate-500 first:pt-1">{header}</li>}
                <li
                  id={`palette-${c.id}`}
                  role="option"
                  aria-selected={i === index}
                  data-idx={i}
                  onMouseMove={() => setIndex(i)}
                  onClick={() => runAt(i)}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors',
                    i === index ? 'bg-brand-500/15 text-slate-50' : 'text-slate-300',
                  )}
                >
                  <span className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-lg', i === index ? 'bg-brand-500/20 text-brand-300' : 'bg-slate-800 text-slate-400')}>{c.icon}</span>
                  <span className="min-w-0 flex-1 truncate">{c.label}</span>
                  {c.hint && <span className="hidden truncate text-xs text-slate-500 sm:block">{c.hint}</span>}
                  {i === index && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />}
                </li>
              </React.Fragment>
            );
          })}
        </ul>
      </div>
    </div>
  );
};

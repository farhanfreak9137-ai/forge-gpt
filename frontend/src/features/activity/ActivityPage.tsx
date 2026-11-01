import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, ScrollText, Search } from 'lucide-react';
import { api } from '../../services/api';
import { wsClient } from '../../services/websocket';
import { dayLabel, formatTime, parseDate } from '../../lib/format';
import { useDebounced, useDocumentTitle } from '../../lib/hooks';
import { ActivityEvent } from '../../types';
import { useAppStore } from '../../stores/useAppStore';
import { Page } from '../../components/layout/AppShell';
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, Segmented, Skeleton, useToast } from '../../components/ui';

type Severity = 'ALL' | ActivityEvent['severity'];
const PAGE_SIZE = 100;

const TONE = { SUCCESS: 'success', ERROR: 'danger', WARNING: 'warning', INFO: 'neutral' } as const;

export const ActivityPage: React.FC = () => {
  useDocumentTitle('Activity');
  const navigate = useNavigate();
  const toast = useToast();
  const setActiveTask = useAppStore((s) => s.setActiveTask);

  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [severity, setSeverity] = useState<Severity>('ALL');
  const [query, setQuery] = useState('');
  const debounced = useDebounced(query, 200);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getEvents();
      setEvents([...data].sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || '')));
    } catch (e: any) {
      setError(e.message || 'Could not load activity.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // New events stream in live
  useEffect(
    () =>
      wsClient.subscribe((ev) => {
        setEvents((prev) => (prev.some((e) => e.id === ev.id) ? prev : [ev, ...prev]));
      }),
    [],
  );

  const counts = useMemo(() => {
    const c: Record<string, number> = { ALL: events.length, INFO: 0, WARNING: 0, ERROR: 0, SUCCESS: 0 };
    events.forEach((e) => (c[e.severity] = (c[e.severity] ?? 0) + 1));
    return c;
  }, [events]);

  const filtered = useMemo(() => {
    const q = debounced.trim().toLowerCase();
    return events.filter((ev) => {
      if (severity !== 'ALL' && ev.severity !== severity) return false;
      if (!q) return true;
      return ev.event_type.toLowerCase().includes(q) || ev.message.toLowerCase().includes(q) || (ev.task_id ?? '').toLowerCase().includes(q);
    });
  }, [events, severity, debounced]);

  const shown = filtered.slice(0, limit);
  const groups = useMemo(() => {
    const out: Array<{ day: string; items: ActivityEvent[] }> = [];
    for (const ev of shown) {
      const day = dayLabel(ev.timestamp);
      const last = out[out.length - 1];
      if (last && last.day === day) last.items.push(ev);
      else out.push({ day, items: [ev] });
    }
    return out;
  }, [shown]);

  const openTask = async (taskId: string) => {
    try {
      setActiveTask(await api.getTask(taskId));
      navigate('/workspace');
    } catch {
      toast.error('That task no longer exists.');
    }
  };

  return (
    <Page>
      <PageHeader
        title="Activity"
        description="A record of everything the agent did, newest first. It updates live."
        actions={
          <Button icon={<RefreshCw className={loading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />} onClick={load} disabled={loading}>
            Refresh
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <label className="relative min-w-[14rem] flex-1">
          <span className="sr-only">Search activity</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden />
          <input
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setLimit(PAGE_SIZE);
            }}
            placeholder="Search by type, message or task ID"
            className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 focus-visible:border-brand-500"
          />
        </label>
        <Segmented<Severity>
          ariaLabel="Filter by severity"
          value={severity}
          onChange={(v) => {
            setSeverity(v);
            setLimit(PAGE_SIZE);
          }}
          options={[
            { value: 'ALL', label: 'All', count: counts.ALL },
            { value: 'ERROR', label: 'Errors', count: counts.ERROR },
            { value: 'WARNING', label: 'Warnings', count: counts.WARNING },
            { value: 'SUCCESS', label: 'Success', count: counts.SUCCESS },
            { value: 'INFO', label: 'Info', count: counts.INFO },
          ]}
        />
      </div>

      {error ? (
        <ErrorState title="Couldn't load activity" message={error} onRetry={load} />
      ) : loading && events.length === 0 ? (
        <Card className="space-y-3 p-4">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </Card>
      ) : filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon={<ScrollText className="h-6 w-6" />}
            title={events.length === 0 ? 'Nothing has happened yet' : 'No events match'}
            description={events.length === 0 ? 'Events appear here as the agent works on tasks.' : 'Try a different search or severity.'}
            action={
              events.length > 0 ? (
                <Button
                  onClick={() => {
                    setQuery('');
                    setSeverity('ALL');
                  }}
                >
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <div className="space-y-5">
          {groups.map((g) => (
            <section key={g.day} aria-label={g.day}>
              <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{g.day}</h2>
              <Card className="overflow-hidden">
                <ul className="divide-y divide-slate-800">
                  {g.items.map((ev, i) => (
                    <li key={ev.id || `${g.day}-${i}`} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 px-4 py-3">
                      <div className="flex min-w-0 flex-1 items-start gap-3">
                        <Badge tone={TONE[ev.severity] ?? 'neutral'} className="mt-0.5 shrink-0">
                          {ev.severity.toLowerCase()}
                        </Badge>
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-slate-100">{ev.event_type.replace(/_/g, ' ').toLowerCase()}</p>
                          <p className="mt-0.5 break-words text-sm text-slate-300">{ev.message}</p>
                          {ev.task_id && (
                            <button
                              type="button"
                              onClick={() => openTask(ev.task_id!)}
                              className="mt-1 text-xs text-brand-300 underline-offset-2 hover:text-brand-200 hover:underline"
                            >
                              Open task {ev.task_id.slice(0, 8)}
                            </button>
                          )}
                        </div>
                      </div>
                      <time dateTime={parseDate(ev.timestamp)?.toISOString()} className="shrink-0 text-xs text-slate-400">
                        {formatTime(ev.timestamp)}
                      </time>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ))}
          {filtered.length > shown.length && (
            <div className="flex justify-center">
              <Button onClick={() => setLimit((l) => l + PAGE_SIZE)}>
                Show more ({filtered.length - shown.length} older)
              </Button>
            </div>
          )}
        </div>
      )}
    </Page>
  );
};

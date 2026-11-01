import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bot, Check, CheckCircle2, CircleAlert, Cpu, EllipsisVertical, Eraser, FolderGit2, Hourglass, Loader, Palette, Plus, Sparkles, X } from 'lucide-react';
import { api } from '../../services/api';
import { cn } from '../../lib/cn';
import { connectorMeta } from '../../lib/connectors';
import { relativeTime, parseDate } from '../../lib/format';
import { useDocumentTitle, usePersistentState } from '../../lib/hooks';
import { useTheme } from '../../lib/theme';
import { usePalette } from '../../lib/palette';
import { isStale, stateInfo } from '../../lib/taskState';
import { ConnectorInfo, Project, Task } from '../../types';
import { useAppStore } from '../../stores/useAppStore';
import { Page } from '../../components/layout/AppShell';
import { Badge, Button, Card, EmptyState, ErrorState, IconButton, Mascot, Menu, Segmented, Skeleton, StateBadge, useCelebration, useConfirm, useToast } from '../../components/ui';
import type { Mood } from '../../components/ui';

type Filter = 'all' | 'running' | 'attention' | 'completed' | 'failed';

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return 'Burning the midnight oil';
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

const RUNNING = (t: Task) => !!stateInfo(t.state).running;
const ATTENTION = (t: Task) => !!stateInfo(t.state).needsYou;

const FILTERS: Record<Filter, (t: Task) => boolean> = {
  all: () => true,
  running: RUNNING,
  attention: ATTENTION,
  completed: (t) => t.state === 'COMPLETED',
  failed: (t) => t.state === 'FAILED',
};

export const OverviewPage: React.FC = () => {
  useDocumentTitle('Overview');
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const setActiveTask = useAppStore((s) => s.setActiveTask);

  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('all');
  const [chatted, setChatted] = useState(false);
  const [dismissed, setDismissed] = usePersistentState('forgeagent.onboarding.dismissed', false);
  const { mode, accent } = useTheme();
  const setPaletteOpen = usePalette((s) => s.setOpen);
  const celebrate = useCelebration((s) => s.celebrate);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [p, t, sessions] = await Promise.all([
        api.getProjects(),
        api.getTasks(),
        api.getStudioSessions(false).catch(() => []),
      ]);
      setChatted(sessions.some((s) => s.message_count > 0));
      setProjects(p);
      setTasks(t);
    } catch (e: any) {
      setError(e.message || 'Could not load the dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const counts = useMemo(
    () => ({
      running: tasks.filter(RUNNING).length,
      attention: tasks.filter(ATTENTION).length,
      completed: tasks.filter(FILTERS.completed).length,
      failed: tasks.filter(FILTERS.failed).length,
    }),
    [tasks],
  );

  const visible = tasks.filter(FILTERS[filter]);

  const staleTasks = useMemo(
    () =>
      tasks.filter((t) => {
        const updated = parseDate(t.updated_at);
        return isStale(t.state) && updated && Date.now() - updated.getTime() > 24 * 3600 * 1000;
      }),
    [tasks],
  );

  const handleCleanup = async () => {
    if (staleTasks.length === 0) {
      toast.info('No stale tasks. Nothing has been waiting for more than 24 hours.');
      return;
    }
    const ok = await confirm({
      title: `Cancel ${staleTasks.length} stale task${staleTasks.length === 1 ? '' : 's'}?`,
      message: 'These tasks have been paused, waiting for approval, or waiting for recovery for over 24 hours. They will be cancelled, not deleted.',
      confirmLabel: 'Cancel stale tasks',
      tone: 'danger',
    });
    if (!ok) return;
    try {
      const res = await api.cleanupTasks({ older_than_hours: 24 });
      setTasks(await api.getTasks());
      toast.success(`Cancelled ${res.cancelled} stale task${res.cancelled === 1 ? '' : 's'}.`);
    } catch (e: any) {
      toast.error(`Clean-up failed: ${e.message}`);
    }
  };

  const openTask = async (task: Task) => {
    try {
      setActiveTask(await api.getTask(task.id));
      navigate('/workspace');
    } catch (e: any) {
      toast.error(`Could not open that task: ${e.message}`);
    }
  };

  const mood: Mood = counts.attention > 0 ? 'alert' : counts.running > 0 ? 'thinking' : counts.completed > 0 ? 'happy' : 'idle';
  const statusLine =
    loading || error
      ? 'Getting things ready\u2026'
      : counts.attention > 0
        ? `${counts.attention} ${counts.attention === 1 ? 'thing needs' : 'things need'} your OK before I can continue.`
        : counts.running > 0
          ? `I'm busy with ${counts.running} ${counts.running === 1 ? 'task' : 'tasks'} right now.`
          : tasks.length === 0
            ? 'All quiet. What shall we build today?'
            : 'All caught up. Ready when you are!';

  const steps = [
    { label: 'Say hello in Studio', hint: 'Chat with the agent once', done: chatted, icon: <Bot className="h-3.5 w-3.5" />, go: () => navigate('/') },
    { label: 'Add a project', hint: 'Create one, or import a folder', done: projects.length > 0, icon: <FolderGit2 className="h-3.5 w-3.5" />, go: () => navigate('/projects') },
    { label: 'Finish your first task', hint: 'Give the agent a job and approve it', done: counts.completed > 0, icon: <CheckCircle2 className="h-3.5 w-3.5" />, go: () => navigate('/projects') },
    { label: 'Make it yours', hint: 'Pick a theme or accent colour', done: accent !== 'violet' || mode !== 'system', icon: <Palette className="h-3.5 w-3.5" />, go: () => setPaletteOpen(true) },
  ];
  const doneCount = steps.filter((x) => x.done).length;
  const allDone = doneCount === steps.length;

  // A little celebration the first time everything is ticked off
  useEffect(() => {
    if (loading || dismissed || !allDone) return;
    try {
      if (localStorage.getItem('forgeagent.onboarding.celebrated')) return;
      localStorage.setItem('forgeagent.onboarding.celebrated', '1');
    } catch {
      /* ignore */
    }
    celebrate();
  }, [loading, dismissed, allDone, celebrate]);

  const kpis: Array<{ label: string; value: number; icon: React.ReactNode; tone: string; onClick: () => void; hint: string }> = [
    { label: 'Projects', value: projects.length, icon: <FolderGit2 className="h-4 w-4" />, tone: 'text-slate-100', onClick: () => navigate('/projects'), hint: 'Open projects' },
    { label: 'Running', value: counts.running, icon: <Loader className="h-4 w-4 text-sky-400" />, tone: 'text-sky-300', onClick: () => setFilter('running'), hint: 'Show running tasks' },
    { label: 'Needs you', value: counts.attention, icon: <Hourglass className="h-4 w-4 text-amber-400" />, tone: 'text-amber-300', onClick: () => setFilter('attention'), hint: 'Show tasks waiting for you' },
    { label: 'Completed', value: counts.completed, icon: <CheckCircle2 className="h-4 w-4 text-emerald-400" />, tone: 'text-emerald-300', onClick: () => setFilter('completed'), hint: 'Show completed tasks' },
    { label: 'Failed', value: counts.failed, icon: <CircleAlert className="h-4 w-4 text-rose-400" />, tone: 'text-rose-300', onClick: () => setFilter('failed'), hint: 'Show failed tasks' },
  ];

  return (
    <Page>
      <section
        aria-label="Welcome"
        className="relative overflow-hidden rounded-3xl border border-brand-500/25 bg-gradient-to-br from-brand-500/15 via-slate-900/40 to-transparent p-5 sm:p-7"
      >
        <div className="flex flex-wrap items-center gap-5 sm:gap-7">
          <Mascot mood={mood} size={88} label="Forge the robot" className="drop-shadow-lg" />
          <div className="min-w-0 flex-1 space-y-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-50 sm:text-3xl">
              {greeting()}! {mood === 'alert' ? '\u{1F440}' : '\u{1F44B}'}
            </h1>
            <p className="text-base text-slate-300">{statusLine}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="lg" icon={<Bot className="h-4 w-4" />} onClick={() => navigate('/')}>
              Open Studio
            </Button>
            <Button size="lg" variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => navigate('/projects')}>
              New task
            </Button>
          </div>
        </div>
      </section>

      {!loading && !error && !dismissed && (
        <Card className="p-5" aria-label="Getting started">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-slate-50">
                {allDone ? "You're all set! \u{1F389}" : 'Getting started'}
              </h2>
              <p className="mt-0.5 text-sm text-slate-400">
                {allDone ? 'You have done the whole tour. Forge is proud of you.' : `${doneCount} of ${steps.length} done. A few quick things to try:`}
              </p>
            </div>
            <IconButton label="Hide getting started" size="sm" onClick={() => setDismissed(true)}>
              <X className="h-4 w-4" />
            </IconButton>
          </div>
          <div
            className="mt-3 h-2 overflow-hidden rounded-full bg-slate-800"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={steps.length}
            aria-valuenow={doneCount}
            aria-label="Getting started progress"
          >
            <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-300 transition-all duration-500" style={{ width: `${(doneCount / steps.length) * 100}%` }} />
          </div>
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {steps.map((st) => (
              <li key={st.label}>
                <button
                  type="button"
                  onClick={st.go}
                  className="flex w-full items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/40 px-3 py-3 text-left transition-all hover:-translate-y-0.5 hover:border-brand-500/40"
                >
                  <span
                    className={cn(
                      'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs',
                      st.done ? 'border-emerald-500 bg-emerald-500 text-white' : 'border-slate-600 text-slate-400',
                    )}
                  >
                    {st.done ? <Check className="h-4 w-4" aria-hidden /> : st.icon}
                  </span>
                  <span className="min-w-0">
                    <span className={cn('block text-sm font-medium', st.done ? 'text-slate-400 line-through' : 'text-slate-100')}>{st.label}</span>
                    <span className="block text-xs text-slate-400">{st.hint}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {error ? (
        <ErrorState title="Couldn't load the dashboard" message={error} onRetry={load} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
            {kpis.map((k) => (
              <button
                key={k.label}
                type="button"
                onClick={k.onClick}
                title={k.hint}
                className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 text-left transition-colors hover:border-slate-600 hover:bg-slate-900"
              >
                <span className="flex items-center justify-between text-sm text-slate-300">
                  {k.label}
                  {k.icon}
                </span>
                {loading ? <Skeleton className="mt-3 h-8 w-12" /> : <span className={cn('mt-2 block text-3xl font-semibold tabular-nums', k.tone)}>{k.value}</span>}
              </button>
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-3">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 p-4">
                <h2 className="text-base font-semibold text-slate-100">Tasks</h2>
                <div className="flex items-center gap-2">
                  <Segmented
                    ariaLabel="Filter tasks"
                    value={filter}
                    onChange={setFilter}
                    options={[
                      { value: 'all', label: 'All', count: tasks.length },
                      { value: 'running', label: 'Running', count: counts.running },
                      { value: 'attention', label: 'Needs you', count: counts.attention },
                      { value: 'completed', label: 'Done', count: counts.completed },
                      { value: 'failed', label: 'Failed', count: counts.failed },
                    ]}
                  />
                  <Menu
                    trigger={(p) => (
                      <IconButton label="Task options" {...p}>
                        <EllipsisVertical className="h-4 w-4" />
                      </IconButton>
                    )}
                    items={[
                      {
                        label: 'Cancel stale tasks…',
                        icon: <Eraser className="h-4 w-4" />,
                        hint: `${staleTasks.length} waiting for over 24 hours`,
                        onSelect: handleCleanup,
                        danger: true,
                      },
                    ]}
                  />
                </div>
              </div>

              {loading ? (
                <div className="space-y-3 p-4">
                  {[0, 1, 2].map((i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : visible.length === 0 ? (
                <EmptyState
                  icon={<Bot className="h-6 w-6" />}
                  title={tasks.length === 0 ? 'No tasks yet' : 'No tasks match this filter'}
                  description={tasks.length === 0 ? 'Chat with the agent in Studio, or create a project and give it a task.' : 'Try a different filter.'}
                  action={
                    tasks.length === 0 ? (
                      <Button variant="primary" onClick={() => navigate('/projects')}>
                        Create a task
                      </Button>
                    ) : (
                      <Button onClick={() => setFilter('all')}>Show all tasks</Button>
                    )
                  }
                />
              ) : (
                <ul className="divide-y divide-slate-800">
                  {visible.slice(0, 12).map((task) => (
                    <li key={task.id}>
                      <button
                        type="button"
                        onClick={() => openTask(task)}
                        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-800/50"
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium text-slate-100">{task.title}</span>
                          <span className="mt-0.5 block text-xs text-slate-400">{relativeTime(task.created_at)}</span>
                        </span>
                        <StateBadge state={task.state} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {!loading && visible.length > 12 && <p className="border-t border-slate-800 px-4 py-2 text-xs text-slate-400">Showing the 12 most recent of {visible.length}.</p>}
            </Card>

          </div>
        </>
      )}
    </Page>
  );
};

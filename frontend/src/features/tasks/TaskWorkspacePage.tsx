import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bot,
  Check,
  CheckCircle2,
  Circle,
  CircleAlert,
  CircleDot,
  EllipsisVertical,
  FileCode,
  ListChecks,
  Loader2,
  Pause,
  Play,
  ShieldAlert,
  Trash2,
  XCircle,
} from 'lucide-react';
import { api } from '../../services/api';
import { wsClient } from '../../services/websocket';
import { cn } from '../../lib/cn';
import { detectLanguage, formatDateTime, relativeTime, splitPath } from '../../lib/format';
import { useDocumentTitle, useMediaQuery } from '../../lib/hooks';
import { PHASES, isTerminal, stateInfo, taskPhase } from '../../lib/taskState';
import { ActivityEvent, Approval, PlanStep, ProposedChange, Task, TaskDetail } from '../../types';
import { useAppStore } from '../../stores/useAppStore';
import { MonacoEditorView } from '../../components/editor/MonacoEditorView';
import { Page } from '../../components/layout/AppShell';
import {
  Badge,
  Button,
  Card,
  CodeBlock,
  CopyButton,
  EmptyState,
  Field,
  IconButton,
  Input,
  Mascot,
  Menu,
  Skeleton,
  StateBadge,
  useCelebration,
  useConfirm,
  useToast,
} from '../../components/ui';
import type { Mood } from '../../components/ui';

type Tab = 'overview' | 'changes' | 'tests' | 'events';

/* ---------- progress stepper ---------- */

const Stepper: React.FC<{ task: TaskDetail }> = ({ task }) => {
  const phase = taskPhase(task);
  const info = stateInfo(task.state);
  const failed = task.state === 'FAILED' || task.state === 'CANCELLED';
  return (
    <ol aria-label="Task progress" className="flex items-center gap-1 overflow-x-auto pb-1 text-xs sm:gap-2">
      {PHASES.map((name, i) => {
        const done = i < phase || task.state === 'COMPLETED';
        const current = i === phase && task.state !== 'COMPLETED';
        return (
          <React.Fragment key={name}>
            <li
              aria-current={current ? 'step' : undefined}
              className={cn(
                'flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 font-medium',
                done && 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
                current && !failed && !info.needsYou && 'border-sky-500/40 bg-sky-500/10 text-sky-200',
                current && info.needsYou && 'border-amber-500/40 bg-amber-500/10 text-amber-200',
                current && failed && 'border-rose-500/40 bg-rose-500/10 text-rose-300',
                !done && !current && 'border-slate-800 text-slate-500',
              )}
            >
              {done ? (
                <Check className="h-3.5 w-3.5" aria-hidden />
              ) : current && info.running ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : current ? (
                <CircleDot className="h-3.5 w-3.5" aria-hidden />
              ) : (
                <Circle className="h-3.5 w-3.5" aria-hidden />
              )}
              {name}
            </li>
            {i < PHASES.length - 1 && <span className={cn('h-px w-3 shrink-0 sm:w-6', done ? 'bg-emerald-500/40' : 'bg-slate-800')} aria-hidden />}
          </React.Fragment>
        );
      })}
    </ol>
  );
};

const STEP_ICON: Record<PlanStep['status'], React.ReactNode> = {
  PENDING: <Circle className="h-4 w-4 text-slate-500" aria-label="Pending" />,
  RUNNING: <Loader2 className="h-4 w-4 animate-spin text-sky-400" aria-label="Running" />,
  COMPLETED: <CheckCircle2 className="h-4 w-4 text-emerald-400" aria-label="Done" />,
  FAILED: <XCircle className="h-4 w-4 text-rose-400" aria-label="Failed" />,
  SKIPPED: <Circle className="h-4 w-4 text-slate-600" aria-label="Skipped" />,
};

const OP_TONE: Record<string, 'success' | 'info' | 'danger' | 'neutral'> = {
  create: 'success',
  replace: 'info',
  patch: 'info',
  delete: 'danger',
  move: 'neutral',
};

function moodFor(state: string): Mood {
  const info = stateInfo(state);
  if (state === 'COMPLETED') return 'happy';
  if (state === 'FAILED' || info.needsYou) return 'alert';
  if (state === 'CANCELLED') return 'sleeping';
  return info.running ? 'thinking' : 'idle';
}

/* ---------- page ---------- */

export const TaskWorkspacePage: React.FC = () => {
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const { activeTask, activeTaskId, setActiveTask } = useAppStore();
  const isDesktop = useMediaQuery('(min-width: 1024px)');

  const [tab, setTab] = useState<Tab>('overview');
  const [selectedChangeId, setSelectedChangeId] = useState<string | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [reason, setReason] = useState('');
  const [deciding, setDeciding] = useState<string | null>(null);
  const [taskEvents, setTaskEvents] = useState<ActivityEvent[]>([]);
  const [recent, setRecent] = useState<Task[] | null>(null);
  const [restoring, setRestoring] = useState(!activeTask && !!activeTaskId);

  const pendingCount = approvals.length;
  useDocumentTitle(activeTask ? (pendingCount ? `(${pendingCount}) ${activeTask.title}` : activeTask.title) : 'Tasks');

  const taskId = activeTask?.id;

  const refreshTask = useCallback(async () => {
    if (!taskId) return;
    try {
      setActiveTask(await api.getTask(taskId));
    } catch (e) {
      console.error(e);
    }
  }, [taskId, setActiveTask]);

  const loadApprovals = useCallback(async () => {
    if (!taskId) return;
    try {
      const data = await api.getApprovals();
      setApprovals(data.filter((a) => a.task_id === taskId && a.status === 'PENDING'));
    } catch (e) {
      console.error(e);
    }
  }, [taskId]);

  // After a reload the in-memory task is gone: restore the one that was open (drop it if deleted)
  useEffect(() => {
    if (activeTask || !activeTaskId) {
      setRestoring(false);
      return;
    }
    api
      .getTask(activeTaskId)
      .then(setActiveTask)
      .catch(() => setActiveTask(null))
      .finally(() => setRestoring(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Recent tasks for the empty state
  useEffect(() => {
    if (activeTask || restoring) return;
    api.getTasks().then(setRecent).catch(() => setRecent([]));
  }, [activeTask, restoring]);

  // Live updates: websocket, plus a slow poll while the task is still moving
  useEffect(() => {
    if (!taskId) return;
    refreshTask();
    loadApprovals();
    setTaskEvents([]);
    api.getEvents({ taskId }).then((evs) => setTaskEvents([...evs].sort((a, b) => b.timestamp.localeCompare(a.timestamp)))).catch(() => undefined);

    const unsubscribe = wsClient.subscribe((event: ActivityEvent) => {
      if (event.task_id !== taskId) return;
      setTaskEvents((prev) => (prev.some((e) => e.id === event.id) ? prev : [event, ...prev].slice(0, 300)));
      refreshTask();
      loadApprovals();
    });
    const interval = setInterval(() => {
      const state = useAppStore.getState().activeTask?.state;
      if (state && isTerminal(state)) return;
      refreshTask();
      loadApprovals();
    }, 5000);

    return () => {
      unsubscribe();
      clearInterval(interval);
    };
  }, [taskId, refreshTask, loadApprovals]);

  // Celebrate when the task we are watching finishes
  const celebrate = useCelebration((s) => s.celebrate);
  const seen = useRef<{ id?: string; state?: string }>({});
  useEffect(() => {
    const prev = seen.current;
    if (activeTask && prev.id === activeTask.id && prev.state && prev.state !== 'COMPLETED' && activeTask.state === 'COMPLETED') {
      celebrate();
      toast.success('Task complete! Nicely done \u{1F389}');
    }
    seen.current = { id: activeTask?.id, state: activeTask?.state };
  }, [activeTask?.id, activeTask?.state, celebrate, toast]);

  const changes = activeTask?.proposed_changes ?? [];
  const selectedChange = useMemo<ProposedChange | null>(
    () => changes.find((c) => c.id === selectedChangeId) ?? changes[0] ?? null,
    [changes, selectedChangeId],
  );

  /* ---------- empty / loading states ---------- */

  if (restoring) {
    return (
      <Page>
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </Page>
    );
  }

  if (!activeTask) {
    return (
      <Page width="md">
        <EmptyState
          icon={<ListChecks className="h-6 w-6" />}
          title="No task selected"
          description="Tasks are jobs you give the agent on a project. Pick a recent one, or start a new task from Projects."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Button variant="primary" onClick={() => navigate('/projects')}>
                Start a task
              </Button>
              <Button icon={<Bot className="h-4 w-4" />} onClick={() => navigate('/')}>
                Chat in Studio
              </Button>
            </div>
          }
        />
        {recent && recent.length > 0 && (
          <Card>
            <h2 className="border-b border-slate-800 px-4 py-3 text-sm font-semibold text-slate-200">Recent tasks</h2>
            <ul className="divide-y divide-slate-800">
              {recent.slice(0, 8).map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        setActiveTask(await api.getTask(t.id));
                      } catch (e: any) {
                        toast.error(`Could not open that task: ${e.message}`);
                      }
                    }}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-800/50"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-slate-100">{t.title}</span>
                      <span className="text-xs text-slate-400">{relativeTime(t.created_at)}</span>
                    </span>
                    <StateBadge state={t.state} />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </Page>
    );
  }

  /* ---------- actions ---------- */

  const info = stateInfo(activeTask.state);
  const finished = isTerminal(activeTask.state);

  const run = async (fn: () => Promise<unknown>, okMsg?: string) => {
    try {
      await fn();
      if (okMsg) toast.success(okMsg);
      await refreshTask();
    } catch (e: any) {
      toast.error(e.message || 'That did not work.');
    }
  };

  const handleCancel = async () => {
    const ok = await confirm({
      title: 'Cancel this task?',
      message: 'The agent stops working on it. Changes already applied stay in your project.',
      confirmLabel: 'Cancel task',
      cancelLabel: 'Keep running',
      tone: 'danger',
    });
    if (ok) run(() => api.cancelTask(activeTask.id), 'Task cancelled.');
  };

  const handleDelete = async () => {
    const ok = await confirm({
      title: 'Delete this task?',
      message: 'The task and its history are removed. Files already written to your project are not touched.',
      confirmLabel: 'Delete task',
      tone: 'danger',
    });
    if (!ok) return;
    try {
      await api.deleteTask(activeTask.id);
      setActiveTask(null);
      toast.success('Task deleted.');
    } catch (e: any) {
      toast.error(`Could not delete the task: ${e.message}`);
    }
  };

  const decide = async (approvalId: string, approved: boolean) => {
    setDeciding(approvalId);
    try {
      await api.decideApproval(approvalId, approved, reason);
      setReason('');
      await Promise.all([loadApprovals(), refreshTask()]);
      toast.success(approved ? 'Approved. The task continues.' : 'Rejected. The task was stopped.');
    } catch (e: any) {
      toast.error(e.message || 'Could not record your decision.');
    } finally {
      setDeciding(null);
    }
  };

  /* ---------- panels ---------- */

  const planPanel = (
    <div className="space-y-6">
      <section aria-label="Plan">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
          <ListChecks className="h-4 w-4 text-brand-400" aria-hidden /> Plan
        </h2>
        {activeTask.steps?.length ? (
          <ol className="space-y-2">
            {activeTask.steps.map((s) => (
              <li key={s.id} className="flex gap-2.5 rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                {/* The plan rows are not always updated by the backend: a completed task has no pending steps */}
                <span className="mt-0.5 shrink-0">
                  {STEP_ICON[activeTask.state === 'COMPLETED' && s.status === 'PENDING' ? 'COMPLETED' : s.status] ?? STEP_ICON.PENDING}
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-slate-100">{s.title}</span>
                  {s.description && <span className="mt-0.5 block text-xs leading-relaxed text-slate-400">{s.description}</span>}
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-slate-400">{finished ? 'No plan was recorded.' : 'The agent is still working out a plan.'}</p>
        )}
      </section>

      <section aria-label="Changed files">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
          <FileCode className="h-4 w-4 text-sky-400" aria-hidden /> Changed files ({changes.length})
        </h2>
        {changes.length === 0 ? (
          <p className="text-sm text-slate-400">No files changed yet.</p>
        ) : (
          <ul className="space-y-1">
            {changes.map((ch) => (
              <li key={ch.id}>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedChangeId(ch.id);
                    setTab('changes');
                  }}
                  className="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left font-mono text-[13px] text-slate-300 transition-colors hover:bg-slate-800"
                >
                  <span className="truncate" title={ch.file_path}>
                    {ch.file_path}
                  </span>
                  <Badge tone={OP_TONE[ch.operation] ?? 'neutral'}>{ch.operation}</Badge>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs text-slate-300">
        <span>Fix attempts</span>
        <span className="font-mono font-semibold text-slate-100">
          {activeTask.repair_attempts} / {activeTask.max_repair_attempts}
        </span>
      </div>
    </div>
  );

  const tabs: Array<{ id: Tab; label: string; count?: number }> = [
    { id: 'overview', label: 'Overview' },
    { id: 'changes', label: 'Changes', count: changes.length },
    { id: 'tests', label: 'Tests', count: activeTask.test_results?.length ?? 0 },
    { id: 'events', label: 'Events', count: taskEvents.length },
  ];

  return (
    <div className="flex h-full flex-col overflow-hidden bg-slate-950">
      {/* Header */}
      <div className="shrink-0 space-y-3 border-b border-slate-800 bg-slate-900/60 px-4 py-4 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-1.5">
            <div className="flex flex-wrap items-center gap-3">
              <Mascot mood={moodFor(activeTask.state)} size={38} />
              <h1 className="text-lg font-semibold text-slate-50">{activeTask.title}</h1>
              <StateBadge state={activeTask.state} />
            </div>
            {info.hint && <p className="text-sm text-slate-300">{info.hint}</p>}
            {activeTask.description && <p className="line-clamp-2 max-w-3xl text-sm text-slate-400">{activeTask.description}</p>}
          </div>
          <div className="flex items-center gap-2">
            {activeTask.state === 'PAUSED' ? (
              <Button variant="primary" icon={<Play className="h-4 w-4" />} onClick={() => run(() => api.resumeTask(activeTask.id), 'Task resumed.')}>
                Resume
              </Button>
            ) : (
              !finished && (
                <Button variant="warning" icon={<Pause className="h-4 w-4" />} onClick={() => run(() => api.pauseTask(activeTask.id), 'Task paused.')}>
                  Pause
                </Button>
              )
            )}
            {!finished && (
              <Button variant="secondary" icon={<XCircle className="h-4 w-4" />} onClick={handleCancel}>
                Cancel task
              </Button>
            )}
            {finished && (
              <Menu
                trigger={(p) => (
                  <IconButton label="Task options" {...p}>
                    <EllipsisVertical className="h-4 w-4" />
                  </IconButton>
                )}
                items={[{ label: 'Delete task…', icon: <Trash2 className="h-4 w-4" />, danger: true, onSelect: handleDelete }]}
              />
            )}
          </div>
        </div>
        <Stepper task={activeTask} />
      </div>

      {/* Approvals */}
      {approvals.length > 0 && (
        <section aria-label="Approvals" className="shrink-0 space-y-3 border-b border-amber-500/40 bg-amber-950/60 px-4 py-4 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-amber-100">
              <ShieldAlert className="h-4 w-4 text-amber-300" aria-hidden />
              {approvals.length === 1 ? 'The agent needs your approval' : `${approvals.length} approvals needed`}
            </h2>
            <div className="w-full sm:w-72">
              <Field label="Note (optional)" htmlFor="approval-note" className="space-y-1">
                <Input id="approval-note" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why you approved or rejected" className="h-9" />
              </Field>
            </div>
          </div>
          {approvals.map((a) => (
            <div key={a.id} className="space-y-3 rounded-xl border border-amber-500/30 bg-slate-950/60 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="warning">{a.action_type.replace(/_/g, ' ').toLowerCase()}</Badge>
                <span className="text-xs text-slate-400">requested {relativeTime(a.requested_at)}</span>
              </div>
              <p className="text-sm text-slate-100">{a.description}</p>
              {a.details && Object.keys(a.details).length > 0 && (
                <details className="text-sm">
                  <summary className="cursor-pointer text-xs font-medium text-slate-300 hover:text-slate-50">Show details</summary>
                  <CodeBlock code={JSON.stringify(a.details, null, 2)} language="json" className="mt-2" maxHeight="14rem" />
                </details>
              )}
              <div className="flex flex-wrap gap-2">
                <Button variant="primary" loading={deciding === a.id} disabled={!!deciding} onClick={() => decide(a.id, true)}>
                  Approve
                </Button>
                <Button variant="secondary" disabled={!!deciding} onClick={() => decide(a.id, false)}>
                  Reject &amp; stop
                </Button>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Body */}
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {isDesktop && <aside aria-label="Plan and files" className="w-80 shrink-0 overflow-y-auto border-r border-slate-800 bg-slate-900/40 p-4">{planPanel}</aside>}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div role="tablist" aria-label="Task details" className="flex shrink-0 gap-1 overflow-x-auto border-b border-slate-800 bg-slate-900/40 px-3">
            {tabs.map((t) => (
              <button
                key={t.id}
                role="tab"
                type="button"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  'flex shrink-0 items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium transition-colors',
                  tab === t.id ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-400 hover:text-slate-100',
                )}
              >
                {t.label}
                {!!t.count && <span className="rounded-full bg-slate-800 px-1.5 text-xs text-slate-300">{t.count}</span>}
              </button>
            ))}
          </div>

          <div role="tabpanel" className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
            {tab === 'overview' && (
              <div className="max-w-3xl space-y-5">
                <Card className="space-y-3 p-5">
                  <h2 className="text-sm font-semibold text-slate-100">Result</h2>
                  <p className="text-sm leading-relaxed text-slate-300">
                    {activeTask.result_summary || (finished ? 'No summary was recorded.' : 'The task is still running. Results appear here when it finishes.')}
                  </p>
                  {activeTask.error_message && (
                    <div role="alert" className="rounded-lg border border-rose-500/40 bg-rose-950/30 p-3 font-mono text-xs leading-relaxed text-rose-200">
                      {activeTask.error_message}
                    </div>
                  )}
                </Card>

                <Card className="space-y-3 p-5">
                  <h2 className="text-sm font-semibold text-slate-100">Checkpoints ({activeTask.checkpoints?.length ?? 0})</h2>
                  {activeTask.checkpoints?.length ? (
                    <ul className="space-y-2">
                      {activeTask.checkpoints.map((cp) => (
                        <li key={cp.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-sm">
                          <span className="min-w-0">
                            <span className="font-mono font-semibold text-brand-300">{cp.git_ref.slice(0, 7)}</span>
                            <span className="ml-2 text-slate-300">{cp.description}</span>
                          </span>
                          <span className="text-xs text-slate-400">{formatDateTime(cp.created_at)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-slate-400">Git checkpoints are saved here as the agent works, so you can roll back.</p>
                  )}
                </Card>

                {!isDesktop && <Card className="p-5">{planPanel}</Card>}
              </div>
            )}

            {tab === 'changes' && (
              <div className="flex h-full min-h-[24rem] flex-col gap-3">
                {changes.length === 0 ? (
                  <EmptyState icon={<FileCode className="h-6 w-6" />} title="No file changes yet" description="Files the agent proposes or writes will be listed here with their diff." />
                ) : (
                  <>
                    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Changed files">
                      {changes.map((c) => (
                        <button
                          key={c.id}
                          type="button"
                          aria-pressed={selectedChange?.id === c.id}
                          onClick={() => setSelectedChangeId(c.id)}
                          className={cn(
                            'max-w-full truncate rounded-lg border px-3 py-1.5 font-mono text-xs transition-colors',
                            selectedChange?.id === c.id ? 'border-brand-500/50 bg-brand-500/10 text-brand-200' : 'border-slate-800 text-slate-300 hover:border-slate-600',
                          )}
                          title={c.file_path}
                        >
                          {splitPath(c.file_path).name}
                        </button>
                      ))}
                    </div>
                    {selectedChange && (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm">
                          <span className="min-w-0 truncate font-mono text-slate-100" title={selectedChange.file_path}>
                            {selectedChange.file_path}
                          </span>
                          <span className="flex items-center gap-2">
                            <Badge tone={OP_TONE[selectedChange.operation] ?? 'neutral'}>{selectedChange.operation}</Badge>
                            <Badge tone={selectedChange.status === 'APPLIED' ? 'success' : selectedChange.status === 'FAILED' ? 'danger' : 'neutral'}>
                              {selectedChange.status.toLowerCase()}
                            </Badge>
                            <CopyButton text={selectedChange.patch_diff || selectedChange.proposed_content || ''} />
                          </span>
                        </div>
                        {selectedChange.explanation && <p className="text-sm text-slate-300">{selectedChange.explanation}</p>}
                        <div className="min-h-[22rem] flex-1">
                          <MonacoEditorView
                            value={selectedChange.patch_diff || selectedChange.proposed_content || ''}
                            language={selectedChange.patch_diff ? 'diff' : detectLanguage(selectedChange.file_path)}
                            readOnly
                          />
                        </div>
                      </>
                    )}
                  </>
                )}
              </div>
            )}

            {tab === 'tests' && (
              <div className="max-w-4xl space-y-3">
                {activeTask.test_results?.length ? (
                  activeTask.test_results.map((tr) => (
                    <div
                      key={tr.id}
                      className={cn('space-y-3 rounded-xl border p-4', tr.passed ? 'border-emerald-500/30 bg-emerald-950/20' : 'border-rose-500/30 bg-rose-950/20')}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="break-all font-mono text-sm font-medium text-slate-100">{tr.test_command}</span>
                        <Badge tone={tr.passed ? 'success' : 'danger'}>
                          {tr.passed ? <CheckCircle2 className="h-3.5 w-3.5" aria-hidden /> : <CircleAlert className="h-3.5 w-3.5" aria-hidden />}
                          {tr.passed ? 'Passed' : 'Failed'}
                          {tr.total_tests > 0 && ` · ${tr.total_tests - tr.failed_tests}/${tr.total_tests}`}
                        </Badge>
                      </div>
                      {tr.error_details && <CodeBlock code={tr.error_details} language="output" tone="error" maxHeight="16rem" />}
                    </div>
                  ))
                ) : (
                  <EmptyState icon={<CheckCircle2 className="h-6 w-6" />} title="No test results yet" description="When the agent runs your checks, the results show up here." />
                )}
              </div>
            )}

            {tab === 'events' && (
              <div className="max-w-4xl">
                {taskEvents.length === 0 ? (
                  <EmptyState icon={<Loader2 className="h-6 w-6" />} title="No events yet" description="This list updates live as the agent works." />
                ) : (
                  <ul className="space-y-2" aria-live="polite">
                    {taskEvents.map((ev, i) => (
                      <li key={ev.id || i} className="flex items-start justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2.5">
                        <div className="min-w-0 space-y-0.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge tone={ev.severity === 'ERROR' ? 'danger' : ev.severity === 'WARNING' ? 'warning' : ev.severity === 'SUCCESS' ? 'success' : 'neutral'}>
                              {ev.severity.toLowerCase()}
                            </Badge>
                            <span className="text-xs font-medium text-slate-400">{ev.event_type.replace(/_/g, ' ').toLowerCase()}</span>
                          </div>
                          <p className="break-words text-sm text-slate-100">{ev.message}</p>
                        </div>
                        <span className="shrink-0 text-xs text-slate-400">{formatDateTime(ev.timestamp)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import {
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileCode,
  Eye,
  ShieldAlert,
  Terminal,
  TriangleAlert,
  XCircle,
  Zap,
} from 'lucide-react';
import { cn } from '../../lib/cn';
import { formatTime } from '../../lib/format';
import { StudioCommandAction, StudioMessage, StudioPendingAction } from '../../types';
import { Badge, Button, CopyButton, Markdown, Mascot } from '../../components/ui';

/* ---------- a command the agent already ran ---------- */

const CommandRow: React.FC<{ cmd: StudioCommandAction }> = ({ cmd }) => {
  const [open, setOpen] = useState(false);
  const blocked = cmd.status === 'BLOCKED';
  const passed = !blocked && (cmd.passed ?? cmd.exit_code === 0);
  const hasOutput = !!(cmd.stdout || cmd.stderr);
  const output = [cmd.stdout, cmd.stderr].filter(Boolean).join('\n');

  return (
    <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-950">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left transition-colors hover:bg-slate-900"
      >
        <span className="flex min-w-0 items-center gap-2">
          {passed ? (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" aria-hidden />
          ) : (
            <XCircle className="h-4 w-4 shrink-0 text-rose-400" aria-hidden />
          )}
          <span className="truncate font-mono text-[13px] text-slate-200">{cmd.command}</span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <Badge tone={blocked ? 'warning' : passed ? 'success' : 'danger'}>
            {blocked ? 'blocked' : passed ? 'passed' : `exit ${cmd.exit_code}`}
          </Badge>
          {open ? (
            <ChevronDown className="h-4 w-4 text-slate-400" aria-hidden />
          ) : (
            <ChevronRight className="h-4 w-4 text-slate-400" aria-hidden />
          )}
        </span>
      </button>
      {open && (
        <div className="border-t border-slate-800 bg-slate-950 p-3">
          {hasOutput ? (
            <>
              <div className="mb-1 flex justify-end">
                <CopyButton text={output} label="Copy output" />
              </div>
              {cmd.stdout && (
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-200">{cmd.stdout}</pre>
              )}
              {cmd.stderr && (
                <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-rose-300">{cmd.stderr}</pre>
              )}
            </>
          ) : (
            <p className="text-xs italic text-slate-400">No output.</p>
          )}
        </div>
      )}
    </div>
  );
};

/* ---------- an action that is waiting for approval ---------- */

const STATUS_LABEL: Record<string, { label: string; tone: 'success' | 'danger' | 'neutral' | 'warning' }> = {
  EXECUTED: { label: 'Ran', tone: 'success' },
  APPLIED: { label: 'Written', tone: 'success' },
  REJECTED: { label: 'Rejected', tone: 'neutral' },
  FAILED: { label: 'Failed', tone: 'danger' },
  BLOCKED: { label: 'Blocked', tone: 'warning' },
};

const ActionCard: React.FC<{
  action: StudioPendingAction;
  busy: boolean;
  onDecide: (approve: boolean) => void;
}> = ({ action, busy, onDecide }) => {
  const pending = action.status === 'PENDING_APPROVAL';
  const isCommand = action.kind === 'command';
  const done = STATUS_LABEL[action.status];

  return (
    <div
      data-pending-action={pending ? 'true' : undefined}
      className={cn(
        'rounded-xl border p-3',
        pending ? 'border-amber-500/40 bg-amber-500/5' : 'border-slate-800 bg-slate-950',
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-medium text-slate-100">
          {isCommand ? <Terminal className="h-4 w-4 text-slate-300" aria-hidden /> : <FileCode className="h-4 w-4 text-sky-300" aria-hidden />}
          {isCommand ? 'Run this command?' : 'Write this file?'}
        </span>
        {pending ? (
          <Badge tone="warning" dot pulse>
            Needs approval
          </Badge>
        ) : (
          <Badge tone={done?.tone ?? 'neutral'}>{done?.label ?? action.status}</Badge>
        )}
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 font-mono text-[13px] text-slate-100">
        {isCommand ? (
          <>
            <span className="select-none text-emerald-400">$ </span>
            {action.command}
          </>
        ) : (
          action.file_path
        )}
      </div>
      {action.reason && (
        <p className="mt-2 flex items-start gap-1.5 text-xs text-slate-300">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" aria-hidden />
          <span>{action.reason.replace(/Auto-?Pilot/gi, 'Auto-run')}</span>
        </p>
      )}
      {action.result && 'error' in action.result && (
        <p className="mt-2 text-xs text-rose-300" role="alert">
          {action.result.error}
        </p>
      )}
      {pending && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="primary" disabled={busy} onClick={() => onDecide(true)}>
            {isCommand ? 'Approve & run' : 'Approve & write'}
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => onDecide(false)}>
            Reject
          </Button>
        </div>
      )}
    </div>
  );
};

/* ---------- a whole chat message ---------- */

export const MessageView: React.FC<{
  msg: StudioMessage;
  assistantName: string;
  busyAction: string | null;
  onOpenFile: (path: string) => void;
  onDecide: (messageId: string, actionId: string, approve: boolean) => void;
}> = ({ msg, assistantName, busyAction, onOpenFile, onDecide }) => {
  const isUser = msg.sender === 'user';
  const body = msg.clean_message || msg.text;
  const pendingActions = (msg.pending_actions ?? []).filter((a) => a.status === 'PENDING_APPROVAL');

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[88%]">
          <div className="mb-1 text-right text-xs text-slate-400">You · {formatTime(msg.timestamp)}</div>
          <div className="whitespace-pre-wrap break-words rounded-2xl rounded-tr-md bg-brand-700 px-4 py-2.5 text-sm leading-relaxed text-white">
            {msg.text}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <Mascot mood="idle" size={36} className="mt-3.5" />
      <div className="min-w-0 flex-1">
        <div className="mb-1 text-xs text-slate-400">
          ForgeAgent <span className="text-slate-500">({assistantName})</span> · {formatTime(msg.timestamp)}
        </div>
        <div className="space-y-3 rounded-2xl rounded-tl-md border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-100">
          <Markdown text={body} />

          {msg.executed_file_changes && msg.executed_file_changes.length > 0 && (
            <section className="space-y-2 border-t border-slate-800 pt-3" aria-label="Files written">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold text-emerald-300">
                <CheckCircle2 className="h-4 w-4" aria-hidden /> Files written
              </h4>
              {msg.executed_file_changes.map((fc, i) => (
                <div key={i} className="flex items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2">
                  <span className="flex min-w-0 items-center gap-2">
                    <FileCode className="h-4 w-4 shrink-0 text-sky-300" aria-hidden />
                    <span className="truncate font-mono text-[13px] text-slate-200">{fc.path}</span>
                    <span className="shrink-0 text-xs text-slate-400">{fc.lines} {fc.lines === 1 ? 'line' : 'lines'}</span>
                  </span>
                  <Button size="sm" variant="ghost" icon={<Eye className="h-3.5 w-3.5" />} onClick={() => onOpenFile(fc.path)}>
                    Open
                  </Button>
                </div>
              ))}
            </section>
          )}

          {msg.executed_commands && msg.executed_commands.length > 0 && (
            <section className="space-y-2 border-t border-slate-800 pt-3" aria-label="Commands run">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                <Terminal className="h-4 w-4 text-slate-300" aria-hidden /> Commands run
              </h4>
              {msg.executed_commands.map((cmd, i) => (
                <CommandRow key={i} cmd={cmd} />
              ))}
            </section>
          )}

          {msg.pending_actions && msg.pending_actions.length > 0 && (
            <section className="space-y-2 border-t border-slate-800 pt-3" aria-label="Waiting for your approval">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="flex items-center gap-1.5 text-xs font-semibold text-amber-300">
                  <ShieldAlert className="h-4 w-4" aria-hidden />
                  {pendingActions.length > 0 ? 'Waiting for your approval' : 'Approval decisions'}
                </h4>
                {pendingActions.length > 1 && (
                  <Button
                    size="sm"
                    variant="warning"
                    disabled={!!busyAction}
                    onClick={async () => {
                      for (const a of pendingActions) await onDecide(msg.id, a.id, true);
                    }}
                  >
                    Approve all ({pendingActions.length})
                  </Button>
                )}
              </div>
              {msg.pending_actions.map((a) => (
                <ActionCard key={a.id} action={a} busy={busyAction === a.id} onDecide={(approve) => onDecide(msg.id, a.id, approve)} />
              ))}
            </section>
          )}

          {msg.action_errors && msg.action_errors.length > 0 && (
            <section className="space-y-1 border-t border-slate-800 pt-3" role="alert">
              {msg.action_errors.map((err, i) => (
                <p key={i} className="flex items-start gap-1.5 text-xs text-amber-200">
                  <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" aria-hidden />
                  <span>{err}</span>
                </p>
              ))}
            </section>
          )}

          {!!msg.repair_iterations && msg.repair_iterations > 0 && (
            <p className="flex items-center gap-1.5 text-xs text-amber-300">
              <Zap className="h-3.5 w-3.5" aria-hidden />
              Auto-run fixed a failure after {msg.repair_iterations} {msg.repair_iterations === 1 ? 'attempt' : 'attempts'}.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

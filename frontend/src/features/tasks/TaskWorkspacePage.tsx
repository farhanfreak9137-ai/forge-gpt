import React, { useEffect, useState } from 'react';
import { Play, Pause, XCircle, RotateCcw, CheckCircle, AlertTriangle, FileCode, CheckSquare, Activity, ShieldAlert, Cpu } from 'lucide-react';
import { api } from '../../services/api';
import { wsClient } from '../../services/websocket';
import { useAppStore } from '../../stores/useAppStore';
import { TaskDetail, ActivityEvent, ProposedChange, Approval } from '../../types';
import { MonacoEditorView } from '../../components/editor/MonacoEditorView';
import { MonacoDiffView } from '../../components/editor/MonacoDiffView';

export const TaskWorkspacePage: React.FC = () => {
  const { activeTask, setActiveTask, addEvent, events } = useAppStore();
  const [selectedChange, setSelectedChange] = useState<ProposedChange | null>(null);
  const [activeTab, setActiveTab] = useState<'plan' | 'diff' | 'tests' | 'events'>('plan');
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([]);
  const [approvalReason, setApprovalReason] = useState('');
  const [loading, setLoading] = useState(false);

  // Poll / refresh active task details
  const refreshTask = async () => {
    if (!activeTask?.id) return;
    try {
      const updated = await api.getTask(activeTask.id);
      setActiveTask(updated);
      if (updated.proposed_changes?.length > 0 && !selectedChange) {
        setSelectedChange(updated.proposed_changes[0]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const loadApprovals = async () => {
    try {
      const data = await api.getApprovals();
      setPendingApprovals(data.filter((a) => a.task_id === activeTask?.id && a.status === 'PENDING'));
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    refreshTask();
    loadApprovals();

    // Subscribe to live WebSocket events
    const unsubscribe = wsClient.subscribe((event: ActivityEvent) => {
      addEvent(event);
      if (event.task_id === activeTask?.id) {
        refreshTask();
        loadApprovals();
      }
    });

    const interval = setInterval(() => {
      refreshTask();
      loadApprovals();
    }, 3000);

    return () => {
      unsubscribe();
      clearInterval(interval);
    };
  }, [activeTask?.id]);

  if (!activeTask) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center text-slate-500">
        <Activity className="w-12 h-12 text-slate-600 mb-4" />
        <h2 className="text-lg font-semibold text-slate-300">No Task Active</h2>
        <p className="text-sm text-slate-500 max-w-sm mt-1">
          Select or launch a development task from the Projects page to monitor execution.
        </p>
      </div>
    );
  }

  const handlePause = async () => {
    await api.pauseTask(activeTask.id);
    refreshTask();
  };

  const handleResume = async () => {
    await api.resumeTask(activeTask.id);
    refreshTask();
  };

  const handleCancel = async () => {
    if (confirm('Are you sure you want to cancel this task?')) {
      await api.cancelTask(activeTask.id);
      refreshTask();
    }
  };

  const handleDecideApproval = async (approvalId: string, approved: boolean) => {
    try {
      await api.decideApproval(approvalId, approved, approvalReason);
      setApprovalReason('');
      await loadApprovals();
      await refreshTask();
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden bg-slate-950">
      {/* Task Top Control Bar */}
      <div className="border-b border-slate-800 bg-slate-900/80 px-6 py-3 flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-bold text-slate-100">{activeTask.title}</h1>
            <span
              className={`text-xs px-2.5 py-0.5 rounded-full font-mono font-bold tracking-wide uppercase ${
                activeTask.state === 'COMPLETED'
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                  : activeTask.state === 'FAILED'
                  ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                  : activeTask.state === 'WAITING_FOR_APPROVAL'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse'
                  : 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
              }`}
            >
              {activeTask.state}
            </span>
          </div>
          <div className="text-xs text-slate-400 font-mono truncate max-w-2xl">{activeTask.description}</div>
        </div>

        {/* Task Control Buttons */}
        <div className="flex items-center gap-2">
          {activeTask.state === 'PAUSED' ? (
            <button
              onClick={handleResume}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Resume</span>
            </button>
          ) : (
            !['COMPLETED', 'FAILED', 'CANCELLED'].includes(activeTask.state) && (
              <button
                onClick={handlePause}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600/30 hover:bg-amber-600/50 text-amber-300 border border-amber-500/30 rounded text-xs font-semibold"
              >
                <Pause className="w-3.5 h-3.5" />
                <span>Pause</span>
              </button>
            )
          )}
          {!['COMPLETED', 'FAILED', 'CANCELLED'].includes(activeTask.state) && (
            <button
              onClick={handleCancel}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-950/40 hover:bg-rose-900/60 text-rose-400 border border-rose-800 rounded text-xs font-semibold"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Cancel</span>
            </button>
          )}
        </div>
      </div>

      {/* Pending Approval Gate Alert */}
      {pendingApprovals.length > 0 && (
        <div className="bg-amber-950/70 border-b border-amber-600/40 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-5 h-5 text-amber-400 animate-pulse" />
            <div>
              <div className="text-xs font-bold text-amber-300 uppercase tracking-wide">Approval Required by Policy</div>
              <div className="text-xs text-amber-200">{pendingApprovals[0].description}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Reason or notes..."
              value={approvalReason}
              onChange={(e) => setApprovalReason(e.target.value)}
              className="text-xs bg-slate-900 border border-amber-700/60 rounded px-2.5 py-1 text-slate-200 placeholder-slate-500"
            />
            <button
              onClick={() => handleDecideApproval(pendingApprovals[0].id, false)}
              className="px-3 py-1 bg-rose-900 hover:bg-rose-800 text-rose-100 rounded text-xs font-semibold"
            >
              Reject
            </button>
            <button
              onClick={() => handleDecideApproval(pendingApprovals[0].id, true)}
              className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold"
            >
              Approve
            </button>
          </div>
        </div>
      )}

      {/* Multi-Panel Workspace Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Side: Plan, Steps & Changes List */}
        <div className="w-80 border-r border-slate-800 bg-slate-900/40 flex flex-col justify-between">
          <div className="overflow-y-auto p-4 space-y-6">
            {/* Plan Steps */}
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                <CheckSquare className="w-3.5 h-3.5 text-emerald-400" />
                <span>Plan & Milestones</span>
              </h2>
              {activeTask.steps?.length === 0 ? (
                <div className="text-xs text-slate-500 italic">Formulating plan with AI...</div>
              ) : (
                <div className="space-y-2">
                  {activeTask.steps.map((step) => (
                    <div
                      key={step.id}
                      className="p-2.5 rounded bg-slate-850 border border-slate-800 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between font-semibold text-slate-200">
                        <span>{step.step_index}. {step.title}</span>
                      </div>
                      <p className="text-slate-400 text-[11px]">{step.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Proposed File Changes */}
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                <FileCode className="w-3.5 h-3.5 text-blue-400" />
                <span>Modified Files ({activeTask.proposed_changes?.length || 0})</span>
              </h2>
              {activeTask.proposed_changes?.length === 0 ? (
                <div className="text-xs text-slate-500 italic">No files modified yet.</div>
              ) : (
                <div className="space-y-1.5 font-mono text-xs">
                  {activeTask.proposed_changes.map((ch) => (
                    <div
                      key={ch.id}
                      onClick={() => {
                        setSelectedChange(ch);
                        setActiveTab('diff');
                      }}
                      className={`p-2 rounded cursor-pointer transition-colors flex items-center justify-between ${
                        selectedChange?.id === ch.id
                          ? 'bg-emerald-950/60 border border-emerald-500/40 text-emerald-300'
                          : 'bg-slate-850 hover:bg-slate-800 text-slate-300 border border-slate-800'
                      }`}
                    >
                      <span className="truncate">{ch.file_path}</span>
                      <span className="text-[10px] uppercase font-bold text-slate-500">{ch.operation}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Repair attempt indicator */}
          <div className="p-3 border-t border-slate-800 text-xs text-slate-400 flex items-center justify-between bg-slate-900">
            <span>Repair Iterations:</span>
            <span className="font-mono font-bold text-slate-200">
              {activeTask.repair_attempts} / {activeTask.max_repair_attempts}
            </span>
          </div>
        </div>

        {/* Center / Right: Tabbed Details (Diff View, Test Results, Live Logs) */}
        <div className="flex-1 flex flex-col bg-slate-950 overflow-hidden">
          {/* Tabs Header */}
          <div className="flex items-center border-b border-slate-800 bg-slate-900/50 px-4 text-xs font-medium">
            <button
              onClick={() => setActiveTab('plan')}
              className={`py-2.5 px-4 border-b-2 transition-colors ${
                activeTab === 'plan'
                  ? 'border-emerald-500 text-emerald-400 font-semibold'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              Task Overview
            </button>
            <button
              onClick={() => setActiveTab('diff')}
              className={`py-2.5 px-4 border-b-2 transition-colors ${
                activeTab === 'diff'
                  ? 'border-emerald-500 text-emerald-400 font-semibold'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              Diff & Code Inspector
            </button>
            <button
              onClick={() => setActiveTab('tests')}
              className={`py-2.5 px-4 border-b-2 transition-colors ${
                activeTab === 'tests'
                  ? 'border-emerald-500 text-emerald-400 font-semibold'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              Verification & Tests ({activeTask.test_results?.length || 0})
            </button>
            <button
              onClick={() => setActiveTab('events')}
              className={`py-2.5 px-4 border-b-2 transition-colors ${
                activeTab === 'events'
                  ? 'border-emerald-500 text-emerald-400 font-semibold'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              Live Event Stream
            </button>
          </div>

          {/* Tab Content Panels */}
          <div className="flex-1 p-6 overflow-y-auto">
            {activeTab === 'plan' && (
              <div className="space-y-6 max-w-3xl">
                <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
                  <h3 className="text-sm font-bold text-slate-200">Execution Summary</h3>
                  <p className="text-sm text-slate-300">
                    {activeTask.result_summary || 'Task is currently processing through the orchestration pipeline.'}
                  </p>
                  {activeTask.error_message && (
                    <div className="bg-rose-950/50 border border-rose-800 p-3 rounded text-xs text-rose-300 font-mono">
                      {activeTask.error_message}
                    </div>
                  )}
                </div>

                <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
                  <h3 className="text-sm font-bold text-slate-200">Git Checkpoints ({activeTask.checkpoints?.length || 0})</h3>
                  {activeTask.checkpoints?.length === 0 ? (
                    <p className="text-xs text-slate-500">No checkpoints recorded yet.</p>
                  ) : (
                    <div className="space-y-2 font-mono text-xs">
                      {activeTask.checkpoints.map((cp) => (
                        <div key={cp.id} className="p-2.5 bg-slate-950 border border-slate-800 rounded flex items-center justify-between">
                          <div>
                            <span className="text-emerald-400 font-bold">{cp.git_ref.slice(0, 7)}</span>
                            <span className="text-slate-300 ml-2">{cp.description}</span>
                          </div>
                          <span className="text-slate-500 text-[11px]">{new Date(cp.created_at).toLocaleTimeString()}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'diff' && (
              <div className="h-full flex flex-col space-y-3">
                {selectedChange ? (
                  <>
                    <div className="flex items-center justify-between text-xs text-slate-400 bg-slate-900 p-2 rounded border border-slate-800">
                      <span>Viewing: <strong className="text-slate-100 font-mono">{selectedChange.file_path}</strong></span>
                      <span className="text-slate-400">{selectedChange.explanation}</span>
                    </div>
                    <div className="flex-1 min-h-[400px]">
                      {selectedChange.patch_diff ? (
                        <MonacoEditorView
                          value={selectedChange.patch_diff}
                          language="diff"
                          readOnly={true}
                        />
                      ) : (
                        <MonacoEditorView
                          value={selectedChange.proposed_content || ''}
                          language="python"
                          readOnly={true}
                        />
                      )}
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-slate-500 text-center py-12">
                    Select a modified file from the left panel to inspect proposed changes.
                  </div>
                )}
              </div>
            )}

            {activeTab === 'tests' && (
              <div className="space-y-4 max-w-4xl">
                {activeTask.test_results?.length === 0 ? (
                  <div className="text-slate-500 text-sm italic">Verification tests not yet executed.</div>
                ) : (
                  activeTask.test_results.map((tr) => (
                    <div
                      key={tr.id}
                      className={`p-4 rounded-lg border ${
                        tr.passed
                          ? 'bg-emerald-950/20 border-emerald-500/30'
                          : 'bg-rose-950/20 border-rose-500/30'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono text-xs font-bold text-slate-200">{tr.test_command}</span>
                        <span
                          className={`text-xs font-bold px-2 py-0.5 rounded ${
                            tr.passed ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white'
                          }`}
                        >
                          {tr.passed ? 'PASSED' : 'FAILED'}
                        </span>
                      </div>
                      {tr.error_details && (
                        <pre className="p-3 bg-slate-950 rounded border border-slate-800 text-xs font-mono text-rose-300 overflow-x-auto max-h-60">
                          {tr.error_details}
                        </pre>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'events' && (
              <div className="space-y-2 font-mono text-xs max-w-4xl">
                {events
                  .filter((ev) => ev.task_id === activeTask.id)
                  .map((ev, i) => (
                    <div
                      key={ev.id || i}
                      className="p-2 rounded bg-slate-900 border border-slate-800 flex items-start justify-between"
                    >
                      <div className="space-y-0.5">
                        <div className="text-slate-400 font-semibold">{ev.event_type}</div>
                        <div className="text-slate-200">{ev.message}</div>
                      </div>
                      <span className="text-[10px] text-slate-500">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};


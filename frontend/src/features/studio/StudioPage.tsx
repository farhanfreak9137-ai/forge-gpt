import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Bot,
  Code2,
  ExternalLink,
  FileCode,
  FolderOpen,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  RefreshCw,
  Save,
  Send,
  ShieldAlert,
  Sparkles,
  Terminal,
} from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../../services/api';
import { cn } from '../../lib/cn';
import { CONNECTORS, connectorMeta } from '../../lib/connectors';
import { detectLanguage, formatBytes, splitPath } from '../../lib/format';
import { useDocumentTitle, useMediaQuery } from '../../lib/hooks';
import { useAppStore } from '../../stores/useAppStore';
import { StudioChatSession, StudioCommandAction, StudioMessage, StudioWorkspaceManifest } from '../../types';
import { MonacoEditorView } from '../../components/editor/MonacoEditorView';
import { Badge, Button, ErrorState, IconButton, Mascot, Segmented, Select, Spinner, Switch, useConfirm, useToast } from '../../components/ui';
import { MessageView } from './MessageView';
import { SessionList } from './SessionList';

const PANEL_KEY = 'forgeagent.studio.panelWidth';
const PANEL_MIN = 340;
const CHAT_MIN = 380;
const HISTORY_W = 256;

const QUICK_PROMPTS = [
  { emoji: '\u{1F44B}', title: 'Say hi', text: 'How are you? What can you do?' },
  { emoji: '\u{1F4DC}', title: 'Write a script', text: 'Write a python script to check system memory and CPU usage' },
  { emoji: '\u{1F9E9}', title: 'Build a component', text: 'Create a simple React counter component with increment and reset' },
  { emoji: '\u{1FA7A}', title: 'Check project health', text: 'Run tests with pytest to check current workspace health' },
];

const WORKING_PHRASES = [
  'Reading your request',
  'Thinking it through',
  'Working out a plan',
  'Writing some code',
  'Double-checking the details',
];

function readPanelWidth(): number {
  try {
    const v = Number(localStorage.getItem(PANEL_KEY));
    return Number.isFinite(v) && v >= PANEL_MIN ? v : 480;
  } catch {
    return 480;
  }
}

export const StudioPage: React.FC = () => {
  const toast = useToast();
  const confirm = useConfirm();
  const { settings, setSettings, setStudioPendingCount, isEmergencyStopActive } = useAppStore();
  const connectorName = settings?.default_ai_connector ?? 'chatgpt_edge';
  const meta = connectorMeta(connectorName);

  // Responsive layout
  const isSplit = useMediaQuery('(min-width: 1280px)'); // chat + workspace side by side
  const historyInline = useMediaQuery('(min-width: 1650px)'); // chat list docked instead of a drawer
  const [mobileView, setMobileView] = useState<'chat' | 'workspace'>('chat');
  const [historyChoice, setHistoryChoice] = useState<boolean | null>(null);
  const historyOpen = historyChoice ?? historyInline;
  const [panelWidth, setPanelWidth] = useState(readPanelWidth);
  const [panelOpen, setPanelOpen] = useState(false); // the workspace stays out of the way until you need it
  const [containerWidth, setContainerWidth] = useState(1400);
  const [dragging, setDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Conversation
  const [messages, setMessages] = useState<StudioMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [autoPilot, setAutoPilot] = useState(false); // AI-suggested commands need approval unless the user opts in
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);

  // Sessions
  const [sessions, setSessions] = useState<StudioChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isSyncingSessions, setIsSyncingSessions] = useState(false);

  // Workspace panel
  const [activeTab, setActiveTab] = useState<'editor' | 'files' | 'terminal'>('editor');
  const [manifest, setManifest] = useState<StudioWorkspaceManifest | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [savedContent, setSavedContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [fileFilter, setFileFilter] = useState('');

  const chatEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dirty = !!selectedFile && fileContent !== savedContent;

  const pendingCount = useMemo(
    () => messages.reduce((n, m) => n + (m.pending_actions ?? []).filter((a) => a.status === 'PENDING_APPROVAL').length, 0),
    [messages],
  );
  useEffect(() => setStudioPendingCount(pendingCount), [pendingCount, setStudioPendingCount]);
  useDocumentTitle(pendingCount > 0 ? `(${pendingCount}) Approval needed` : 'Agent Studio');

  /* ---------------- loading ---------------- */

  const loadSessions = useCallback(async (sync = false) => {
    setIsSyncingSessions(sync);
    try {
      const data = await api.getStudioSessions(sync);
      setSessions(data);
      const active = data.find((s) => s.is_active);
      setActiveSessionId((cur) => active?.id ?? cur ?? data[0]?.id ?? null);
      return true;
    } catch (e) {
      console.error('Failed to load sessions', e);
      return false;
    } finally {
      setIsSyncingSessions(false);
    }
  }, []);

  const loadWorkspaceFiles = useCallback(async () => {
    try {
      setManifest(await api.getStudioFiles());
    } catch (e) {
      console.error('Failed to load workspace files', e);
    }
  }, []);

  const loadAll = useCallback(async () => {
    setInitialLoading(true);
    setLoadError(null);
    // Not syncing with ChatGPT here: that would drive your Edge browser just for opening the page.
    const results = await Promise.allSettled([
      loadSessions(false),
      api.getStudioHistory().then(setMessages),
      loadWorkspaceFiles(),
    ]);
    const failed = results.find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined;
    if (failed || results[0].status === 'fulfilled' && results[0].value === false) {
      setLoadError((failed?.reason as Error)?.message || 'The backend did not respond.');
    }
    setInitialLoading(false);
  }, [loadSessions, loadWorkspaceFiles]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Keep the newest message in view
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, isLoading]);

  // "Working…" timer
  useEffect(() => {
    if (!isLoading) return;
    setElapsed(0);
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [isLoading]);

  // Track the width available to the split layout
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setContainerWidth(el.clientWidth));
    ro.observe(el);
    setContainerWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const effectivePanel = Math.min(
    Math.max(panelWidth, PANEL_MIN),
    Math.max(PANEL_MIN, containerWidth - (historyOpen && historyInline ? HISTORY_W : 0) - CHAT_MIN),
  );

  /* ---------------- panel resize ---------------- */

  const persistPanel = (w: number) => {
    try {
      localStorage.setItem(PANEL_KEY, String(Math.round(w)));
    } catch {
      /* ignore */
    }
  };

  const onDividerDown = (e: React.PointerEvent) => {
    e.preventDefault();
    setDragging(true);
    const move = (ev: PointerEvent) => {
      const right = containerRef.current?.getBoundingClientRect().right ?? window.innerWidth;
      setPanelWidth(Math.round(right - ev.clientX));
    };
    const up = (ev: PointerEvent) => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      setDragging(false);
      const right = containerRef.current?.getBoundingClientRect().right ?? window.innerWidth;
      persistPanel(right - ev.clientX);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const onDividerKey = (e: React.KeyboardEvent) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    const next = effectivePanel + (e.key === 'ArrowLeft' ? 32 : -32);
    setPanelWidth(next);
    persistPanel(next);
  };

  /* ---------------- sessions ---------------- */

  const handleSelectSession = async (sessionId: string) => {
    try {
      setActiveSessionId(sessionId);
      const session = await api.selectStudioSession(sessionId);
      setMessages(session.messages || []);
      setSessions((prev) => prev.map((s) => ({ ...s, is_active: s.id === sessionId })));
      if (!historyInline) setHistoryChoice(false);
      setMobileView('chat');
    } catch (e: any) {
      toast.error(`Could not open that chat: ${e.message}`);
    }
  };

  const handleNewChat = async () => {
    try {
      const created = await api.createStudioSession('New Chat');
      setMessages([]);
      setActiveSessionId(created.id);
      await loadSessions(false);
      if (!historyInline) setHistoryChoice(false);
      setMobileView('chat');
      textareaRef.current?.focus();
    } catch (e: any) {
      toast.error(`Could not start a new chat: ${e.message}`);
    }
  };

  const handleDeleteSession = async (sessionId: string, title: string) => {
    const ok = await confirm({
      title: 'Delete this chat?',
      message: (
        <>
          “{title}” and its messages will be permanently removed. This can't be undone.
        </>
      ),
      confirmLabel: 'Delete chat',
      tone: 'danger',
    });
    if (!ok) return;
    try {
      await api.deleteStudioSession(sessionId);
      if (sessionId === activeSessionId) {
        const remaining = sessions.filter((s) => s.id !== sessionId);
        if (remaining.length > 0) await handleSelectSession(remaining[0].id);
        else await handleNewChat();
      }
      await loadSessions(false);
      toast.success('Chat deleted.');
    } catch (e: any) {
      toast.error(`Could not delete the chat: ${e.message}`);
    }
  };

  const handlePrune = async () => {
    const ok = await confirm({
      title: 'Clean up old chats?',
      message: 'This deletes empty chats and everything except your 10 most recent chats. It can\'t be undone.',
      confirmLabel: 'Delete old chats',
      tone: 'danger',
    });
    if (!ok) return;
    try {
      const res = await api.pruneStudioSessions(10);
      await loadSessions(false);
      toast.success(`Removed ${res.removed} chat${res.removed === 1 ? '' : 's'}.`);
    } catch (e: any) {
      toast.error(`Clean-up failed: ${e.message}`);
    }
  };

  const handleSync = async () => {
    const ok = await loadSessions(true);
    if (ok) toast.success('Chats synced with ChatGPT.');
    else toast.error('Could not sync. Is Edge open and logged in to ChatGPT?');
  };

  // "New chat" from the command palette arrives as /?new=1
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    // Wait for the first load so its (older) history can't overwrite the fresh chat
    if (!initialLoading && searchParams.get('new')) {
      setSearchParams({}, { replace: true });
      handleNewChat();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialLoading, searchParams]);

  /* ---------------- connector / edge ---------------- */

  const handleConnectorChange = async (value: string) => {
    const previous = settings;
    if (settings) setSettings({ ...settings, default_ai_connector: value });
    try {
      await api.updateSettings({ default_ai_connector: value });
    } catch (e: any) {
      if (previous) setSettings(previous);
      toast.error(`Could not switch the AI engine: ${e.message}`);
    }
  };

  const handleOpenEdge = async () => {
    try {
      await api.openStudioBrowser();
      toast.info('Edge is opening. Log in to ChatGPT there, then come back.');
    } catch (e: any) {
      toast.error(`Could not open Edge automatically: ${e.message}. You can also run OPEN_EDGE_CHATGPT.bat.`);
    }
  };

  /* ---------------- messaging ---------------- */

  const handleDecideAction = async (messageId: string, actionId: string, approve: boolean) => {
    setBusyAction(actionId);
    try {
      const updated = approve
        ? await api.approveStudioAction(messageId, actionId)
        : await api.rejectStudioAction(messageId, actionId);
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== messageId) return m;
          const executed = [...(m.executed_commands || [])];
          if (approve && updated.kind === 'command' && updated.result && 'command' in updated.result) {
            executed.push(updated.result as StudioCommandAction);
          }
          return {
            ...m,
            pending_actions: (m.pending_actions || []).map((a) => (a.id === actionId ? updated : a)),
            executed_commands: executed,
          };
        }),
      );
      if (approve && updated.kind === 'file') await loadWorkspaceFiles();
    } catch (e: any) {
      toast.error(`Could not ${approve ? 'approve' : 'reject'} the action: ${e.message}`);
    } finally {
      setBusyAction(null);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend ?? inputMessage).trim();
    if (!text || isLoading) return;

    setInputMessage('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setIsLoading(true);
    setMobileView('chat');

    const tempUserMsg: StudioMessage = { id: `temp-${Date.now()}`, sender: 'user', text, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const reply = await api.sendStudioChat({ message: text, auto_pilot: autoPilot, connector_name: connectorName });
      setMessages((prev) => [...prev.filter((m) => m.id !== tempUserMsg.id), tempUserMsg, reply]);
      await loadSessions(false);

      if (reply.executed_file_changes && reply.executed_file_changes.length > 0) {
        await loadWorkspaceFiles();
        await handleOpenFile(reply.executed_file_changes[reply.executed_file_changes.length - 1].path, true);
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'assistant',
          text: `Error: ${err.message || 'Failed to process request'}`,
          clean_message: `**Something went wrong.** ${err.message || 'The agent backend did not respond.'}\n\nYour message was not lost. Edit it above and send it again.`,
          timestamp: new Date().toISOString(),
        },
      ]);
      setInputMessage((cur) => cur || text);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const autoGrow = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  };

  /* ---------------- files ---------------- */

  const handleOpenFile = async (filePath: string, skipGuard = false) => {
    if (!skipGuard && dirty && filePath !== selectedFile) {
      const ok = await confirm({
        title: 'Discard unsaved changes?',
        message: `You have unsaved edits in ${selectedFile}. Opening another file will lose them.`,
        confirmLabel: 'Discard & open',
        tone: 'danger',
      });
      if (!ok) return;
    }
    setSelectedFile(filePath);
    setActiveTab('editor');
    setPanelOpen(true);
    if (!isSplit) setMobileView('workspace');
    try {
      const res = await api.getStudioFileContent(filePath);
      setFileContent(res.content);
      setSavedContent(res.content);
    } catch (e: any) {
      toast.error(`Could not read ${filePath}: ${e.message}`);
      setFileContent('');
      setSavedContent('');
    }
  };

  const handleSaveFile = async () => {
    if (!selectedFile || !dirty) return;
    setIsSaving(true);
    try {
      await api.saveStudioFile({ file_path: selectedFile, content: fileContent });
      setSavedContent(fileContent);
      toast.success(`Saved ${splitPath(selectedFile).name}`);
    } catch (e: any) {
      toast.error(`Save failed: ${e.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const onPanelKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's' && activeTab === 'editor') {
      e.preventDefault();
      handleSaveFile();
    }
  };

  const reviewPending = () => {
    setMobileView('chat');
    setTimeout(() => {
      document.querySelector('[data-pending-action="true"]')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 50);
  };

  const filteredFiles = (manifest?.files ?? []).filter((f) => f.path.toLowerCase().includes(fileFilter.toLowerCase()));
  const allCommands = messages.flatMap((m) => m.executed_commands ?? []);

  /* ---------------- render ---------------- */

  const showChat = isSplit || mobileView === 'chat';
  const showPanel = isSplit ? panelOpen : mobileView === 'workspace';
  const activeSession = sessions.find((s) => s.id === activeSessionId);

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-slate-950">
      {/* Toolbar */}
      <header className="flex shrink-0 items-center gap-2 border-b border-slate-800 bg-slate-900/60 px-3 py-2 sm:px-4">
        <IconButton
          label={historyOpen ? 'Hide chat list' : 'Show chat list'}
          aria-expanded={historyOpen}
          onClick={() => setHistoryChoice(!historyOpen)}
        >
          {historyOpen ? <PanelLeftClose className="h-5 w-5" /> : <PanelLeftOpen className="h-5 w-5" />}
        </IconButton>
        <h1 className="min-w-0 flex-1 truncate text-base font-semibold text-slate-50">
          Agent Studio
          {activeSession?.title && <span className="hidden font-normal text-slate-500 sm:inline"> {'\u00b7'} {activeSession.title}</span>}
        </h1>

        {connectorName === 'chatgpt_edge' && (
          <Button size="sm" icon={<ExternalLink className="h-3.5 w-3.5" />} onClick={handleOpenEdge} title="Open a visible Edge window so you can log in to ChatGPT">
            <span className="hidden sm:inline">Open Edge to log in</span>
            <span className="sm:hidden">Edge</span>
          </Button>
        )}
        {!historyOpen && (
          <Button size="sm" variant="primary" icon={<Plus className="h-4 w-4" />} onClick={handleNewChat}>
            <span className="hidden sm:inline">New chat</span>
            <span className="sm:hidden">New</span>
          </Button>
        )}
        {isSplit && (
          <Button
            size="sm"
            variant={panelOpen ? 'secondary' : 'ghost'}
            aria-pressed={panelOpen}
            icon={panelOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
            onClick={() => setPanelOpen(!panelOpen)}
            title="Show or hide the files, editor and terminal"
          >
            Workspace
            {!!manifest?.total_files && <span className="rounded-full bg-slate-700 px-1.5 text-xs text-slate-200">{manifest.total_files}</span>}
          </Button>
        )}
      </header>

      {/* Chat / Workspace switch on narrower screens */}
      {!isSplit && (
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-800 px-3 py-2">
          <Segmented
            ariaLabel="Studio view"
            value={mobileView}
            onChange={setMobileView}
            options={[
              { value: 'chat', label: 'Chat' },
              { value: 'workspace', label: 'Workspace', count: manifest?.total_files },
            ]}
          />
          {pendingCount > 0 && mobileView !== 'chat' && (
            <Button size="sm" variant="warning" onClick={reviewPending}>
              {pendingCount} to approve
            </Button>
          )}
        </div>
      )}

      <div ref={containerRef} className={cn('relative flex min-h-0 flex-1', dragging && 'select-none')}>
        {/* Chat list: docked on wide screens, drawer otherwise */}
        {historyOpen && !historyInline && (
          <div className="absolute inset-0 z-20 bg-black/60 animate-fade-in" onClick={() => setHistoryChoice(false)} aria-hidden />
        )}
        {historyOpen && (
          <aside
            aria-label="Chat list"
            className={cn(
              'bg-slate-950',
              historyInline
                ? 'w-64 shrink-0 border-r border-slate-800'
                : 'absolute inset-y-0 left-0 z-30 w-72 max-w-[85%] border-r border-slate-700 shadow-2xl animate-slide-in-left',
            )}
          >
            <SessionList
              sessions={sessions}
              activeId={activeSessionId}
              syncing={isSyncingSessions}
              loading={initialLoading}
              onSelect={handleSelectSession}
              onNew={handleNewChat}
              onDelete={handleDeleteSession}
              onSync={handleSync}
              onPrune={handlePrune}
            />
          </aside>
        )}

        {/* Conversation */}
        <section aria-label="Conversation" className={cn('min-w-0 flex-1 flex-col', showChat ? 'flex' : 'hidden')}>
          <div
            role="log"
            aria-live="polite"
            aria-label="Conversation messages"
            className="flex-1 overflow-y-auto px-3 py-5 sm:px-6"
          >
            <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col space-y-5">
            {loadError ? (
              <ErrorState title="Couldn't load Studio" message={loadError} onRetry={loadAll} className="mx-auto max-w-md" />
            ) : initialLoading && messages.length === 0 ? (
              <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-400">
                <Spinner /> Loading your chats…
              </div>
            ) : messages.length === 0 ? (
              <div className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center gap-6 py-8 text-center">
                <Mascot mood="happy" size={104} label="Forge the robot waving hello" className="drop-shadow-xl" />
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold text-slate-50">What should we build?</h2>
                  <p className="text-sm leading-relaxed text-slate-400">
                    Tell {meta.short} what you want. ForgeAgent writes the files and runs commands on your machine, and asks you before anything risky.
                  </p>
                </div>
                <div className="grid w-full gap-2 sm:grid-cols-2">
                  {QUICK_PROMPTS.map((p) => (
                    <button
                      key={p.title}
                      type="button"
                      onClick={() => handleSendMessage(p.text)}
                      className="rounded-2xl border border-slate-800 bg-slate-900 p-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-brand-500/50 hover:bg-slate-800 hover:shadow-lg hover:shadow-brand-500/10"
                    >
                      <span className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                        <span className="text-lg" aria-hidden>
                          {p.emoji}
                        </span>
                        {p.title}
                      </span>
                      <span className="mt-0.5 block text-xs leading-relaxed text-slate-400">{p.text}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, i) => (
                <MessageView
                  key={msg.id || i}
                  msg={msg}
                  assistantName={meta.short}
                  busyAction={busyAction}
                  onOpenFile={(p) => handleOpenFile(p)}
                  onDecide={handleDecideAction}
                />
              ))
            )}

            {isLoading && (
              <div className="flex gap-3" role="status">
                <Mascot mood="thinking" size={36} />
                <div className="flex items-center gap-3 rounded-2xl rounded-tl-md border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-200">
                  <span>
                    {WORKING_PHRASES[Math.floor(elapsed / 4) % WORKING_PHRASES.length]}
                    <span className="text-slate-400"> with {meta.short}</span>
                  </span>
                  <span className="flex items-center gap-1" aria-hidden>
                    {[0, 1, 2].map((i) => (
                      <span key={i} className="h-1.5 w-1.5 animate-bounce-dot rounded-full bg-brand-400" style={{ animationDelay: `${i * 0.16}s` }} />
                    ))}
                  </span>
                  <span className="text-xs text-slate-500">{elapsed}s</span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
            </div>
          </div>

          {/* Approval reminder */}
          {pendingCount > 0 && (
            <div className="flex items-center justify-between gap-3 border-t border-amber-500/30 bg-amber-500/10 px-4 py-1.5 text-sm text-amber-100">
              <span className="flex items-center gap-2">
                <Mascot mood="alert" size={24} />
                {pendingCount} action{pendingCount === 1 ? '' : 's'} waiting for your approval
              </span>
              <Button size="sm" variant="warning" onClick={reviewPending}>
                Review
              </Button>
            </div>
          )}

          {/* Composer: one slim row for the message, one quiet row for the settings */}
          <div className="border-t border-slate-800 bg-slate-900/60 px-3 pb-2 pt-2.5 sm:px-6">
            <div className="mx-auto max-w-3xl space-y-1.5">
              <div className="flex items-end gap-2 rounded-2xl border border-slate-700 bg-slate-950 p-1.5 shadow-sm transition-colors focus-within:border-brand-500">
                <textarea
                  ref={textareaRef}
                  value={inputMessage}
                  onChange={(e) => {
                    setInputMessage(e.target.value);
                    autoGrow(e.target);
                  }}
                  onKeyDown={handleKeyDown}
                  aria-label="Message to ForgeAgent"
                  placeholder="Ask ForgeAgent to build, fix or explain something…"
                  rows={1}
                  disabled={isLoading}
                  className="block max-h-40 min-h-[2.25rem] flex-1 resize-none bg-transparent px-2.5 py-1.5 text-sm leading-relaxed text-slate-100 placeholder:text-slate-500 focus-visible:outline-none disabled:opacity-60"
                />
                <Button
                  variant="primary"
                  size="sm"
                  className="h-9 w-9 shrink-0 rounded-xl px-0"
                  aria-label="Send message"
                  title="Send (Enter). Shift+Enter for a new line."
                  onClick={() => handleSendMessage()}
                  disabled={!inputMessage.trim() || isLoading}
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 text-xs text-slate-400">
                <Select
                  aria-label="AI engine"
                  value={connectorName}
                  onChange={(e) => handleConnectorChange(e.target.value)}
                  className="h-7 w-auto max-w-[13rem] rounded-lg border-transparent bg-transparent py-0 text-xs hover:border-slate-700"
                >
                  {CONNECTORS.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </Select>
                <Switch compact checked={autoPilot} onChange={setAutoPilot} label="Auto-run safe commands" />
                {isEmergencyStopActive && <span className="text-rose-300">Emergency stop is on, so nothing will run</span>}
              </div>
            </div>
          </div>
        </section>

        {/* Drag handle */}
        {isSplit && panelOpen && (
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize workspace panel"
            aria-valuenow={Math.round(effectivePanel)}
            aria-valuemin={PANEL_MIN}
            tabIndex={0}
            onPointerDown={onDividerDown}
            onKeyDown={onDividerKey}
            className={cn(
              'group relative w-1.5 shrink-0 cursor-col-resize bg-slate-800 transition-colors hover:bg-brand-500/60 focus-visible:bg-brand-500/60',
              dragging && 'bg-brand-500/60',
            )}
          >
            <span className="absolute inset-y-0 -left-1.5 -right-1.5" aria-hidden />
          </div>
        )}

        {/* Workspace panel */}
        <section
          aria-label="Workspace"
          onKeyDown={onPanelKeyDown}
          style={isSplit ? { width: effectivePanel } : undefined}
          className={cn('min-w-0 flex-col bg-slate-950', showPanel ? 'flex' : 'hidden', isSplit ? 'shrink-0' : 'flex-1')}
        >
          <div className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-800 bg-slate-900/60 px-2">
            <div role="tablist" aria-label="Workspace views" className="flex">
              {(
                [
                  { id: 'editor', label: selectedFile ? splitPath(selectedFile).name : 'Editor', icon: Code2, dot: dirty },
                  { id: 'files', label: `Files${manifest ? ` (${manifest.total_files})` : ''}`, icon: FolderOpen },
                  { id: 'terminal', label: 'Terminal', icon: Terminal },
                ] as const
              ).map((t) => (
                <button
                  key={t.id}
                  role="tab"
                  type="button"
                  aria-selected={activeTab === t.id}
                  onClick={() => setActiveTab(t.id)}
                  className={cn(
                    'flex max-w-[11rem] items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors',
                    activeTab === t.id ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-400 hover:text-slate-100',
                  )}
                >
                  <t.icon className="h-4 w-4 shrink-0" aria-hidden />
                  <span className="truncate">{t.label}</span>
                  {'dot' in t && t.dot && <span className="h-2 w-2 shrink-0 rounded-full bg-amber-400" title="Unsaved changes" aria-label="Unsaved changes" />}
                </button>
              ))}
            </div>
            {activeTab === 'editor' && selectedFile && (
              <Button
                size="sm"
                variant={dirty ? 'primary' : 'secondary'}
                icon={<Save className="h-3.5 w-3.5" />}
                onClick={handleSaveFile}
                loading={isSaving}
                disabled={!dirty}
                title="Save (Ctrl+S)"
              >
                Save
              </Button>
            )}
            {activeTab === 'files' && (
              <IconButton label="Refresh files" size="sm" onClick={loadWorkspaceFiles}>
                <RefreshCw className="h-4 w-4" />
              </IconButton>
            )}
          </div>

          <div className="relative min-h-0 flex-1" role="tabpanel">
            {activeTab === 'editor' &&
              (selectedFile ? (
                <div className="flex h-full flex-col">
                  <div className="flex items-center justify-between gap-2 border-b border-slate-800 bg-slate-900 px-3 py-1.5 text-xs">
                    <span className="truncate font-mono text-slate-300" title={selectedFile}>
                      {selectedFile}
                    </span>
                    <span className="shrink-0 text-slate-400">{detectLanguage(selectedFile)}</span>
                  </div>
                  <div className="min-h-0 flex-1">
                    <MonacoEditorView
                      value={fileContent}
                      language={detectLanguage(selectedFile)}
                      readOnly={false}
                      onChange={(val) => setFileContent(val || '')}
                    />
                  </div>
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
                  <FileCode className="h-10 w-10 text-slate-600" aria-hidden />
                  <div className="space-y-1">
                    <h3 className="text-sm font-semibold text-slate-100">No file open</h3>
                    <p className="max-w-xs text-sm text-slate-400">Files the agent writes open here automatically. You can also pick one from the file list.</p>
                  </div>
                  <Button size="sm" onClick={() => setActiveTab('files')}>
                    Browse files
                  </Button>
                </div>
              ))}

            {activeTab === 'files' && (
              <div className="flex h-full flex-col gap-2 p-3">
                <input
                  type="search"
                  aria-label="Filter files"
                  placeholder="Filter files"
                  value={fileFilter}
                  onChange={(e) => setFileFilter(e.target.value)}
                  className="h-9 w-full rounded-lg border border-slate-800 bg-slate-900 px-3 text-sm text-slate-100 placeholder:text-slate-500 focus-visible:border-brand-500"
                />
                {manifest && (
                  <p className="truncate px-1 text-xs text-slate-500" title={manifest.root_path}>
                    {manifest.root_path}
                  </p>
                )}
                <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto">
                  {filteredFiles.map((f) => {
                    const { dir, name } = splitPath(f.path);
                    return (
                      <li key={f.path}>
                        <button
                          type="button"
                          onClick={() => handleOpenFile(f.path)}
                          aria-current={selectedFile === f.path ? 'true' : undefined}
                          className={cn(
                            'flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left font-mono text-[13px] transition-colors',
                            selectedFile === f.path ? 'bg-brand-500/15 text-brand-200' : 'text-slate-300 hover:bg-slate-900',
                          )}
                        >
                          <span className="flex min-w-0 items-center gap-2">
                            <FileCode className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                            <span className="truncate">
                              <span className="text-slate-500">{dir}</span>
                              <span className="font-medium">{name}</span>
                            </span>
                          </span>
                          <span className="shrink-0 text-xs text-slate-500">{formatBytes(f.size_bytes)}</span>
                        </button>
                      </li>
                    );
                  })}
                  {filteredFiles.length === 0 && (
                    <li className="px-3 py-10 text-center text-sm text-slate-400">
                      {manifest?.files.length ? 'No files match your filter.' : 'The workspace is empty. Ask the agent to create something.'}
                    </li>
                  )}
                </ul>
              </div>
            )}

            {activeTab === 'terminal' && (
              <div className="h-full overflow-y-auto bg-slate-950 p-3 font-mono text-[13px]">
                {allCommands.length === 0 ? (
                  <p className="py-10 text-center font-sans text-sm text-slate-400">Commands the agent runs in this chat will show up here.</p>
                ) : (
                  allCommands.map((cmd, i) => {
                    const ok = cmd.status !== 'BLOCKED' && (cmd.passed ?? cmd.exit_code === 0);
                    return (
                      <div key={i} className="space-y-1 border-b border-slate-800/70 py-2.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-emerald-400">$</span>
                          <span className="break-all text-slate-100">{cmd.command}</span>
                          <Badge tone={cmd.status === 'BLOCKED' ? 'warning' : ok ? 'success' : 'danger'}>
                            {cmd.status === 'BLOCKED' ? 'blocked' : `exit ${cmd.exit_code}`}
                            {cmd.duration_ms !== undefined && ` · ${cmd.duration_ms} ms`}
                          </Badge>
                        </div>
                        {cmd.stdout && <pre className="whitespace-pre-wrap pl-4 text-slate-300">{cmd.stdout}</pre>}
                        {cmd.stderr && <pre className="whitespace-pre-wrap pl-4 text-rose-300">{cmd.stderr}</pre>}
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

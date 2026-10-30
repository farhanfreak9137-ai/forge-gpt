import React, { useState, useEffect, useRef } from 'react';
import {
  Bot,
  Send,
  Terminal,
  FileCode,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Save,
  FolderOpen,
  RefreshCw,
  Eye,
  Zap,
  ChevronDown,
  ChevronRight,
  Code2,
  Sparkles,
} from 'lucide-react';
import { api } from '../../services/api';
import { StudioMessage, StudioWorkspaceManifest } from '../../types';
import { MonacoEditorView } from '../../components/editor/MonacoEditorView';

export const StudioPage: React.FC = () => {
  // State
  const [messages, setMessages] = useState<StudioMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [autoPilot, setAutoPilot] = useState(true);
  const [connectorName, setConnectorName] = useState('chatgpt_edge');
  const [activeTab, setActiveTab] = useState<'editor' | 'files' | 'terminal'>('editor');
  
  // Workspace & Editor state
  const [manifest, setManifest] = useState<StudioWorkspaceManifest | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [fileFilter, setFileFilter] = useState('');
  const [expandedCommands, setExpandedCommands] = useState<Record<string, boolean>>({});

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Load chat history & workspace files on mount
  useEffect(() => {
    loadChatHistory();
    loadWorkspaceFiles();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const loadChatHistory = async () => {
    try {
      const history = await api.getStudioHistory();
      setMessages(history);
    } catch (e) {
      console.error('Failed to load studio chat history', e);
    }
  };

  const loadWorkspaceFiles = async () => {
    try {
      const data = await api.getStudioFiles();
      setManifest(data);
    } catch (e) {
      console.error('Failed to load workspace files', e);
    }
  };

  const handleClearHistory = async () => {
    if (confirm('Clear chat history and start a fresh session?')) {
      try {
        await api.clearStudioHistory();
        setMessages([]);
      } catch (e) {
        console.error('Failed to clear history', e);
      }
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || isLoading) return;

    setInputMessage('');
    setIsLoading(true);

    // Optimistically add user message
    const tempUserMsg: StudioMessage = {
      id: `temp-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const assistantReply = await api.sendStudioChat({
        message: text,
        auto_pilot: autoPilot,
        connector_name: connectorName,
      });

      // Replace or append
      setMessages((prev) => [...prev.filter((m) => m.id !== tempUserMsg.id), tempUserMsg, assistantReply]);

      // If files were modified, refresh file list and open the last modified file
      if (assistantReply.executed_file_changes && assistantReply.executed_file_changes.length > 0) {
        await loadWorkspaceFiles();
        const lastFile = assistantReply.executed_file_changes[assistantReply.executed_file_changes.length - 1].path;
        handleOpenFile(lastFile);
      }
    } catch (err: any) {
      const errorMsg: StudioMessage = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        text: `Error: ${err.message || 'Failed to process request'}`,
        clean_message: `An error occurred: ${err.message || 'Failed to connect to agent backend'}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleOpenFile = async (filePath: string) => {
    setSelectedFile(filePath);
    setActiveTab('editor');
    setSaveStatus(null);
    try {
      const res = await api.getStudioFileContent(filePath);
      setFileContent(res.content);
    } catch (e: any) {
      console.error(`Failed to read file ${filePath}`, e);
      setFileContent(`// Error reading file ${filePath}: ${e.message}`);
    }
  };

  const handleSaveFile = async () => {
    if (!selectedFile) return;
    setIsSaving(true);
    setSaveStatus(null);
    try {
      await api.saveStudioFile({
        file_path: selectedFile,
        content: fileContent,
      });
      setSaveStatus('Saved!');
      setTimeout(() => setSaveStatus(null), 2500);
    } catch (e: any) {
      setSaveStatus(`Save failed: ${e.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const toggleCommandExpanded = (idx: string) => {
    setExpandedCommands((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const detectLanguage = (filePath: string) => {
    const ext = filePath.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'ts':
      case 'tsx':
        return 'typescript';
      case 'js':
      case 'jsx':
        return 'javascript';
      case 'py':
        return 'python';
      case 'json':
        return 'json';
      case 'html':
        return 'html';
      case 'css':
        return 'css';
      case 'md':
        return 'markdown';
      case 'sh':
      case 'bash':
      case 'ps1':
        return 'shell';
      default:
        return 'plaintext';
    }
  };

  const quickPrompts = [
    'How are you? What can you do?',
    'Write a python script to check system memory and CPU usage',
    'Create a simple React counter component with increment and reset',
    'Run tests with pytest to check current workspace health',
  ];

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 overflow-hidden">
      {/* Top Studio Toolbar */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/90 px-4 flex items-center justify-between z-10 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 font-bold text-emerald-400">
            <Bot className="w-5 h-5 text-emerald-400" />
            <span className="text-slate-100 font-semibold tracking-wide">ForgeAgent Studio</span>
            <span className="text-[10px] uppercase font-bold tracking-widest bg-emerald-500/10 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/20">
              Antigravity / Cursor Mode
            </span>
          </div>

          {/* AI Brain Connector Selector */}
          <div className="hidden md:flex items-center gap-1.5 ml-4 pl-4 border-l border-slate-800">
            <span className="text-xs text-slate-400">Brain:</span>
            <select
              value={connectorName}
              onChange={(e) => setConnectorName(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-xs rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="chatgpt_edge">Microsoft Edge (ChatGPT Web - Unlimited Tokens)</option>
              <option value="openai">OpenAI Compatible API</option>
              <option value="ollama">Ollama (Local LLM)</option>
              <option value="mock">Mock AI Adapter (Instant Test)</option>
              <option value="browser_handoff">Manual Browser Handoff</option>
            </select>
          </div>
        </div>

        {/* Toolbar Controls */}
        <div className="flex items-center gap-3">
          {/* Auto-Pilot Toggle */}
          <button
            onClick={() => setAutoPilot(!autoPilot)}
            className={`flex items-center gap-2 px-3 py-1 rounded text-xs font-semibold border transition-all ${
              autoPilot
                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40 shadow-sm shadow-emerald-500/10'
                : 'bg-slate-800 text-slate-400 border-slate-700'
            }`}
            title="Auto-Pilot: Automatically writes generated code, executes terminal commands, and auto-repairs failures in a loop."
          >
            <Zap className={`w-3.5 h-3.5 ${autoPilot ? 'text-emerald-400 fill-emerald-400' : 'text-slate-400'}`} />
            <span>Auto-Pilot: {autoPilot ? 'ON (Self-Executing)' : 'OFF (Review Only)'}</span>
          </button>

          {/* New Chat Button */}
          <button
            onClick={handleClearHistory}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800 rounded border border-slate-700 transition"
            title="Start a new clean chat session"
          >
            <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
            <span>New Chat</span>
          </button>
        </div>
      </header>

      {/* Main Split Layout: Left Chat & Right IDE/Editor */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT PANEL: Chat with Brain & Agent Hands */}
        <div className="w-1/2 flex flex-col border-r border-slate-800 bg-slate-950/60 overflow-hidden">
          {/* Chat Messages Scrollable */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-6">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-500/20 to-teal-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-lg shadow-emerald-500/5">
                  <Sparkles className="w-7 h-7" />
                </div>
                <div className="space-y-1.5 max-w-md">
                  <h3 className="text-base font-semibold text-slate-200">
                    Welcome to ForgeAgent Studio
                  </h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Talk naturally with ChatGPT. ForgeAgent operates as the autonomous hands on your local machine—writing files, executing commands, running tests, and fixing bugs.
                  </p>
                </div>

                {/* Quick Prompts */}
                <div className="w-full max-w-md space-y-2 text-left">
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    Suggested Prompts:
                  </span>
                  <div className="grid grid-cols-1 gap-2">
                    {quickPrompts.map((p, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSendMessage(p)}
                        className="text-left text-xs bg-slate-900/90 hover:bg-slate-800/90 text-slate-300 hover:text-slate-100 p-2.5 rounded-md border border-slate-800 hover:border-slate-700 transition-all"
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              messages.map((msg, index) => {
                const isUser = msg.sender === 'user';
                return (
                  <div
                    key={msg.id || index}
                    className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
                  >
                    <div className="flex items-center gap-2 mb-1 px-1 text-[11px] text-slate-500">
                      <span>{isUser ? 'You' : 'ForgeAgent (ChatGPT Brain)'}</span>
                      <span>•</span>
                      <span>{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>

                    <div
                      className={`max-w-[92%] rounded-xl px-4 py-3 text-xs leading-relaxed ${
                        isUser
                          ? 'bg-blue-600/90 text-white rounded-tr-none'
                          : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none shadow-sm'
                      }`}
                    >
                      {/* Clean Message Body */}
                      <div className="whitespace-pre-wrap font-sans text-[13px] leading-relaxed">
                        {msg.clean_message || msg.text}
                      </div>

                      {/* File Modifications ("The Hands" executed changes) */}
                      {msg.executed_file_changes && msg.executed_file_changes.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-2">
                          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-400">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Files written to workspace:</span>
                          </div>
                          <div className="space-y-1.5">
                            {msg.executed_file_changes.map((fc, fIdx) => (
                              <div
                                key={fIdx}
                                className="flex items-center justify-between bg-slate-950/70 border border-slate-800/90 px-2.5 py-1.5 rounded text-xs"
                              >
                                <div className="flex items-center gap-2 overflow-hidden">
                                  <FileCode className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                                  <span className="font-mono text-slate-300 truncate">{fc.path}</span>
                                  <span className="text-[10px] text-slate-500">({fc.lines} lines)</span>
                                </div>
                                <button
                                  onClick={() => handleOpenFile(fc.path)}
                                  className="flex items-center gap-1 text-[11px] text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20 px-2 py-0.5 rounded border border-emerald-500/20 transition shrink-0"
                                >
                                  <Eye className="w-3 h-3" />
                                  <span>View in Editor</span>
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Executed Commands ("The Hands" terminal runs) */}
                      {msg.executed_commands && msg.executed_commands.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-2">
                          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-300">
                            <Terminal className="w-3.5 h-3.5 text-slate-400" />
                            <span>Executed Terminal Commands:</span>
                          </div>
                          <div className="space-y-1.5">
                            {msg.executed_commands.map((cmd, cIdx) => {
                              const cmdKey = `${index}-${cIdx}`;
                              const isExp = !!expandedCommands[cmdKey];
                              const isPassed = cmd.passed ?? cmd.exit_code === 0;

                              return (
                                <div
                                  key={cIdx}
                                  className="bg-slate-950 border border-slate-800/90 rounded overflow-hidden text-xs"
                                >
                                  <div
                                    onClick={() => toggleCommandExpanded(cmdKey)}
                                    className="flex items-center justify-between px-2.5 py-1.5 cursor-pointer hover:bg-slate-900/60 transition"
                                  >
                                    <div className="flex items-center gap-2 overflow-hidden">
                                      {isPassed ? (
                                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                                      ) : (
                                        <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                                      )}
                                      <span className="font-mono text-slate-300 truncate">{cmd.command}</span>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                      <span
                                        className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                                          isPassed
                                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                                        }`}
                                      >
                                        exit {cmd.exit_code}
                                      </span>
                                      {isExp ? (
                                        <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
                                      ) : (
                                        <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
                                      )}
                                    </div>
                                  </div>

                                  {/* Command Output Accordion */}
                                  {isExp && (
                                    <div className="p-2 border-t border-slate-800/80 bg-black/60 font-mono text-[11px] text-slate-300 max-h-48 overflow-y-auto space-y-1">
                                      {cmd.stdout && (
                                        <div>
                                          <span className="text-[10px] text-slate-500 uppercase block">STDOUT:</span>
                                          <pre className="whitespace-pre-wrap">{cmd.stdout}</pre>
                                        </div>
                                      )}
                                      {cmd.stderr && (
                                        <div>
                                          <span className="text-[10px] text-rose-400 uppercase block">STDERR:</span>
                                          <pre className="whitespace-pre-wrap text-rose-300">{cmd.stderr}</pre>
                                        </div>
                                      )}
                                      {!cmd.stdout && !cmd.stderr && (
                                        <div className="text-slate-500 italic">No output produced.</div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Repair Iterations Badge */}
                      {msg.repair_iterations && msg.repair_iterations > 0 ? (
                        <div className="mt-2 text-[11px] text-amber-400 flex items-center gap-1.5">
                          <Zap className="w-3 h-3 text-amber-400" />
                          <span>Auto-pilot repaired failure after {msg.repair_iterations} iteration(s).</span>
                        </div>
                      ) : null}
                    </div>
                  </div>
                );
              })
            )}

            {/* Thinking / Executing Indicator */}
            {isLoading && (
              <div className="flex flex-col items-start space-y-1">
                <div className="px-1 text-[11px] text-slate-500">ForgeAgent (ChatGPT Brain)</div>
                <div className="bg-slate-900 border border-slate-800 rounded-xl rounded-tl-none px-4 py-3 flex items-center gap-3 text-xs text-slate-300 shadow-sm">
                  <div className="w-4 h-4 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin" />
                  <span>ChatGPT is analyzing & agent hands are executing changes...</span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Chat Input Bar */}
          <div className="p-3 border-t border-slate-800 bg-slate-900/80">
            <div className="flex flex-col bg-slate-950 border border-slate-800 focus-within:border-emerald-500 rounded-lg p-2.5 transition">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message ChatGPT (e.g. 'Build a CLI tool', 'Fix the bug in main.py', 'How are you?')..."
                className="w-full bg-transparent resize-none text-xs text-slate-200 placeholder-slate-500 focus:outline-none min-h-[56px] max-h-36 font-sans"
                rows={2}
                disabled={isLoading}
              />
              <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 mt-1">
                <div className="flex items-center gap-2 text-[11px] text-slate-500">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <span>Enter to send • Shift+Enter for new line</span>
                </div>
                <button
                  onClick={() => handleSendMessage()}
                  disabled={!inputMessage.trim() || isLoading}
                  className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 text-white disabled:text-slate-500 px-3 py-1.5 rounded-md text-xs font-semibold transition"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Send</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT PANEL: Workspace IDE & Monaco Editor */}
        <div className="w-1/2 flex flex-col bg-slate-950 overflow-hidden">
          {/* Right Panel Tabs Header */}
          <div className="h-10 border-b border-slate-800 bg-slate-900/60 px-3 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setActiveTab('editor')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-t border-b-2 transition ${
                  activeTab === 'editor'
                    ? 'border-emerald-500 text-emerald-400 bg-slate-800/40'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Code2 className="w-3.5 h-3.5" />
                <span>Editor {selectedFile ? `(${selectedFile.split(/[/\\]/).pop()})` : ''}</span>
              </button>

              <button
                onClick={() => setActiveTab('files')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-t border-b-2 transition ${
                  activeTab === 'files'
                    ? 'border-emerald-500 text-emerald-400 bg-slate-800/40'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <FolderOpen className="w-3.5 h-3.5" />
                <span>Files ({manifest?.total_files || 0})</span>
              </button>

              <button
                onClick={() => setActiveTab('terminal')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-t border-b-2 transition ${
                  activeTab === 'terminal'
                    ? 'border-emerald-500 text-emerald-400 bg-slate-800/40'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Terminal className="w-3.5 h-3.5" />
                <span>Terminal Output</span>
              </button>
            </div>

            {/* Right Header Actions */}
            {activeTab === 'editor' && selectedFile && (
              <div className="flex items-center gap-2">
                {saveStatus && (
                  <span className="text-[11px] text-emerald-400 font-medium">{saveStatus}</span>
                )}
                <button
                  onClick={handleSaveFile}
                  disabled={isSaving}
                  className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 text-slate-200 px-2 py-1 rounded text-xs border border-slate-700 transition"
                  title="Save current file changes"
                >
                  <Save className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Save</span>
                </button>
              </div>
            )}

            {activeTab === 'files' && (
              <button
                onClick={loadWorkspaceFiles}
                className="flex items-center gap-1 text-slate-400 hover:text-slate-200 text-xs px-2 py-1 rounded hover:bg-slate-800 transition"
                title="Refresh file tree"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Refresh</span>
              </button>
            )}
          </div>

          {/* Right Panel Body */}
          <div className="flex-1 overflow-hidden relative">
            {/* TAB 1: MONACO EDITOR */}
            {activeTab === 'editor' && (
              <div className="h-full flex flex-col">
                {selectedFile ? (
                  <>
                    <div className="px-3 py-1 bg-slate-900 border-b border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                      <span className="font-mono text-slate-300">{selectedFile}</span>
                      <span className="text-slate-500 font-mono uppercase">{detectLanguage(selectedFile)}</span>
                    </div>
                    <div className="flex-1 overflow-hidden">
                      <MonacoEditorView
                        value={fileContent}
                        language={detectLanguage(selectedFile)}
                        readOnly={false}
                        onChange={(val) => setFileContent(val || '')}
                      />
                    </div>
                  </>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4 text-slate-500">
                    <FileCode className="w-10 h-10 text-slate-600" />
                    <div className="space-y-1">
                      <h4 className="text-sm font-semibold text-slate-300">No File Open</h4>
                      <p className="text-xs max-w-xs">
                        Select a file from the Files tab, or ask ChatGPT to create/edit code to inspect it here in Monaco.
                      </p>
                    </div>
                    <button
                      onClick={() => setActiveTab('files')}
                      className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded border border-slate-700 transition"
                    >
                      Browse Workspace Files
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: WORKSPACE FILE EXPLORER */}
            {activeTab === 'files' && (
              <div className="h-full flex flex-col p-3 overflow-hidden">
                <input
                  type="text"
                  placeholder="Filter files..."
                  value={fileFilter}
                  onChange={(e) => setFileFilter(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 mb-2 focus:outline-none focus:border-emerald-500"
                />
                <div className="flex-1 overflow-y-auto space-y-1 pr-1 font-mono text-xs">
                  {manifest?.files
                    .filter((f) => f.path.toLowerCase().includes(fileFilter.toLowerCase()))
                    .map((f, fIdx) => (
                      <div
                        key={fIdx}
                        onClick={() => handleOpenFile(f.path)}
                        className={`flex items-center justify-between px-2.5 py-1.5 rounded cursor-pointer transition ${
                          selectedFile === f.path
                            ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                            : 'hover:bg-slate-800/70 text-slate-300'
                        }`}
                      >
                        <div className="flex items-center gap-2 overflow-hidden">
                          <FileCode className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span className="truncate">{f.path}</span>
                        </div>
                        <span className="text-[10px] text-slate-500 shrink-0">
                          {(f.size_bytes / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    ))}
                  {(!manifest?.files || manifest.files.length === 0) && (
                    <div className="text-xs text-slate-500 text-center py-8">
                      No files found in workspace root.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 3: TERMINAL LOGS */}
            {activeTab === 'terminal' && (
              <div className="h-full p-3 font-mono text-xs overflow-y-auto bg-black/80 text-slate-300 space-y-2">
                <div className="text-[11px] text-emerald-400 font-bold mb-2">
                  === Agent Execution Log & Diagnostic Stream ===
                </div>
                {messages
                  .filter((m) => m.executed_commands && m.executed_commands.length > 0)
                  .flatMap((m) => m.executed_commands || [])
                  .map((cmd, i) => (
                    <div key={i} className="border-b border-slate-900 pb-2 space-y-1">
                      <div className="flex items-center gap-2 text-slate-400">
                        <span className="text-emerald-400 font-bold">&gt;</span>
                        <span className="text-slate-100">{cmd.command}</span>
                        <span
                          className={`text-[10px] px-1 rounded ${
                            cmd.passed || cmd.exit_code === 0 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                          }`}
                        >
                          exit: {cmd.exit_code} ({cmd.duration_ms}ms)
                        </span>
                      </div>
                      {cmd.stdout && <pre className="whitespace-pre-wrap text-slate-300 pl-4">{cmd.stdout}</pre>}
                      {cmd.stderr && <pre className="whitespace-pre-wrap text-rose-300 pl-4">{cmd.stderr}</pre>}
                    </div>
                  ))}
                {messages.filter((m) => m.executed_commands && m.executed_commands.length > 0).length === 0 && (
                  <div className="text-slate-500 italic py-6 text-center">
                    No commands executed yet in this session.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

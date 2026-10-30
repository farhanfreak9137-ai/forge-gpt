import React, { useEffect, useState } from 'react';
import { Cpu, Shield, Save, CheckCircle, AlertTriangle, RefreshCw } from 'lucide-react';
import { api } from '../../services/api';
import { AppSettings, ConnectorInfo } from '../../types';
import { useAppStore } from '../../stores/useAppStore';

export const SettingsPage: React.FC = () => {
  const { settings, setSettings } = useAppStore();
  const [formData, setFormData] = useState<Partial<AppSettings>>({});
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');

  const loadSettings = async () => {
    try {
      const s = await api.getSettings();
      setSettings(s);
      setFormData(s);
      const conns = await api.getConnectors();
      setConnectors(conns);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = { ...formData };
      if (apiKeyInput) {
        (payload as any).openai_api_key = apiKeyInput;
      }
      await api.updateSettings(payload);
      await loadSettings();
      alert('Settings updated successfully');
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnector = async (name: string) => {
    setTesting(true);
    try {
      const res = await api.testConnector(name);
      setTestResult(res);
    } catch (e: any) {
      setTestResult({ name, available: false, error: e.message });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">System Settings & Connectors</h1>
        <p className="text-sm text-slate-400 mt-1">Configure external AI reasoning engines, sandboxing, and execution policies.</p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* AI Connector Configuration */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Cpu className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-semibold text-slate-200">AI Reasoning Engine</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-400">Active Connector</label>
              <select
                value={formData.default_ai_connector || 'mock'}
                onChange={(e) => setFormData({ ...formData, default_ai_connector: e.target.value })}
                className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200"
              >
                <option value="mock">Deterministic Mock Provider (Offline / Testing)</option>
                <option value="openai">OpenAI-Compatible HTTP Endpoint (Local / Cloud)</option>
                <option value="ollama">Local Ollama Model Server</option>
                <option value="browser_handoff">Manual Browser Handoff (Copy/Paste)</option>
                <option value="browser_automation">Playwright Permitted Browser Automation</option>
                <option value="chatgpt_edge">Playwright Microsoft Edge (ChatGPT Web)</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400">OpenAI / Model Base URL</label>
              <input
                type="text"
                value={formData.openai_base_url || ''}
                onChange={(e) => setFormData({ ...formData, openai_base_url: e.target.value })}
                placeholder="https://api.openai.com/v1"
                className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 font-mono text-xs"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400">Model ID / Name</label>
              <input
                type="text"
                value={formData.openai_model_id || ''}
                onChange={(e) => setFormData({ ...formData, openai_model_id: e.target.value })}
                placeholder="gpt-4o or local-model"
                className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 font-mono text-xs"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400">
                API Key {formData.has_openai_key && <span className="text-emerald-400 font-normal">(Configured)</span>}
              </label>
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder={formData.has_openai_key ? '••••••••••••••••' : 'Enter API Key if required'}
                className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 font-mono text-xs"
              />
            </div>
          </div>

          <div className="pt-2 flex items-center justify-between">
            <button
              type="button"
              disabled={testing}
              onClick={() => handleTestConnector(formData.default_ai_connector || 'mock')}
              className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-semibold border border-slate-700"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${testing ? 'animate-spin' : ''}`} />
              <span>Test Current Connector</span>
            </button>

            {testResult && (
              <div className="text-xs flex items-center gap-2">
                {testResult.available ? (
                  <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                    <CheckCircle className="w-3.5 h-3.5" />
                    <span>Connection Verified Online</span>
                  </span>
                ) : (
                  <span className="text-rose-400 flex items-center gap-1 font-semibold">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Endpoint Offline or Unreachable</span>
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Sandboxing & Execution Safety */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Shield className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-semibold text-slate-200">Execution Safety & Boundaries</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-400">Execution Mode</label>
              <select
                value={formData.execution_mode || 'native'}
                onChange={(e) => setFormData({ ...formData, execution_mode: e.target.value })}
                className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200"
              >
                <option value="native">Native Windows Execution (Allowlist Guarded)</option>
                <option value="docker">Docker Container Isolation (Optional)</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400">Max Repair Attempts</label>
              <input
                type="number"
                min="1"
                max="10"
                value={formData.max_repair_attempts || 4}
                onChange={(e) => setFormData({ ...formData, max_repair_attempts: Number(e.target.value) })}
                className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-sm font-bold shadow-sm"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving...' : 'Save Configuration'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};


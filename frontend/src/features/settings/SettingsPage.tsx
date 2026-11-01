import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, CheckCircle2, Cpu, Palette, RefreshCw, Save, Shield, TriangleAlert } from 'lucide-react';
import { api } from '../../services/api';
import { CONNECTORS, connectorMeta } from '../../lib/connectors';
import { cn } from '../../lib/cn';
import { ACCENTS, useTheme } from '../../lib/theme';
import { useDocumentTitle } from '../../lib/hooks';
import { AppSettings } from '../../types';
import { useAppStore } from '../../stores/useAppStore';
import { Page } from '../../components/layout/AppShell';
import { Button, Card, ErrorState, Field, Input, PageHeader, Segmented, Select, Skeleton, useToast } from '../../components/ui';

const KEYS = [
  'default_ai_connector',
  'openai_base_url',
  'openai_model_id',
  'ollama_base_url',
  'ollama_model_id',
  'execution_mode',
  'max_repair_attempts',
] as const;

type TestState = { name: string; ok: boolean; message?: string } | null;

export const SettingsPage: React.FC = () => {
  useDocumentTitle('Settings');
  const toast = useToast();
  const setSettings = useAppStore((s) => s.setSettings);
  const { mode, accent, setMode, setAccent } = useTheme();

  const [initial, setInitial] = useState<AppSettings | null>(null);
  const [form, setForm] = useState<Partial<AppSettings>>({});
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestState>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const s = await api.getSettings();
      setSettings(s);
      setInitial(s);
      setForm(s);
      setApiKey('');
    } catch (e: any) {
      setError(e.message || 'Could not load settings.');
    }
  }, [setSettings]);

  useEffect(() => {
    load();
  }, [load]);

  const set = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    if (key === 'default_ai_connector') setTestResult(null);
  };

  const dirty = useMemo(() => {
    if (!initial) return false;
    return !!apiKey || KEYS.some((k) => form[k] !== initial[k]);
  }, [form, initial, apiKey]);

  const connector = form.default_ai_connector || 'mock';
  const meta = connectorMeta(connector);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!initial) return;
    setSaving(true);
    try {
      const changes: Record<string, unknown> = {};
      KEYS.forEach((k) => {
        if (form[k] !== initial[k]) changes[k] = form[k];
      });
      if (apiKey) changes.openai_api_key = apiKey;
      await api.updateSettings(changes as Partial<AppSettings>);
      await load();
      toast.success('Settings saved.');
    } catch (err: any) {
      toast.error(`Could not save settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.testConnector(connector);
      setTestResult({ name: connector, ok: !!res.available, message: res.error });
    } catch (e: any) {
      setTestResult({ name: connector, ok: false, message: e.message });
    } finally {
      setTesting(false);
    }
  };

  if (error) {
    return (
      <Page width="md">
        <PageHeader title="Settings" />
        <ErrorState title="Couldn't load settings" message={error} onRetry={load} />
      </Page>
    );
  }

  if (!initial) {
    return (
      <Page width="md">
        <PageHeader title="Settings" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-40 w-full" />
      </Page>
    );
  }

  return (
    <Page width="md">
      <PageHeader title="Settings" description="Choose the AI engine and how much freedom the agent gets." />

      <Card className="space-y-5 p-5">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-100">
          <Palette className="h-5 w-5 text-brand-400" aria-hidden /> Make it yours
        </h2>
        <div className="space-y-2">
          <span className="block text-sm font-medium text-slate-200">Theme</span>
          <Segmented
            ariaLabel="Theme"
            value={mode}
            onChange={setMode}
            options={[
              { value: 'system', label: 'Match my device' },
              { value: 'light', label: 'Light' },
              { value: 'dark', label: 'Dark' },
            ]}
          />
        </div>
        <div className="space-y-2">
          <span className="block text-sm font-medium text-slate-200">Accent colour</span>
          <div role="radiogroup" aria-label="Accent colour" className="flex flex-wrap gap-3">
            {ACCENTS.map((a) => (
              <button
                key={a.value}
                type="button"
                role="radio"
                aria-checked={accent === a.value}
                onClick={() => setAccent(a.value)}
                className={cn(
                  'flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-all hover:-translate-y-0.5',
                  accent === a.value ? 'border-brand-500 bg-brand-500/10 text-slate-50' : 'border-slate-700 text-slate-300 hover:border-slate-500',
                )}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full" style={{ background: a.swatch }}>
                  {accent === a.value && <Check className="h-3.5 w-3.5 text-white" aria-hidden />}
                </span>
                {a.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-400">Changes apply instantly and are remembered on this device.</p>
        </div>
      </Card>

      <form onSubmit={handleSave} className="space-y-6 pb-24">
        <Card className="space-y-5 p-5">
          <h2 className="flex items-center gap-2 text-base font-semibold text-slate-100">
            <Cpu className="h-5 w-5 text-brand-400" aria-hidden /> AI engine
          </h2>

          <Field label="Engine" htmlFor="s-connector" hint={meta.description}>
            <Select id="s-connector" value={connector} onChange={(e) => set('default_ai_connector', e.target.value)}>
              {CONNECTORS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Field>

          {connector === 'openai' && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Base URL" htmlFor="s-url" hint="Include /v1 for OpenAI-style APIs." className="sm:col-span-2">
                <Input
                  id="s-url"
                  value={form.openai_base_url || ''}
                  onChange={(e) => set('openai_base_url', e.target.value)}
                  placeholder="https://api.openai.com/v1"
                  className="font-mono text-[13px]"
                />
              </Field>
              <Field label="Model" htmlFor="s-model">
                <Input id="s-model" value={form.openai_model_id || ''} onChange={(e) => set('openai_model_id', e.target.value)} placeholder="gpt-4o" className="font-mono text-[13px]" />
              </Field>
              <Field
                label="API key"
                htmlFor="s-key"
                hint={initial.has_openai_key ? 'A key is saved. Leave blank to keep it.' : 'Only needed if your endpoint requires one.'}
              >
                <Input
                  id="s-key"
                  type="password"
                  autoComplete="off"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={initial.has_openai_key ? '••••••••••••••••' : 'Paste your key'}
                  className="font-mono text-[13px]"
                />
              </Field>
            </div>
          )}

          {connector === 'ollama' && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Server URL" htmlFor="s-ollama-url">
                <Input
                  id="s-ollama-url"
                  value={form.ollama_base_url || ''}
                  onChange={(e) => set('ollama_base_url', e.target.value)}
                  placeholder="http://localhost:11434"
                  className="font-mono text-[13px]"
                />
              </Field>
              <Field label="Model" htmlFor="s-ollama-model">
                <Input
                  id="s-ollama-model"
                  value={form.ollama_model_id || ''}
                  onChange={(e) => set('ollama_model_id', e.target.value)}
                  placeholder="llama3"
                  className="font-mono text-[13px]"
                />
              </Field>
            </div>
          )}

          {(connector === 'chatgpt_edge' || connector === 'browser_automation') && (
            <p className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2.5 text-sm text-slate-300">
              No keys needed. Open Agent Studio and use <strong>Open Edge to log in</strong> once so ForgeAgent can use your ChatGPT session.
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 pt-4">
            <Button icon={<RefreshCw className={testing ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />} onClick={handleTest} disabled={testing || dirty} title={dirty ? 'Save your changes first' : undefined}>
              Test connection
            </Button>
            {dirty && <span className="text-xs text-slate-400">Save first, then test.</span>}
            {testResult && (
              <span role="status" className={testResult.ok ? 'flex items-center gap-1.5 text-sm font-medium text-emerald-300' : 'flex items-center gap-1.5 text-sm font-medium text-rose-300'}>
                {testResult.ok ? <CheckCircle2 className="h-4 w-4" aria-hidden /> : <TriangleAlert className="h-4 w-4" aria-hidden />}
                {testResult.ok ? `${connectorMeta(testResult.name).short} is reachable` : `Can't reach ${connectorMeta(testResult.name).short}${testResult.message ? `: ${testResult.message}` : ''}`}
              </span>
            )}
          </div>
        </Card>

        <Card className="space-y-5 p-5">
          <h2 className="flex items-center gap-2 text-base font-semibold text-slate-100">
            <Shield className="h-5 w-5 text-brand-400" aria-hidden /> Safety
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Where commands run" htmlFor="s-mode" hint="Native runs on your machine with a strict allowlist. Docker isolation is not available yet.">
              <Select id="s-mode" value={form.execution_mode || 'native'} onChange={(e) => set('execution_mode', e.target.value)}>
                <option value="native">On this computer (allowlist guarded)</option>
                <option value="docker" disabled>
                  In a Docker container (coming soon)
                </option>
              </Select>
            </Field>
            <Field label="Max fix attempts" htmlFor="s-repair" hint="How many times the agent retries after a failure (1 to 10).">
              <Input
                id="s-repair"
                type="number"
                min={1}
                max={10}
                value={form.max_repair_attempts ?? 4}
                onChange={(e) => set('max_repair_attempts', Math.min(10, Math.max(1, Number(e.target.value) || 1)))}
              />
            </Field>
          </div>
        </Card>

        {/* Sticky save bar: always shows whether there is something unsaved */}
        <div className="fixed inset-x-0 bottom-0 z-10 border-t border-slate-800 bg-slate-900/95 px-4 py-3 backdrop-blur lg:left-60">
          <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
            <span className={dirty ? 'text-sm font-medium text-amber-300' : 'text-sm text-slate-400'}>{dirty ? 'You have unsaved changes' : 'All changes saved'}</span>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                disabled={!dirty || saving}
                onClick={() => {
                  setForm(initial);
                  setApiKey('');
                  setTestResult(null);
                }}
              >
                Discard
              </Button>
              <Button type="submit" variant="primary" icon={<Save className="h-4 w-4" />} loading={saving} disabled={!dirty}>
                Save changes
              </Button>
            </div>
          </div>
        </div>
      </form>
    </Page>
  );
};

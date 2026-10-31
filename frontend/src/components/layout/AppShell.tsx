import React, { useEffect } from 'react';
import { WifiOff } from 'lucide-react';
import { api } from '../../services/api';
import { useAppStore } from '../../stores/useAppStore';
import { Navbar, EmergencyBanner } from './Navbar';
import { Sidebar } from './Sidebar';
import { CommandPalette } from './CommandPalette';
import { ConfettiHost } from '../ui';

const POLL_MS = 8000;

/** Keeps backend status, emergency-stop state and pending approvals fresh for the whole app. */
function useSystemStatus() {
  const { setBackendOnline, setSettings, setEmergencyStop, setPendingApprovalCount } = useAppStore();

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const s = await api.getSettings();
        if (cancelled) return;
        setBackendOnline(true);
        setSettings(s);
        setEmergencyStop(s.emergency_stop_active);
        const approvals = await api.getApprovals().catch(() => []);
        if (!cancelled) setPendingApprovalCount(approvals.filter((a) => a.status === 'PENDING').length);
      } catch {
        if (!cancelled) setBackendOnline(false);
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    const onVisible = () => document.visibilityState === 'visible' && tick();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [setBackendOnline, setSettings, setEmergencyStop, setPendingApprovalCount]);
}

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const backendOnline = useAppStore((s) => s.backendOnline);
  useSystemStatus();

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      <a
        href="#main"
        className="sr-only z-[70] rounded-lg bg-brand-600 px-3 py-2 text-white focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Skip to content
      </a>
      <Navbar />
      <EmergencyBanner />
      <CommandPalette />
      <ConfettiHost />
      {!backendOnline && (
        <div role="alert" className="flex items-center gap-2 border-b border-amber-500/40 bg-amber-950 px-4 py-2 text-sm text-amber-100">
          <WifiOff className="h-4 w-4 shrink-0 text-amber-300" aria-hidden />
          <span>
            <strong>Can't reach the ForgeAgent backend.</strong> Make sure it is running on port 8000. This page retries automatically.
          </span>
        </div>
      )}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Sidebar />
        <main id="main" tabIndex={-1} className="min-w-0 flex-1 overflow-y-auto bg-[radial-gradient(60rem_26rem_at_50%_-8rem,rgb(var(--brand-500)/0.13),transparent)] focus:outline-none">
          {children}
        </main>
      </div>
    </div>
  );
};

/** Padded, centred container for scrolling pages. */
export const Page: React.FC<{ children: React.ReactNode; width?: 'md' | 'lg' | 'xl' }> = ({ children, width = 'xl' }) => (
  <div
    className={
      'mx-auto w-full space-y-6 p-4 sm:p-6 lg:p-8 ' +
      (width === 'md' ? 'max-w-3xl' : width === 'lg' ? 'max-w-5xl' : 'max-w-6xl')
    }
  >
    {children}
  </div>
);

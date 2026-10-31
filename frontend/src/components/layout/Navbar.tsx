import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Menu as MenuIcon, Moon, Monitor, OctagonAlert, Palette, Play, Search, Sun } from 'lucide-react';
import { cn } from '../../lib/cn';
import { usePalette } from '../../lib/palette';
import { ACCENTS, useTheme } from '../../lib/theme';
import { useAppStore } from '../../stores/useAppStore';
import { api } from '../../services/api';
import { Button, IconButton, Menu, useConfirm, useToast } from '../ui';
import { Mascot, Mood } from '../ui/Mascot';

export const useEmergencyStop = () => {
  const { isEmergencyStopActive, setEmergencyStop } = useAppStore();
  const confirm = useConfirm();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    const next = !isEmergencyStopActive;
    // Stopping is instant (it is an emergency). Resuming asks first.
    if (!next) {
      const ok = await confirm({
        title: 'Resume the agent?',
        message: 'The agent will be allowed to run commands and change files again.',
        confirmLabel: 'Resume agent',
      });
      if (!ok) return;
    }
    setBusy(true);
    try {
      const res = await api.toggleEmergencyStop(next);
      setEmergencyStop(res.emergency_stop_active);
      // Stopping is announced by the red banner; only resuming needs a toast
      if (!res.emergency_stop_active) toast.success('Agent resumed. Back to work!');
    } catch (e: any) {
      toast.error(`Could not change emergency stop: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return { active: isEmergencyStopActive, busy, toggle };
};

const AppearanceMenu: React.FC = () => {
  const { mode, accent, resolved, setMode, setAccent } = useTheme();
  return (
    <Menu
      trigger={(p) => (
        <IconButton label="Appearance" {...p}>
          {resolved === 'light' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </IconButton>
      )}
      items={[
        { label: 'Light', icon: <Sun className="h-4 w-4" />, hint: mode === 'light' ? 'Current' : undefined, onSelect: () => setMode('light') },
        { label: 'Dark', icon: <Moon className="h-4 w-4" />, hint: mode === 'dark' ? 'Current' : undefined, onSelect: () => setMode('dark') },
        { label: 'Match my device', icon: <Monitor className="h-4 w-4" />, hint: mode === 'system' ? 'Current' : undefined, onSelect: () => setMode('system') },
        ...ACCENTS.map((a) => ({
          label: `${a.label} accent`,
          icon: (
            <span className="flex h-4 w-4 items-center justify-center rounded-full" style={{ background: a.swatch }}>
              {accent === a.value && <Check className="h-3 w-3 text-white" aria-hidden />}
            </span>
          ),
          hint: accent === a.value ? 'Current' : undefined,
          onSelect: () => setAccent(a.value),
        })),
      ]}
    />
  );
};

export const Navbar: React.FC = () => {
  const { currentProject, setMobileNavOpen, pendingApprovalCount, studioPendingCount } = useAppStore();
  const setPaletteOpen = usePalette((s) => s.setOpen);
  const stop = useEmergencyStop();
  const mood: Mood = stop.active ? 'sleeping' : pendingApprovalCount + studioPendingCount > 0 ? 'alert' : 'idle';

  return (
    <header className="z-20 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-3 sm:px-5">
      <div className="flex min-w-0 items-center gap-2 sm:gap-3">
        <IconButton label="Open menu" className="lg:hidden" onClick={() => setMobileNavOpen(true)} aria-controls="app-sidebar">
          <MenuIcon className="h-5 w-5" />
        </IconButton>
        <Link to="/" className="flex items-center gap-2 rounded-lg text-lg font-bold tracking-tight text-slate-50" aria-label="ForgeAgent home">
          <Mascot mood={mood} size={34} />
          <span>
            Forge<span className="text-brand-400">Agent</span>
          </span>
        </Link>
        {currentProject && (
          <Link
            to="/projects"
            className="hidden items-center gap-2 border-l border-slate-800 pl-3 text-sm text-slate-400 hover:text-slate-200 md:flex"
            title="Current project"
          >
            <span className="max-w-[14rem] truncate rounded-full bg-slate-800 px-3 py-0.5 font-medium text-slate-200">{currentProject.name}</span>
          </Link>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          className="hidden h-9 items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/60 px-3 text-sm text-slate-400 transition-colors hover:border-slate-600 hover:text-slate-100 md:flex"
          aria-label="Open command palette"
        >
          <Search className="h-4 w-4" aria-hidden />
          <span>Jump to…</span>
          <kbd className="rounded-md border border-slate-700 px-1.5 py-0.5 text-xs text-slate-400">Ctrl K</kbd>
        </button>
        <IconButton label="Search and commands (Ctrl K)" className="md:hidden" onClick={() => setPaletteOpen(true)}>
          <Search className="h-5 w-5" />
        </IconButton>

        <AppearanceMenu />

        <button
          type="button"
          onClick={stop.toggle}
          disabled={stop.busy}
          aria-pressed={stop.active}
          className={cn(
            'inline-flex h-9 items-center gap-2 rounded-xl border px-3 text-xs font-semibold uppercase tracking-wide transition-colors',
            stop.active
              ? 'border-rose-400 bg-rose-600 text-white hover:bg-rose-500'
              : 'border-rose-700/50 bg-rose-950/40 text-rose-300 hover:bg-rose-900/60',
          )}
          title={
            stop.active
              ? 'Emergency stop is ON. Click to resume the agent.'
              : 'Emergency stop: immediately block all agent commands and file changes'
          }
        >
          <OctagonAlert className="h-4 w-4" aria-hidden />
          <span className="hidden sm:inline">{stop.active ? 'Stopped' : 'Emergency stop'}</span>
          <span className="sm:hidden">{stop.active ? 'Stopped' : 'Stop'}</span>
        </button>
      </div>
    </header>
  );
};

export const EmergencyBanner: React.FC = () => {
  const stop = useEmergencyStop();
  if (!stop.active) return null;
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-2 border-b border-rose-500/50 bg-rose-950 px-4 py-2 text-sm text-rose-100">
      <div className="flex items-center gap-3">
        <Mascot mood="sleeping" size={30} />
        <span>
          <strong>Emergency stop is on.</strong> The agent is napping: it can't run commands or change files until you resume it.
        </span>
      </div>
      <Button size="sm" variant="secondary" icon={<Play className="h-3.5 w-3.5" />} onClick={stop.toggle} loading={stop.busy}>
        Resume agent
      </Button>
    </div>
  );
};

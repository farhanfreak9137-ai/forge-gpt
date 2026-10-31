import React, { useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Bot, LayoutDashboard, FolderGit2, ListChecks, PanelLeftClose, PanelLeftOpen, ScrollText, Settings, X } from 'lucide-react';
import { usePersistentState } from '../../lib/hooks';
import { cn } from '../../lib/cn';
import { useAppStore } from '../../stores/useAppStore';
import { IconButton } from '../ui';

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: number;
}

export const Sidebar: React.FC = () => {
  const { mobileNavOpen, setMobileNavOpen, pendingApprovalCount, studioPendingCount, backendOnline, settings } = useAppStore();
  const location = useLocation();
  const [collapsed, setCollapsed] = usePersistentState('forgeagent.sidebar.collapsed', false);

  // Close the drawer after navigating on small screens
  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname, setMobileNavOpen]);

  // Esc closes the drawer
  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMobileNavOpen(false);
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [mobileNavOpen, setMobileNavOpen]);

  const links: NavItem[] = [
    { to: '/', label: 'Agent Studio', icon: Bot, badge: studioPendingCount },
    { to: '/overview', label: 'Overview', icon: LayoutDashboard },
    { to: '/projects', label: 'Projects', icon: FolderGit2 },
    { to: '/workspace', label: 'Tasks', icon: ListChecks, badge: pendingApprovalCount },
    { to: '/activity', label: 'Activity', icon: ScrollText },
    { to: '/settings', label: 'Settings', icon: Settings },
  ];

  return (
    <>
      {mobileNavOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm animate-fade-in lg:hidden"
          onClick={() => setMobileNavOpen(false)}
          aria-hidden
        />
      )}
      <aside
        id="app-sidebar"
        aria-label="Main navigation"
        className={cn(
          'z-40 flex w-60 shrink-0 flex-col justify-between border-r border-slate-800 bg-slate-900 p-3 transition-[width] duration-200 select-none',
          collapsed && 'lg:w-[4.75rem]',
          'fixed inset-y-0 left-0 lg:static lg:bg-slate-900/50',
          mobileNavOpen ? 'flex animate-slide-in-left' : 'hidden lg:flex',
        )}
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between px-1 lg:hidden">
            <span className="text-sm font-semibold text-slate-200">Menu</span>
            <IconButton label="Close menu" size="sm" onClick={() => setMobileNavOpen(false)}>
              <X className="h-4 w-4" />
            </IconButton>
          </div>
          <nav className="space-y-1">
            {links.map(({ to, label, icon: Icon, badge }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                aria-label={label}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  cn(
                    'relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
                    collapsed && 'lg:justify-center lg:px-0',
                    isActive
                      ? 'bg-brand-500/10 text-brand-300 ring-1 ring-inset ring-brand-500/25'
                      : 'text-slate-300 hover:bg-slate-800/70 hover:text-slate-50',
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className={cn('flex-1', collapsed && 'lg:hidden')}>{label}</span>
                {!!badge && badge > 0 && (
                  <span
                    className={cn(
                      'inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-amber-500 px-1.5 text-xs font-bold text-slate-950',
                      collapsed && 'lg:absolute lg:right-1.5 lg:top-0.5 lg:min-w-[1rem] lg:px-1 lg:text-[10px]',
                    )}
                    aria-label={`${badge} waiting for approval`}
                    title={`${badge} waiting for your approval`}
                  >
                    {badge}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="space-y-2 border-t border-slate-800 pt-3 text-xs text-slate-400">
          <div className={cn('flex items-center gap-2 px-2', collapsed && 'lg:justify-center lg:px-0')} title={backendOnline ? 'Backend connected' : 'Backend offline'}>
            <span className={cn('h-2 w-2 shrink-0 rounded-full', backendOnline ? 'bg-emerald-500' : 'bg-rose-500')} aria-hidden />
            <span className={cn(collapsed && 'lg:hidden')}>{backendOnline ? 'Backend connected' : 'Backend offline'}</span>
          </div>
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className={cn(
              'hidden items-center gap-2 rounded-xl px-2 py-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50 lg:flex',
              collapsed ? 'w-full justify-center' : 'w-full',
            )}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            <span className={cn(collapsed && 'hidden')}>Collapse</span>
          </button>
        </div>
      </aside>
    </>
  );
};

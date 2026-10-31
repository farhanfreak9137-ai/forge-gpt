import React from 'react';
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Tone } from '../../lib/taskState';
import { Button } from './Button';

const TONES: Record<Tone, string> = {
  neutral: 'bg-slate-800 text-slate-300 border-slate-700',
  info: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
  success: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  warning: 'bg-amber-500/10 text-amber-300 border-amber-500/40',
  danger: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
};

const DOTS: Record<Tone, string> = {
  neutral: 'bg-slate-500',
  info: 'bg-sky-400',
  success: 'bg-emerald-400',
  warning: 'bg-amber-400',
  danger: 'bg-rose-400',
};

export const Badge: React.FC<{
  tone?: Tone;
  dot?: boolean;
  pulse?: boolean;
  className?: string;
  children: React.ReactNode;
}> = ({ tone = 'neutral', dot, pulse, className, children }) => (
  <span
    className={cn(
      'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium',
      TONES[tone],
      className,
    )}
  >
    {dot && <span className={cn('h-1.5 w-1.5 rounded-full', DOTS[tone], pulse && 'animate-pulse')} aria-hidden />}
    {children}
  </span>
);

export const Spinner: React.FC<{ className?: string; label?: string }> = ({ className, label = 'Loading' }) => (
  <Loader2 className={cn('h-4 w-4 animate-spin text-brand-400', className)} role="status" aria-label={label} />
);

export const Skeleton: React.FC<{ className?: string }> = ({ className }) => (
  <div className={cn('animate-pulse rounded-md bg-slate-800/70', className)} aria-hidden />
);

export const Card: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...rest }) => (
  <div className={cn('rounded-2xl border border-slate-800 bg-slate-900/70 shadow-sm', className)} {...rest} />
);

export const EmptyState: React.FC<{
  icon?: React.ReactNode;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}> = ({ icon, title, description, action, className }) => (
  <div className={cn('flex flex-col items-center justify-center gap-3 px-6 py-12 text-center', className)}>
    {icon && (
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900 text-slate-400">
        {icon}
      </div>
    )}
    <div className="space-y-1">
      <h3 className="text-base font-semibold text-slate-100">{title}</h3>
      {description && <p className="mx-auto max-w-sm text-sm leading-relaxed text-slate-400">{description}</p>}
    </div>
    {action}
  </div>
);

export const ErrorState: React.FC<{
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}> = ({ title = 'Something went wrong', message, onRetry, className }) => (
  <div
    role="alert"
    className={cn(
      'flex flex-col items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-950/20 px-6 py-8 text-center',
      className,
    )}
  >
    <AlertTriangle className="h-6 w-6 text-rose-400" aria-hidden />
    <div className="space-y-1">
      <h3 className="text-sm font-semibold text-rose-100">{title}</h3>
      {message && <p className="max-w-md text-sm text-rose-200/80">{message}</p>}
    </div>
    {onRetry && (
      <Button size="sm" icon={<RefreshCw className="h-3.5 w-3.5" />} onClick={onRetry}>
        Try again
      </Button>
    )}
  </div>
);

export const PageHeader: React.FC<{
  title: string;
  description?: string;
  actions?: React.ReactNode;
}> = ({ title, description, actions }) => (
  <div className="flex flex-wrap items-start justify-between gap-3">
    <div className="min-w-0">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-50">{title}</h1>
      {description && <p className="mt-1 text-sm text-slate-400">{description}</p>}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
  </div>
);

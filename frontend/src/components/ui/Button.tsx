import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'warning';
type Size = 'sm' | 'md' | 'lg';

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-gradient-to-b from-brand-500 to-brand-600 text-white shadow-md shadow-brand-600/25 hover:from-brand-400 hover:to-brand-500 active:translate-y-px disabled:bg-none disabled:bg-slate-800 disabled:text-slate-500 disabled:shadow-none',
  secondary:
    'bg-slate-800 text-slate-100 border border-slate-700 hover:bg-slate-700 hover:border-slate-600 disabled:bg-slate-900 disabled:text-slate-500',
  ghost: 'text-slate-300 hover:bg-slate-800 hover:text-slate-50 disabled:text-slate-600 disabled:hover:bg-transparent',
  danger:
    'bg-rose-600 text-white hover:bg-rose-500 active:bg-rose-700 disabled:bg-slate-800 disabled:text-slate-500',
  warning:
    'bg-amber-500/15 text-amber-200 border border-amber-500/40 hover:bg-amber-500/25 disabled:text-slate-500',
};

const SIZES: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-4 text-sm gap-2',
  lg: 'h-11 px-5 text-sm gap-2',
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'secondary', size = 'md', loading, icon, className, children, disabled, type = 'button', ...rest }, ref) => (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-xl font-medium transition-all',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  ),
);
Button.displayName = 'Button';

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  size?: 'sm' | 'md';
  variant?: 'ghost' | 'secondary';
}

/** Icon-only button. `label` is required so it always has an accessible name and tooltip. */
export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ label, size = 'md', variant = 'ghost', className, children, type = 'button', ...rest }, ref) => (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-lg transition-colors',
        size === 'sm' ? 'h-7 w-7' : 'h-9 w-9',
        variant === 'ghost'
          ? 'text-slate-400 hover:bg-slate-800 hover:text-slate-50 disabled:text-slate-600'
          : 'border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  ),
);
IconButton.displayName = 'IconButton';

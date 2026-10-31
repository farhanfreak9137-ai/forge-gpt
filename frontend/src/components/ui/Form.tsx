import React, { useId } from 'react';
import { cn } from '../../lib/cn';

const CONTROL =
  'w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 placeholder:text-slate-500 transition-colors ' +
  'hover:border-slate-600 focus-visible:border-brand-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500/40 ' +
  'disabled:cursor-not-allowed disabled:opacity-60';

export const Field: React.FC<{
  label: string;
  hint?: React.ReactNode;
  error?: string;
  htmlFor?: string;
  children: React.ReactNode;
  className?: string;
}> = ({ label, hint, error, htmlFor, children, className }) => (
  <div className={cn('space-y-1.5', className)}>
    <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-200">
      {label}
    </label>
    {children}
    {error ? (
      <p className="text-xs text-rose-400" role="alert">
        {error}
      </p>
    ) : (
      hint && <p className="text-xs text-slate-400">{hint}</p>
    )}
  </div>
);

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...rest }, ref) => <input ref={ref} className={cn(CONTROL, 'h-10', className)} {...rest} />,
);
Input.displayName = 'Input';

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...rest }, ref) => <textarea ref={ref} className={cn(CONTROL, 'py-2 leading-relaxed', className)} {...rest} />,
);
Textarea.displayName = 'Textarea';

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...rest }, ref) => (
    <select ref={ref} className={cn(CONTROL, 'h-10 pr-8', className)} {...rest}>
      {children}
    </select>
  ),
);
Select.displayName = 'Select';

/** On/off switch with a visible label. */
export const Switch: React.FC<{
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
  compact?: boolean;
  className?: string;
}> = ({ checked, onChange, label, description, compact, className }) => {
  const id = useId();
  return (
    <div className={cn('flex items-center gap-3', className)}>
      <button
        type="button"
        role="switch"
        id={id}
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative h-6 w-11 shrink-0 rounded-full border transition-colors',
          checked ? 'border-brand-500 bg-brand-600' : 'border-slate-600 bg-slate-700',
        )}
      >
        <span
          className={cn(
            'absolute left-0.5 top-0.5 h-4.5 w-4.5 rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-5' : 'translate-x-0',
          )}
          style={{ height: 18, width: 18 }}
          aria-hidden
        />
      </button>
      <label htmlFor={id} className="min-w-0 cursor-pointer select-none">
        <span className={cn('block font-medium text-slate-100', compact ? 'text-xs' : 'text-sm')}>{label}</span>
        {description && !compact && <span className="block text-xs text-slate-400">{description}</span>}
      </label>
    </div>
  );
};

/** Segmented control (single choice). Uses aria-pressed so state is announced. */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: Array<{ value: T; label: string; count?: number }>;
  ariaLabel: string;
  className?: string;
}) {
  return (
    <div role="group" aria-label={ariaLabel} className={cn('inline-flex flex-wrap gap-1 rounded-xl border border-slate-800 bg-slate-900 p-1', className)}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
            value === o.value ? 'bg-slate-700 text-slate-50 shadow-sm' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100',
          )}
        >
          {o.label}
          {o.count !== undefined && <span className="ml-1.5 text-slate-400">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

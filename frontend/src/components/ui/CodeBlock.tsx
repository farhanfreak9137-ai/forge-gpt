import React, { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { cn } from '../../lib/cn';

export function useCopy() {
  const [copied, setCopied] = useState(false);
  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked: nothing useful to do */
    }
  };
  return { copied, copy };
}

export const CopyButton: React.FC<{ text: string; label?: string; className?: string }> = ({ text, label = 'Copy', className }) => {
  const { copied, copy } = useCopy();
  return (
    <button
      type="button"
      onClick={() => copy(text)}
      aria-label={copied ? 'Copied' : label}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50',
        className,
      )}
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
      <span>{copied ? 'Copied' : label}</span>
    </button>
  );
};

export const CodeBlock: React.FC<{
  code: string;
  language?: string;
  maxHeight?: string;
  className?: string;
  tone?: 'default' | 'error';
}> = ({ code, language, maxHeight = '20rem', className, tone = 'default' }) => (
  <div className={cn('overflow-hidden rounded-lg border border-slate-800 bg-slate-950', className)}>
    <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900 px-3 py-1">
      <span className="font-mono text-xs text-slate-400">{language || 'text'}</span>
      <CopyButton text={code} />
    </div>
    <pre
      className={cn('overflow-auto p-3 font-mono text-[13px] leading-relaxed', tone === 'error' ? 'text-rose-200' : 'text-slate-100')}
      style={{ maxHeight }}
      tabIndex={0}
    >
      <code>{code}</code>
    </pre>
  </div>
);

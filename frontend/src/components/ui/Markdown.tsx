import React from 'react';
import { cn } from '../../lib/cn';
import { CodeBlock } from './CodeBlock';

/* A small, dependency-free, XSS-safe markdown renderer (no innerHTML).
   Supports: fenced code, headings, bullet/numbered lists, blockquotes, bold, italic, inline code, links. */

function safeHref(url: string): string | null {
  return /^(https?:|mailto:)/i.test(url.trim()) ? url.trim() : null;
}

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const re = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\[[^\]\n]+\]\([^)\s]+\))|(\*[^*\n]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    const key = `${keyPrefix}-${i++}`;
    if (tok.startsWith('`')) {
      nodes.push(
        <code key={key} className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[0.85em] text-emerald-200">
          {tok.slice(1, -1)}
        </code>,
      );
    } else if (tok.startsWith('**')) {
      nodes.push(
        <strong key={key} className="font-semibold text-slate-50">
          {tok.slice(2, -2)}
        </strong>,
      );
    } else if (tok.startsWith('[')) {
      const mm = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(tok)!;
      const href = safeHref(mm[2]);
      nodes.push(
        href ? (
          <a key={key} href={href} target="_blank" rel="noreferrer noopener" className="text-sky-300 underline underline-offset-2 hover:text-sky-200">
            {mm[1]}
          </a>
        ) : (
          mm[1]
        ),
      );
    } else {
      nodes.push(<em key={key}>{tok.slice(1, -1)}</em>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function renderTextBlock(text: string, keyPrefix: string): React.ReactNode[] {
  const lines = text.split('\n');
  const out: React.ReactNode[] = [];
  let i = 0;
  let k = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      out.push(
        <p
          key={`${keyPrefix}-${k++}`}
          className={cn('font-semibold text-slate-50', level <= 2 ? 'mt-3 text-base' : 'mt-2 text-sm')}
        >
          {renderInline(heading[2], `${keyPrefix}-h${k}`)}
        </p>,
      );
      i++;
      continue;
    }
    if (/^\s*[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*+]\s+/, ''));
      out.push(
        <ul key={`${keyPrefix}-${k++}`} className="my-1.5 list-disc space-y-1 pl-5 marker:text-slate-500">
          {items.map((it, n) => (
            <li key={n}>{renderInline(it, `${keyPrefix}-l${k}-${n}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*\d+[.)]\s+/, ''));
      out.push(
        <ol key={`${keyPrefix}-${k++}`} className="my-1.5 list-decimal space-y-1 pl-5 marker:text-slate-500">
          {items.map((it, n) => (
            <li key={n}>{renderInline(it, `${keyPrefix}-o${k}-${n}`)}</li>
          ))}
        </ol>,
      );
      continue;
    }
    if (/^>\s?/.test(line)) {
      const quote: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) quote.push(lines[i++].replace(/^>\s?/, ''));
      out.push(
        <blockquote key={`${keyPrefix}-${k++}`} className="my-1.5 border-l-2 border-slate-600 pl-3 text-slate-300">
          {renderInline(quote.join(' '), `${keyPrefix}-q${k}`)}
        </blockquote>,
      );
      continue;
    }
    // Paragraph: gather until blank line or block start
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^(#{1,4})\s+/.test(lines[i]) &&
      !/^\s*[-*+]\s+/.test(lines[i]) &&
      !/^\s*\d+[.)]\s+/.test(lines[i]) &&
      !/^>\s?/.test(lines[i])
    )
      para.push(lines[i++]);
    out.push(
      <p key={`${keyPrefix}-${k++}`} className="my-1.5 whitespace-pre-wrap">
        {renderInline(para.join('\n'), `${keyPrefix}-p${k}`)}
      </p>,
    );
  }
  return out;
}

export const Markdown: React.FC<{ text: string; className?: string }> = ({ text, className }) => {
  if (!text) return null;
  const parts = text.split(/(```[\s\S]*?```)/g);
  return (
    <div className={cn('break-words leading-relaxed', className)}>
      {parts.map((part, idx) => {
        if (part.startsWith('```') && part.endsWith('```') && part.length >= 6) {
          const nl = part.indexOf('\n');
          const lang = nl !== -1 ? part.slice(3, nl).trim() : '';
          const code = (nl !== -1 ? part.slice(nl + 1, -3) : part.slice(3, -3)).replace(/\s+$/, '');
          return <CodeBlock key={idx} code={code} language={lang} className="my-2" maxHeight="22rem" />;
        }
        return <React.Fragment key={idx}>{renderTextBlock(part, `t${idx}`)}</React.Fragment>;
      })}
    </div>
  );
};

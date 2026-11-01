import React from 'react';
import { useTheme } from '../../lib/theme';
import { DiffEditor } from '@monaco-editor/react';

interface MonacoDiffViewProps {
  original: string;
  modified: string;
  language?: string;
  height?: string;
}

export const MonacoDiffView: React.FC<MonacoDiffViewProps> = ({
  original,
  modified,
  language = 'python',
  height = '100%',
}) => {
  const { resolved } = useTheme();
  return (
    <div className="w-full h-full border border-slate-800 rounded-md overflow-hidden bg-slate-950">
      <DiffEditor
        height={height}
        language={language}
        original={original}
        modified={modified}
        theme={resolved === 'light' ? 'light' : 'vs-dark'}
        options={{
          readOnly: true,
          renderSideBySide: true,
          minimap: { enabled: false },
          fontSize: 13,
          fontFamily: 'Consolas, "Fira Code", monospace',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          padding: { top: 10, bottom: 10 },
        }}
      />
    </div>
  );
};


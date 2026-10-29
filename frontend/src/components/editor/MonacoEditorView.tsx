import React from 'react';
import Editor from '@monaco-editor/react';

interface MonacoEditorViewProps {
  value: string;
  language?: string;
  readOnly?: boolean;
  onChange?: (val: string | undefined) => void;
  height?: string;
}

export const MonacoEditorView: React.FC<MonacoEditorViewProps> = ({
  value,
  language = 'python',
  readOnly = true,
  onChange,
  height = '100%',
}) => {
  return (
    <div className="w-full h-full border border-slate-800 rounded-md overflow-hidden bg-slate-950">
      <Editor
        height={height}
        language={language}
        value={value}
        theme="vs-dark"
        onChange={onChange}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          fontFamily: 'Consolas, "Fira Code", monospace',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          renderWhitespace: 'selection',
          padding: { top: 10, bottom: 10 },
        }}
      />
    </div>
  );
};

import React from 'react';
import { stateInfo } from '../../lib/taskState';
import { Badge } from './Feedback';

export const StateBadge: React.FC<{ state: string; className?: string }> = ({ state, className }) => {
  const info = stateInfo(state);
  return (
    <Badge tone={info.tone} dot pulse={info.running || info.needsYou} className={className}>
      {info.label}
    </Badge>
  );
};

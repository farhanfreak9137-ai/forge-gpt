import React from 'react';
import { ShieldAlert, Cpu, Activity, AlertOctagon } from 'lucide-react';
import { useAppStore } from '../../stores/useAppStore';
import { api } from '../../services/api';

export const Navbar: React.FC = () => {
  const { currentProject, isEmergencyStopActive, setEmergencyStop, settings } = useAppStore();

  const handleToggleEmergencyStop = async () => {
    try {
      const nextState = !isEmergencyStopActive;
      const res = await api.toggleEmergencyStop(nextState);
      setEmergencyStop(res.emergency_stop_active);
    } catch (e) {
      console.error('Failed to toggle emergency stop', e);
    }
  };

  return (
    <header className="h-14 border-b border-slate-800 bg-slate-900 px-6 flex items-center justify-between z-10">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 font-bold tracking-wide text-emerald-400 text-lg">
          <Cpu className="w-5 h-5 text-emerald-400" />
          <span>ForgeAgent <span className="text-xs bg-emerald-500/10 text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-500/20">V1</span></span>
        </div>
        {currentProject && (
          <div className="hidden md:flex items-center gap-2 pl-4 border-l border-slate-800 text-xs text-slate-400">
            <span>Project:</span>
            <span className="font-semibold text-slate-200 bg-slate-800 px-2 py-0.5 rounded">{currentProject.name}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* Connector Status */}
        <div className="flex items-center gap-2 text-xs bg-slate-800 px-2.5 py-1 rounded-full border border-slate-700 text-slate-300">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>AI: <strong className="text-slate-100">{settings?.default_ai_connector || 'mock'}</strong></span>
        </div>

        {/* Emergency Stop Button */}
        <button
          onClick={handleToggleEmergencyStop}
          className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-bold uppercase tracking-wider transition-colors border ${
            isEmergencyStopActive
              ? 'bg-rose-600 text-white border-rose-500 animate-bounce'
              : 'bg-rose-950/40 text-rose-400 border-rose-800/60 hover:bg-rose-900/60'
          }`}
          title="Emergency Stop: Halt all agent execution and block new operations"
        >
          <AlertOctagon className="w-4 h-4" />
          <span>{isEmergencyStopActive ? 'E-STOP ACTIVE' : 'EMERGENCY STOP'}</span>
        </button>
      </div>
    </header>
  );
};


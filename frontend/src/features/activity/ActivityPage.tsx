import React, { useEffect, useState } from 'react';
import { ListFilter, Search, RefreshCw, AlertCircle, CheckCircle, Info } from 'lucide-react';
import { api } from '../../services/api';
import { ActivityEvent } from '../../types';

export const ActivityPage: React.FC = () => {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [filterSeverity, setFilter] = useState<string>('ALL');
  const [searchQuery, setSearch] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const data = await api.getEvents();
      setEvents(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const filtered = events.filter((ev) => {
    if (filterSeverity !== 'ALL' && ev.severity !== filterSeverity) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        ev.event_type.toLowerCase().includes(q) ||
        ev.message.toLowerCase().includes(q) ||
        (ev.task_id && ev.task_id.toLowerCase().includes(q))
      );
    }
    return true;
  });

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Audit & Activity Log</h1>
          <p className="text-sm text-slate-400 mt-1">Structured chronological event stream and supervisory audit trail.</p>
        </div>
        <button
          onClick={loadEvents}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-medium border border-slate-700"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-4 bg-slate-900 border border-slate-800 p-3 rounded-lg">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search events by type, message, or task ID..."
            value={searchQuery}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500"
          />
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-500 font-semibold">Severity:</span>
          {['ALL', 'INFO', 'WARNING', 'ERROR', 'SUCCESS'].map((sev) => (
            <button
              key={sev}
              onClick={() => setFilter(sev)}
              className={`px-2.5 py-1 rounded font-semibold text-[11px] ${
                filterSeverity === sev
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Events Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
        {filtered.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-sm">No activity events found.</div>
        ) : (
          <div className="divide-y divide-slate-800 font-mono text-xs">
            {filtered.map((ev, idx) => (
              <div key={ev.id || idx} className="p-3.5 flex items-start justify-between hover:bg-slate-850/50">
                <div className="flex items-start gap-3">
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase mt-0.5 ${
                      ev.severity === 'SUCCESS'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : ev.severity === 'ERROR'
                        ? 'bg-rose-950 text-rose-400 border border-rose-800'
                        : ev.severity === 'WARNING'
                        ? 'bg-amber-950 text-amber-400 border border-amber-800'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}
                  >
                    {ev.severity}
                  </span>
                  <div>
                    <div className="font-bold text-slate-200">{ev.event_type}</div>
                    <div className="text-slate-400 mt-0.5">{ev.message}</div>
                    {ev.task_id && (
                      <div className="text-[11px] text-slate-600 mt-1">Task: {ev.task_id}</div>
                    )}
                  </div>
                </div>
                <div className="text-right text-[11px] text-slate-500 space-y-1">
                  <div>#{ev.sequence_number || '-'}</div>
                  <div>{new Date(ev.timestamp).toLocaleTimeString()}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};


import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { Project, TaskDetail, ActivityEvent, AppSettings } from '../types';

interface AppState {
  currentProject: Project | null;
  activeTask: TaskDetail | null;
  activeTaskId: string | null; // persisted, so a page reload can reload the task the user was watching
  events: ActivityEvent[];
  settings: AppSettings | null;
  isEmergencyStopActive: boolean;

  // Live status (not persisted)
  backendOnline: boolean;
  pendingApprovalCount: number; // task approvals waiting for a decision
  studioPendingCount: number; // Studio actions waiting for a decision
  mobileNavOpen: boolean;

  setCurrentProject: (project: Project | null) => void;
  setActiveTask: (task: TaskDetail | null) => void;
  addEvent: (event: ActivityEvent) => void;
  setEvents: (events: ActivityEvent[]) => void;
  setSettings: (settings: AppSettings | null) => void;
  setEmergencyStop: (active: boolean) => void;
  setBackendOnline: (online: boolean) => void;
  setPendingApprovalCount: (count: number) => void;
  setStudioPendingCount: (count: number) => void;
  setMobileNavOpen: (open: boolean) => void;
}

export const useAppStore = create<AppState>()(persist((set) => ({
  currentProject: null,
  activeTask: null,
  activeTaskId: null,
  events: [],
  settings: null,
  isEmergencyStopActive: false,
  backendOnline: true,
  pendingApprovalCount: 0,
  studioPendingCount: 0,
  mobileNavOpen: false,

  setCurrentProject: (project) => set({ currentProject: project }),
  setActiveTask: (task) => set({ activeTask: task, activeTaskId: task?.id ?? null }),
  addEvent: (event) =>
    set((state) => ({
      events: [event, ...state.events].slice(0, 500),
    })),
  setEvents: (events) => set({ events }),
  setSettings: (settings) => set({ settings }),
  setEmergencyStop: (active) => set({ isEmergencyStopActive: active }),
  setBackendOnline: (online) => set({ backendOnline: online }),
  setPendingApprovalCount: (count) => set({ pendingApprovalCount: count }),
  setStudioPendingCount: (count) => set({ studioPendingCount: count }),
  setMobileNavOpen: (open) => set({ mobileNavOpen: open }),
}), {
  name: 'forgeagent-ui',
  storage: createJSONStorage(() => localStorage),
  partialize: (state) => ({ currentProject: state.currentProject, activeTaskId: state.activeTaskId }),
}));

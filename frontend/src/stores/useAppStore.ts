import { create } from 'zustand';
import { Project, Task, TaskDetail, ActivityEvent, AppSettings } from '../types';

interface AppState {
  currentProject: Project | null;
  activeTask: TaskDetail | null;
  events: ActivityEvent[];
  settings: AppSettings | null;
  isEmergencyStopActive: boolean;

  setCurrentProject: (project: Project | null) => void;
  setActiveTask: (task: TaskDetail | null) => void;
  addEvent: (event: ActivityEvent) => void;
  setEvents: (events: ActivityEvent[]) => void;
  setSettings: (settings: AppSettings | null) => void;
  setEmergencyStop: (active: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentProject: null,
  activeTask: null,
  events: [],
  settings: null,
  isEmergencyStopActive: false,

  setCurrentProject: (project) => set({ currentProject: project }),
  setActiveTask: (task) => set({ activeTask: task }),
  addEvent: (event) =>
    set((state) => ({
      events: [event, ...state.events].slice(0, 500),
    })),
  setEvents: (events) => set({ events }),
  setSettings: (settings) => set({ settings }),
  setEmergencyStop: (active) => set({ isEmergencyStopActive: active }),
}));


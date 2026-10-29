import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navbar } from './components/layout/Navbar';
import { Sidebar } from './components/layout/Sidebar';
import { OverviewPage } from './features/dashboard/OverviewPage';
import { ProjectsPage } from './features/projects/ProjectsPage';
import { TaskWorkspacePage } from './features/tasks/TaskWorkspacePage';
import { ActivityPage } from './features/activity/ActivityPage';
import { SettingsPage } from './features/settings/SettingsPage';

const queryClient = new QueryClient();

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 text-slate-100">
          <Navbar />
          <div className="flex flex-1 overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto">
              <Routes>
                <Route path="/" element={<OverviewPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/workspace" element={<TaskWorkspacePage />} />
                <Route path="/activity" element={<ActivityPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </main>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;

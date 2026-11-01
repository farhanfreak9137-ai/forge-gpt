import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from './components/layout/AppShell';
import { ConfirmProvider, ToastProvider } from './components/ui';
import { StudioPage } from './features/studio/StudioPage';
import { OverviewPage } from './features/dashboard/OverviewPage';
import { ProjectsPage } from './features/projects/ProjectsPage';
import { TaskWorkspacePage } from './features/tasks/TaskWorkspacePage';
import { ActivityPage } from './features/activity/ActivityPage';
import { SettingsPage } from './features/settings/SettingsPage';

const queryClient = new QueryClient();

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <ConfirmProvider>
            <AppShell>
              <Routes>
                <Route path="/" element={<StudioPage />} />
                <Route path="/studio" element={<StudioPage />} />
                <Route path="/overview" element={<OverviewPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/workspace" element={<TaskWorkspacePage />} />
                <Route path="/activity" element={<ActivityPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </AppShell>
          </ConfirmProvider>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
};

export default App;

import { Project, Task, TaskDetail, ActivityEvent, ConnectorInfo, AppSettings, Approval, StudioMessage, StudioWorkspaceManifest, StudioChatSession, StudioPendingAction } from '../types';

const BASE_URL = '/api/v1';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || `Request failed with status ${res.status}`);
  }

  return res.json();
}

export const api = {
  // Projects
  getProjects: () => request<Project[]>('/projects'),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (data: { name: string; path: string; description?: string; is_new?: boolean }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),
  getProjectFiles: (id: string) => request<{ files: any[]; total: number }>(`/projects/${id}/files`),
  getProjectGitStatus: (id: string) => request<any>(`/projects/${id}/git-status`),
  getProjectCheckpoints: (id: string) => request<any[]>(`/projects/${id}/checkpoints`),

  // Tasks
  getTasks: (projectId?: string) =>
    request<Task[]>(`/tasks${projectId ? `?project_id=${projectId}` : ''}`),
  getTask: (id: string) => request<TaskDetail>(`/tasks/${id}`),
  createTask: (data: { project_id: string; title: string; description: string; connector_name?: string }) =>
    request<Task>('/tasks', { method: 'POST', body: JSON.stringify(data) }),
  pauseTask: (id: string) => request<{ status: string }>(`/tasks/${id}/pause`, { method: 'POST' }),
  resumeTask: (id: string) => request<{ status: string }>(`/tasks/${id}/resume`, { method: 'POST' }),
  cancelTask: (id: string) => request<{ status: string }>(`/tasks/${id}/cancel`, { method: 'POST' }),
  deleteTask: (id: string) => request<{ status: string }>(`/tasks/${id}`, { method: 'DELETE' }),
  cleanupTasks: (data: { older_than_hours?: number; project_id?: string; delete_finished?: boolean } = {}) =>
    request<{ cancelled: number; deleted: number }>('/tasks/cleanup', { method: 'POST', body: JSON.stringify(data) }),
  rollbackTask: (taskId: string, checkpointRef: string) =>
    request<{ status: string }>(`/tasks/${taskId}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ checkpoint_ref: checkpointRef }),
    }),

  // Connectors
  getConnectors: () => request<ConnectorInfo[]>('/connectors'),
  testConnector: (name: string) => request<any>(`/connectors/${name}/test`, { method: 'POST' }),
  submitBrowserHandoff: (requestId: string, responseText: string) =>
    request<any>('/connectors/browser_handoff/submit', {
      method: 'POST',
      body: JSON.stringify({ request_id: requestId, response_text: responseText }),
    }),

  // Approvals
  getApprovals: () => request<Approval[]>('/approvals'),
  decideApproval: (id: string, approved: boolean, reason?: string) =>
    request<Approval>(`/approvals/${id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ approved, reason }),
    }),

  // Files & Diffs
  getFileContent: (projectId: string, path: string) =>
    request<{ path: string; content: string }>(`/files/content?project_id=${projectId}&path=${encodeURIComponent(path)}`),
  getDiff: (projectId: string, commitRef?: string) =>
    request<{ diff: string }>(`/files/diff?project_id=${projectId}${commitRef ? `&commit_ref=${commitRef}` : ''}`),

  // Events
  getEvents: (params?: { taskId?: string; projectId?: string; sinceSequence?: number }) => {
    const q = new URLSearchParams();
    if (params?.taskId) q.set('task_id', params.taskId);
    if (params?.projectId) q.set('project_id', params.projectId);
    if (params?.sinceSequence !== undefined) q.set('since_sequence', String(params.sinceSequence));
    return request<ActivityEvent[]>(`/events?${q.toString()}`);
  },

  // Settings
  getSettings: () => request<AppSettings>('/settings'),
  updateSettings: (updates: Partial<AppSettings>) =>
    request<{ status: string }>('/settings', { method: 'PUT', body: JSON.stringify(updates) }),
  toggleEmergencyStop: (active: boolean) =>
    request<{ emergency_stop_active: boolean }>('/settings/emergency-stop', {
      method: 'POST',
      body: JSON.stringify({ active }),
    }),

  // Studio (Conversational AI Agent Studio)
  getStudioSessions: (sync = true) =>
    request<StudioChatSession[]>(`/studio/sessions?sync=${sync}`),
  createStudioSession: (title = 'New Chat') =>
    request<StudioChatSession>('/studio/sessions', { method: 'POST', body: JSON.stringify({ title }) }),
  getStudioSession: (sessionId: string) =>
    request<any>(`/studio/sessions/${sessionId}`),
  selectStudioSession: (sessionId: string) =>
    request<any>(`/studio/sessions/${sessionId}/select`, { method: 'POST' }),
  deleteStudioSession: (sessionId: string) =>
    request<{ status: string; session_id: string }>(`/studio/sessions/${sessionId}`, { method: 'DELETE' }),
  sendStudioChat: (data: { message: string; workspace_path?: string; auto_pilot?: boolean; connector_name?: string }) =>
    request<StudioMessage>('/studio/chat', { method: 'POST', body: JSON.stringify(data) }),
  approveStudioAction: (messageId: string, actionId: string) =>
    request<StudioPendingAction>(`/studio/messages/${messageId}/actions/${actionId}/approve`, { method: 'POST' }),
  rejectStudioAction: (messageId: string, actionId: string) =>
    request<StudioPendingAction>(`/studio/messages/${messageId}/actions/${actionId}/reject`, { method: 'POST' }),
  pruneStudioSessions: (keepLatest = 10) =>
    request<{ removed: number; remaining: number }>('/studio/sessions/prune', {
      method: 'POST',
      body: JSON.stringify({ keep_latest: keepLatest, remove_empty: true }),
    }),
  getStudioHistory: () => request<StudioMessage[]>('/studio/history'),
  clearStudioHistory: () => request<{ status: string }>('/studio/history', { method: 'DELETE' }),
  getStudioFiles: (workspacePath?: string) =>
    request<StudioWorkspaceManifest>(`/studio/files${workspacePath ? `?workspace_path=${encodeURIComponent(workspacePath)}` : ''}`),
  getStudioFileContent: (path: string, workspacePath?: string) =>
    request<{ path: string; content: string }>(`/studio/file-content?path=${encodeURIComponent(path)}${workspacePath ? `&workspace_path=${encodeURIComponent(workspacePath)}` : ''}`),
  saveStudioFile: (data: { file_path: string; content: string; workspace_path?: string }) =>
    request<{ status: string; path: string; sha256: string }>('/studio/save-file', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  openStudioBrowser: () =>
    request<{ status: string; message: string }>('/studio/open-browser', { method: 'POST' }),
};


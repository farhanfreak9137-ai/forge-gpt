export interface Project {
  id: string;
  name: string;
  path: string;
  description?: string;
  created_at: string;
  updated_at: string;
  project_metadata: {
    languages?: string[];
    frameworks?: string[];
    scripts?: Record<string, string>;
    entry_points?: string[];
    total_files?: number;
    files?: Array<{ path: string; size_bytes: number; extension: string }>;
  };
}

export type TaskState =
  | 'CREATED'
  | 'SCANNING'
  | 'PLANNING'
  | 'WAITING_FOR_AI'
  | 'PARSING'
  | 'VALIDATING'
  | 'WAITING_FOR_APPROVAL'
  | 'APPLYING'
  | 'TESTING'
  | 'REPAIRING'
  | 'VERIFYING'
  | 'COMPLETED'
  | 'PAUSED'
  | 'FAILED'
  | 'CANCELLED'
  | 'RECOVERY_REQUIRED';

export interface PlanStep {
  id: string;
  step_index: number;
  step_type: string;
  title: string;
  description?: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';
  created_at: string;
  completed_at?: string;
}

export interface ProposedChange {
  id: string;
  file_path: string;
  operation: 'create' | 'replace' | 'patch' | 'delete' | 'move';
  proposed_content?: string;
  patch_diff?: string;
  explanation?: string;
  status: 'PENDING' | 'APPLIED' | 'REJECTED' | 'FAILED';
  created_at: string;
}

export interface Execution {
  id: string;
  command: string;
  working_dir: string;
  exit_code?: number;
  stdout?: string;
  stderr?: string;
  duration_ms: number;
  status: string;
  created_at: string;
}

export interface TestResult {
  id: string;
  test_command: string;
  passed: boolean;
  total_tests: number;
  failed_tests: number;
  error_details?: string;
  created_at: string;
}

export interface Approval {
  id: string;
  task_id: string;
  action_type: string;
  description: string;
  details: Record<string, any>;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  decision_reason?: string;
  requested_at: string;
  decided_at?: string;
}

export interface Checkpoint {
  id: string;
  git_ref: string;
  description: string;
  files_affected: string[];
  created_at: string;
}

export interface Task {
  id: string;
  project_id: string;
  session_id?: string;
  title: string;
  description: string;
  state: TaskState;
  current_step_index: number;
  repair_attempts: number;
  max_repair_attempts: number;
  error_message?: string;
  result_summary?: string;
  created_at: string;
  updated_at: string;
}

export interface TaskDetail extends Task {
  steps: PlanStep[];
  proposed_changes: ProposedChange[];
  executions: Execution[];
  test_results: TestResult[];
  approvals: Approval[];
  checkpoints: Checkpoint[];
}

export interface ActivityEvent {
  id: string;
  sequence_number?: number;
  task_id?: string;
  project_id?: string;
  event_type: string;
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS';
  message: string;
  payload: Record<string, any>;
  timestamp: string;
}

export interface ConnectorInfo {
  name: string;
  provider_type: string;
  available: boolean;
  capabilities: Record<string, any>;
}

export interface AppSettings {
  app_name: string;
  version: string;
  execution_mode: string;
  default_ai_connector: string;
  openai_base_url: string;
  openai_model_id: string;
  has_openai_key: boolean;
  ollama_base_url: string;
  ollama_model_id: string;
  command_timeout_seconds: number;
  max_repair_attempts: number;
  emergency_stop_active: boolean;
}

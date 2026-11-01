import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, FolderDown, FolderGit2, ListChecks, Plus, Search } from 'lucide-react';
import { api } from '../../services/api';
import { cn } from '../../lib/cn';
import { formatBytes } from '../../lib/format';
import { useDocumentTitle } from '../../lib/hooks';
import { Project } from '../../types';
import { useAppStore } from '../../stores/useAppStore';
import { Page } from '../../components/layout/AppShell';
import { Badge, Button, Card, Dialog, EmptyState, ErrorState, Field, Input, PageHeader, Skeleton, Textarea, useToast } from '../../components/ui';

type ProjectMode = 'create' | 'import';

export const ProjectsPage: React.FC = () => {
  useDocumentTitle('Projects');
  const navigate = useNavigate();
  const toast = useToast();
  const { setCurrentProject, setActiveTask } = useAppStore();

  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [fileFilter, setFileFilter] = useState('');
  const [projectQuery, setProjectQuery] = useState('');

  // Project dialog (create / import share one form)
  const [projectMode, setProjectMode] = useState<ProjectMode | null>(null);
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
  const [desc, setDesc] = useState('');
  const [formError, setFormError] = useState('');

  // Task dialog
  const [taskOpen, setTaskOpen] = useState(false);
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDesc, setTaskDesc] = useState('');
  const [taskError, setTaskError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadProjects = useCallback(async (selectId?: string) => {
    setLoadError(null);
    try {
      const data = await api.getProjects();
      setProjects(data);
      setSelected((cur) => data.find((p) => p.id === (selectId ?? cur?.id)) ?? data[0] ?? null);
    } catch (e: any) {
      setLoadError(e.message || 'Could not load projects.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const selectProject = (p: Project) => {
    setSelected(p);
    setCurrentProject(p);
    setFileFilter('');
  };

  const openProjectDialog = (mode: ProjectMode) => {
    setName('');
    setPath('');
    setDesc('');
    setFormError('');
    setProjectMode(mode);
  };

  const submitProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectMode) return;
    setSubmitting(true);
    setFormError('');
    try {
      const created = await api.createProject({
        name: name.trim(),
        path: path.trim(),
        description: desc.trim(),
        is_new: projectMode === 'create',
      });
      setProjectMode(null);
      await loadProjects(created.id);
      setCurrentProject(created);
      toast.success(projectMode === 'create' ? `Created “${created.name}”.` : `Imported “${created.name}”.`);
    } catch (err: any) {
      setFormError(err.message || 'Could not save the project.');
    } finally {
      setSubmitting(false);
    }
  };

  const openTaskDialog = () => {
    setTaskTitle('');
    setTaskDesc('');
    setTaskError('');
    setTaskOpen(true);
  };

  const submitTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    setSubmitting(true);
    setTaskError('');
    try {
      const task = await api.createTask({ project_id: selected.id, title: taskTitle.trim(), description: taskDesc.trim() });
      setTaskOpen(false);
      setCurrentProject(selected);
      setActiveTask(await api.getTask(task.id));
      navigate('/workspace');
    } catch (err: any) {
      setTaskError(err.message || 'Could not start the task.');
    } finally {
      setSubmitting(false);
    }
  };

  const visibleProjects = projects.filter((p) => `${p.name} ${p.path}`.toLowerCase().includes(projectQuery.trim().toLowerCase()));
  const files = (selected?.project_metadata?.files ?? []).filter((f) => f.path.toLowerCase().includes(fileFilter.toLowerCase()));
  const isCreate = projectMode === 'create';

  return (
    <Page>
      <PageHeader
        title="Projects"
        description="Pick a project, then give the agent a task to work on."
        actions={
          <>
            <Button icon={<FolderDown className="h-4 w-4" />} onClick={() => openProjectDialog('import')}>
              Import existing
            </Button>
            <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => openProjectDialog('create')}>
              New project
            </Button>
          </>
        }
      />

      {loadError ? (
        <ErrorState title="Couldn't load projects" message={loadError} onRetry={() => loadProjects()} />
      ) : loading ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
          <Skeleton className="h-72 w-full lg:col-span-2" />
        </div>
      ) : projects.length === 0 ? (
        <Card>
          <EmptyState
            icon={<FolderGit2 className="h-6 w-6" />}
            title="No projects yet"
            description="Create a new project folder, or import one you already have. The agent works inside the project you choose."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => openProjectDialog('create')}>
                  New project
                </Button>
                <Button icon={<FolderDown className="h-4 w-4" />} onClick={() => openProjectDialog('import')}>
                  Import existing
                </Button>
              </div>
            }
          />
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-3 lg:sticky lg:top-4 lg:self-start">
          {projects.length > 5 && (
            <label className="relative block">
              <span className="sr-only">Search projects</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden />
              <input
                type="search"
                value={projectQuery}
                onChange={(e) => setProjectQuery(e.target.value)}
                placeholder={`Search ${projects.length} projects`}
                className="h-10 w-full rounded-xl border border-slate-700 bg-slate-950 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 focus-visible:border-brand-500"
              />
            </label>
          )}
          <ul className="space-y-2 lg:max-h-[calc(100vh-15rem)] lg:overflow-y-auto lg:pr-1" aria-label="Projects">
            {visibleProjects.length === 0 && <li className="px-2 py-6 text-center text-sm text-slate-400">No project matches “{projectQuery}”.</li>}
            {visibleProjects.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => selectProject(p)}
                  aria-current={selected?.id === p.id ? 'true' : undefined}
                  className={cn(
                    'w-full rounded-xl border p-4 text-left transition-colors',
                    selected?.id === p.id ? 'border-brand-500/60 bg-slate-850' : 'border-slate-800 bg-slate-900/70 hover:border-slate-600',
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate font-semibold text-slate-100">{p.name}</span>
                    <ChevronRight className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                  </span>
                  <span className="mt-1 block truncate font-mono text-xs text-slate-400">{p.path}</span>
                  {!!p.project_metadata?.languages?.length && (
                    <span className="mt-3 flex flex-wrap gap-1.5">
                      {p.project_metadata.languages.map((l) => (
                        <Badge key={l} tone="success">
                          {l}
                        </Badge>
                      ))}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
          </div>

          {selected && (
            <Card className="space-y-6 p-5 lg:col-span-2 lg:self-start">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-4">
                <div className="min-w-0">
                  <h2 className="text-xl font-semibold text-slate-50">{selected.name}</h2>
                  <p className="mt-1 break-all font-mono text-xs text-slate-400">{selected.path}</p>
                  {selected.description && <p className="mt-2 text-sm text-slate-300">{selected.description}</p>}
                </div>
                <Button variant="primary" icon={<ListChecks className="h-4 w-4" />} onClick={openTaskDialog}>
                  Start a task
                </Button>
              </div>

              <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {[
                  { k: 'Frameworks', v: selected.project_metadata?.frameworks?.join(', ') || 'None detected' },
                  { k: 'Entry points', v: selected.project_metadata?.entry_points?.join(', ') || 'Auto-detected', mono: true },
                  { k: 'Files', v: String(selected.project_metadata?.total_files ?? 0) },
                ].map((m) => (
                  <div key={m.k} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                    <dt className="text-xs font-medium text-slate-400">{m.k}</dt>
                    <dd className={cn('mt-1 break-words text-sm text-slate-100', m.mono && 'font-mono text-xs')}>{m.v}</dd>
                  </div>
                ))}
              </dl>

              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-slate-200">Files</h3>
                  <input
                    type="search"
                    aria-label="Filter project files"
                    placeholder="Filter files"
                    value={fileFilter}
                    onChange={(e) => setFileFilter(e.target.value)}
                    className="h-8 w-48 rounded-lg border border-slate-800 bg-slate-900 px-3 text-xs text-slate-100 placeholder:text-slate-500 focus-visible:border-brand-500"
                  />
                </div>
                <ul className="max-h-64 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-1 font-mono text-xs">
                  {files.length === 0 ? (
                    <li className="px-3 py-6 text-center font-sans text-sm text-slate-400">{fileFilter ? 'No files match.' : 'No files found.'}</li>
                  ) : (
                    files.map((f) => (
                      <li key={f.path} className="flex items-center justify-between gap-3 rounded px-2 py-1.5 text-slate-300 hover:bg-slate-900">
                        <span className="truncate">{f.path}</span>
                        <span className="shrink-0 text-slate-500">{formatBytes(f.size_bytes)}</span>
                      </li>
                    ))
                  )}
                </ul>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Create / import project */}
      <Dialog
        open={!!projectMode}
        onClose={() => setProjectMode(null)}
        locked={submitting}
        title={isCreate ? 'New project' : 'Import existing project'}
        description={isCreate ? 'ForgeAgent creates the folder for you.' : 'Point ForgeAgent at a folder that already has your code.'}
        footer={
          <>
            <Button variant="ghost" onClick={() => setProjectMode(null)} disabled={submitting}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" form="project-form" loading={submitting}>
              {isCreate ? 'Create project' : 'Import project'}
            </Button>
          </>
        }
      >
        <form id="project-form" onSubmit={submitProject} className="space-y-4">
          <Field label="Project name" htmlFor="p-name">
            <Input id="p-name" required value={name} onChange={(e) => setName(e.target.value)} placeholder={isCreate ? 'My new app' : 'Existing repository'} />
          </Field>
          <Field
            label={isCreate ? 'Where should the folder go?' : 'Folder path'}
            htmlFor="p-path"
            hint={isCreate ? 'A full path, for example C:\\Projects\\my-new-app' : 'A full path, for example C:\\Projects\\my-codebase'}
          >
            <Input id="p-path" required value={path} onChange={(e) => setPath(e.target.value)} placeholder="C:\Projects\my-app" className="font-mono text-[13px]" />
          </Field>
          <Field label="Description (optional)" htmlFor="p-desc">
            <Textarea id="p-desc" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="What is this project for?" rows={3} />
          </Field>
          {formError && (
            <p role="alert" className="rounded-lg border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-sm text-rose-200">
              {formError}
            </p>
          )}
        </form>
      </Dialog>

      {/* Start task */}
      <Dialog
        open={taskOpen}
        onClose={() => setTaskOpen(false)}
        locked={submitting}
        size="lg"
        title="Start a task"
        description={selected ? `The agent will plan and make changes inside “${selected.name}”. You approve anything risky.` : undefined}
        footer={
          <>
            <Button variant="ghost" onClick={() => setTaskOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" form="task-form" loading={submitting}>
              Launch task
            </Button>
          </>
        }
      >
        <form id="task-form" onSubmit={submitTask} className="space-y-4">
          <Field label="Task title" htmlFor="t-title">
            <Input id="t-title" required value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} placeholder="Add a calculator module with tests" />
          </Field>
          <Field label="What should it do?" htmlFor="t-desc" hint="Be specific about the files, behaviour and checks you expect.">
            <Textarea
              id="t-desc"
              required
              value={taskDesc}
              onChange={(e) => setTaskDesc(e.target.value)}
              placeholder="Describe the change you want, and how to know it works."
              rows={5}
            />
          </Field>
          {taskError && (
            <p role="alert" className="rounded-lg border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-sm text-rose-200">
              {taskError}
            </p>
          )}
        </form>
      </Dialog>
    </Page>
  );
};

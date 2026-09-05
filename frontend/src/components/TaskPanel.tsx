import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  api,
  type AcceptanceCriterion,
  type Project,
  type Task,
  type TaskDependency,
  type TaskIsBlocked,
} from "@/lib/api";

interface TaskPanelProps {
  taskId: string | null;
  featureId: string;
  productId: string;
  projects: Project[];
  onClose: () => void;
  onSaved: () => void;
}

export function TaskPanel({ taskId, featureId, productId, projects, onClose, onSaved }: TaskPanelProps) {
  const [task, setTask] = useState<Task | null>(null);
  const [criteria, setCriteria] = useState<AcceptanceCriterion[]>([]);
  const [title, setTitle] = useState("");
  const [taskType, setTaskType] = useState("feature");
  const [projectId, setProjectId] = useState(projects[0]?.id ?? "");
  const [status, setStatus] = useState("todo");
  const [context, setContext] = useState("");
  const [dependencies, setDependencies] = useState<TaskDependency[]>([]);
  const [productTasks, setProductTasks] = useState<Task[]>([]);
  const [selectedDependencyId, setSelectedDependencyId] = useState("");
  const [isBlocked, setIsBlocked] = useState<TaskIsBlocked | null>(null);

  const [acFormat, setAcFormat] = useState<"basic" | "gherkin">("basic");
  const [acDescription, setAcDescription] = useState("");
  const [acGiven, setAcGiven] = useState("");
  const [acWhen, setAcWhen] = useState("");
  const [acThen, setAcThen] = useState("");

  useEffect(() => {
    if (!taskId) return;
    api.getTask(taskId).then((loaded) => {
      setTask(loaded);
      setTitle(loaded.title);
      setTaskType(loaded.task_type);
      setStatus(loaded.status);
      setContext(loaded.context ?? "");
    });
    api.listAcceptanceCriteria(taskId).then(setCriteria);
    api.listTaskDependencies(taskId).then(setDependencies);
    api.listTasksByProduct(productId).then(setProductTasks);
    api.getTaskIsBlocked(taskId).then(setIsBlocked);
  }, [taskId, productId]);

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      if (taskId) {
        await api.updateTask(taskId, { title, task_type: taskType, status, context });
      } else {
        await api.createTask({
          feature_id: featureId,
          project_id: projectId,
          title,
          task_type: taskType,
          context,
        });
      }
      onSaved();
    } catch {
      // panel stays open with input intact
    }
  };

  const handleAddCriterion = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!taskId) return;
    try {
      await api.createAcceptanceCriterion(taskId, {
        format: acFormat,
        description: acFormat === "basic" ? acDescription : undefined,
        given: acFormat === "gherkin" ? acGiven : undefined,
        when_: acFormat === "gherkin" ? acWhen : undefined,
        then_: acFormat === "gherkin" ? acThen : undefined,
      });
      setAcDescription("");
      setAcGiven("");
      setAcWhen("");
      setAcThen("");
      api.listAcceptanceCriteria(taskId).then(setCriteria);
    } catch {
      // form stays open with input intact
    }
  };

  const handleToggleCriterion = async (criterionId: string, checked: boolean) => {
    if (!taskId) return;
    await api.toggleAcceptanceCriterion(taskId, criterionId, checked);
    api.listAcceptanceCriteria(taskId).then(setCriteria);
  };

  const handleAddDependency = async () => {
    if (!taskId || !selectedDependencyId) return;
    try {
      await api.createTaskDependency(taskId, selectedDependencyId);
      setSelectedDependencyId("");
      api.listTaskDependencies(taskId).then(setDependencies);
      api.getTaskIsBlocked(taskId).then(setIsBlocked);
    } catch {
      // selection stays intact; user can retry
    }
  };

  const handleRemoveDependency = async (dependencyId: string) => {
    if (!taskId) return;
    try {
      await api.deleteTaskDependency(taskId, dependencyId);
      api.listTaskDependencies(taskId).then(setDependencies);
      api.getTaskIsBlocked(taskId).then(setIsBlocked);
    } catch {
      // row stays until a retry succeeds
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-96 flex-col overflow-y-auto border-l bg-white p-6 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">{taskId ? (task?.issue_key ?? "Task") : "New Task"}</h2>
        <button type="button" onClick={onClose} className="text-sm underline">
          Close
        </button>
      </div>

      <form onSubmit={handleSave} className="flex flex-col gap-2">
        <input
          className="rounded border px-2 py-1"
          placeholder="Title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          required
        />
        <select
          className="rounded border px-2 py-1"
          value={taskType}
          onChange={(event) => setTaskType(event.target.value)}
        >
          <option value="feature">Feature</option>
          <option value="bug">Bug</option>
          <option value="improvement">Improvement</option>
          <option value="chore">Chore</option>
          <option value="research">Research</option>
        </select>
        {!taskId && projects.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Create a Project for this Product before adding tasks.
          </p>
        )}
        {!taskId && projects.length > 0 && (
          <select
            className="rounded border px-2 py-1"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            required
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        )}
        {taskId && (
          <select
            className="rounded border px-2 py-1"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="todo">Todo</option>
            <option value="in_progress">In Progress</option>
            <option value="done">Done</option>
            <option value="outdated">Outdated</option>
          </select>
        )}
        <textarea
          className="rounded border px-2 py-1"
          placeholder="Context"
          value={context}
          onChange={(event) => setContext(event.target.value)}
        />
        <Button type="submit" disabled={!taskId && projects.length === 0}>
          {taskId ? "Save" : "Create"}
        </Button>
      </form>

      {taskId && (
        <div className="mt-6">
          <h3 className="mb-2 text-sm font-semibold">Acceptance Criteria</h3>
          <div className="flex flex-col gap-2">
            {criteria.map((criterion) => (
              <label key={criterion.id} className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={criterion.checked}
                  onChange={(event) => handleToggleCriterion(criterion.id, event.target.checked)}
                />
                <span>
                  {criterion.format === "basic"
                    ? criterion.description
                    : `Given ${criterion.given}, when ${criterion.when_}, then ${criterion.then_}`}
                </span>
              </label>
            ))}
          </div>

          <form onSubmit={handleAddCriterion} className="mt-3 flex flex-col gap-2">
            <select
              className="rounded border px-2 py-1"
              value={acFormat}
              onChange={(event) => setAcFormat(event.target.value as "basic" | "gherkin")}
            >
              <option value="basic">Basic</option>
              <option value="gherkin">Gherkin</option>
            </select>
            {acFormat === "basic" && (
              <input
                className="rounded border px-2 py-1"
                placeholder="Description"
                value={acDescription}
                onChange={(event) => setAcDescription(event.target.value)}
                required
              />
            )}
            {acFormat === "gherkin" && (
              <>
                <input
                  className="rounded border px-2 py-1"
                  placeholder="Given"
                  value={acGiven}
                  onChange={(event) => setAcGiven(event.target.value)}
                  required
                />
                <input
                  className="rounded border px-2 py-1"
                  placeholder="When"
                  value={acWhen}
                  onChange={(event) => setAcWhen(event.target.value)}
                  required
                />
                <input
                  className="rounded border px-2 py-1"
                  placeholder="Then"
                  value={acThen}
                  onChange={(event) => setAcThen(event.target.value)}
                  required
                />
              </>
            )}
            <Button type="submit">Add Criterion</Button>
          </form>
        </div>
      )}

      {taskId && (
        <div className="mt-6">
          <h3 className="mb-2 text-sm font-semibold">Depends on</h3>
          {isBlocked?.is_blocked && (
            <p className="mb-2 rounded bg-yellow-50 p-2 text-sm text-yellow-800">
              Blocked by {isBlocked.blocking_tasks.length} unresolved{" "}
              {isBlocked.blocking_tasks.length === 1 ? "dependency" : "dependencies"}.
            </p>
          )}
          <div className="flex flex-col gap-2">
            {dependencies.map((dependency) => (
              <div key={dependency.id} className="flex items-center justify-between text-sm">
                <span>
                  <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-mono text-blue-800">
                    {dependency.depends_on_task.issue_key}
                  </span>{" "}
                  {dependency.depends_on_task.title} ({dependency.depends_on_task.status})
                </span>
                <button
                  type="button"
                  onClick={() => handleRemoveDependency(dependency.id)}
                  className="text-xs underline"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <select
              className="flex-1 rounded border px-2 py-1"
              value={selectedDependencyId}
              onChange={(event) => setSelectedDependencyId(event.target.value)}
            >
              <option value="">Select a task…</option>
              {productTasks
                .filter(
                  (candidate) =>
                    candidate.id !== taskId &&
                    !dependencies.some((dep) => dep.depends_on_task.id === candidate.id),
                )
                .map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.issue_key} — {candidate.title}
                  </option>
                ))}
            </select>
            <Button type="button" onClick={handleAddDependency} disabled={!selectedDependencyId}>
              Add
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

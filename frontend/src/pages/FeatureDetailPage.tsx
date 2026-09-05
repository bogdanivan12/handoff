import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { TaskPanel } from "@/components/TaskPanel";
import {
  api,
  type Epic,
  type Feature,
  type FeatureDependency,
  type Initiative,
  type Product,
  type Project,
  type Task,
} from "@/lib/api";

export function FeatureDetailPage() {
  const { productId, initiativeId, epicId, featureId } = useParams<{
    productId: string;
    initiativeId: string;
    epicId: string;
    featureId: string;
  }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [initiative, setInitiative] = useState<Initiative | null>(null);
  const [epic, setEpic] = useState<Epic | null>(null);
  const [feature, setFeature] = useState<Feature | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [openTaskId, setOpenTaskId] = useState<string | "new" | null>(null);
  const [featureDependencies, setFeatureDependencies] = useState<FeatureDependency[]>([]);
  const [productFeatures, setProductFeatures] = useState<Feature[]>([]);
  const [selectedFeatureDependencyId, setSelectedFeatureDependencyId] = useState("");

  const loadTasks = () => {
    if (!featureId) return;
    api.listTasks(featureId).then(setTasks).catch(() => {
      // best-effort refresh; the list simply stays stale until the next successful load
    });
  };

  const loadFeatureDependencies = () => {
    if (!featureId) return;
    api.listFeatureDependencies(featureId).then(setFeatureDependencies).catch(() => {
      // best-effort refresh; the list simply stays stale until the next successful load
    });
  };

  const handleAddFeatureDependency = async () => {
    if (!featureId || !selectedFeatureDependencyId) return;
    await api.createFeatureDependency(featureId, selectedFeatureDependencyId);
    setSelectedFeatureDependencyId("");
    loadFeatureDependencies();
  };

  const handleRemoveFeatureDependency = async (dependencyId: string) => {
    if (!featureId) return;
    await api.deleteFeatureDependency(featureId, dependencyId);
    loadFeatureDependencies();
  };

  const load = () => {
    if (!productId || !initiativeId || !epicId || !featureId) return;
    setLoadError(false);
    Promise.all([
      api.getProduct(productId),
      api.getInitiative(initiativeId),
      api.getEpic(epicId),
      api.getFeature(featureId),
      api.listProjects(productId),
      api.listTasks(featureId),
      api.listFeatureDependencies(featureId),
      api.listFeaturesByProduct(productId),
    ])
      .then(
        ([
          productResult,
          initiativeResult,
          epicResult,
          featureResult,
          projectsResult,
          tasksResult,
          featureDependenciesResult,
          productFeaturesResult,
        ]) => {
          setProduct(productResult);
          setInitiative(initiativeResult);
          setEpic(epicResult);
          setFeature(featureResult);
          setProjects(projectsResult);
          setTasks(tasksResult);
          setFeatureDependencies(featureDependenciesResult);
          setProductFeatures(productFeaturesResult);
        },
      )
      .catch(() => setLoadError(true));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, initiativeId, epicId, featureId]);

  if (loadError) {
    return (
      <div className="mx-auto max-w-2xl p-8">
        <p className="text-red-600">Couldn't load this page. It may have been deleted.</p>
        <Link to="/" className="text-sm underline">
          Back to Products
        </Link>
      </div>
    );
  }

  if (!product || !initiative || !epic || !feature) return null;

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Breadcrumb
        items={[
          { label: "Products", to: "/" },
          { label: product.name, to: `/products/${product.id}` },
          { label: initiative.name, to: `/products/${product.id}/initiatives/${initiative.id}` },
          {
            label: epic.name,
            to: `/products/${product.id}/initiatives/${initiative.id}/epics/${epic.id}`,
          },
          {
            label: feature.name,
            to: `/products/${product.id}/initiatives/${initiative.id}/epics/${epic.id}/features/${feature.id}`,
          },
        ]}
      />

      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{feature.name} — Tasks</h1>
        <Button onClick={() => setOpenTaskId("new")}>New Task</Button>
      </div>

      <div className="flex flex-col gap-2">
        {tasks.map((task) => (
          <button
            key={task.id}
            type="button"
            onClick={() => setOpenTaskId(task.id)}
            className={`rounded border p-4 text-left hover:bg-gray-50 ${task.is_blocked ? "opacity-50" : ""}`}
          >
            <div className="flex items-center gap-2">
              {task.is_blocked && <span title="Blocked">🔒</span>}
              <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-mono text-blue-800">
                {task.issue_key}
              </span>
              <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-mono">
                {task.task_type}
              </span>
              <span>{task.title}</span>
            </div>
            <div className="mt-1 text-sm text-muted-foreground">{task.status}</div>
          </button>
        ))}
      </div>

      <div className="mt-6">
        <h3 className="mb-2 text-sm font-semibold">Depends on</h3>
        <div className="flex flex-col gap-2">
          {featureDependencies.map((dependency) => (
            <div key={dependency.id} className="flex items-center justify-between text-sm">
              <span>
                <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-mono text-blue-800">
                  {dependency.depends_on_feature.issue_key}
                </span>{" "}
                {dependency.depends_on_feature.name} ({dependency.depends_on_feature.status})
              </span>
              <button
                type="button"
                onClick={() => handleRemoveFeatureDependency(dependency.id)}
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
            value={selectedFeatureDependencyId}
            onChange={(event) => setSelectedFeatureDependencyId(event.target.value)}
          >
            <option value="">Select a feature…</option>
            {productFeatures
              .filter(
                (candidate) =>
                  candidate.id !== feature.id &&
                  !featureDependencies.some((dep) => dep.depends_on_feature.id === candidate.id),
              )
              .map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.issue_key} — {candidate.name}
                </option>
              ))}
          </select>
          <Button
            type="button"
            onClick={handleAddFeatureDependency}
            disabled={!selectedFeatureDependencyId}
          >
            Add
          </Button>
        </div>
      </div>

      {openTaskId && (
        <TaskPanel
          key={openTaskId}
          taskId={openTaskId === "new" ? null : openTaskId}
          featureId={feature.id}
          productId={product.id}
          projects={projects}
          onClose={() => setOpenTaskId(null)}
          onSaved={() => {
            setOpenTaskId(null);
            loadTasks();
          }}
        />
      )}
    </div>
  );
}

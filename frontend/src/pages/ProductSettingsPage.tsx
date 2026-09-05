import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Product, type Project, type Sprint } from "@/lib/api";

export function ProductSettingsPage() {
  const { productId } = useParams<{ productId: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [loadError, setLoadError] = useState(false);

  const [showProjectForm, setShowProjectForm] = useState(false);
  const [projectName, setProjectName] = useState("");

  const [showSprintForm, setShowSprintForm] = useState(false);
  const [sprintName, setSprintName] = useState("");
  const [sprintStart, setSprintStart] = useState("");
  const [sprintEnd, setSprintEnd] = useState("");

  const load = () => {
    if (!productId) return;
    setLoadError(false);
    Promise.all([
      api.getProduct(productId),
      api.listProjects(productId),
      api.listSprints(productId),
    ])
      .then(([productResult, projectsResult, sprintsResult]) => {
        setProduct(productResult);
        setProjects(projectsResult);
        setSprints(sprintsResult);
      })
      .catch(() => setLoadError(true));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const handleCreateProject = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!productId) return;
    try {
      await api.createProject({ product_id: productId, name: projectName });
      setProjectName("");
      setShowProjectForm(false);
      load();
    } catch {
      // form stays open with input intact
    }
  };

  const handleCreateSprint = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!productId) return;
    try {
      await api.createSprint({
        product_id: productId,
        name: sprintName,
        start_date: sprintStart || undefined,
        end_date: sprintEnd || undefined,
      });
      setSprintName("");
      setSprintStart("");
      setSprintEnd("");
      setShowSprintForm(false);
      load();
    } catch {
      // form stays open with input intact
    }
  };

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

  if (!product) return null;

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Breadcrumb
        items={[
          { label: "Products", to: "/" },
          { label: product.name, to: `/products/${product.id}` },
          { label: "Settings", to: `/products/${product.id}/settings` },
        ]}
      />

      <h1 className="mb-4 text-2xl font-semibold">{product.name} — Settings</h1>

      <section className="mb-8">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Projects</h2>
          <Button onClick={() => setShowProjectForm((value) => !value)}>New Project</Button>
        </div>

        {showProjectForm && (
          <form
            onSubmit={handleCreateProject}
            className="mb-4 flex flex-col gap-2 rounded border p-4"
          >
            <input
              className="rounded border px-2 py-1"
              placeholder="Name"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              required
            />
            <Button type="submit">Create</Button>
          </form>
        )}

        <div className="flex flex-col gap-2">
          {projects.map((project) => (
            <Card key={project.id}>
              <CardHeader>
                <CardTitle>{project.name}</CardTitle>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Sprints</h2>
          <Button onClick={() => setShowSprintForm((value) => !value)}>New Sprint</Button>
        </div>

        {showSprintForm && (
          <form
            onSubmit={handleCreateSprint}
            className="mb-4 flex flex-col gap-2 rounded border p-4"
          >
            <input
              className="rounded border px-2 py-1"
              placeholder="Name"
              value={sprintName}
              onChange={(event) => setSprintName(event.target.value)}
              required
            />
            <input
              className="rounded border px-2 py-1"
              type="date"
              value={sprintStart}
              onChange={(event) => setSprintStart(event.target.value)}
            />
            <input
              className="rounded border px-2 py-1"
              type="date"
              value={sprintEnd}
              onChange={(event) => setSprintEnd(event.target.value)}
            />
            <Button type="submit">Create</Button>
          </form>
        )}

        <div className="flex flex-col gap-2">
          {sprints.map((sprint) => (
            <Card key={sprint.id}>
              <CardHeader>
                <CardTitle>{sprint.name}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {sprint.status}
                {sprint.start_date && ` · ${sprint.start_date}`}
                {sprint.end_date && ` → ${sprint.end_date}`}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}

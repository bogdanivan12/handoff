import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type KnowledgeItem, type Product, type Project } from "@/lib/api";

type ContentKind =
  | "decision"
  | "convention"
  | "constraint"
  | "domain_concept"
  | "technical_fact"
  | "known_issue";

function summarize(item: KnowledgeItem): string {
  const content = item.content;
  switch (item.type) {
    case "decision":
      return `Chose ${String(content.chosen)} for ${String(content.subject)}`;
    case "convention":
      return `${String(content.subject)}: ${String(content.rule)}`;
    case "constraint":
      return `${String(content.subject)}: ${String(content.rule)} (${String(content.severity)})`;
    case "domain_concept":
      return `${String(content.term)}: ${String(content.definition)}`;
    case "technical_fact":
      return `${String(content.subject)}: ${String(content.fact)}`;
    case "known_issue":
      return String(content.description);
    default:
      return JSON.stringify(content);
  }
}

export function ProductKnowledgePage() {
  const { productId } = useParams<{ productId: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loadError, setLoadError] = useState(false);

  const [selectedScopeRefId, setSelectedScopeRefId] = useState<string>("");
  const [showForm, setShowForm] = useState(false);
  const [kind, setKind] = useState<ContentKind>("decision");
  const [fields, setFields] = useState<Record<string, string>>({});

  const scope = selectedScopeRefId === productId ? "product" : "project";

  const load = () => {
    if (!productId) return;
    setLoadError(false);
    Promise.all([api.getProduct(productId), api.listProjects(productId)])
      .then(([productResult, projectsResult]) => {
        setProduct(productResult);
        setProjects(projectsResult);
        if (!selectedScopeRefId) setSelectedScopeRefId(productId);
      })
      .catch(() => setLoadError(true));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  useEffect(() => {
    if (!selectedScopeRefId) return;
    api
      .listKnowledgeItems(scope, selectedScopeRefId)
      .then(setItems)
      .catch(() => setLoadError(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedScopeRefId]);

  const setField = (name: string, value: string) => {
    setFields((prev) => ({ ...prev, [name]: value }));
  };

  const buildContent = (): Record<string, unknown> => {
    switch (kind) {
      case "decision":
        return {
          kind,
          subject: fields.subject ?? "",
          chosen: fields.chosen ?? "",
          alternatives_considered: (fields.alternatives_considered ?? "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          rationale: fields.rationale ?? "",
        };
      case "convention":
        return {
          kind,
          subject: fields.subject ?? "",
          rule: fields.rule ?? "",
          example: fields.example || undefined,
        };
      case "constraint":
        return {
          kind,
          subject: fields.subject ?? "",
          rule: fields.rule ?? "",
          rationale: fields.rationale || undefined,
          severity: fields.severity ?? "soft",
        };
      case "domain_concept":
        return {
          kind,
          term: fields.term ?? "",
          definition: fields.definition ?? "",
          related_terms: (fields.related_terms ?? "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        };
      case "technical_fact":
        return {
          kind,
          subject: fields.subject ?? "",
          fact: fields.fact ?? "",
          verified_at: fields.verified_at ?? "",
        };
      case "known_issue":
        return {
          kind,
          subject: fields.subject ?? "",
          description: fields.description ?? "",
          workaround: fields.workaround || undefined,
          status: fields.status ?? "",
        };
    }
  };

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedScopeRefId) return;
    try {
      await api.createKnowledgeItem({
        scope,
        scope_ref_id: selectedScopeRefId,
        content: buildContent(),
      });
      setFields({});
      setShowForm(false);
      api.listKnowledgeItems(scope, selectedScopeRefId).then(setItems);
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
          { label: "Knowledge", to: `/products/${product.id}/knowledge` },
        ]}
      />

      <h1 className="mb-4 text-2xl font-semibold">{product.name} — Knowledge</h1>

      <div className="mb-4 flex items-center justify-between gap-2">
        <select
          className="rounded border px-2 py-1"
          value={selectedScopeRefId}
          onChange={(event) => setSelectedScopeRefId(event.target.value)}
        >
          <option value={product.id}>Product-level</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              Project: {project.name}
            </option>
          ))}
        </select>
        <Button onClick={() => setShowForm((value) => !value)}>New Knowledge Item</Button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 flex flex-col gap-2 rounded border p-4">
          <select
            className="rounded border px-2 py-1"
            value={kind}
            onChange={(event) => {
              setKind(event.target.value as ContentKind);
              setFields({});
            }}
          >
            <option value="decision">Decision</option>
            <option value="convention">Convention</option>
            <option value="constraint">Constraint</option>
            <option value="domain_concept">Domain Concept</option>
            <option value="technical_fact">Technical Fact</option>
            <option value="known_issue">Known Issue</option>
          </select>

          {kind === "decision" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Subject"
                value={fields.subject ?? ""}
                onChange={(event) => setField("subject", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Chosen"
                value={fields.chosen ?? ""}
                onChange={(event) => setField("chosen", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Alternatives considered (comma-separated)"
                value={fields.alternatives_considered ?? ""}
                onChange={(event) => setField("alternatives_considered", event.target.value)}
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Rationale"
                value={fields.rationale ?? ""}
                onChange={(event) => setField("rationale", event.target.value)}
                required
              />
            </>
          )}

          {kind === "convention" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Subject"
                value={fields.subject ?? ""}
                onChange={(event) => setField("subject", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Rule"
                value={fields.rule ?? ""}
                onChange={(event) => setField("rule", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Example (optional)"
                value={fields.example ?? ""}
                onChange={(event) => setField("example", event.target.value)}
              />
            </>
          )}

          {kind === "constraint" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Subject"
                value={fields.subject ?? ""}
                onChange={(event) => setField("subject", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Rule"
                value={fields.rule ?? ""}
                onChange={(event) => setField("rule", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Rationale (optional)"
                value={fields.rationale ?? ""}
                onChange={(event) => setField("rationale", event.target.value)}
              />
              <select
                className="rounded border px-2 py-1"
                value={fields.severity ?? "soft"}
                onChange={(event) => setField("severity", event.target.value)}
              >
                <option value="hard">Hard</option>
                <option value="soft">Soft</option>
              </select>
            </>
          )}

          {kind === "domain_concept" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Term"
                value={fields.term ?? ""}
                onChange={(event) => setField("term", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Definition"
                value={fields.definition ?? ""}
                onChange={(event) => setField("definition", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Related terms (comma-separated)"
                value={fields.related_terms ?? ""}
                onChange={(event) => setField("related_terms", event.target.value)}
              />
            </>
          )}

          {kind === "technical_fact" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Subject"
                value={fields.subject ?? ""}
                onChange={(event) => setField("subject", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Fact"
                value={fields.fact ?? ""}
                onChange={(event) => setField("fact", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                type="date"
                value={fields.verified_at ?? ""}
                onChange={(event) => setField("verified_at", event.target.value)}
                required
              />
            </>
          )}

          {kind === "known_issue" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Subject"
                value={fields.subject ?? ""}
                onChange={(event) => setField("subject", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Description"
                value={fields.description ?? ""}
                onChange={(event) => setField("description", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Status (e.g. open, resolved)"
                value={fields.status ?? ""}
                onChange={(event) => setField("status", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Workaround (optional)"
                value={fields.workaround ?? ""}
                onChange={(event) => setField("workaround", event.target.value)}
              />
            </>
          )}

          <Button type="submit">Create</Button>
        </form>
      )}

      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <Card key={item.id}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-mono">
                  {item.type}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{summarize(item)}</CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

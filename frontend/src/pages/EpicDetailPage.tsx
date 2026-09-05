import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Epic, type Feature, type Initiative, type Product } from "@/lib/api";

export function EpicDetailPage() {
  const { productId, initiativeId, epicId } = useParams<{
    productId: string;
    initiativeId: string;
    epicId: string;
  }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [initiative, setInitiative] = useState<Initiative | null>(null);
  const [epic, setEpic] = useState<Epic | null>(null);
  const [features, setFeatures] = useState<Feature[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    if (!productId || !initiativeId || !epicId) return;
    setLoadError(false);
    Promise.all([
      api.getProduct(productId),
      api.getInitiative(initiativeId),
      api.getEpic(epicId),
      api.listFeatures(epicId),
    ])
      .then(([productResult, initiativeResult, epicResult, featuresResult]) => {
        setProduct(productResult);
        setInitiative(initiativeResult);
        setEpic(epicResult);
        setFeatures(featuresResult);
      })
      .catch(() => setLoadError(true));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, initiativeId, epicId]);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!epicId) return;
    try {
      await api.createFeature({ epic_id: epicId, name });
      setName("");
      setShowForm(false);
      load();
    } catch {
      // form stays open with the user's input intact; a real toast/error UI is a later polish pass
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

  if (!product || !initiative || !epic) return null;

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
        ]}
      />

      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{epic.name} — Features</h1>
        <Button onClick={() => setShowForm((value) => !value)}>New Feature</Button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 flex flex-col gap-2 rounded border p-4">
          <input
            className="rounded border px-2 py-1"
            placeholder="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <Button type="submit">Create</Button>
        </form>
      )}

      <div className="flex flex-col gap-2">
        {features.map((feature) => (
          <Card key={feature.id}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="rounded bg-blue-100 px-2 py-0.5 font-mono text-xs text-blue-800">
                  {feature.issue_key}
                </span>
                {feature.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{feature.status}</CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

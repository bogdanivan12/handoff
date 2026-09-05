import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Epic, type Initiative, type Product } from "@/lib/api";

export function InitiativeDetailPage() {
  const { productId, initiativeId } = useParams<{ productId: string; initiativeId: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [initiative, setInitiative] = useState<Initiative | null>(null);
  const [epics, setEpics] = useState<Epic[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    if (!productId || !initiativeId) return;
    setLoadError(false);
    Promise.all([
      api.getProduct(productId),
      api.getInitiative(initiativeId),
      api.listEpics(initiativeId),
    ])
      .then(([productResult, initiativeResult, epicsResult]) => {
        setProduct(productResult);
        setInitiative(initiativeResult);
        setEpics(epicsResult);
      })
      .catch(() => setLoadError(true));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, initiativeId]);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!initiativeId) return;
    try {
      await api.createEpic({ initiative_id: initiativeId, name });
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

  if (!product || !initiative) return null;

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Breadcrumb
        items={[
          { label: "Products", to: "/" },
          { label: product.name, to: `/products/${product.id}` },
          { label: initiative.name, to: `/products/${product.id}/initiatives/${initiative.id}` },
        ]}
      />

      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{initiative.name} — Epics</h1>
        <Button onClick={() => setShowForm((value) => !value)}>New Epic</Button>
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
        {epics.map((epic) => (
          <Link
            key={epic.id}
            to={`/products/${product.id}/initiatives/${initiative.id}/epics/${epic.id}`}
          >
            <Card>
              <CardHeader>
                <CardTitle>{epic.name}</CardTitle>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

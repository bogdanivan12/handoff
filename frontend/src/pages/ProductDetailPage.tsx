import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Initiative, type Product } from "@/lib/api";

export function ProductDetailPage() {
  const { productId } = useParams<{ productId: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [initiatives, setInitiatives] = useState<Initiative[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");

  const load = () => {
    if (!productId) return;
    api.getProduct(productId).then(setProduct);
    api.listInitiatives(productId).then(setInitiatives);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!productId) return;
    await api.createInitiative({ product_id: productId, name });
    setName("");
    setShowForm(false);
    load();
  };

  if (!product) return null;

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Breadcrumb
        items={[
          { label: "Products", to: "/" },
          { label: product.name, to: `/products/${product.id}` },
        ]}
      />

      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{product.name} — Initiatives</h1>
        <Button onClick={() => setShowForm((value) => !value)}>New Initiative</Button>
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
        {initiatives.map((initiative) => (
          <Link key={initiative.id} to={`/products/${product.id}/initiatives/${initiative.id}`}>
            <Card>
              <CardHeader>
                <CardTitle>{initiative.name}</CardTitle>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

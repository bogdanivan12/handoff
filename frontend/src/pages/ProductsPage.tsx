import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Product } from "@/lib/api";

export function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [keyPrefix, setKeyPrefix] = useState("");

  const loadProducts = () => {
    api.listProducts().then(setProducts);
  };

  useEffect(() => {
    loadProducts();
  }, []);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    await api.createProduct({ name, key_prefix: keyPrefix });
    setName("");
    setKeyPrefix("");
    setShowForm(false);
    loadProducts();
  };

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Products</h1>
        <Button onClick={() => setShowForm((value) => !value)}>New Product</Button>
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
          <input
            className="rounded border px-2 py-1"
            placeholder="Key prefix (e.g. HAND)"
            value={keyPrefix}
            onChange={(event) => setKeyPrefix(event.target.value.toUpperCase())}
            required
          />
          <Button type="submit">Create</Button>
        </form>
      )}

      <div className="flex flex-col gap-2">
        {products.map((product) => (
          <Link key={product.id} to={`/products/${product.id}`}>
            <Card>
              <CardHeader>
                <CardTitle>{product.name}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {product.key_prefix}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

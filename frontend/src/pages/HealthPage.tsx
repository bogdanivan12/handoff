import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type HealthStatus = "checking" | "ok" | "error";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function HealthPage() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((response) => setStatus(response.ok ? "ok" : "error"))
      .catch(() => setStatus("error"));
  }, []);

  const statusColor =
    status === "ok" ? "text-green-600" : status === "error" ? "text-red-600" : "text-gray-500";

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <Card className="w-80">
        <CardHeader>
          <CardTitle>Handoff — Backend Health</CardTitle>
        </CardHeader>
        <CardContent>
          <p className={statusColor}>
            {status === "checking" && "Checking..."}
            {status === "ok" && "✓ Connected"}
            {status === "error" && "✗ Unreachable"}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

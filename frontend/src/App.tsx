import { BrowserRouter, Route, Routes } from "react-router-dom";

import { EpicDetailPage } from "@/pages/EpicDetailPage";
import { HealthPage } from "@/pages/HealthPage";
import { InitiativeDetailPage } from "@/pages/InitiativeDetailPage";
import { ProductDetailPage } from "@/pages/ProductDetailPage";
import { ProductKnowledgePage } from "@/pages/ProductKnowledgePage";
import { ProductSettingsPage } from "@/pages/ProductSettingsPage";
import { ProductsPage } from "@/pages/ProductsPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ProductsPage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/products/:productId" element={<ProductDetailPage />} />
        <Route path="/products/:productId/settings" element={<ProductSettingsPage />} />
        <Route path="/products/:productId/knowledge" element={<ProductKnowledgePage />} />
        <Route
          path="/products/:productId/initiatives/:initiativeId"
          element={<InitiativeDetailPage />}
        />
        <Route
          path="/products/:productId/initiatives/:initiativeId/epics/:epicId"
          element={<EpicDetailPage />}
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

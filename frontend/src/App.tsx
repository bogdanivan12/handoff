import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HealthPage } from "@/pages/HealthPage";
import { ProductsPage } from "@/pages/ProductsPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ProductsPage />} />
        <Route path="/health" element={<HealthPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

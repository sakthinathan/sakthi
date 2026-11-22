import React, { useEffect, useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import OrderIntake from './pages/OrderIntake';
import OrderReview from './pages/OrderReview';
import Dispatch from './pages/Dispatch';
import VIPAndPricing from './pages/VIPAndPricing';
import AIOpsCenter from './pages/AIOpsCenter';
import AuditLog from './pages/AuditLog';
import { api } from './services/api';

export default function App() {
  const [surgeMode, setSurgeMode] = useState(false);

  useEffect(() => {
    async function checkSurge() {
      try {
        const data = await api.getFlags();
        setSurgeMode(data.surge_survival_mode || false);
      } catch (_) {}
    }
    checkSurge();
    const interval = setInterval(checkSurge, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Routes>
      <Route path="/" element={<Layout surgeMode={surgeMode} />}>
        <Route index element={<Dashboard />} />
        <Route path="intake" element={<OrderIntake />} />
        <Route path="orders" element={<OrderReview />} />
        <Route path="dispatch" element={<Dispatch />} />
        <Route path="vip-pricing" element={<VIPAndPricing />} />
        <Route path="aiops" element={<AIOpsCenter />} />
        <Route path="audit" element={<AuditLog />} />
      </Route>
    </Routes>
  );
}

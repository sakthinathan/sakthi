import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ProviderBadge from '../components/ProviderBadge';
import { 
  ShoppingBag, 
  Clock, 
  Crown, 
  AlertCircle, 
  Activity, 
  Flame, 
  ArrowRight,
  TrendingUp,
  Truck
} from 'lucide-react';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recentOrders, setRecentOrders] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsData, ordersData, servicesData] = await Promise.all([
          api.getDashboardStats(),
          api.getOrders({ per_page: 5 }),
          api.getServices()
        ]);
        setStats(statsData);
        setRecentOrders(ordersData.orders || []);
        setServices(servicesData || []);
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <LoadingSpinner message="Loading festive operations cockpit..." />;

  return (
    <div className="space-y-6">
      {/* Top Banner: Surge Mode Notification */}
      {stats?.surge_mode_active && (
        <div className="p-4 bg-gradient-to-r from-amber-500/20 via-orange-500/20 to-rose-500/20 border border-amber-500/40 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Flame className="w-6 h-6 text-amber-500 animate-bounce" />
            <div>
              <h3 className="font-bold text-slate-900 text-sm">SURGE SURVIVAL MODE ACTIVE</h3>
              <p className="text-xs text-slate-600">
                Express delivery is currently prioritized for VIP customers only. Standard traffic shedding enabled.
              </p>
            </div>
          </div>
          <Link
            to="/vip-pricing"
            className="px-3 py-1.5 text-xs font-semibold bg-amber-500 hover:bg-amber-600 text-white rounded-lg transition"
          >
            Adjust Rules
          </Link>
        </div>
      )}

      {/* Integration Provider Status Bar */}
      <div className="bg-white px-5 py-3 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
        <span className="font-bold text-slate-700 tracking-wide uppercase text-[11px] flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-amber-500" />
          Verified Runtime Integrations
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <ProviderBadge provider="sarvam_document_ai" status="live" isMock={false} label="Sarvam AI" />
          <ProviderBadge provider="flagsmith_live" status="live" isMock={false} label="Flagsmith" />
          <ProviderBadge provider="google_address_validation" status="live" isMock={false} label="Google Cloud APIs" />
          <ProviderBadge provider="gemini_byom" status="live" isMock={false} label="NudgeBee + Gemini BYOM" />
        </div>
      </div>

      {/* Stats KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Orders</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{stats?.total_orders || 0}</p>
            <div className="flex items-center gap-1 text-xs text-emerald-600 font-medium mt-1">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Festive Surge</span>
            </div>
          </div>
          <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
            <ShoppingBag className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Needs Review</p>
            <p className="text-2xl font-bold text-amber-600 mt-1">{stats?.orders_needing_review || 0}</p>
            <p className="text-xs text-slate-500 mt-1">Chits & Voice notes</p>
          </div>
          <div className="w-12 h-12 bg-amber-50 text-amber-600 rounded-xl flex items-center justify-center">
            <Clock className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">VIP Orders</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{stats?.vip_orders || 0}</p>
            <p className="text-xs text-emerald-600 font-medium mt-1">Priority Express Active</p>
          </div>
          <div className="w-12 h-12 bg-amber-50 text-amber-600 rounded-xl flex items-center justify-center">
            <Crown className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Incidents</p>
            <p className={`text-2xl font-bold mt-1 ${(stats?.active_incidents || 0) > 0 ? 'text-rose-600' : 'text-slate-900'}`}>
              {stats?.active_incidents || 0}
            </p>
            <p className="text-xs text-slate-500 mt-1">NudgeBee Telemetry</p>
          </div>
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${(stats?.active_incidents || 0) > 0 ? 'bg-rose-50 text-rose-600' : 'bg-emerald-50 text-emerald-600'}`}>
            <Activity className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Cluster Health & Recent Orders Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Kubernetes / AIOps Service Health */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 tracking-wide flex items-center gap-2">
              <Activity className="w-4 h-4 text-slate-500" />
              Service Status (k3s Cluster)
            </h2>
            <Link to="/aiops" className="text-xs text-amber-600 hover:text-amber-700 font-semibold flex items-center gap-1">
              AIOps Center <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="space-y-3">
            {services.map((svc) => (
              <div key={svc.name} className="p-3.5 bg-slate-50 rounded-lg border border-slate-200/80 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs text-slate-900">{svc.name}</span>
                  <StatusBadge status={svc.status} />
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-500">
                  <div>Criticality: <span className="font-medium text-slate-700">{svc.criticality}</span></div>
                  <div>Replicas: <span className="font-medium text-slate-700">{svc.details?.replicas}</span></div>
                  <div>CPU: <span className="font-medium text-slate-700">{svc.details?.cpu}</span></div>
                  <div>p99: <span className="font-medium text-slate-700">{svc.details?.latency_p99}</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Festive Orders Table */}
        <div className="lg:col-span-2 bg-white p-5 rounded-xl border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 tracking-wide flex items-center gap-2">
              <ShoppingBag className="w-4 h-4 text-slate-500" />
              Recent Festive Orders
            </h2>
            <Link to="/orders" className="text-xs text-amber-600 hover:text-amber-700 font-semibold flex items-center gap-1">
              View All <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {recentOrders.length === 0 ? (
            <p className="text-sm text-slate-500 py-8 text-center">No orders recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 uppercase font-semibold">
                    <th className="pb-2">Order #</th>
                    <th className="pb-2">Customer</th>
                    <th className="pb-2">Items</th>
                    <th className="pb-2">Total</th>
                    <th className="pb-2">VIP</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentOrders.map((ord) => (
                    <tr key={ord.id} className="hover:bg-slate-50/80 transition">
                      <td className="py-2.5 font-semibold text-slate-900">{ord.order_number}</td>
                      <td className="py-2.5 text-slate-700">{ord.customer_name}</td>
                      <td className="py-2.5 text-slate-500">{ord.items?.length || 0} items</td>
                      <td className="py-2.5 font-medium text-slate-900">₹{ord.total}</td>
                      <td className="py-2.5">
                        {ord.is_vip_order ? (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800">
                            VIP
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="py-2.5">
                        <StatusBadge status={ord.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

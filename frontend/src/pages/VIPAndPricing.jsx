import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import ConfirmDialog from '../components/ConfirmDialog';
import { 
  Crown, 
  Flame, 
  Tag, 
  CheckCircle2, 
  XCircle,
  ToggleLeft,
  ToggleRight,
  ShieldCheck
} from 'lucide-react';

export default function VIPAndPricing() {
  const [customers, setCustomers] = useState([]);
  const [flags, setFlags] = useState({});
  const [surgeMode, setSurgeMode] = useState(false);
  const [rules, setRules] = useState({});
  const [loading, setLoading] = useState(true);
  const [confirmSurge, setConfirmSurge] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const [custList, flagData, ruleData] = await Promise.all([
        api.getCustomers({ per_page: 50 }),
        api.getFlags(),
        api.getBusinessRules()
      ]);
      setCustomers(custList.customers || []);
      setFlags(flagData.flags || {});
      setSurgeMode(flagData.surge_survival_mode || false);
      setRules(ruleData.rules || {});
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  const handleToggleVIP = async (id) => {
    try {
      const res = await api.toggleVIP(id);
      setToast({
        message: `${res.name} is now ${res.is_vip ? 'VIP (Express Prioritized)' : 'Regular tier'}`,
        type: 'success'
      });
      await loadAll();
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    }
  };

  const handleSurgeConfirm = async () => {
    const nextState = !surgeMode;
    try {
      await api.toggleSurgeMode(nextState, 'Operator triggered in VIP Cockpit');
      setSurgeMode(nextState);
      setToast({
        message: `Surge Survival Mode ${nextState ? 'ENABLED - Express locked to VIPs' : 'DISABLED'}`,
        type: nextState ? 'error' : 'success'
      });
      setConfirmSurge(false);
      await loadAll();
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    }
  };

  if (loading) return <LoadingSpinner message="Evaluating Flagsmith feature flags..." />;

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <ConfirmDialog
        isOpen={confirmSurge}
        title={surgeMode ? 'Disable Surge Survival Mode?' : 'Enable Surge Survival Mode?'}
        message={
          surgeMode
            ? 'This will restore standard express delivery availability for all customers across India.'
            : 'During peak festive traffic, this strictly restricts express delivery slots to verified VIP festive buyers to protect checkout stability.'
        }
        confirmText={surgeMode ? 'Disable Surge' : 'Enable Surge'}
        confirmStyle={surgeMode ? 'normal' : 'danger'}
        onConfirm={handleSurgeConfirm}
        onCancel={() => setConfirmSurge(false)}
      />

      {/* Flagsmith Business Rules & Surge Cockpit */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Crown className="w-5 h-5 text-amber-500" />
              Flagsmith Business Rules & Surge Survival Mode
            </h2>
            <p className="text-xs text-slate-500">
              Live feature flag evaluation and festive segment prioritization (vip_festive_buyers)
            </p>
          </div>

          <button
            onClick={() => setConfirmSurge(true)}
            className={`px-4 py-2.5 rounded-xl font-bold text-xs flex items-center gap-2 transition shadow-xs ${
              surgeMode
                ? 'bg-rose-600 hover:bg-rose-700 text-white'
                : 'bg-slate-900 hover:bg-slate-800 text-white'
            }`}
          >
            <Flame className="w-4 h-4 text-amber-400" />
            {surgeMode ? 'Surge Mode ACTIVE (Turn Off)' : 'Trigger Surge Survival Mode'}
          </button>
        </div>

        {/* Live Rule Indicators */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200/80 space-y-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">VIP Express Delivery</span>
            <div className="flex items-center gap-2 text-emerald-600 font-bold text-sm">
              <CheckCircle2 className="w-4 h-4" /> Always Enabled
            </div>
            <p className="text-[11px] text-slate-500">Guaranteed dispatch slots even during severe traffic bursts</p>
          </div>

          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200/80 space-y-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Non-VIP Express Delivery</span>
            <div className={`flex items-center gap-2 font-bold text-sm ${surgeMode ? 'text-rose-600' : 'text-emerald-600'}`}>
              {surgeMode ? <XCircle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
              {surgeMode ? 'Disabled (Surge Shedding)' : 'Active (Normal Capacity)'}
            </div>
            <p className="text-[11px] text-slate-500">Controlled dynamically by `surge_survival_mode` flag</p>
          </div>

          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200/80 space-y-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Festive Bundle Pricing</span>
            <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
              <Tag className="w-4 h-4 text-amber-500" /> ₹{rules.festive_bundle_price || 999}
            </div>
            <p className="text-[11px] text-slate-500">Live dynamic pricing value from Flagsmith</p>
          </div>
        </div>
      </div>

      {/* Customer Directory & VIP Promotion */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
        <h3 className="font-bold text-sm text-slate-900">Festive Customer Directory & VIP Segmentation</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-400 uppercase font-semibold">
                <th className="pb-3">Customer Name</th>
                <th className="pb-3">Phone</th>
                <th className="pb-3">Tier</th>
                <th className="pb-3">Orders</th>
                <th className="pb-3">Lifetime Spend</th>
                <th className="pb-3">VIP Status</th>
                <th className="pb-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {customers.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/80 transition">
                  <td className="py-3 font-semibold text-slate-900">{c.name}</td>
                  <td className="py-3 text-slate-600">{c.phone || '—'}</td>
                  <td className="py-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${c.is_vip ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700'}`}>
                      {c.tier?.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 text-slate-700">{c.total_orders}</td>
                  <td className="py-3 font-medium text-slate-900">₹{c.total_spent}</td>
                  <td className="py-3">
                    {c.is_vip ? (
                      <span className="text-amber-600 font-bold flex items-center gap-1">
                        <Crown className="w-3.5 h-3.5" /> VIP
                      </span>
                    ) : (
                      <span className="text-slate-400">Regular</span>
                    )}
                  </td>
                  <td className="py-3">
                    <button
                      onClick={() => handleToggleVIP(c.id)}
                      className="px-2.5 py-1 text-[11px] font-bold text-amber-700 hover:bg-amber-50 rounded border border-amber-300 transition"
                    >
                      {c.is_vip ? 'Revoke VIP' : 'Promote to VIP'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import { ShieldCheck, Clock } from 'lucide-react';

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadLogs() {
      try {
        const data = await api.getAuditLogs(100);
        setLogs(data || []);
      } catch (err) {
        console.error('Audit load failed:', err);
      } finally {
        setLoading(false);
      }
    }
    loadLogs();
  }, []);

  if (loading) return <LoadingSpinner message="Retrieving tamper-evident audit logs..." />;

  return (
    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
      <div>
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-emerald-600" />
          Immutable Operational Audit Trail
        </h2>
        <p className="text-xs text-slate-500">
          Full observability record of all orders, human approvals, AIOps mitigations, and feature flag changes.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-200 text-slate-400 uppercase font-semibold">
              <th className="pb-3">Timestamp</th>
              <th className="pb-3">Entity</th>
              <th className="pb-3">Action</th>
              <th className="pb-3">Actor</th>
              <th className="pb-3">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-mono">
            {logs.map((log) => (
              <tr key={log.id} className="hover:bg-slate-50/80 transition">
                <td className="py-2.5 text-slate-500 whitespace-nowrap">
                  {new Date(log.created_at).toLocaleString()}
                </td>
                <td className="py-2.5 font-semibold text-slate-900">{log.entity_type}</td>
                <td className="py-2.5 text-amber-700 font-medium">{log.action}</td>
                <td className="py-2.5 text-slate-600">{log.actor}</td>
                <td className="py-2.5 text-slate-500 text-[11px] max-w-xs truncate">
                  {JSON.stringify(log.details)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

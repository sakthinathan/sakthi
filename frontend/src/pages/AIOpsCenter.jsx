import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import StatusBadge from '../components/StatusBadge';
import ProviderBadge from '../components/ProviderBadge';
import { 
  Activity, 
  AlertTriangle, 
  ShieldAlert, 
  Search, 
  CheckCircle, 
  Play, 
  RotateCcw,
  Cpu,
  Flame,
  Check
} from 'lucide-react';

export default function AIOpsCenter() {
  const [services, setServices] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [investigating, setInvestigating] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    loadAIOpsData();
  }, []);

  async function loadAIOpsData() {
    setLoading(true);
    try {
      const [svcList, incList] = await Promise.all([
        api.getServices(),
        api.getIncidents()
      ]);
      setServices(svcList || []);
      setIncidents(incList.incidents || []);
      if (incList.incidents?.length > 0 && !selectedIncident) {
        setSelectedIncident(incList.incidents[0]);
      }
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  const handleSimulateDegradation = async () => {
    setSimulating(true);
    try {
      const res = await api.simulateDegradation('utsavops-checkout');
      setToast({
        message: 'Diwali rush surge simulated: Checkout p99 degraded to 4800ms!',
        type: 'error'
      });
      await loadAIOpsData();
      if (res.incident_id) {
        const fresh = await api.getIncident(res.incident_id);
        setSelectedIncident(fresh);
      }
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    } finally {
      setSimulating(false);
    }
  };

  const handleInvestigate = async () => {
    if (!selectedIncident) return;
    setInvestigating(true);
    try {
      await api.investigateIncident(selectedIncident.id);
      setToast({ message: 'Gemini BYOM RCA investigation completed!', type: 'success' });
      const fresh = await api.getIncident(selectedIncident.id);
      setSelectedIncident(fresh);
      await loadAIOpsData();
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    } finally {
      setInvestigating(false);
    }
  };

  const handleApproveAction = async (actionId) => {
    try {
      await api.approveAction(selectedIncident.id, actionId, 'Lead SRE', 'Approved bounded mitigation');
      setToast({ message: 'Mitigation approved by human operator', type: 'success' });
      const fresh = await api.getIncident(selectedIncident.id);
      setSelectedIncident(fresh);
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    }
  };

  const handleExecuteAction = async (actionId) => {
    try {
      await api.executeAction(selectedIncident.id, actionId);
      setToast({ message: 'Bounded mitigation safely executed', type: 'success' });
      const fresh = await api.getIncident(selectedIncident.id);
      setSelectedIncident(fresh);
      await loadAIOpsData();
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    }
  };

  const handleVerifyRecovery = async () => {
    try {
      const verif = await api.verifyRecovery(selectedIncident.id);
      setToast({ message: 'Checkout recovery verified: latency restored to 110ms!', type: 'success' });
      const fresh = await api.getIncident(selectedIncident.id);
      setSelectedIncident(fresh);
      await loadAIOpsData();
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    }
  };

  const handleRestore = async () => {
    try {
      await api.restoreChanges(selectedIncident.id);
      setToast({ message: 'Workload limits and feature flags restored to normal', type: 'info' });
      await loadAIOpsData();
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    }
  };

  if (loading) return <LoadingSpinner message="Querying NudgeBee telemetry and k3s status..." />;

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* Cluster Overview Header */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Activity className="w-5 h-5 text-amber-500" />
              NudgeBee & Kubernetes AIOps Cockpit
            </h2>
            <ProviderBadge
              provider="gemini_byom"
              status="live"
              isMock={false}
              label="Gemini BYOM RCA"
            />
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Automated anomaly detection, Gemini BYOM root-cause analysis, and human-authorized bounded mitigations.
          </p>
        </div>

        <button
          onClick={handleSimulateDegradation}
          disabled={simulating}
          className="px-4 py-2.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white font-bold rounded-xl text-xs flex items-center gap-2 transition shadow-md shadow-rose-600/20"
        >
          <Flame className="w-4 h-4" />
          Simulate Diwali Surge Incident
        </button>
      </div>

      {/* Service Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {services.map((svc) => (
          <div key={svc.name} className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-slate-900">{svc.name}</span>
                {svc.status === 'degraded' ? (
                  <span className="text-[10px] bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded-full border border-amber-300">
                    SIMULATED SURGE ANOMALY
                  </span>
                ) : (
                  <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded-full border border-emerald-300">
                    LIVE CLUSTER (utsavops-nudgebee)
                  </span>
                )}
              </div>
              <StatusBadge status={svc.status} />
            </div>
            <div className="grid grid-cols-4 gap-2 text-center text-xs">
              <div className="bg-slate-50 p-2 rounded">
                <span className="text-[10px] text-slate-400 block font-semibold">PODS</span>
                <span className="font-bold text-slate-800">{svc.details?.replicas}</span>
              </div>
              <div className="bg-slate-50 p-2 rounded">
                <span className="text-[10px] text-slate-400 block font-semibold">CPU</span>
                <span className="font-bold text-slate-800">{svc.details?.cpu}</span>
              </div>
              <div className="bg-slate-50 p-2 rounded">
                <span className="text-[10px] text-slate-400 block font-semibold">p99 LATENCY</span>
                <span className={`font-bold ${svc.status === 'degraded' ? 'text-rose-600' : 'text-slate-800'}`}>
                  {svc.details?.latency_p99}
                </span>
              </div>
              <div className="bg-slate-50 p-2 rounded">
                <span className="text-[10px] text-slate-400 block font-semibold">ERRORS</span>
                <span className="font-bold text-slate-800">{svc.details?.error_rate}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Incident Investigation Timeline & Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Incidents List */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden flex flex-col h-[650px]">
          <div className="p-4 border-b border-slate-100 font-bold text-xs uppercase tracking-wider text-slate-500">
            Detected Incidents ({incidents.length})
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {incidents.map((inc) => (
              <div
                key={inc.id}
                onClick={() => setSelectedIncident(inc)}
                className={`p-4 cursor-pointer transition ${
                  selectedIncident?.id === inc.id ? 'bg-amber-50/70 border-l-4 border-amber-500' : 'hover:bg-slate-50'
                }`}
              >
                <div className="flex justify-between items-start">
                  <span className="font-bold text-xs text-slate-900">{inc.service_name}</span>
                  <StatusBadge status={inc.status} />
                </div>
                <p className="text-xs text-slate-600 mt-1 line-clamp-2">{inc.title}</p>
                <p className="text-[10px] text-slate-400 mt-2 font-mono">
                  {new Date(inc.detected_at).toLocaleTimeString()}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* RCA & Mitigation Details */}
        {selectedIncident && (
          <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-6">
            <div className="flex justify-between items-start border-b border-slate-100 pb-4">
              <div>
                <h3 className="font-bold text-base text-slate-900">{selectedIncident.title}</h3>
                <div className="flex items-center gap-2 mt-1">
                  <StatusBadge status={selectedIncident.status} />
                  <span className="text-xs text-slate-500">Service: {selectedIncident.service_name}</span>
                </div>
              </div>

              {selectedIncident.status === 'detected' && (
                <button
                  onClick={handleInvestigate}
                  disabled={investigating}
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-lg transition flex items-center gap-1.5 shadow-xs"
                >
                  <Search className="w-3.5 h-3.5" />
                  {investigating ? 'Analyzing Telemetry...' : 'NudgeBee / Gemini RCA'}
                </button>
              )}
            </div>

            {/* Root Cause Analysis Box */}
            {selectedIncident.root_cause && (
              <div className="p-4 bg-amber-50/60 rounded-xl border border-amber-200 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-amber-900 uppercase tracking-wider flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4 text-amber-600" />
                    Gemini BYOM Grounded Root Cause
                  </span>
                  <span className="text-[10px] font-mono bg-amber-200/80 text-amber-900 font-bold px-2 py-0.5 rounded border border-amber-300/60">
                    Model: gemini-flash-latest
                  </span>
                </div>
                <p className="text-xs text-amber-950 leading-relaxed font-medium">
                  {selectedIncident.root_cause}
                </p>
                {selectedIncident.evidence && (
                  <div className="pt-2 border-t border-amber-200/60 flex flex-wrap gap-3 text-[11px] text-amber-900">
                    <span className="font-semibold">Telemetry Evidence:</span>
                    {Object.entries(selectedIncident.evidence).map(([k, v]) => (
                      <span key={k} className="bg-white/80 px-2 py-0.5 rounded border border-amber-200 font-mono text-[10px]">
                        {k}: {String(v)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Bounded Mitigations Timeline */}
            <div className="space-y-3">
              <h4 className="font-bold text-xs uppercase tracking-wider text-slate-500">
                Authorized Bounded Mitigations (Safety Allowlist)
              </h4>
              <div className="space-y-3">
                {selectedIncident.actions?.map((act) => (
                  <div key={act.id} className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-900">{act.action_type}</span>
                        <StatusBadge status={act.status} />
                      </div>
                      <p className="text-xs text-slate-600">{act.description}</p>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {act.status === 'proposed' && (
                        <button
                          onClick={() => handleApproveAction(act.id)}
                          className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold flex items-center gap-1"
                        >
                          <Check className="w-3.5 h-3.5" /> Approve
                        </button>
                      )}
                      {act.status === 'approved' && (
                        <button
                          onClick={() => handleExecuteAction(act.id)}
                          className="px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-slate-950 rounded-lg text-xs font-bold flex items-center gap-1 shadow-xs"
                        >
                          <Play className="w-3.5 h-3.5" /> Execute
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Recovery & Restore Buttons */}
            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <button
                onClick={handleRestore}
                className="px-4 py-2 border border-slate-300 hover:bg-slate-50 rounded-lg text-xs font-semibold text-slate-700 flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Restore Normal Workload
              </button>

              {selectedIncident.status !== 'resolved' && (
                <button
                  onClick={handleVerifyRecovery}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg text-xs flex items-center gap-1.5 shadow-xs"
                >
                  <CheckCircle className="w-4 h-4" /> Verify Checkout Recovery
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import StatusBadge from '../components/StatusBadge';
import { 
  Truck, 
  MapPin, 
  Wind, 
  CheckCircle, 
  AlertTriangle,
  ExternalLink,
  Navigation
} from 'lucide-react';

export default function Dispatch() {
  const [orders, setOrders] = useState([]);
  const [selectedOrderId, setSelectedOrderId] = useState('');
  const [dispatchInfo, setDispatchInfo] = useState(null);
  const [aqiData, setAqiData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [addressInput, setAddressInput] = useState('');
  const [toast, setToast] = useState(null);

  useEffect(() => {
    async function init() {
      try {
        const res = await api.getOrders({ per_page: 50 });
        setOrders(res.orders || []);
        if (res.orders?.length > 0) {
          const firstId = res.orders[0].id;
          setSelectedOrderId(firstId);
          await loadDispatch(firstId);
        }
      } catch (err) {
        setToast({ message: err.message, type: 'error' });
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  async function loadDispatch(orderId) {
    try {
      const data = await api.getDispatch(orderId);
      setDispatchInfo(data);
      setAddressInput(data.delivery_address || '');
      if (data.latitude && data.longitude) {
        const aqi = await api.getAirQuality(orderId);
        setAqiData(aqi);
      }
    } catch (err) {
      console.log('Dispatch load note:', err);
    }
  }

  const handleOrderChange = async (e) => {
    const id = e.target.value;
    setSelectedOrderId(id);
    await loadDispatch(id);
  };

  const handleValidateAddress = async () => {
    if (!addressInput) return;
    setLoading(true);
    try {
      const updated = await api.validateAddress(selectedOrderId, addressInput);
      setDispatchInfo(updated);
      setToast({ message: 'Address validated via Google Address Validation API', type: 'success' });
      if (updated.latitude && updated.longitude) {
        const aqi = await api.getAirQuality(selectedOrderId);
        setAqiData(aqi);
      }
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner message="Loading delivery & geocoding data..." />;

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Dispatch & Google Maps Intelligence</h2>
            <p className="text-xs text-slate-500">
              Address Validation, High-Precision Geocoding, and Contextual Air Quality Telemetry
            </p>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-slate-600">Select Order:</label>
            <select
              value={selectedOrderId}
              onChange={handleOrderChange}
              className="text-xs font-medium border border-slate-300 rounded-lg px-3 py-1.5 bg-white text-slate-800 focus:outline-hidden"
            >
              {orders.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.order_number} ({o.customer_name})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Address Validation Cockpit */}
        <div className="space-y-3 pt-2">
          <label className="text-xs font-bold text-slate-700">Delivery Address</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={addressInput}
              onChange={(e) => setAddressInput(e.target.value)}
              className="flex-1 text-xs border border-slate-300 rounded-lg p-2.5 text-slate-800"
              placeholder="Enter delivery address..."
            />
            <button
              onClick={handleValidateAddress}
              className="px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold rounded-lg text-xs transition flex items-center gap-1.5"
            >
              <Navigation className="w-3.5 h-3.5" /> Validate Address
            </button>
          </div>
        </div>

        {/* Validation Results Grid */}
        {dispatchInfo && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-100">
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Google Address Validation
              </span>
              <div className="flex items-center gap-2">
                <StatusBadge status={dispatchInfo.validation_status} />
                <span className="text-xs text-slate-500">Status: {dispatchInfo.geocoding_status || 'OK'}</span>
              </div>
              <p className="text-xs font-medium text-slate-800">
                {dispatchInfo.validated_address || dispatchInfo.delivery_address}
              </p>
              {dispatchInfo.latitude && dispatchInfo.longitude && (
                <div className="flex items-center gap-3 text-xs text-slate-600 pt-1">
                  <span className="font-mono bg-slate-200/60 px-2 py-0.5 rounded text-[11px]">
                    {Number(dispatchInfo.latitude).toFixed(4)}, {Number(dispatchInfo.longitude).toFixed(4)}
                  </span>
                  <a
                    href={`https://maps.google.com/?q=${dispatchInfo.latitude},${dispatchInfo.longitude}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-amber-600 hover:text-amber-700 flex items-center gap-1 font-semibold"
                  >
                    Open in Maps <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              )}
            </div>

            {/* Contextual Air Quality Telemetry */}
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                <Wind className="w-3.5 h-3.5 text-slate-400" />
                Air Quality Telemetry (Contextual)
              </span>
              {aqiData ? (
                <>
                  <div className="flex items-center gap-3">
                    <span className="text-2xl font-black text-amber-600">{aqiData.aqi_value}</span>
                    <span className="text-xs font-bold text-slate-800">{aqiData.aqi_category}</span>
                  </div>
                  <p className="text-[11px] text-slate-600">{aqiData.health_recommendations}</p>
                  <p className="text-[10px] text-slate-400 italic pt-1 border-t border-slate-200">
                    {aqiData.disclaimer}
                  </p>
                </>
              ) : (
                <p className="text-xs text-slate-500">Validate address to fetch local air quality metrics.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

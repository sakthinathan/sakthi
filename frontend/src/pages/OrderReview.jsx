import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import ProviderBadge from '../components/ProviderBadge';
import { 
  Check, 
  X, 
  Edit3, 
  Volume2, 
  Crown, 
  MapPin, 
  Sparkles,
  ShoppingBag
} from 'lucide-react';

export default function OrderReview() {
  const [orders, setOrders] = useState([]);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState({});
  const [toast, setToast] = useState(null);

  useEffect(() => {
    loadOrders();
  }, []);

  async function loadOrders() {
    setLoading(true);
    try {
      const data = await api.getOrders({ per_page: 50 });
      setOrders(data.orders || []);
      if (data.orders?.length > 0 && !selectedOrder) {
        setSelectedOrder(data.orders[0]);
        setFormData({
          customer_name: data.orders[0].customer_name || '',
          special_instructions: data.orders[0].special_instructions || '',
        });
      }
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  const handleSelectOrder = (ord) => {
    setSelectedOrder(ord);
    setFormData({
      customer_name: ord.customer_name || '',
      special_instructions: ord.special_instructions || '',
    });
    setEditing(false);
  };

  const handleApprove = async () => {
    try {
      await api.approveOrder(selectedOrder.id);
      setToast({ message: `Order ${selectedOrder.order_number} approved!`, type: 'success' });
      await loadOrders();
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    }
  };

  const handleReject = async () => {
    try {
      await api.rejectOrder(selectedOrder.id, 'Operator rejected in review');
      setToast({ message: `Order ${selectedOrder.order_number} rejected.`, type: 'info' });
      await loadOrders();
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    }
  };

  const handleSaveReview = async () => {
    try {
      await api.reviewOrder(selectedOrder.id, formData);
      setToast({ message: 'Order changes saved', type: 'success' });
      setEditing(false);
      await loadOrders();
    } catch (err) {
      setToast({ message: err.message, type: 'error' });
    }
  };

  const handlePlayVoiceConfirm = () => {
    const url = api.getVoiceConfirmationUrl(selectedOrder.id);
    const audio = new Audio(url);
    audio.play().catch((e) => console.log('Audio playback notice:', e));
    setToast({ message: 'Bulbul v3 voice confirmation triggered', type: 'info' });
  };

  if (loading) return <LoadingSpinner message="Loading orders..." />;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* Orders Sidebar List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden flex flex-col h-[750px]">
        <div className="p-4 border-b border-slate-100 font-bold text-sm text-slate-800 flex justify-between items-center">
          <span>Festive Orders ({orders.length})</span>
        </div>
        <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
          {orders.map((ord) => (
            <div
              key={ord.id}
              onClick={() => handleSelectOrder(ord)}
              className={`p-4 cursor-pointer transition ${
                selectedOrder?.id === ord.id ? 'bg-amber-50/70 border-l-4 border-amber-500' : 'hover:bg-slate-50'
              }`}
            >
              <div className="flex justify-between items-start">
                <span className="font-bold text-xs text-slate-900">{ord.order_number}</span>
                <StatusBadge status={ord.status} />
              </div>
              <p className="text-xs font-medium text-slate-700 mt-1">{ord.customer_name}</p>
              <div className="flex justify-between items-center mt-2 text-[11px] text-slate-500">
                <span>{ord.items?.length || 0} items</span>
                <span className="font-bold text-slate-900">₹{ord.total}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Order Details & Human-In-The-Loop Cockpit */}
      {selectedOrder && (
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900">{selectedOrder.order_number}</h2>
                <StatusBadge status={selectedOrder.status} />
                {selectedOrder.is_vip_order && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded">
                    <Crown className="w-3 h-3 text-amber-600" /> VIP ORDER
                  </span>
                )}
                <ProviderBadge
                  provider={selectedOrder.order_input?.input_type === 'audio' ? 'sarvam_saaras_stt' : 'sarvam_document_ai'}
                  status="live"
                  isMock={false}
                />
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Intake Source: {selectedOrder.order_input?.input_type?.toUpperCase() || 'MANUAL'}
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2">
              <button
                onClick={handlePlayVoiceConfirm}
                className="p-2 text-slate-600 hover:bg-slate-100 rounded-lg text-xs font-semibold flex items-center gap-1 border border-slate-200"
                title="Sarvam Bulbul Voice Confirmation"
              >
                <Volume2 className="w-4 h-4 text-amber-600" />
                Voice Confirmation
              </button>
              {selectedOrder.status === 'pending_review' && (
                <>
                  <button
                    onClick={handleReject}
                    className="px-3 py-2 bg-rose-50 text-rose-700 hover:bg-rose-100 rounded-lg text-xs font-bold transition flex items-center gap-1"
                  >
                    <X className="w-4 h-4" /> Reject
                  </button>
                  <button
                    onClick={handleApprove}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1 shadow-xs"
                  >
                    <Check className="w-4 h-4" /> Approve Order
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Original Input Text / Transcript */}
          {selectedOrder.order_input?.original_text && (
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80 space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Original Input / Regional Transcription
              </span>
              <p className="text-xs text-slate-800 italic">
                "{selectedOrder.order_input.original_text}"
              </p>
            </div>
          )}

          {/* Editable Customer & Order Information */}
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-bold text-xs uppercase tracking-wider text-slate-500">Customer Details</h3>
              <button
                onClick={() => setEditing(!editing)}
                className="text-xs text-amber-600 font-semibold flex items-center gap-1"
              >
                <Edit3 className="w-3.5 h-3.5" />
                {editing ? 'Cancel' : 'Edit Information'}
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[11px] font-medium text-slate-500">Customer Name</label>
                {editing ? (
                  <input
                    type="text"
                    value={formData.customer_name}
                    onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                    className="w-full text-xs border rounded p-2 mt-1"
                  />
                ) : (
                  <p className="font-bold text-slate-900 text-sm mt-0.5">{selectedOrder.customer_name}</p>
                )}
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-500">Special Instructions</label>
                {editing ? (
                  <input
                    type="text"
                    value={formData.special_instructions}
                    onChange={(e) => setFormData({ ...formData, special_instructions: e.target.value })}
                    className="w-full text-xs border rounded p-2 mt-1"
                  />
                ) : (
                  <p className="text-xs text-slate-700 mt-0.5">
                    {selectedOrder.special_instructions || 'None provided'}
                  </p>
                )}
              </div>
            </div>

            {editing && (
              <button
                onClick={handleSaveReview}
                className="px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-semibold"
              >
                Save Changes
              </button>
            )}
          </div>

          {/* Order Items Table */}
          <div className="space-y-2">
            <h3 className="font-bold text-xs uppercase tracking-wider text-slate-500">Order Items</h3>
            <div className="border border-slate-200 rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="p-3">Product Name</th>
                    <th className="p-3">Quantity</th>
                    <th className="p-3">Unit Price</th>
                    <th className="p-3">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {selectedOrder.items?.map((it) => (
                    <tr key={it.id}>
                      <td className="p-3 font-medium text-slate-900">{it.product_name}</td>
                      <td className="p-3 text-slate-600">{it.quantity}</td>
                      <td className="p-3 text-slate-600">₹{it.unit_price}</td>
                      <td className="p-3 font-semibold text-slate-900">₹{it.total_price}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end pt-2 text-sm font-bold text-slate-900">
              Total: ₹{selectedOrder.total}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

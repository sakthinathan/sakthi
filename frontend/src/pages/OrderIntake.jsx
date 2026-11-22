import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import { UploadCloud, Mic, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';

export default function OrderIntake() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('image'); // 'image' or 'audio'
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [language, setLanguage] = useState('hi-IN');
  const [loading, setLoading] = useState(false);
  const [extractedResult, setExtractedResult] = useState(null);
  const [toast, setToast] = useState(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      if (activeTab === 'image') {
        setPreviewUrl(URL.createObjectURL(file));
      }
    }
  };

  const handleProcessOrder = async () => {
    if (!selectedFile) {
      setToast({ message: 'Please select a file to analyze', type: 'error' });
      return;
    }

    setLoading(true);
    try {
      let res;
      if (activeTab === 'image') {
        res = await api.uploadOrderImage(selectedFile);
      } else {
        res = await api.uploadOrderAudio(selectedFile, language);
      }
      setExtractedResult(res);
      setToast({ message: 'Order analyzed by Sarvam AI successfully!', type: 'success' });
    } catch (err) {
      setToast({ message: `Intake failed: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Multilingual Order Intake</h2>
          <p className="text-xs text-slate-500">
            Powered by Sarvam AI: Document AI (handwritten chits), Saaras v4 (speech-to-text), and Mayura v1 (translation)
          </p>
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => { setActiveTab('image'); setSelectedFile(null); setPreviewUrl(null); }}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition ${
              activeTab === 'image'
                ? 'border-amber-500 text-amber-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <UploadCloud className="w-4 h-4" />
            Handwritten Order Chit (Image)
          </button>
          <button
            onClick={() => { setActiveTab('audio'); setSelectedFile(null); setPreviewUrl(null); }}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition ${
              activeTab === 'audio'
                ? 'border-amber-500 text-amber-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Mic className="w-4 h-4" />
            Voice Note Order (Audio)
          </button>
        </div>

        {/* Image Tab */}
        {activeTab === 'image' && (
          <div className="space-y-4">
            <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-amber-400 transition bg-slate-50/50">
              <input
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="hidden"
                id="chit-upload"
              />
              <label htmlFor="chit-upload" className="cursor-pointer space-y-2 block">
                <UploadCloud className="w-10 h-10 text-slate-400 mx-auto" />
                <div className="text-sm font-semibold text-slate-700">
                  {selectedFile ? selectedFile.name : 'Upload handwritten festive chit'}
                </div>
                <p className="text-xs text-slate-400">PNG, JPG, or WebP up to 10MB</p>
              </label>
            </div>

            {previewUrl && (
              <div className="flex items-center gap-4 p-3 bg-slate-100 rounded-lg">
                <img src={previewUrl} alt="Preview" className="w-20 h-20 object-cover rounded border" />
                <div className="text-xs text-slate-600 space-y-1">
                  <p className="font-semibold text-slate-800">{selectedFile?.name}</p>
                  <p>{(selectedFile.size / 1024).toFixed(1)} KB</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Audio Tab */}
        {activeTab === 'audio' && (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <label className="text-xs font-semibold text-slate-700">Spoken Language:</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="text-xs font-medium border border-slate-300 rounded-lg px-3 py-1.5 bg-white text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-amber-500"
              >
                <option value="hi-IN">Hindi (हिन्दी)</option>
                <option value="ta-IN">Tamil (தமிழ்)</option>
                <option value="te-IN">Telugu (తెలుగు)</option>
                <option value="kn-IN">Kannada (ಕನ್ನಡ)</option>
                <option value="bn-IN">Bengali (বাংলা)</option>
                <option value="en-IN">Indian English</option>
              </select>
            </div>

            <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-amber-400 transition bg-slate-50/50">
              <input
                type="file"
                accept="audio/*"
                onChange={handleFileChange}
                className="hidden"
                id="audio-upload"
              />
              <label htmlFor="audio-upload" className="cursor-pointer space-y-2 block">
                <Mic className="w-10 h-10 text-slate-400 mx-auto" />
                <div className="text-sm font-semibold text-slate-700">
                  {selectedFile ? selectedFile.name : 'Upload voice recording / WhatsApp audio'}
                </div>
                <p className="text-xs text-slate-400">WAV, MP3, M4A or OGG</p>
              </label>
            </div>
          </div>
        )}

        <button
          onClick={handleProcessOrder}
          disabled={loading || !selectedFile}
          className="w-full py-3 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-slate-950 font-bold rounded-xl transition shadow-md shadow-amber-500/20 flex items-center justify-center gap-2 text-sm"
        >
          {loading ? (
            <LoadingSpinner message="Extracting with Sarvam AI..." />
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Analyze Order with Sarvam AI
            </>
          )}
        </button>
      </div>

      {/* Extracted Intelligence Result */}
      {extractedResult && (
        <div className="bg-white p-6 rounded-xl border border-emerald-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2 text-emerald-700 font-bold text-sm">
              <CheckCircle2 className="w-5 h-5" />
              Order Created: {extractedResult.order_number}
            </div>
            <div className="text-xs text-slate-500">
              Confidence: <span className="font-bold text-emerald-600">{(extractedResult.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <p className="text-slate-400 font-semibold uppercase">Customer</p>
              <p className="font-bold text-slate-800 text-sm mt-0.5">
                {extractedResult.extracted_data?.customer_name || 'Valued Customer'}
              </p>
              <p className="text-slate-500">{extractedResult.extracted_data?.phone || 'No phone'}</p>
            </div>
            <div>
              <p className="text-slate-400 font-semibold uppercase">Delivery Address</p>
              <p className="font-medium text-slate-800 mt-0.5">
                {extractedResult.extracted_data?.delivery_address || 'Address pending'}
              </p>
            </div>
          </div>

          {/* Extracted Items */}
          <div>
            <p className="text-xs text-slate-400 font-semibold uppercase mb-2">Extracted Items</p>
            <div className="space-y-1">
              {extractedResult.extracted_data?.items?.map((it, idx) => (
                <div key={idx} className="flex justify-between text-xs py-1.5 px-3 bg-slate-50 rounded border border-slate-100">
                  <span className="font-semibold text-slate-800">{it.product_name}</span>
                  <span className="text-slate-600">Qty: {it.quantity}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-2">
            <button
              onClick={() => navigate('/orders')}
              className="w-full py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-lg text-xs transition"
            >
              Open Order Review & Dispatch
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

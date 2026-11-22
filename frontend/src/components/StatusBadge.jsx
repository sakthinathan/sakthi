import React from 'react';

export default function StatusBadge({ status, type = 'order' }) {
  const normalized = (status || '').toLowerCase();

  const getStyle = () => {
    switch (normalized) {
      case 'approved':
      case 'healthy':
      case 'completed':
      case 'validated':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'pending_review':
      case 'pending':
      case 'investigating':
      case 'moderate':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'rejected':
      case 'degraded':
      case 'critical':
      case 'failed':
        return 'bg-rose-100 text-rose-800 border-rose-200';
      case 'vip':
      case 'premium':
        return 'bg-amber-50 text-amber-700 border-amber-300 font-semibold';
      default:
        return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStyle()}`}>
      {status?.replace('_', ' ').toUpperCase()}
    </span>
  );
}

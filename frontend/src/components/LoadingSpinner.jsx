import React from 'react';

export default function LoadingSpinner({ message = 'Processing...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 space-y-3">
      <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
      <p className="text-sm text-slate-500 font-medium">{message}</p>
    </div>
  );
}

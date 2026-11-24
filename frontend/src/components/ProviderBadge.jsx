import React from 'react';

/**
 * Reusable Provider Status Badge
 * Reflects verified runtime status: LIVE, MOCK FALLBACK, ERROR, or NOT CONFIGURED.
 * Never guesses status; relies strictly on backend response metadata.
 */
export default function ProviderBadge({
  provider,
  status,
  isMock,
  metadata,
  label
}) {
  // Normalize fields from either direct props or a metadata object
  const meta = metadata || {};
  const effectiveProvider = provider || meta.provider || 'Integration';
  const effectiveIsMock = isMock !== undefined ? isMock : (meta.is_mock ?? meta.isMock);
  let effectiveStatus = (status || meta.status || '').toLowerCase();

  if (!effectiveStatus) {
    if (effectiveIsMock === false) {
      effectiveStatus = 'live';
    } else if (effectiveIsMock === true) {
      effectiveStatus = 'fallback';
    } else {
      effectiveStatus = 'not_configured';
    }
  }

  // Friendly provider name mapping
  const formatProviderName = (p) => {
    switch (p) {
      case 'sarvam_document_ai':
        return 'Sarvam Document AI';
      case 'sarvam_saaras_stt':
        return 'Sarvam Saaras v4 STT';
      case 'sarvam_mayura_translation':
        return 'Sarvam Mayura v1';
      case 'sarvam_bulbul_tts':
        return 'Sarvam Bulbul v3 TTS';
      case 'google_address_validation':
        return 'Google Address Validation';
      case 'google_geocoding':
        return 'Google Geocoding';
      case 'google_air_quality':
        return 'Google Air Quality';
      case 'flagsmith_live':
      case 'flagsmith_live_identity':
      case 'flagsmith':
        return 'Flagsmith Live Feature Engine';
      case 'flagsmith_remote_admin':
        return 'Flagsmith Management API';
      case 'gemini_byom':
        return 'Gemini BYOM SRE Engine';
      case 'cloud_sql_postgresql':
        return 'Cloud SQL PostgreSQL';
      default:
        return p?.replace(/_/g, ' ') || 'Provider';
    }
  };

  const getBadgeStyle = () => {
    switch (effectiveStatus) {
      case 'live':
        return {
          container: 'bg-emerald-50 text-emerald-800 border-emerald-300',
          dot: 'bg-emerald-500',
          tag: 'LIVE',
          tagClass: 'bg-emerald-100 text-emerald-800 border-emerald-400'
        };
      case 'fallback':
      case 'mock_fallback':
        return {
          container: 'bg-amber-50 text-amber-800 border-amber-300',
          dot: 'bg-amber-500',
          tag: 'MOCK FALLBACK',
          tagClass: 'bg-amber-100 text-amber-800 border-amber-400'
        };
      case 'error':
        return {
          container: 'bg-rose-50 text-rose-800 border-rose-300',
          dot: 'bg-rose-500',
          tag: 'ERROR',
          tagClass: 'bg-rose-100 text-rose-800 border-rose-400'
        };
      case 'not_configured':
      default:
        return {
          container: 'bg-slate-50 text-slate-700 border-slate-300',
          dot: 'bg-slate-400',
          tag: 'NOT CONFIGURED',
          tagClass: 'bg-slate-100 text-slate-700 border-slate-300'
        };
    }
  };

  const style = getBadgeStyle();
  const displayName = label || formatProviderName(effectiveProvider);
  const failureReason = meta.failure_reason || meta.error;

  return (
    <div
      className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-md border text-xs font-medium shadow-xs transition-colors ${style.container}`}
      title={failureReason ? `Failure reason: ${failureReason}` : `Provider: ${displayName}`}
    >
      <span className={`w-2 h-2 rounded-full shrink-0 ${style.dot}`} />
      <span className="font-semibold">{displayName}:</span>
      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase border ${style.tagClass}`}>
        {style.tag}
      </span>
      {failureReason && (
        <span className="text-[10px] text-rose-600 truncate max-w-[140px]" title={failureReason}>
          ({failureReason})
        </span>
      )}
    </div>
  );
}

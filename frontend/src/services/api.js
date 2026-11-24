/**
 * API Service Client for UtsavOps Backend
 * Built-in native fetch with error handling and JSON auto-parsing
 */
const API_BASE = '/api';

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = options.headers || {};

  const token = localStorage.getItem('utsavops_token');
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    let errorDetail = 'API Request Failed';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.error || JSON.stringify(errJson);
    } catch (_) {
      errorDetail = await response.text();
    }
    throw new Error(errorDetail);
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return await response.json();
  }
  return response;
}

export const api = {
  // Auth
  login: (email, password) => request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  getMe: () => request('/auth/me'),

  // Health & Dashboard
  getHealth: () => request('/health'),
  getDashboardStats: () => request('/dashboard/stats'),

  // Orders
  getOrders: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/orders?${q}`);
  },
  getOrder: (id) => request(`/orders/${id}`),
  uploadOrderImage: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return request('/orders/intake/image', { method: 'POST', body: fd });
  },
  uploadOrderAudio: (file, language = 'hi-IN') => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('language', language);
    return request('/orders/intake/audio', { method: 'POST', body: fd });
  },
  reviewOrder: (id, data) => request(`/orders/${id}/review`, { method: 'PUT', body: JSON.stringify(data) }),
  approveOrder: (id) => request(`/orders/${id}/approve`, { method: 'POST' }),
  rejectOrder: (id, reason) => request(`/orders/${id}/reject?reason=${encodeURIComponent(reason)}`, { method: 'POST' }),
  getVoiceConfirmationUrl: (id, lang = 'hi-IN') => `/api/orders/${id}/voice-confirmation?language=${lang}`,

  // Customers
  getCustomers: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/customers?${q}`);
  },
  getCustomer: (id) => request(`/customers/${id}`),
  createCustomer: (data) => request('/customers', { method: 'POST', body: JSON.stringify(data) }),
  toggleVIP: (id) => request(`/customers/${id}/vip`, { method: 'POST' }),

  // Dispatch & Google APIs
  getDispatch: (orderId) => request(`/dispatch/${orderId}`),
  validateAddress: (orderId, address) => request(`/dispatch/${orderId}/validate-address`, {
    method: 'POST',
    body: JSON.stringify({ address })
  }),
  getAirQuality: (orderId) => request(`/dispatch/${orderId}/air-quality`),

  // Feature Flags & Flagsmith
  getFlags: () => request('/flags'),
  getBusinessRules: () => request('/flags/business-rules'),
  evaluateFlags: (customerId) => request('/flags/evaluate', {
    method: 'POST',
    body: JSON.stringify({ customer_id: customerId })
  }),
  toggleSurgeMode: (enabled, reason) => request('/flags/surge-mode', {
    method: 'POST',
    body: JSON.stringify({ enabled, reason })
  }),

  // AIOps & NudgeBee
  getServices: () => request('/aiops/services'),
  simulateDegradation: (serviceName) => request(`/aiops/services/${serviceName}/simulate-degradation`, { method: 'POST' }),
  getIncidents: () => request('/aiops/incidents'),
  getIncident: (id) => request(`/aiops/incidents/${id}`),
  investigateIncident: (id) => request(`/aiops/incidents/${id}/investigate`, { method: 'POST' }),
  approveAction: (incidentId, actionId, approvedBy, notes) => request(`/aiops/incidents/${incidentId}/actions/${actionId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ approved_by: approvedBy, notes })
  }),
  executeAction: (incidentId, actionId) => request(`/aiops/incidents/${incidentId}/actions/${actionId}/execute`, { method: 'POST' }),
  verifyRecovery: (incidentId) => request(`/aiops/incidents/${incidentId}/verify`, { method: 'POST' }),
  restoreChanges: (incidentId) => request(`/aiops/incidents/${incidentId}/restore`, { method: 'POST' }),

  // Audit Logs
  getAuditLogs: (limit = 50) => request(`/audit?limit=${limit}`),
};

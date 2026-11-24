import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('utsavops_token') || null);
  const [loading, setLoading] = useState(true);

  // Initialize session from stored token
  useEffect(() => {
    async function initAuth() {
      const storedToken = localStorage.getItem('utsavops_token');
      if (storedToken) {
        try {
          const profile = await api.getMe();
          setUser(profile);
          setToken(storedToken);
        } catch (err) {
          console.warn('Session expired or invalid, logging out', err);
          localStorage.removeItem('utsavops_token');
          setUser(null);
          setToken(null);
        }
      }
      setLoading(false);
    }
    initAuth();
  }, []);

  const login = async (email, password) => {
    const res = await api.login(email, password);
    if (res.access_token) {
      localStorage.setItem('utsavops_token', res.access_token);
      setToken(res.access_token);
      setUser(res.operator);
      return res.operator;
    }
    throw new Error('No access token received from authentication server');
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch (_) {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem('utsavops_token');
      setToken(null);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  LayoutDashboard, 
  FileText, 
  ListOrdered, 
  Truck, 
  Crown, 
  Activity, 
  ShieldCheck,
  Sparkles,
  AlertTriangle,
  LogOut,
  User
} from 'lucide-react';

export default function Layout({ surgeMode = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };
  const navItems = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/intake', label: 'Order Intake', icon: FileText },
    { to: '/orders', label: 'Order Review', icon: ListOrdered },
    { to: '/dispatch', label: 'Dispatch & Map', icon: Truck },
    { to: '/vip-pricing', label: 'VIP & Pricing', icon: Crown },
    { to: '/aiops', label: 'AIOps Center', icon: Activity },
    { to: '/audit', label: 'Audit Log', icon: ShieldCheck },
  ];

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-white flex flex-col shrink-0 border-r border-slate-800 shadow-xl">
        {/* Brand Header */}
        <div className="p-5 border-b border-slate-800 flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-orange-500 flex items-center justify-center text-xl shadow-lg shadow-orange-500/20">
            🪔
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-wide text-white flex items-center gap-1.5">
              UtsavOps
              <span className="text-[10px] bg-amber-500/20 text-amber-300 font-semibold px-1.5 py-0.5 rounded border border-amber-500/30">
                FESTIVE
              </span>
            </h1>
            <p className="text-xs text-slate-400">Self-Healing Commerce OS</p>
          </div>
        </div>

        {/* Surge Mode Banner if Active */}
        {surgeMode && (
          <div className="mx-3 mt-3 p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-center gap-2 text-xs text-amber-300">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 animate-pulse" />
            <span className="font-medium">Surge Survival Mode Active</span>
          </div>
        )}

        {/* Navigation Links */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-amber-500 text-slate-950 font-semibold shadow-md shadow-amber-500/20'
                      : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Footer Sponsor Badges */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40 text-[11px] text-slate-400 space-y-1">
          <div className="text-slate-500 font-medium uppercase tracking-wider text-[10px]">INTEGRATIONS</div>
          <div className="flex items-center gap-2 text-slate-300">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Sarvam AI • Flagsmith • NudgeBee</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-y-auto">
        <header className="h-14 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0 sticky top-0 z-10 shadow-xs">
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <span className="font-medium text-slate-900">Festive Season 2026</span>
            <span>•</span>
            <span className="text-xs bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-medium">
              Live Cluster: Ready
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <div className="flex items-center gap-2 bg-slate-100 border border-slate-200 px-2.5 py-1 rounded-lg">
              <User className="w-3.5 h-3.5 text-amber-600" />
              <span className="font-semibold text-slate-800">{user?.name || 'Operator'}</span>
              <span className="text-[10px] bg-amber-500/10 text-amber-800 font-medium px-1.5 py-0.5 rounded uppercase">
                {user?.role || 'SRE'}
              </span>
            </div>
            <button
              onClick={handleLogout}
              title="Sign out of operator session"
              className="flex items-center gap-1.5 text-slate-600 hover:text-rose-600 bg-white hover:bg-rose-50 border border-slate-200 hover:border-rose-200 px-2.5 py-1 rounded-lg transition font-medium"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Logout</span>
            </button>
          </div>
        </header>

        <div className="p-6 flex-1 max-w-7xl w-full mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

import { useState, useEffect } from 'react';
import {
  Package, ShoppingCart, Users, CalendarDays, AlertTriangle,
  TrendingUp, Activity, ArrowUpRight, ArrowDownRight
} from 'lucide-react';

interface DashboardStats {
  inventory: { total_items: number; total_quantity: number; low_stock: number };
  purchase_orders: { total: number; pending: number; delivered: number };
  vendors: number;
  leaves: number;
  users: number;
  recent_activity: { tool: string; status: string; timestamp: string }[];
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/dashboard/stats')
      .then((r) => r.json())
      .then((data) => { setStats(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-8 h-8 border-3 border-[#DDD0C0] border-t-[#8B2C2C] rounded-full animate-spin" />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex-1 flex items-center justify-center text-[#8B7355]">
        Failed to load dashboard data.
      </div>
    );
  }

  const statCards = [
    {
      title: 'Inventory Items',
      value: stats.inventory.total_items.toLocaleString(),
      subtitle: `${stats.inventory.total_quantity.toLocaleString()} total units`,
      icon: Package,
      color: 'from-[#8B2C2C] to-[#B94040]',
      iconBg: 'bg-red-100 text-[#8B2C2C]',
    },
    {
      title: 'Purchase Orders',
      value: stats.purchase_orders.total,
      subtitle: `${stats.purchase_orders.pending} pending`,
      icon: ShoppingCart,
      color: 'from-[#6F4E37] to-[#9B7B5B]',
      iconBg: 'bg-amber-100 text-[#6F4E37]',
    },
    {
      title: 'Vendors',
      value: stats.vendors,
      subtitle: 'Active suppliers',
      icon: Users,
      color: 'from-[#4B6F44] to-[#6B9B60]',
      iconBg: 'bg-green-100 text-[#4B6F44]',
    },
    {
      title: 'Leave Applications',
      value: stats.leaves,
      subtitle: `${stats.users} registered users`,
      icon: CalendarDays,
      color: 'from-[#4B5B8B] to-[#6B7BAB]',
      iconBg: 'bg-blue-100 text-[#4B5B8B]',
    },
  ];

  const poTotal = stats.purchase_orders.total || 1;
  const deliveredPct = Math.round((stats.purchase_orders.delivered / poTotal) * 100);
  const pendingPct = 100 - deliveredPct;

  const toolNameMap: Record<string, string> = {
    plan_execution: 'Plan Executed',
    get_inventory: 'Inventory Check',
    create_purchase_order: 'PO Created',
    check_po_status: 'PO Status Check',
    update_inventory_stock: 'Stock Updated',
    apply_leave: 'Leave Applied',
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 lg:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[#2D1B18]">Dashboard</h1>
          <p className="text-sm text-[#8B7355] mt-1">Overview of your ERP system</p>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {statCards.map((card, i) => (
            <div
              key={i}
              className="bg-white rounded-2xl p-5 shadow-sm border border-[#F0E0CC] hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-3">
                <div className={`w-10 h-10 rounded-xl ${card.iconBg} flex items-center justify-center`}>
                  <card.icon className="w-5 h-5" />
                </div>
                <span className="text-xs text-[#A8927B] font-medium">{card.title}</span>
              </div>
              <p className="text-3xl font-bold text-[#2D1B18]">{card.value}</p>
              <p className="text-xs text-[#8B7355] mt-1">{card.subtitle}</p>
            </div>
          ))}
        </div>

        {/* Row 2: PO breakdown + Low stock alert */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* PO Status Breakdown */}
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#F0E0CC]">
            <h2 className="text-sm font-semibold text-[#2D1B18] mb-5">Purchase Order Status</h2>
            <div className="flex items-center gap-6">
              {/* Visual bar */}
              <div className="flex-1">
                <div className="h-4 rounded-full bg-[#F5E6D3] overflow-hidden flex">
                  <div
                    className="h-full bg-gradient-to-r from-[#4B9B44] to-[#6BC060] rounded-l-full transition-all"
                    style={{ width: `${deliveredPct}%` }}
                  />
                  <div
                    className="h-full bg-gradient-to-r from-[#D4A040] to-[#E8B84C] rounded-r-full transition-all"
                    style={{ width: `${pendingPct}%` }}
                  />
                </div>
                <div className="flex justify-between mt-3">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-[#4B9B44]" />
                    <span className="text-xs text-[#6B5744]">Delivered ({stats.purchase_orders.delivered})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-[#D4A040]" />
                    <span className="text-xs text-[#6B5744]">Pending ({stats.purchase_orders.pending})</span>
                  </div>
                </div>
              </div>
              {/* Big number */}
              <div className="text-center px-4">
                <p className="text-4xl font-bold text-[#2D1B18]">{stats.purchase_orders.total}</p>
                <p className="text-xs text-[#8B7355] mt-1">Total POs</p>
              </div>
            </div>
          </div>

          {/* Low Stock Alert */}
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#F0E0CC]">
            <h2 className="text-sm font-semibold text-[#2D1B18] mb-4">Stock Alerts</h2>
            {stats.inventory.low_stock > 0 ? (
              <div className="flex items-center gap-4 p-4 rounded-xl bg-red-50 border border-red-200">
                <div className="w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0">
                  <AlertTriangle className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <p className="font-semibold text-red-700">{stats.inventory.low_stock} items low on stock</p>
                  <p className="text-xs text-red-500 mt-0.5">Items with less than 10 units remaining</p>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-4 p-4 rounded-xl bg-green-50 border border-green-200">
                <div className="w-10 h-10 rounded-xl bg-green-100 flex items-center justify-center flex-shrink-0">
                  <TrendingUp className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="font-semibold text-green-700">Stock levels healthy</p>
                  <p className="text-xs text-green-500 mt-0.5">All items above minimum threshold</p>
                </div>
              </div>
            )}

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="p-3 rounded-xl bg-[#FAF0E1] text-center">
                <p className="text-2xl font-bold text-[#2D1B18]">{stats.inventory.total_items}</p>
                <p className="text-xs text-[#8B7355]">SKUs</p>
              </div>
              <div className="p-3 rounded-xl bg-[#FAF0E1] text-center">
                <p className="text-2xl font-bold text-[#2D1B18]">{(stats.inventory.total_quantity / 1000).toFixed(0)}k</p>
                <p className="text-xs text-[#8B7355]">Units</p>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#F0E0CC]">
          <h2 className="text-sm font-semibold text-[#2D1B18] mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-[#8B7355]" />
            Recent Activity
          </h2>
          <div className="space-y-3">
            {stats.recent_activity.length > 0 ? (
              stats.recent_activity.map((log, i) => (
                <div key={i} className="flex items-center gap-3 p-3 rounded-xl hover:bg-[#FAF0E1] transition-colors">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    log.status === 'SUCCESS' ? 'bg-green-100' : 'bg-red-100'
                  }`}>
                    {log.status === 'SUCCESS'
                      ? <ArrowUpRight className="w-4 h-4 text-green-600" />
                      : <ArrowDownRight className="w-4 h-4 text-red-600" />
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[#2D1B18]">
                      {toolNameMap[log.tool] || log.tool}
                    </p>
                    <p className="text-xs text-[#A8927B]">{log.timestamp}</p>
                  </div>
                  <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                    log.status === 'SUCCESS'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}>
                    {log.status}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-sm text-[#A8927B] text-center py-4">No recent activity</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

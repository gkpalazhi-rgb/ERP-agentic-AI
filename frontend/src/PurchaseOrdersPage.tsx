import { useState, useEffect } from 'react';
import { ShoppingCart, Filter } from 'lucide-react';

interface PurchaseOrder {
  id: number;
  po_id: string;
  item_name: string;
  item_code: string;
  quantity: number;
  vendor: string;
  status: string;
  created_at: string;
}

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);

    fetch(`/purchase-orders?${params}`)
      .then((r) => r.json())
      .then((data) => { setOrders(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [statusFilter]);

  const statusColors: Record<string, string> = {
    Pending: 'bg-amber-100 text-amber-700 border-amber-200',
    Delivered: 'bg-green-100 text-green-700 border-green-200',
    Cancelled: 'bg-red-100 text-red-700 border-red-200',
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 lg:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-[#2D1B18]">Purchase Orders</h1>
            <p className="text-sm text-[#8B7355] mt-1">{orders.length} orders</p>
          </div>

          {/* Status filter */}
          <div className="flex gap-2">
            {['', 'Pending', 'Delivered'].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-4 py-2 rounded-xl text-xs font-medium transition-all border-2 ${
                  statusFilter === s
                    ? 'bg-[#4B2E2B] border-[#4B2E2B] text-white'
                    : 'bg-white border-[#DDD0C0] text-[#6B5744] hover:bg-[#FAF0E1]'
                }`}
              >
                {s || 'All'}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-2xl shadow-sm border border-[#F0E0CC] overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-7 h-7 border-3 border-[#DDD0C0] border-t-[#8B2C2C] rounded-full animate-spin" />
            </div>
          ) : orders.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-[#A8927B]">
              <ShoppingCart className="w-10 h-10 mb-2 opacity-40" />
              <p className="text-sm">No purchase orders found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#F0E0CC]">
                    <th className="text-left py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">PO ID</th>
                    <th className="text-left py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">Item</th>
                    <th className="text-left py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">Vendor</th>
                    <th className="text-right py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">Qty</th>
                    <th className="text-center py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">Status</th>
                    <th className="text-right py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F5EDE0]">
                  {orders.map((po) => (
                    <tr key={po.id} className="hover:bg-[#FDF8F0] transition-colors">
                      <td className="py-3 px-5">
                        <span className="text-xs font-mono bg-[#F5E6D3] text-[#6B5744] px-2 py-1 rounded-md">
                          {po.po_id || `#${po.id}`}
                        </span>
                      </td>
                      <td className="py-3 px-5">
                        <p className="text-sm font-medium text-[#2D1B18] capitalize">{po.item_name}</p>
                        <p className="text-xs text-[#A8927B] font-mono">{po.item_code}</p>
                      </td>
                      <td className="py-3 px-5 text-sm text-[#6B5744] capitalize">{po.vendor}</td>
                      <td className="py-3 px-5 text-right text-sm font-semibold text-[#2D1B18]">{po.quantity}</td>
                      <td className="py-3 px-5 text-center">
                        <span className={`inline-block text-xs font-medium px-3 py-1 rounded-full border ${
                          statusColors[po.status] || 'bg-gray-100 text-gray-700 border-gray-200'
                        }`}>
                          {po.status}
                        </span>
                      </td>
                      <td className="py-3 px-5 text-right text-xs text-[#A8927B]">
                        {new Date(po.created_at).toLocaleDateString('en-IN', {
                          day: '2-digit', month: 'short', year: 'numeric'
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

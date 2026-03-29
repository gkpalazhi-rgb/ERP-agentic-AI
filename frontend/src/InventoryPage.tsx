import { useState, useEffect } from 'react';
import { Search, Package, Filter } from 'lucide-react';

interface InventoryItem {
  id: number;
  item_code: string;
  item_name: string;
  category: string;
  quantity: number;
  mrp: number | null;
}

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [search, setSearch] = useState('');
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('');

  const fetchItems = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (lowStockOnly) params.set('low_stock', 'true');

    const token = localStorage.getItem('erp_token');
    fetch(`/inventory?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((data) => { setItems(data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchItems();
  }, [lowStockOnly]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(fetchItems, 400);
    return () => clearTimeout(timer);
  }, [search]);

  // Get unique categories
  const categories = [...new Set(items.map((i) => i.category).filter(Boolean))];
  const filteredItems = categoryFilter
    ? items.filter((i) => i.category === categoryFilter)
    : items;

  return (
    <div className="flex-1 overflow-y-auto p-6 lg:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-[#2D1B18]">Inventory</h1>
            <p className="text-sm text-[#8B7355] mt-1">{items.length} items loaded</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setLowStockOnly(!lowStockOnly)}
              className={`px-4 py-2 rounded-xl text-xs font-medium transition-all border-2 ${
                lowStockOnly
                  ? 'bg-red-50 border-red-300 text-red-700'
                  : 'bg-white border-[#DDD0C0] text-[#6B5744] hover:bg-[#FAF0E1]'
              }`}
            >
              Low Stock Only
            </button>
          </div>
        </div>

        {/* Search + Category Filter */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A8927B]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search items by name..."
              className="w-full pl-11 pr-4 py-3 rounded-xl border-2 border-[#DDD0C0] bg-white text-[#2D1B18] placeholder-[#B8A898] focus:outline-none focus:border-[#8B2C2C] focus:ring-3 focus:ring-[#8B2C2C]/10 transition-all text-sm"
            />
          </div>
          {categories.length > 0 && (
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A8927B]" />
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="pl-9 pr-8 py-3 rounded-xl border-2 border-[#DDD0C0] bg-white text-[#2D1B18] text-sm focus:outline-none focus:border-[#8B2C2C] appearance-none cursor-pointer"
              >
                <option value="">All Categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Table */}
        <div className="bg-white rounded-2xl shadow-sm border border-[#F0E0CC] overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-7 h-7 border-3 border-[#DDD0C0] border-t-[#8B2C2C] rounded-full animate-spin" />
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-[#A8927B]">
              <Package className="w-10 h-10 mb-2 opacity-40" />
              <p className="text-sm">No items found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#F0E0CC]">
                    <th className="text-left py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">Item Code</th>
                    <th className="text-left py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">Item Name</th>
                    <th className="text-left py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">Category</th>
                    <th className="text-right py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">Quantity</th>
                    <th className="text-right py-3.5 px-5 text-xs font-semibold text-[#8B7355] uppercase tracking-wider">MRP</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F5EDE0]">
                  {filteredItems.slice(0, 100).map((item) => (
                    <tr key={item.id} className="hover:bg-[#FDF8F0] transition-colors">
                      <td className="py-3 px-5">
                        <span className="text-xs font-mono bg-[#F5E6D3] text-[#6B5744] px-2 py-1 rounded-md">
                          {item.item_code}
                        </span>
                      </td>
                      <td className="py-3 px-5 text-sm font-medium text-[#2D1B18]">{item.item_name}</td>
                      <td className="py-3 px-5">
                        <span className="text-xs bg-[#F0E0CC] text-[#6B5744] px-2.5 py-1 rounded-full">
                          {item.category}
                        </span>
                      </td>
                      <td className="py-3 px-5 text-right">
                        <span className={`text-sm font-semibold ${
                          item.quantity < 10 ? 'text-red-600' : 'text-[#2D1B18]'
                        }`}>
                          {item.quantity.toLocaleString()}
                        </span>
                      </td>
                      <td className="py-3 px-5 text-right text-sm text-[#6B5744]">
                        {item.mrp != null ? `₹${item.mrp.toFixed(2)}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredItems.length > 100 && (
                <div className="text-center py-3 text-xs text-[#A8927B] border-t border-[#F0E0CC]">
                  Showing first 100 of {filteredItems.length} items. Use search to narrow down.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { Users, Search, Plus, MapPin, Tag, Mail } from 'lucide-react';

interface Vendor {
  id: string;
  vendor_code: string;
  vendor_name: string;
  location: string;
  item_category: string;
  email: string | null;
}

const VendorsPage: React.FC = () => {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    fetchVendors();
  }, []);

  const fetchVendors = async () => {
    try {
      const res = await fetch('/vendors');
      if (res.ok) {
        const data = await res.json();
        setVendors(data);
      }
    } catch (e) {
      console.error('Failed to fetch vendors', e);
    } finally {
      setLoading(false);
    }
  };

  const filteredVendors = vendors.filter(v =>
    v.vendor_name.toLowerCase().includes(search.toLowerCase()) ||
    v.item_category.toLowerCase().includes(search.toLowerCase()) ||
    v.vendor_code.toLowerCase().includes(search.toLowerCase()) ||
    v.location.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[500px]">
        <div className="w-8 h-8 rounded-full border-4 border-[#8B2C2C] border-t-transparent animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="p-8 animate-fadeIn flex-1 bg-[#F5E6D3] overflow-y-auto">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Header Section */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white/60 p-6 rounded-2xl border border-[#E8D8C8] shadow-sm backdrop-blur-sm">
          <div>
            <h1 className="text-2xl font-bold text-[#4B2E2B] flex items-center gap-2">
              <Users className="hidden sm:block text-[#8B2C2C]" />
              Supplier Management
            </h1>
            <p className="text-sm text-[#8B7355] mt-1">Manage external vendors and supply partners.</p>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="relative w-full sm:w-64">
              <Search className="w-4 h-4 text-[#A8927B] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search vendors..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-white/50 border border-[#E8D8C8] rounded-xl text-sm focus:outline-none focus:border-[#8B2C2C] focus:ring-2 focus:ring-[#8B2C2C]/10 transition-all text-[#4B2E2B] placeholder-[#B8A898]"
              />
            </div>
            
            <button className="flex-shrink-0 bg-[#8B2C2C] hover:bg-[#A33535] text-white px-4 py-2 rounded-xl text-sm font-medium transition-all shadow-sm flex items-center gap-2">
              <Plus className="w-4 h-4" />
              Add Vendor
            </button>
          </div>
        </div>

        {/* Vendors Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredVendors.map((vendor) => (
            <div key={vendor.id || vendor.vendor_code} className="bg-white p-5 rounded-2xl border border-[#E8D8C8] shadow-sm hover:shadow-md transition-all group">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <span className="inline-block px-2 py-1 bg-[#F5E6D3] text-[#6F4E37] text-[10px] font-bold rounded-md mb-2 tracking-wide uppercase">
                    {vendor.vendor_code}
                  </span>
                  <h3 className="font-bold text-[#4B2E2B] text-lg leading-tight group-hover:text-[#8B2C2C] transition-colors">{vendor.vendor_name}</h3>
                </div>
              </div>

              <div className="space-y-2 mt-4 pt-4 border-t border-[#F5E6D3]">
                
                <div className="flex items-start gap-2 text-sm">
                  <Tag className="w-4 h-4 text-[#A8927B] mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-[10px] text-[#A8927B] font-semibold uppercase tracking-wider">Category</p>
                    <p className="text-[#6F4E37] font-medium">{vendor.item_category}</p>
                  </div>
                </div>

                <div className="flex items-start gap-2 text-sm">
                  <MapPin className="w-4 h-4 text-[#A8927B] mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-[10px] text-[#A8927B] font-semibold uppercase tracking-wider">Location</p>
                    <p className="text-[#6F4E37]">{vendor.location || 'Not specified'}</p>
                  </div>
                </div>

                {vendor.email && (
                  <div className="flex items-start gap-2 text-sm">
                    <Mail className="w-4 h-4 text-[#A8927B] mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-[10px] text-[#A8927B] font-semibold uppercase tracking-wider">Contact</p>
                      <a href={`mailto:${vendor.email}`} className="text-[#8B2C2C] hover:underline truncate w-full inline-block">
                        {vendor.email}
                      </a>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          
          {filteredVendors.length === 0 && (
            <div className="col-span-full py-12 text-center text-[#8B7355] bg-white/40 rounded-2xl border border-dashed border-[#C4A892]">
              <Users className="w-12 h-12 mx-auto mb-3 opacity-40 text-[#4B2E2B]" />
              <p className="font-medium text-lg">No vendors found</p>
              <p className="text-sm mt-1 opacity-80">Try adjusting your search terms.</p>
            </div>
          )}
        </div>
        
      </div>
    </div>
  );
}

export default VendorsPage;

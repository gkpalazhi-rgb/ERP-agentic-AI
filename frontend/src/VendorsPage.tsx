import React, { useState, useEffect } from 'react';
import { Users, Search, Plus, MapPin, Tag, Mail, Edit2, X } from 'lucide-react';

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
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'add' | 'edit'>('add');
  const [formData, setFormData] = useState<Partial<Vendor>>({});
  const [saving, setSaving] = useState(false);

  const openModal = (mode: 'add' | 'edit', vendor?: Vendor) => {
    setModalMode(mode);
    setFormData(vendor || { vendor_code: '', vendor_name: '', location: '', item_category: '', email: '' });
    setIsModalOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('erp_token');
      const method = modalMode === 'add' ? 'POST' : 'PUT';
      const url = modalMode === 'add' ? '/vendors' : `/vendors/${formData.vendor_code}`;
      
      const res = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });
      
      if (res.ok) {
        setIsModalOpen(false);
        fetchVendors();
      } else {
        alert('Failed to save vendor');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    fetchVendors();
  }, []);

  const fetchVendors = async () => {
    try {
      const token = localStorage.getItem('erp_token');
      const res = await fetch('/vendors', { headers: { Authorization: `Bearer ${token}` } });
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
    <>
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
            
            <button 
              onClick={() => openModal('add')}
              className="flex-shrink-0 bg-[#8B2C2C] hover:bg-[#A33535] text-white px-4 py-2 rounded-xl text-sm font-medium transition-all shadow-sm flex items-center gap-2">
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
                <button 
                  onClick={() => openModal('edit', vendor)}
                  className="p-2 text-[#A8927B] hover:text-[#8B2C2C] hover:bg-[#F5E6D3] rounded-lg transition-colors">
                  <Edit2 className="w-4 h-4" />
                </button>
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

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 z-[9999]">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-fadeIn">
            <div className="flex items-center justify-between p-5 border-b border-[#F0E0CC]">
              <h2 className="text-lg font-bold text-[#4B2E2B]">
                {modalMode === 'add' ? 'Add New Vendor' : 'Edit Vendor'}
              </h2>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="p-2 text-[#A8927B] hover:text-[#8B2C2C] hover:bg-[#F5E6D3] rounded-full transition-colors"
                disabled={saving}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#8B7355] uppercase tracking-wider mb-1">Vendor Code</label>
                <input 
                  type="text" 
                  value={formData.vendor_code || ''}
                  onChange={(e) => setFormData({...formData, vendor_code: e.target.value})}
                  disabled={modalMode === 'edit'}
                  className="w-full px-4 py-2 border border-[#E8D8C8] rounded-xl text-sm focus:outline-none focus:border-[#8B2C2C] disabled:bg-[#F5E6D3] disabled:text-[#A8927B]"
                  placeholder="e.g. V-001"
                />
              </div>
              
              <div>
                <label className="block text-xs font-semibold text-[#8B7355] uppercase tracking-wider mb-1">Vendor Name</label>
                <input 
                  type="text" 
                  value={formData.vendor_name || ''}
                  onChange={(e) => setFormData({...formData, vendor_name: e.target.value})}
                  className="w-full px-4 py-2 border border-[#E8D8C8] rounded-xl text-sm focus:outline-none focus:border-[#8B2C2C]"
                  placeholder="e.g. Acme Corp"
                />
              </div>
              
              <div>
                <label className="block text-xs font-semibold text-[#8B7355] uppercase tracking-wider mb-1">Category</label>
                <input 
                  type="text" 
                  value={formData.item_category || ''}
                  onChange={(e) => setFormData({...formData, item_category: e.target.value})}
                  className="w-full px-4 py-2 border border-[#E8D8C8] rounded-xl text-sm focus:outline-none focus:border-[#8B2C2C]"
                  placeholder="e.g. Raw Materials"
                />
              </div>
              
              <div>
                <label className="block text-xs font-semibold text-[#8B7355] uppercase tracking-wider mb-1">Location</label>
                <input 
                  type="text" 
                  value={formData.location || ''}
                  onChange={(e) => setFormData({...formData, location: e.target.value})}
                  className="w-full px-4 py-2 border border-[#E8D8C8] rounded-xl text-sm focus:outline-none focus:border-[#8B2C2C]"
                  placeholder="e.g. New York, NY"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#8B7355] uppercase tracking-wider mb-1">Email</label>
                <input 
                  type="email" 
                  value={formData.email || ''}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  className="w-full px-4 py-2 border border-[#E8D8C8] rounded-xl text-sm focus:outline-none focus:border-[#8B2C2C]"
                  placeholder="contact@example.com"
                />
              </div>
            </div>
            
            <div className="p-5 border-t border-[#F0E0CC] flex justify-end gap-3 bg-[#FAF5F0]">
              <button 
                onClick={() => setIsModalOpen(false)}
                disabled={saving}
                className="px-4 py-2 text-sm font-medium text-[#6F4E37] hover:bg-[#F0E0CC] rounded-xl transition-all"
              >
                Cancel
              </button>
              <button 
                onClick={handleSave}
                disabled={saving || !formData.vendor_code || !formData.vendor_name}
                className="px-4 py-2 bg-[#8B2C2C] hover:bg-[#A33535] disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl shadow-sm transition-all flex items-center gap-2"
              >
                {saving ? 'Saving...' : 'Save Vendor'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default VendorsPage;

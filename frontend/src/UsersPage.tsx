import { useEffect, useMemo, useState } from 'react';
import { Save, ShieldAlert, Users } from 'lucide-react';

interface UserEntry {
  id: number;
  username: string;
  email?: string | null;
  role: string;
  feature_access: string[];
}

const FEATURE_LABELS: Record<string, string> = {
  chat: 'AI Chat',
  dashboard: 'Dashboard',
  inventory: 'Inventory',
  purchase_orders: 'Purchase Orders',
  vendors: 'Vendors',
  leaves: 'Leaves',
  users: 'Users Admin',
};

const normalizeFeature = (value: string): string =>
  value.trim().toLowerCase().replace(/[-\s]+/g, '_');

export default function UsersPage() {
  const [users, setUsers] = useState<UserEntry[]>([]);
  const [availableFeatures, setAvailableFeatures] = useState<string[]>([]);
  const [draftAccessByUser, setDraftAccessByUser] = useState<Record<number, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [savingUserId, setSavingUserId] = useState<number | null>(null);
  const [error, setError] = useState('');

  const token = localStorage.getItem('erp_token');

  const loadUsers = async () => {
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const [usersRes, featuresRes] = await Promise.all([
        fetch('/users', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/users/features', { headers: { Authorization: `Bearer ${token}` } }),
      ]);

      if (!usersRes.ok) throw new Error('Unable to load users');
      if (!featuresRes.ok) throw new Error('Unable to load feature catalog');

      const usersData = (await usersRes.json()) as UserEntry[];
      const featureData = (await featuresRes.json()) as { features?: string[] };

      const normalizedFeatures = Array.isArray(featureData.features)
        ? featureData.features.map((f) => normalizeFeature(String(f)))
        : [];
      const draftMap: Record<number, string[]> = {};
      usersData.forEach((user) => {
        draftMap[user.id] = Array.isArray(user.feature_access)
          ? user.feature_access.map((f) => normalizeFeature(String(f)))
          : [];
      });

      setUsers(usersData);
      setAvailableFeatures(normalizedFeatures);
      setDraftAccessByUser(draftMap);
    } catch (e) {
      console.error(e);
      setError('Only admin users can access this page.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const updateDraftFeature = (userId: number, feature: string) => {
    setDraftAccessByUser((prev) => {
      const current = new Set(prev[userId] || []);
      if (current.has(feature)) current.delete(feature);
      else current.add(feature);
      return { ...prev, [userId]: Array.from(current) };
    });
  };

  const saveUserFeatures = async (userId: number) => {
    if (!token) return;
    setSavingUserId(userId);
    setError('');
    try {
      const payloadFeatures = draftAccessByUser[userId] || [];
      const res = await fetch(`/users/${userId}/features`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ feature_access: payloadFeatures }),
      });

      if (!res.ok) throw new Error('Failed to save user features');
      const updated = (await res.json()) as UserEntry;

      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, feature_access: updated.feature_access } : u)));
      setDraftAccessByUser((prev) => ({ ...prev, [userId]: updated.feature_access || [] }));
    } catch (e) {
      console.error(e);
      setError('Saving failed. Please try again.');
    } finally {
      setSavingUserId(null);
    }
  };

  const rows = useMemo(() => users.map((user) => ({ user, draft: draftAccessByUser[user.id] || [] })), [users, draftAccessByUser]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-8 h-8 border-3 border-[#DDD0C0] border-t-[#8B2C2C] rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 lg:p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-[#2D1B18] flex items-center gap-2">
            <Users className="w-6 h-6 text-[#8B2C2C]" />
            User Access Control
          </h1>
          <p className="text-sm text-[#8B7355] mt-1">Adjust feature access per account.</p>
        </div>

        {error && (
          <div className="mb-5 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <ShieldAlert className="w-4 h-4" />
            {error}
          </div>
        )}

        <div className="space-y-4">
          {rows.map(({ user, draft }) => {
            const effective = new Set(user.feature_access || []);
            const hasChanges = JSON.stringify([...effective].sort()) !== JSON.stringify([...draft].sort());
            return (
              <div key={user.id} className="rounded-2xl border border-[#F0E0CC] bg-white p-5 shadow-sm">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-base font-semibold text-[#2D1B18]">{user.username}</p>
                    <p className="text-xs text-[#8B7355]">
                      {user.role}
                      {user.email ? ` · ${user.email}` : ''}
                    </p>
                  </div>
                  <button
                    onClick={() => saveUserFeatures(user.id)}
                    disabled={!hasChanges || savingUserId === user.id}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-[#8B2C2C] px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-[#A33535] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Save className="w-3.5 h-3.5" />
                    {savingUserId === user.id ? 'Saving...' : 'Save'}
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                  {availableFeatures.map((feature) => {
                    const checked = draft.includes(feature);
                    return (
                      <label
                        key={`${user.id}-${feature}`}
                        className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-all ${
                          checked
                            ? 'border-[#B76A6A] bg-[#FDF2F2] text-[#6B2A2A]'
                            : 'border-[#DDD0C0] bg-white text-[#6B5744] hover:bg-[#FAF0E1]'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => updateDraftFeature(user.id, feature)}
                          className="accent-[#8B2C2C]"
                        />
                        {FEATURE_LABELS[feature] || feature}
                      </label>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { CalendarDays, Check, X, Clock, CheckCircle, XCircle } from 'lucide-react';

interface LeaveEntry {
  id: number;
  user_id: number;
  username: string;
  reason: string;
  leave_date: string;
  leave_type: string;
  status: string;
  created_at: string;
}

interface LeavesPageProps {
  userRole: string;
  userId: number;
}

export default function LeavesPage({ userRole, userId }: LeavesPageProps) {
  const [leaves, setLeaves] = useState<LeaveEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const isAdmin = userRole === 'administrator';

  const fetchLeaves = () => {
    setLoading(true);
    const url = isAdmin ? '/leaves' : `/leaves/${userId}`;
    const token = localStorage.getItem('erp_token');
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((data) => { setLeaves(data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchLeaves();
  }, []);

  const handleStatusUpdate = async (leaveId: number, newStatus: 'Approved' | 'Rejected') => {
    setActionLoading(leaveId);
    try {
      const token = localStorage.getItem('erp_token');
      const res = await fetch(`/leaves/${leaveId}/status`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (res.ok) {
        setLeaves((prev) =>
          prev.map((l) => (l.id === leaveId ? { ...l, status: newStatus } : l))
        );
      }
    } catch (e) {
      console.error('Failed to update leave status', e);
    } finally {
      setActionLoading(null);
    }
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case 'Approved': return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'Rejected': return <XCircle className="w-4 h-4 text-red-600" />;
      default: return <Clock className="w-4 h-4 text-amber-600" />;
    }
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      Pending: 'bg-amber-100 text-amber-700 border-amber-200',
      Approved: 'bg-green-100 text-green-700 border-green-200',
      Rejected: 'bg-red-100 text-red-700 border-red-200',
    };
    return colors[status] || 'bg-gray-100 text-gray-700 border-gray-200';
  };

  const filteredLeaves = filter
    ? leaves.filter((l) => l.status === filter)
    : leaves;

  const counts = {
    all: leaves.length,
    pending: leaves.filter((l) => l.status === 'Pending').length,
    approved: leaves.filter((l) => l.status === 'Approved').length,
    rejected: leaves.filter((l) => l.status === 'Rejected').length,
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 lg:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-[#2D1B18]">
              {isAdmin ? 'Leave Management' : 'My Leaves'}
            </h1>
            <p className="text-sm text-[#8B7355] mt-1">
              {isAdmin
                ? `${counts.pending} pending approvals`
                : `${leaves.length} leave applications`}
            </p>
          </div>

          {/* Filter tabs */}
          <div className="flex gap-2">
            {[
              { key: '', label: 'All', count: counts.all },
              { key: 'Pending', label: 'Pending', count: counts.pending },
              { key: 'Approved', label: 'Approved', count: counts.approved },
              { key: 'Rejected', label: 'Rejected', count: counts.rejected },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setFilter(tab.key)}
                className={`px-3 py-2 rounded-xl text-xs font-medium transition-all border-2 ${
                  filter === tab.key
                    ? 'bg-[#4B2E2B] border-[#4B2E2B] text-white'
                    : 'bg-white border-[#DDD0C0] text-[#6B5744] hover:bg-[#FAF0E1]'
                }`}
              >
                {tab.label}
                <span className="ml-1.5 opacity-70">({tab.count})</span>
              </button>
            ))}
          </div>
        </div>

        {/* Pending summary banner (admin only) */}
        {isAdmin && counts.pending > 0 && (
          <div className="flex items-center gap-4 p-4 rounded-2xl bg-amber-50 border border-amber-200 mb-6 animate-fadeIn">
            <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center flex-shrink-0">
              <Clock className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="font-semibold text-amber-800">
                {counts.pending} leave {counts.pending === 1 ? 'request' : 'requests'} awaiting review
              </p>
              <p className="text-xs text-amber-600 mt-0.5">Review and approve or reject pending applications</p>
            </div>
          </div>
        )}

        {/* Leave cards */}
        <div className="space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-7 h-7 border-3 border-[#DDD0C0] border-t-[#8B2C2C] rounded-full animate-spin" />
            </div>
          ) : filteredLeaves.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-[#A8927B]">
              <CalendarDays className="w-10 h-10 mb-2 opacity-40" />
              <p className="text-sm">No leave applications found</p>
            </div>
          ) : (
            filteredLeaves.map((leave) => (
              <div
                key={leave.id}
                className="bg-white rounded-2xl p-5 shadow-sm border border-[#F0E0CC] hover:shadow-md transition-shadow animate-fadeIn"
              >
                <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                  {/* Left: Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      {/* User avatar */}
                      <div className="w-9 h-9 rounded-lg bg-[#E8D8C8] flex items-center justify-center text-[#6B5744] font-bold text-sm flex-shrink-0">
                        {leave.username?.[0]?.toUpperCase() || '?'}
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-[#2D1B18] capitalize">{leave.username}</p>
                        <p className="text-[10px] text-[#A8927B]">Applied {new Date(leave.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</p>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span className="text-xs bg-[#F5E6D3] text-[#6B5744] px-2.5 py-1 rounded-full font-medium">
                        📅 {new Date(leave.leave_date).toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })}
                      </span>
                      <span className="text-xs bg-[#F0E0CC] text-[#6B5744] px-2.5 py-1 rounded-full">
                        {leave.leave_type}
                      </span>
                      <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${statusBadge(leave.status)}`}>
                        {statusIcon(leave.status)}
                        {leave.status}
                      </span>
                    </div>

                    {leave.reason && (
                      <p className="text-sm text-[#6B5744] bg-[#FAF0E1] rounded-lg px-3 py-2 mt-2">
                        <span className="font-medium text-[#4B2E2B]">Reason:</span> {leave.reason}
                      </p>
                    )}
                  </div>

                  {/* Right: Action buttons (admin only, only for pending) */}
                  {isAdmin && leave.status === 'Pending' && (
                    <div className="flex sm:flex-col gap-2 flex-shrink-0">
                      <button
                        onClick={() => handleStatusUpdate(leave.id, 'Approved')}
                        disabled={actionLoading === leave.id}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-green-50 text-green-700 border-2 border-green-200 hover:bg-green-100 hover:border-green-300 transition-all disabled:opacity-50"
                      >
                        <Check className="w-3.5 h-3.5" />
                        Approve
                      </button>
                      <button
                        onClick={() => handleStatusUpdate(leave.id, 'Rejected')}
                        disabled={actionLoading === leave.id}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-red-50 text-red-700 border-2 border-red-200 hover:bg-red-100 hover:border-red-300 transition-all disabled:opacity-50"
                      >
                        <X className="w-3.5 h-3.5" />
                        Reject
                      </button>
                    </div>
                  )}

                  {/* Already actioned badge */}
                  {leave.status !== 'Pending' && (
                    <div className="flex-shrink-0 text-center">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center mx-auto ${
                        leave.status === 'Approved' ? 'bg-green-100' : 'bg-red-100'
                      }`}>
                        {leave.status === 'Approved'
                          ? <CheckCircle className="w-5 h-5 text-green-600" />
                          : <XCircle className="w-5 h-5 text-red-600" />
                        }
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

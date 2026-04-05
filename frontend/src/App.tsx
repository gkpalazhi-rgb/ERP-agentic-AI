import { useState, useEffect, useRef } from 'react';
import {
  Send, Plus, MessageSquare, Bot, Trash2, LogOut,
  LayoutDashboard, Package, ShoppingCart, MessageCircle, CalendarDays, Users, Settings
} from 'lucide-react';
import LoginPage from './LoginPage';
import DashboardPage from './DashboardPage';
import InventoryPage from './InventoryPage';
import PurchaseOrdersPage from './PurchaseOrdersPage';
import LeavesPage from './LeavesPage';
import VendorsPage from './VendorsPage';
import UsersPage from './UsersPage';

interface Message {
  id: number;
  sender: 'user' | 'ai';
  text: string;
  timestamp: string;
  metadata?: any;
}

interface Conversation {
  session_id: string;
  title: string;
  last_updated: string;
}

interface AuthUser {
  user_id: number;
  username: string;
  role: string;
  feature_access?: string[];
}

type Page = 'chat' | 'dashboard' | 'inventory' | 'purchase-orders' | 'leaves' | 'vendors' | 'users';

const DEFAULT_FEATURES_BY_ROLE: Record<string, string[]> = {
  admin: ['chat', 'dashboard', 'inventory', 'purchase_orders', 'vendors', 'leaves', 'users'],
  administrator: ['chat', 'dashboard', 'inventory', 'purchase_orders', 'vendors', 'leaves', 'users'],
  employee: ['chat', 'dashboard', 'inventory', 'vendors', 'leaves'],
  staff: ['chat', 'dashboard', 'inventory', 'vendors', 'leaves'],
  user: ['chat', 'dashboard', 'inventory', 'vendors', 'leaves'],
};

const PAGE_TO_FEATURE: Record<Page, string> = {
  chat: 'chat',
  dashboard: 'dashboard',
  inventory: 'inventory',
  'purchase-orders': 'purchase_orders',
  vendors: 'vendors',
  leaves: 'leaves',
  users: 'users',
};

const normalizeFeature = (value: string): string => {
  const normalized = value.trim().toLowerCase().replace(/[-\s]+/g, '_');
  const aliases: Record<string, string> = {
    leave: 'leaves',
    purchase_order: 'purchase_orders',
  };
  return aliases[normalized] || normalized;
};

const getAllowedFeatures = (authUser: AuthUser | null): string[] => {
  if (!authUser) return ['chat'];
  const roleKey = normalizeFeature(authUser.role || 'employee');
  if (roleKey === 'admin' || roleKey === 'administrator') {
    return DEFAULT_FEATURES_BY_ROLE.admin;
  }
  const explicit = Array.isArray(authUser.feature_access)
    ? authUser.feature_access.map((f) => normalizeFeature(String(f))).filter(Boolean)
    : [];
  if (explicit.length > 0) {
    return Array.from(new Set(explicit));
  }
  return DEFAULT_FEATURES_BY_ROLE[roleKey] || ['chat'];
};

const canManageLeaves = (authUser: AuthUser | null): boolean => {
  if (!authUser) return false;
  const roleKey = normalizeFeature(authUser.role || '');
  if (roleKey === 'admin' || roleKey === 'administrator' || roleKey === 'hr') {
    return true;
  }
  const features = new Set(getAllowedFeatures(authUser));
  return features.has('leaves') && features.has('dashboard');
};

const firstAllowedPage = (features: string[]): Page => {
  const allowedFeatureSet = new Set(features);
  const orderedPages: Page[] = ['dashboard', 'chat', 'inventory', 'purchase-orders', 'vendors', 'leaves', 'users'];
  const match = orderedPages.find((page) => allowedFeatureSet.has(PAGE_TO_FEATURE[page]));
  return match || 'chat';
};

const toDisplayText = (value: unknown, fallback: string): string => {
  if (typeof value === 'string' && value.trim()) return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (value && typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return fallback;
    }
  }
  return fallback;
};

const extractApiErrorMessage = (payload: unknown, fallback: string): string => {
  if (!payload || typeof payload !== 'object') return fallback;
  const candidate = payload as {
    detail?: unknown;
    message?: unknown;
    error?: unknown;
  };

  if (typeof candidate.error === 'object' && candidate.error !== null) {
    const errorMessage = (candidate.error as { message?: unknown }).message;
    if (typeof errorMessage === 'string' && errorMessage.trim()) return errorMessage;
  }
  if (typeof candidate.detail === 'string' && candidate.detail.trim()) return candidate.detail;
  if (typeof candidate.message === 'string' && candidate.message.trim()) return candidate.message;
  if (typeof candidate.error === 'string' && candidate.error.trim()) return candidate.error;
  return fallback;
};

const extractVendorNamesFromPrompt = (text: string): string[] => {
  const names = Array.from(text.matchAll(/^\s*\d+\.\s+(.+)$/gm))
    .map((m) => m[1].trim())
    .filter(Boolean);
  return Array.from(new Set(names));
};

function App() {
  // Auth state
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('erp_token'));
  const [user, setUser] = useState<AuthUser | null>(() => {
    const saved = localStorage.getItem('erp_user');
    if (!saved) return null;
    try {
      return JSON.parse(saved) as AuthUser;
    } catch {
      return null;
    }
  });

  // Navigation
  const [currentPage, setCurrentPage] = useState<Page>(() => {
    const saved = localStorage.getItem('erp_user');
    if (!saved) return 'chat';
    try {
      const parsed = JSON.parse(saved) as AuthUser;
      return firstAllowedPage(getAllowedFeatures(parsed));
    } catch {
      return 'chat';
    }
  });

  // Chat state
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [vendors, setVendors] = useState<{vendor_code: string, vendor_name: string}[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // Verify token on mount
  useEffect(() => {
    if (token) {
      fetch('/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => {
          if (!res.ok) throw new Error('Invalid token');
          return res.json();
        })
        .then((data) => {
          const hydratedUser: AuthUser = {
            user_id: data.user_id,
            username: data.username,
            role: data.role,
            feature_access: Array.isArray(data.feature_access) ? data.feature_access : undefined,
          };
          setUser(hydratedUser);
          localStorage.setItem('erp_user', JSON.stringify(hydratedUser));
          setCurrentPage(firstAllowedPage(getAllowedFeatures(hydratedUser)));
        })
        .catch(() => {
          handleLogout();
        });
    }
  }, []);

  const handleLogin = (newToken: string, newUser: AuthUser) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem('erp_token', newToken);
    localStorage.setItem('erp_user', JSON.stringify(newUser));
    setCurrentPage(firstAllowedPage(getAllowedFeatures(newUser)));
  };

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setMessages([]);
    setConversations([]);
    setCurrentSessionId(null);
    localStorage.removeItem('erp_token');
    localStorage.removeItem('erp_user');
  };

  useEffect(() => {
    if (!user) return;
    const allowedFeatures = new Set(getAllowedFeatures(user));
    const requiredFeature = PAGE_TO_FEATURE[currentPage];
    if (!allowedFeatures.has(requiredFeature)) {
      setCurrentPage(firstAllowedPage(Array.from(allowedFeatures)));
    }
  }, [user, currentPage]);

  const loadHistory = async () => {
    if (!user) return;
    try {
      const res = await fetch(`/history/${user.user_id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch (e) {
      console.error('Failed to load history', e);
    }
  };

  useEffect(() => {
    if (user) {
      const features = new Set(getAllowedFeatures(user));
      if (features.has('chat')) {
        loadHistory();
      } else {
        setConversations([]);
      }

      if (features.has('vendors')) {
        fetch('/vendors', { headers: { Authorization: `Bearer ${token}` } })
          .then(res => res.ok ? res.json() : [])
          .then(data => setVendors(data))
          .catch(e => console.error('Failed to preload vendors', e));
      } else {
        setVendors([]);
      }
    }
  }, [user]);

  const loadSessionChat = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    try {
      const res = await fetch(`/history/chat/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        const formattedMessages = data.map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }));
        setMessages(formattedMessages);
      }
    } catch (e) {
      console.error('Failed to load session chat', e);
    }
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setCurrentPage('chat');
  };

  const handleDeleteChat = async (sessionId: string) => {
    try {
      const res = await fetch(`/history/chat/${sessionId}`, { 
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setConversations((prev) => prev.filter((c) => c.session_id !== sessionId));
        if (currentSessionId === sessionId) {
          handleNewChat();
        }
      }
    } catch (e) {
      console.error('Failed to delete chat', e);
    }
  };

  const handleSend = async (directText?: string) => {
    let userText = '';
    if (typeof directText === 'string') {
      userText = directText.trim();
    } else {
      userText = inputValue.trim();
      setInputValue('');
    }

    if (!userText || !user) return;

    const tempId = Date.now();
    const newUserMsg: Message = {
      id: tempId,
      sender: 'user',
      text: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, newUserMsg]);
    setIsTyping(true);

    try {
      let url = `/chat?user_id=${user.user_id}&message=${encodeURIComponent(userText)}`;
      if (currentSessionId) {
        url += `&session_id=${encodeURIComponent(currentSessionId)}`;
      }

      const res = await fetch(url, { 
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });

      if (res.ok) {
        const data = await res.json();

        if (!currentSessionId && data.session_id) {
          setCurrentSessionId(data.session_id);
          loadHistory();
        }

        const newAiMsg: Message = {
          id: Date.now() + 1,
          sender: 'ai',
          text: toDisplayText(data.response ?? data.error, 'Done.'),
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          metadata: data.intent_detection,
        };

        setMessages((prev) => [...prev, newAiMsg]);
      } else {
        let errorText = 'Sorry, something went wrong. Please try again.';
        try {
          const rawBody = await res.text();
          if (rawBody) {
            try {
              const errData = JSON.parse(rawBody);
              errorText = extractApiErrorMessage(errData, errorText);
            } catch {
              errorText = `Request failed (${res.status}): ${rawBody.slice(0, 160)}`;
            }
          } else {
            errorText = `Request failed (${res.status}).`;
          }
        } catch {
          errorText = `Request failed (${res.status}).`;
        }
        setMessages((prev) => [
          ...prev,
          { id: Date.now() + 1, sender: 'ai', text: errorText, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) },
        ]);
      }
    } catch (e) {
      console.error('Chat error', e);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'ai',
          text: 'Unable to reach backend API. Please ensure the server is running on http://127.0.0.1:8000.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Show login page if not authenticated
  if (!token || !user) {
    return <LoginPage onLogin={handleLogin} />;
  }

  // Navigation items
  const allNavItems: { key: Page; label: string; icon: typeof LayoutDashboard }[] = [
    { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { key: 'chat', label: 'AI Chat', icon: MessageCircle },
    { key: 'inventory', label: 'Inventory', icon: Package },
    { key: 'purchase-orders', label: 'Orders', icon: ShoppingCart },
    { key: 'vendors', label: 'Vendors', icon: Users },
    { key: 'leaves', label: 'Leaves', icon: CalendarDays },
    { key: 'users', label: 'Users', icon: Settings },
  ];

  const allowedFeatureSet = new Set(getAllowedFeatures(user));
  const navItems = allNavItems.filter((item) => allowedFeatureSet.has(PAGE_TO_FEATURE[item.key]));

  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const lastAiText = lastMessage?.sender === 'ai' ? lastMessage.text : '';
  const isVendorClarificationPrompt =
    typeof lastAiText === 'string' &&
    /which vendor should i place this order with|available vendors/i.test(lastAiText);
  const vendorNamesFromPrompt = isVendorClarificationPrompt
    ? extractVendorNamesFromPrompt(lastAiText)
    : [];
  const quickVendorOptions = vendorNamesFromPrompt.length > 0
    ? vendorNamesFromPrompt
    : vendors.map((v) => v.vendor_name);

  return (
    <div className="flex h-screen bg-[#F5E6D3]">
      {/* Sidebar */}
      <aside className="w-64 bg-[#4B2E2B] text-white flex flex-col">
        {/* Brand + User */}
        <div className="p-5 pb-2">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center overflow-hidden shadow-sm border border-white/20">
              <img src="/logo.png" alt="Logo" className="w-full h-full object-contain p-0.5" />
            </div>
            <span className="text-base font-bold tracking-tight">ERP AI</span>
          </div>

          {/* User badge */}
          <div className="flex items-center gap-2.5 bg-white/10 rounded-xl px-3 py-2 mb-4">
            <div className="w-7 h-7 rounded-lg bg-[#D4A574] flex items-center justify-center text-[#4B2E2B] font-bold text-xs">
              {user.username[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user.username}</p>
              <p className="text-[10px] text-[#C4A892] capitalize">{user.role}</p>
            </div>
            <button
              id="logout-btn"
              onClick={handleLogout}
              className="p-1 rounded-md hover:bg-white/10 transition-colors"
              title="Sign out"
            >
              <LogOut className="w-3.5 h-3.5 text-[#C4A892]" />
            </button>
          </div>
        </div>

        {/* Navigation */}
        <div className="px-3 mb-4">
          <p className="text-[10px] font-semibold text-[#C4A892] uppercase tracking-widest px-2 mb-2">Navigation</p>
          <div className="space-y-1">
            {navItems.map((item) => (
              <button
                key={item.key}
                onClick={() => setCurrentPage(item.key)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-all ${
                  currentPage === item.key
                    ? 'bg-white/15 text-white font-medium'
                    : 'text-[#C4A892] hover:bg-white/8 hover:text-white'
                }`}
              >
                <item.icon className="w-4 h-4" />
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {/* Chat section — only when on chat page */}
        {currentPage === 'chat' && (
          <>
            <div className="px-3 mb-3">
              <button
                id="new-chat-btn"
                onClick={handleNewChat}
                className="w-full bg-[#8B2C2C] hover:bg-[#a33535] transition-colors rounded-xl py-2.5 px-4 flex items-center gap-2 font-medium text-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                New Chat
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-3 pb-3">
              <p className="text-[10px] font-semibold text-[#C4A892] uppercase tracking-widest px-2 mb-2">Recent</p>
              <div className="space-y-0.5">
                {conversations.map((conv) => (
                  <div
                    key={conv.session_id}
                    className={`w-full px-2.5 py-2 rounded-lg transition-all flex items-center justify-between group ${
                      currentSessionId === conv.session_id ? 'bg-white/15' : 'hover:bg-white/8'
                    }`}
                  >
                    <button
                      onClick={() => loadSessionChat(conv.session_id)}
                      className="flex items-center gap-2 flex-1 text-left overflow-hidden"
                    >
                      <MessageSquare className="w-3 h-3 opacity-40 group-hover:opacity-70 flex-shrink-0" />
                      <span className="text-xs truncate text-[#E8D8C8]">{conv.title}</span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleDeleteChat(conv.session_id);
                      }}
                      className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all flex-shrink-0 ml-1 p-0.5"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                {conversations.length === 0 && (
                  <p className="text-[10px] text-[#C4A892] opacity-60 px-2 py-3 text-center">No conversations yet</p>
                )}
              </div>
            </div>
          </>
        )}

        {/* Spacer when not on chat */}
        {currentPage !== 'chat' && <div className="flex-1" />}
      </aside>

      {/* Main Content Area */}
      {currentPage === 'dashboard' && <DashboardPage />}
      {currentPage === 'inventory' && <InventoryPage />}
      {currentPage === 'purchase-orders' && <PurchaseOrdersPage />}
      {currentPage === 'vendors' && <VendorsPage />}
      {currentPage === 'leaves' && (
        <LeavesPage
          userRole={user.role}
          userId={user.user_id}
          canManageLeaves={canManageLeaves(user)}
        />
      )}
      {currentPage === 'users' && <UsersPage />}
      {currentPage === 'chat' && (
        <main className="flex-1 flex flex-col">
          <div className="flex-1 overflow-y-auto p-8">
            <div className="max-w-4xl mx-auto space-y-6">
              {messages.length === 0 && !isTyping && (
                <div className="h-full flex flex-col items-center justify-center text-[#8B7355] mt-20">
                  <div className="w-14 h-14 rounded-2xl bg-[#E8D8C8] flex items-center justify-center mb-4">
                    <Bot className="w-7 h-7 text-[#8B7355]" />
                  </div>
                  <p className="text-lg font-medium text-[#6B5744]">How can I help you today?</p>
                  <p className="text-sm text-[#A8927B] mt-1">Ask about inventory, purchase orders, vendors, or leaves</p>
                  <div className="flex gap-2 mt-6 flex-wrap justify-center max-w-lg">
                    {[
                      "Show all purchase orders done today",
                      "Show low stock items",
                      "Who all are on leave today?",
                      "Apply for leave tomorrow, Full Day, Personal",
                    ].map((prompt, i) => (
                      <button key={i} onClick={() => handleSend(prompt)} className="px-3 py-2 bg-white/50 border border-[#E8D8C8] rounded-xl text-xs font-medium text-[#8B7355] hover:bg-white hover:text-[#4B2E2B] transition-all shadow-sm">
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-3 animate-fadeIn ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {message.sender === 'ai' && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-xl bg-[#8B2C2C] flex items-center justify-center mt-1">
                      <Bot className="w-4 h-4 text-white" />
                    </div>
                  )}

                  <div className={`flex flex-col ${message.sender === 'user' ? 'items-end' : 'items-start'}`}>
                    <div
                      className={`rounded-2xl px-5 py-3 max-w-2xl shadow-sm ${
                        message.sender === 'user'
                          ? 'bg-[#6F4E37] text-white rounded-br-md'
                          : 'bg-white text-[#4B2E2B] rounded-bl-md border border-[#E8D8C8]'
                      }`}
                    >
                      <p className="whitespace-pre-line leading-relaxed text-sm">{message.text}</p>
                    </div>
                    <span className="text-[10px] text-[#A8927B] mt-1.5 px-2 flex items-center gap-1.5 font-medium tracking-wide">
                      {message.timestamp}
                      {message.metadata?.source && (
                        <>
                          <span className="w-1 h-1 rounded-full bg-[#E5D4BB] inline-block" />
                          <span className={`${message.metadata.source.includes('llm') ? 'text-amber-600' : 'text-green-600'}`}>
                            Routed via {message.metadata.source} ({message.metadata.latency_ms}ms)
                          </span>
                        </>
                      )}
                    </span>
                  </div>

                  {message.sender === 'user' && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-xl bg-[#6F4E37] flex items-center justify-center mt-1 text-white font-semibold text-xs">
                      {user.username[0].toUpperCase()}
                    </div>
                  )}
                </div>
              ))}

              {isTyping && (
                <div className="flex gap-3 animate-fadeIn">
                  <div className="flex-shrink-0 w-8 h-8 rounded-xl bg-[#8B2C2C] flex items-center justify-center">
                    <Bot className="w-4 h-4 text-white" />
                  </div>
                  <div className="bg-white rounded-2xl rounded-bl-md px-5 py-3 shadow-sm border border-[#E8D8C8]">
                    <div className="flex gap-1.5">
                      <div className="w-2 h-2 bg-[#C4A892] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 bg-[#C4A892] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 bg-[#C4A892] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          <div className="border-t border-[#E5D4BB] bg-white/60 backdrop-blur-sm p-4">
            <div className="max-w-4xl mx-auto">
              
              {/* Quick-Insert Vendor Dropdown */}
              {isVendorClarificationPrompt && quickVendorOptions.length > 0 && (
                <div className="flex items-center gap-2 mb-2 px-1 animate-fadeIn">
                  <span className="text-xs text-[#A8927B] font-medium uppercase tracking-wider">Quick Select:</span>
                  <select 
                    className="bg-white/80 border border-[#E8D8C8] rounded-lg text-xs px-2.5 py-1 focus:outline-none focus:border-[#8B2C2C] focus:ring-2 focus:ring-[#8B2C2C]/10 text-[#4B2E2B] font-medium shadow-sm cursor-pointer hover:bg-white transition-all"
                    defaultValue=""
                    disabled={isTyping}
                    onChange={(e) => {
                      if (e.target.value) {
                        handleSend(`from vendor ${e.target.value}`);
                        e.target.value = ''; // reset properly
                      }
                    }}
                  >
                    <option value="" disabled>Select vendor and send</option>
                    {quickVendorOptions.map((vendorName) => (
                      <option key={vendorName} value={vendorName}>{vendorName}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex gap-3 items-end">
                <div className="flex-1">
                  <textarea
                    id="chat-input"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Ask the ERP assistant..."
                    className="w-full px-5 py-3 rounded-2xl border-2 border-[#DDD0C0] bg-white text-[#4B2E2B] placeholder-[#B8A898] focus:outline-none focus:border-[#8B2C2C] focus:ring-3 focus:ring-[#8B2C2C]/10 transition-all resize-none text-sm"
                    rows={1}
                    style={{ minHeight: '48px', maxHeight: '120px' }}
                  />
                </div>
                <button
                  id="chat-send-btn"
                  onClick={() => handleSend()}
                  className="bg-gradient-to-r from-[#8B2C2C] to-[#A33535] hover:from-[#7A2626] hover:to-[#922F2F] text-white rounded-2xl px-5 py-3 transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={!inputValue.trim() || isTyping}
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </main>
      )}
    </div>
  );
}

export default App;

import { useState, useEffect, useRef } from 'react';
import {
  Send, Plus, MessageSquare, Bot, Trash2, LogOut,
  LayoutDashboard, Package, ShoppingCart, MessageCircle, CalendarDays, Users
} from 'lucide-react';
import LoginPage from './LoginPage';
import DashboardPage from './DashboardPage';
import InventoryPage from './InventoryPage';
import PurchaseOrdersPage from './PurchaseOrdersPage';
import LeavesPage from './LeavesPage';
import VendorsPage from './VendorsPage';

interface Message {
  id: number;
  sender: 'user' | 'ai';
  text: string;
  timestamp: string;
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
}

type Page = 'chat' | 'dashboard' | 'inventory' | 'purchase-orders' | 'leaves' | 'vendors';

function App() {
  // Auth state
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('erp_token'));
  const [user, setUser] = useState<AuthUser | null>(() => {
    const saved = localStorage.getItem('erp_user');
    return saved ? JSON.parse(saved) : null;
  });

  // Navigation
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');

  // Chat state
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

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
          setUser({ user_id: data.user_id, username: data.username, role: data.role });
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

  const loadHistory = async () => {
    if (!user) return;
    try {
      const res = await fetch(`/history/${user.user_id}`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch (e) {
      console.error('Failed to load history', e);
    }
  };

  useEffect(() => {
    if (user) loadHistory();
  }, [user]);

  const loadSessionChat = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    try {
      const res = await fetch(`/history/chat/${sessionId}`);
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
      const res = await fetch(`/history/chat/${sessionId}`, { method: 'DELETE' });
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

  const handleSend = async () => {
    if (!inputValue.trim() || !user) return;

    const userText = inputValue.trim();
    setInputValue('');

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

      const res = await fetch(url, { method: 'POST' });

      if (res.ok) {
        const data = await res.json();

        if (!currentSessionId && data.session_id) {
          setCurrentSessionId(data.session_id);
          loadHistory();
        }

        const newAiMsg: Message = {
          id: Date.now() + 1,
          sender: 'ai',
          text: data.response || data.error || 'Done.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setMessages((prev) => [...prev, newAiMsg]);
      } else {
        let errorText = 'Sorry, something went wrong. Please try again.';
        try {
          const errData = await res.json();
          errorText = errData.detail || errData.error || errorText;
        } catch {}
        setMessages((prev) => [
          ...prev,
          { id: Date.now() + 1, sender: 'ai', text: errorText, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) },
        ]);
      }
    } catch (e) {
      console.error('Chat error', e);
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, sender: 'ai', text: 'Sorry, something went wrong.', timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) },
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
  const navItems: { key: Page; label: string; icon: typeof LayoutDashboard }[] = [
    { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { key: 'chat', label: 'AI Chat', icon: MessageCircle },
    { key: 'inventory', label: 'Inventory', icon: Package },
    { key: 'purchase-orders', label: 'Orders', icon: ShoppingCart },
    { key: 'vendors', label: 'Vendors', icon: Users },
    { key: 'leaves', label: 'Leaves', icon: CalendarDays },
  ];

  return (
    <div className="flex h-screen bg-[#F5E6D3]">
      {/* Sidebar */}
      <aside className="w-64 bg-[#4B2E2B] text-white flex flex-col">
        {/* Brand + User */}
        <div className="p-5 pb-2">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
              <Bot className="w-4 h-4 text-[#D4A574]" />
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
                      onClick={(e) => {
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
      {currentPage === 'leaves' && <LeavesPage userRole={user.role} userId={user.user_id} />}
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
                    <span className="text-[10px] text-[#A8927B] mt-1 px-2">{message.timestamp}</span>
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
                  onClick={handleSend}
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

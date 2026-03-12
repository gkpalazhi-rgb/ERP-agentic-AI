import { useState, useEffect, useRef } from 'react';
import { Send, Plus, MessageSquare, Bot, Trash2 } from 'lucide-react';

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

function App() {
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  
  // Ref to automatically scroll to the bottom of the chat
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Hardcoded user ID for now based on the backend schema
  const USER_ID = 1;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const loadHistory = async () => {
    try {
      const res = await fetch(`/history/${USER_ID}`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch (e) {
      console.error('Failed to load history', e);
    }
  };

  // Load history on mount
  useEffect(() => {
    loadHistory();
  }, []);

  const loadSessionChat = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    try {
      const res = await fetch(`/history/chat/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        // The backend returns timestamp which we will format roughly for display
        const formattedMessages = data.map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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
  };

  const handleDeleteChat = async (sessionId: string) => {
    try {
      const res = await fetch(`/history/chat/${sessionId}`, { method: 'DELETE' });
      if (res.ok) {
        setConversations(prev => prev.filter(c => c.session_id !== sessionId));
        if (currentSessionId === sessionId) {
          handleNewChat();
        }
      }
    } catch (e) {
      console.error('Failed to delete chat', e);
    }
  };

  const handleSend = async () => {
    if (!inputValue.trim()) return;
    
    const userText = inputValue.trim();
    setInputValue('');
    
    // Optimistic UI update for user message
    const tempId = Date.now();
    const newUserMsg: Message = {
      id: tempId,
      sender: 'user',
      text: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    
    setMessages(prev => [...prev, newUserMsg]);
    setIsTyping(true);

    try {
      // Build the URL with query parameters
      let url = `/chat?user_id=${USER_ID}&message=${encodeURIComponent(userText)}`;
      if (currentSessionId) {
        url += `&session_id=${encodeURIComponent(currentSessionId)}`;
      }

      const res = await fetch(url, { method: 'POST' });
      
      if (res.ok) {
        const data = await res.json();
        
        // If it was a new chat, the backend returned a new session_id
        if (!currentSessionId && data.session_id) {
          setCurrentSessionId(data.session_id);
          // Refresh conversation list to get the new session
          loadHistory();
        }

        const newAiMsg: Message = {
          id: Date.now() + 1,
          sender: 'ai',
          text: data.response || data.error || 'Done.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        
        setMessages(prev => [...prev, newAiMsg]);
      } else {
        let errorText = 'Sorry, something went wrong. Please try again.';
        try {
          const errData = await res.json();
          errorText = errData.detail || errData.error || errorText;
        } catch {}
        const errorMsg: Message = {
          id: Date.now() + 1,
          sender: 'ai',
          text: errorText,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, errorMsg]);
      }
    } catch (e) {
      console.error("Chat error", e);
      const errorMsg: Message = {
        id: Date.now() + 1,
        sender: 'ai',
        text: 'Sorry, something went wrong. Please try again.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMsg]);
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

  return (
    <div className="flex h-screen bg-[#F5E6D3]">
      <aside className="w-72 bg-[#4B2E2B] text-white flex flex-col">
        <div className="p-6">
          <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
            <Bot className="w-7 h-7" />
            ERP AI Assistant
          </h1>

          <button 
            onClick={handleNewChat}
            className="w-full bg-[#8B2C2C] hover:bg-[#a33535] transition-colors duration-200 rounded-lg py-3 px-4 flex items-center gap-2 font-medium mb-6"
          >
            <Plus className="w-5 h-5" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 pb-4">
          <h2 className="text-sm font-semibold text-[#F5E6D3] mb-3 px-2">Recent Conversations</h2>
          <div className="space-y-2">
            {conversations.map((conv) => (
              <div
                key={conv.session_id}
                className={`w-full px-4 py-3 rounded-lg transition-all duration-200 flex items-center justify-between group ${currentSessionId === conv.session_id ? 'bg-[#F5E6D3] bg-opacity-20' : 'hover:bg-[#F5E6D3] hover:bg-opacity-10'}`}
              >
                <button
                  onClick={() => loadSessionChat(conv.session_id)}
                  className="flex items-center gap-3 flex-1 text-left overflow-hidden"
                >
                  <MessageSquare className="w-4 h-4 opacity-70 group-hover:opacity-100 flex-shrink-0" />
                  <span className="text-sm truncate">{conv.title}</span>
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDeleteChat(conv.session_id); }}
                  className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all flex-shrink-0 ml-2"
                  title="Delete Chat"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
            {conversations.length === 0 && (
              <p className="text-xs text-[#F5E6D3] opacity-60 px-2">No past conversations.</p>
            )}
          </div>
        </div>
      </aside>

      <main className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-4xl mx-auto space-y-6">
            {messages.length === 0 && !isTyping && (
              <div className="h-full flex flex-col items-center justify-center text-[#8B7355] mt-20">
                 <Bot className="w-16 h-16 mb-4 opacity-50" />
                 <p className="text-lg">How can I help you with the ERP today?</p>
              </div>
            )}
            
            {messages.map((message, index) => (
              <div
                key={message.id}
                className={`flex gap-3 animate-fadeIn ${
                  message.sender === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.sender === 'ai' && (
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-[#8B2C2C] flex items-center justify-center mt-1">
                    <Bot className="w-5 h-5 text-white" />
                  </div>
                )}

                <div className={`flex flex-col ${message.sender === 'user' ? 'items-end' : 'items-start'}`}>
                  <div
                    className={`rounded-2xl px-6 py-4 max-w-2xl shadow-md ${
                      message.sender === 'user'
                        ? 'bg-[#6F4E37] text-white rounded-br-md'
                        : 'bg-[#FFF3E4] text-[#4B2E2B] rounded-bl-md'
                    }`}
                  >
                    <p className="whitespace-pre-line leading-relaxed">{message.text}</p>
                  </div>
                  <span className="text-xs text-[#8B7355] mt-2 px-2">{message.timestamp}</span>
                </div>

                {message.sender === 'user' && (
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-[#6F4E37] flex items-center justify-center mt-1 text-white font-semibold">
                    U
                  </div>
                )}
              </div>
            ))}

            {isTyping && (
              <div className="flex gap-3 animate-fadeIn">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-[#8B2C2C] flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div className="bg-[#FFF3E4] rounded-2xl rounded-bl-md px-6 py-4 shadow-md">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-[#8B7355] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-[#8B7355] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-[#8B7355] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="border-t border-[#E5D4BB] bg-[#FAF0E1] p-6">
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-4 items-end">
              <div className="flex-1 relative">
                <textarea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask the ERP assistant..."
                  className="w-full px-6 py-4 rounded-2xl border-2 border-[#C4A882] bg-white text-[#4B2E2B] placeholder-[#A8927B] focus:outline-none focus:border-[#8B2C2C] focus:ring-2 focus:ring-[#8B2C2C] focus:ring-opacity-20 transition-all duration-200 resize-none"
                  rows={1}
                  style={{
                    minHeight: '56px',
                    maxHeight: '120px',
                  }}
                />
              </div>
              <button
                onClick={handleSend}
                className="bg-[#8B2C2C] hover:bg-[#a33535] text-white rounded-2xl px-6 py-4 transition-all duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!inputValue.trim() || isTyping}
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;

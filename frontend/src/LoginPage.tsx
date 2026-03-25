import { useState } from 'react';
import { Bot, Eye, EyeOff, LogIn, UserPlus, ArrowRight } from 'lucide-react';

interface LoginPageProps {
  onLogin: (token: string, user: { user_id: number; username: string; role: string }) => void;
}

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const endpoint = isRegister ? '/auth/register' : '/auth/login';
      const body: Record<string, string> = { username, password };
      if (isRegister && email) body.email = email;

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || 'Something went wrong');
        return;
      }

      onLogin(data.token, {
        user_id: data.user_id,
        username: data.username,
        role: data.role,
      });
    } catch {
      setError('Unable to connect to server');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setIsRegister(!isRegister);
    setError('');
    setEmail('');
  };

  return (
    <div className="flex h-screen bg-[#F5E6D3]">
      {/* Left Branding Panel */}
      <div className="hidden lg:flex lg:w-[420px] bg-gradient-to-br from-[#4B2E2B] via-[#5C3A36] to-[#3D2421] flex-col justify-between p-10 relative overflow-hidden">
        {/* Decorative circles */}
        <div className="absolute -top-20 -left-20 w-64 h-64 rounded-full bg-white/5" />
        <div className="absolute -bottom-32 -right-32 w-96 h-96 rounded-full bg-white/5" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 rounded-full bg-white/[0.03]" />

        {/* Logo & Brand */}
        <div className="relative z-10">
          <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur-sm flex items-center justify-center mb-6 border border-white/10">
            <Bot className="w-7 h-7 text-[#F5E6D3]" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            ERP AI
          </h1>
          <h2 className="text-3xl font-bold text-[#D4A574] tracking-tight">
            Assistant
          </h2>
          <p className="text-[#B8A090] mt-4 text-sm leading-relaxed max-w-[280px]">
            Your intelligent enterprise resource planning companion. Manage inventory, 
            purchase orders, vendors, and more with natural language.
          </p>
        </div>

        {/* Features list */}
        <div className="relative z-10 space-y-4">
          {[
            'AI-Powered Inventory Management',
            'Automated Purchase Orders',
            'Smart Vendor Analytics',
          ].map((feature, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="w-1.5 h-1.5 rounded-full bg-[#D4A574]" />
              <span className="text-[#C4A892] text-sm">{feature}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Right Login Form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-[420px]">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <div className="w-11 h-11 rounded-xl bg-[#4B2E2B] flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="text-lg font-bold text-[#4B2E2B]">ERP AI</span>
              <span className="text-lg font-bold text-[#8B2C2C] ml-1">Assistant</span>
            </div>
          </div>

          {/* Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-[#2D1B18]">
              {isRegister ? 'Create Account' : 'Welcome Back'}
            </h1>
            <p className="text-[#8B7355] mt-1.5 text-sm">
              {isRegister
                ? 'Set up your account to get started'
                : 'Sign in to your ERP dashboard'}
            </p>
          </div>

          {/* Error message */}
          {error && (
            <div className="mb-5 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm animate-fadeIn">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username */}
            <div>
              <label className="block text-xs font-semibold text-[#6B5744] uppercase tracking-wider mb-1.5">
                Username
              </label>
              <input
                id="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                required
                className="w-full px-4 py-3 rounded-xl border-2 border-[#DDD0C0] bg-white text-[#2D1B18] placeholder-[#B8A898] focus:outline-none focus:border-[#8B2C2C] focus:ring-3 focus:ring-[#8B2C2C]/10 transition-all text-sm"
              />
            </div>

            {/* Email — only for register */}
            {isRegister && (
              <div className="animate-fadeIn">
                <label className="block text-xs font-semibold text-[#6B5744] uppercase tracking-wider mb-1.5">
                  Email <span className="font-normal text-[#A8927B]">(optional)</span>
                </label>
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="w-full px-4 py-3 rounded-xl border-2 border-[#DDD0C0] bg-white text-[#2D1B18] placeholder-[#B8A898] focus:outline-none focus:border-[#8B2C2C] focus:ring-3 focus:ring-[#8B2C2C]/10 transition-all text-sm"
                />
              </div>
            )}

            {/* Password */}
            <div>
              <label className="block text-xs font-semibold text-[#6B5744] uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  className="w-full px-4 py-3 pr-12 rounded-xl border-2 border-[#DDD0C0] bg-white text-[#2D1B18] placeholder-[#B8A898] focus:outline-none focus:border-[#8B2C2C] focus:ring-3 focus:ring-[#8B2C2C]/10 transition-all text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#A8927B] hover:text-[#6B5744] transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              id="login-submit"
              type="submit"
              disabled={loading || !username || !password}
              className="w-full mt-2 bg-gradient-to-r from-[#8B2C2C] to-[#A33535] hover:from-[#7A2626] hover:to-[#922F2F] text-white font-semibold py-3.5 rounded-xl transition-all duration-200 shadow-lg shadow-[#8B2C2C]/20 hover:shadow-xl hover:shadow-[#8B2C2C]/30 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-lg flex items-center justify-center gap-2 text-sm"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  {isRegister ? <UserPlus className="w-4 h-4" /> : <LogIn className="w-4 h-4" />}
                  {isRegister ? 'Create Account' : 'Sign In'}
                  <ArrowRight className="w-4 h-4 ml-1" />
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-[#DDD0C0]" />
            <span className="text-xs text-[#A8927B]">or</span>
            <div className="flex-1 h-px bg-[#DDD0C0]" />
          </div>

          {/* Toggle login/register */}
          <button
            id="login-toggle"
            onClick={switchMode}
            className="w-full py-3 rounded-xl border-2 border-[#DDD0C0] text-[#6B5744] font-medium hover:bg-[#F0E0CC] hover:border-[#C4A882] transition-all text-sm"
          >
            {isRegister ? 'Already have an account? Sign In' : "Don't have an account? Register"}
          </button>

          {/* Footer */}
          <p className="text-center text-xs text-[#B8A898] mt-8">
            Powered by AI · Secure & Private
          </p>
        </div>
      </div>
    </div>
  );
}

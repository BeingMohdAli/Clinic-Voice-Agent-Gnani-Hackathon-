'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Activity,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  HeartPulse,
  Lock,
  Mail,
  Mic,
  Phone,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  User,
} from 'lucide-react';
import { createClient } from '@/lib/supabase/client';

function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialMode = searchParams.get('mode') === 'login' ? 'login' : 'signup';

  const [mode, setMode] = useState<'signup' | 'login'>(initialMode);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [existingUser, setExistingUser] = useState<string | null>(null);

  const supabase = createClient();

  useEffect(() => {
    async function checkUser() {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (user?.email) {
        setExistingUser(user.email);
      }
    }
    checkUser();
  }, [supabase]);

  useEffect(() => {
    const qMode = searchParams.get('mode');
    if (qMode === 'login' || qMode === 'signup') {
      setMode(qMode);
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);
    setLoading(true);

    try {
      if (mode === 'signup') {
        const cleanPhone = phone.replace(/\D/g, '').slice(0, 10);
        if (cleanPhone && cleanPhone.length !== 10) {
          setErrorMessage('Please enter a valid 10-digit mobile number.');
          setLoading(false);
          return;
        }

        const { data, error } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: {
            data: {
              full_name: fullName.trim(),
              phone: cleanPhone,
            },
            emailRedirectTo: typeof window !== 'undefined' ? `${window.location.origin}/` : undefined,
          },
        });

        if (error) {
          setErrorMessage(error.message);
        } else if (data.session) {
          setSuccessMessage('Account created successfully! Launching Voice Assistant...');
          setTimeout(() => {
            router.push('/');
            router.refresh();
          }, 1500);
        } else if (data.user && !data.session) {
          setSuccessMessage(
            'Registration successful! Please check your email to confirm your account.'
          );
        } else {
          setSuccessMessage('Signup complete! You can now log in.');
          setMode('login');
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        });

        if (error) {
          setErrorMessage(error.message);
        } else {
          setSuccessMessage('Welcome back! Launching Voice Assistant...');
          setTimeout(() => {
            router.push('/');
            router.refresh();
          }, 1000);
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('An unexpected error occurred. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    setExistingUser(null);
    setSuccessMessage('Signed out successfully.');
  };

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-[#060b14] text-slate-100 flex flex-col justify-between">
      {/* Top Emerald-Teal Bar with Orange Accent Pill */}
      <header className="relative z-20 w-full bg-[#008778] px-4 py-2 text-white shadow-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between text-xs sm:text-sm">
          <div className="flex items-center gap-2">
            <HeartPulse className="h-4 w-4 text-[#00dfc4] animate-pulse" />
            <span className="font-semibold tracking-wide">
              Sir Ganga Ram City Hospital
            </span>
            <span className="hidden md:inline text-teal-100/80">
              • Hands-free Voice AI OPD Appointment System
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden sm:inline-flex items-center rounded-full bg-[#ff621f] px-3 py-0.5 text-xs font-bold text-white shadow-xs">
              Voice OPD 24x7
            </span>
            <Link
              href="/"
              className="inline-flex items-center gap-1 rounded-full bg-black/20 hover:bg-black/35 px-3 py-1 text-xs font-medium text-white transition"
            >
              <span>Voice Call</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="relative z-10 flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-10">
        {/* Background Ambient Glows (Teal, Cyan, Deep Slate) */}
        <div className="pointer-events-none absolute -top-24 -left-24 h-96 w-96 rounded-full bg-[#008778]/25 blur-[120px]" />
        <div className="pointer-events-none absolute -bottom-24 -right-24 h-96 w-96 rounded-full bg-[#00dfc4]/20 blur-[120px]" />
        <div className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[500px] w-[500px] rounded-full bg-[#00dfc4]/10 blur-[150px]" />

        {/* Subtle Cyber Grid */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.18]"
          style={{
            backgroundImage:
              'radial-gradient(circle at 1px 1px, rgba(0, 223, 196, 0.4) 1px, transparent 0)',
            backgroundSize: '36px 36px',
          }}
        />

        {/* Main Card */}
        <div className="relative z-10 w-full max-w-4xl overflow-hidden rounded-3xl border border-[#00dfc4]/20 bg-[#0a121e]/95 shadow-[0_25px_60px_-15px_rgba(0,223,196,0.18)] backdrop-blur-2xl">
          <div className="grid grid-cols-1 lg:grid-cols-12">
            {/* Left Hero Panel (Teal & Cyan Brand Banner) */}
            <div className="relative flex flex-col justify-between overflow-hidden bg-gradient-to-br from-[#032320] via-[#063531] to-[#041a22] p-8 text-white lg:col-span-5 lg:p-10 border-b lg:border-b-0 lg:border-r border-[#00dfc4]/15">
              {/* Internal glow accents */}
              <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-[#00dfc4]/20 blur-3xl" />
              <div className="pointer-events-none absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-[#008778]/30 blur-3xl" />

              {/* Brand Header */}
              <div className="relative z-10 space-y-3">
                <div className="inline-flex items-center gap-2 rounded-full bg-[#00dfc4]/10 px-3 py-1 text-xs font-semibold tracking-wide text-[#00dfc4] border border-[#00dfc4]/25">
                  <span className="flex h-2 w-2 rounded-full bg-[#00dfc4] animate-ping" />
                  <span>Sir Ganga Ram City Hospital</span>
                </div>

                <h1 className="text-2xl font-bold tracking-tight text-white lg:text-3xl">
                  Clinic Voice <span className="text-[#00dfc4]">AI Assistant</span>
                </h1>

                <p className="text-xs sm:text-sm text-teal-100/80 leading-relaxed">
                  Book, reschedule, and manage OPD doctor appointments seamlessly with conversational Hindi &amp; English AI voice calls.
                </p>
              </div>

              {/* Feature Highlights with Glowing Cyan Accents */}
              <div className="relative z-10 my-8 space-y-3.5">
                <div className="flex items-start gap-3 rounded-2xl bg-[#031d1b]/70 p-3.5 border border-[#00dfc4]/15 backdrop-blur-md">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#00dfc4]/15 text-[#00dfc4] border border-[#00dfc4]/30">
                    <Mic className="h-5 w-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[#00dfc4]">
                      Voice Booking
                    </h4>
                    <p className="text-xs text-teal-100/70">
                      Fluent voice AI in Hindi and English for instant slot reservation.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 rounded-2xl bg-[#031d1b]/70 p-3.5 border border-[#00dfc4]/15 backdrop-blur-md">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#00dfc4]/15 text-[#00dfc4] border border-[#00dfc4]/30">
                    <Stethoscope className="h-5 w-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[#00dfc4]">
                      OPD Specialists
                    </h4>
                    <p className="text-xs text-teal-100/70">
                      Direct doctor scheduling for General Medicine, Cardiology, &amp; Pediatrics.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 rounded-2xl bg-[#031d1b]/70 p-3.5 border border-[#00dfc4]/15 backdrop-blur-md">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#00dfc4]/15 text-[#00dfc4] border border-[#00dfc4]/30">
                    <ShieldCheck className="h-5 w-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[#00dfc4]">
                      Secure &amp; Encrypted
                    </h4>
                    <p className="text-xs text-teal-100/70">
                      Protected with Supabase auth and encrypted patient data.
                    </p>
                  </div>
                </div>
              </div>

              {/* Status footer */}
              <div className="relative z-10 pt-2 border-t border-teal-500/20 flex items-center justify-between text-xs text-teal-200/60">
                <span className="flex items-center gap-1.5">
                  <Activity className="h-3.5 w-3.5 text-[#00dfc4]" /> Live Voice Network
                </span>
                <span className="rounded-md bg-[#ff621f]/20 px-2 py-0.5 text-[#ff621f] font-semibold text-[11px]">
                  OPD Active
                </span>
              </div>
            </div>

            {/* Right Form Panel (Midnight Dark + Neon Cyan Controls) */}
            <div className="flex flex-col justify-between bg-[#08101e] p-8 sm:p-10 lg:col-span-7">
              <div>
                {/* Header & Tab Switcher */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-5">
                  <div>
                    <h2 className="text-2xl font-bold text-white tracking-tight">
                      {mode === 'signup' ? 'Create Patient Account' : 'Welcome Back'}
                    </h2>
                    <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                      {mode === 'signup'
                        ? 'Register your profile for personalized voice appointments'
                        : 'Sign in to access your consultations and appointments'}
                    </p>
                  </div>

                  {/* Tabs */}
                  <div className="inline-flex rounded-xl bg-[#040811] p-1 border border-slate-800 shrink-0">
                    <button
                      type="button"
                      onClick={() => {
                        setMode('signup');
                        setErrorMessage(null);
                        setSuccessMessage(null);
                      }}
                      className={`rounded-lg px-3.5 py-1.5 text-xs font-bold transition-all duration-200 cursor-pointer ${
                        mode === 'signup'
                          ? 'bg-[#00dfc4] text-[#04201c] shadow-md shadow-[#00dfc4]/25'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      Sign Up
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setMode('login');
                        setErrorMessage(null);
                        setSuccessMessage(null);
                      }}
                      className={`rounded-lg px-3.5 py-1.5 text-xs font-bold transition-all duration-200 cursor-pointer ${
                        mode === 'login'
                          ? 'bg-[#00dfc4] text-[#04201c] shadow-md shadow-[#00dfc4]/25'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      Sign In
                    </button>
                  </div>
                </div>

                {/* Logged in notification banner */}
                {existingUser && (
                  <div className="mt-5 rounded-2xl bg-[#032320] p-4 border border-[#00dfc4]/30 flex items-center justify-between gap-3 text-xs text-[#00dfc4]">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-[#00dfc4] shrink-0" />
                      <span className="text-slate-200">
                        Signed in as <strong className="font-semibold text-[#00dfc4]">{existingUser}</strong>
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Link
                        href="/"
                        className="rounded-lg bg-[#00dfc4] px-3 py-1 font-bold text-[#04201c] hover:bg-[#00f3d6] transition"
                      >
                        Voice Agent
                      </Link>
                      <button
                        type="button"
                        onClick={handleSignOut}
                        className="rounded-lg border border-[#00dfc4]/40 bg-transparent px-2.5 py-1 text-[#00dfc4] hover:bg-[#00dfc4]/10 transition cursor-pointer"
                      >
                        Sign Out
                      </button>
                    </div>
                  </div>
                )}

                {/* Error Banner */}
                {errorMessage && (
                  <div className="mt-5 flex items-start gap-2.5 rounded-2xl border border-rose-500/40 bg-rose-950/40 p-3.5 text-xs text-rose-300">
                    <AlertCircle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
                    <div className="flex-1 font-medium">{errorMessage}</div>
                  </div>
                )}

                {/* Success Banner */}
                {successMessage && (
                  <div className="mt-5 flex items-start gap-2.5 rounded-2xl border border-[#00dfc4]/40 bg-[#00dfc4]/10 p-3.5 text-xs text-[#00dfc4]">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-[#00dfc4] mt-0.5" />
                    <div className="flex-1 font-medium text-slate-100">{successMessage}</div>
                  </div>
                )}

                {/* Form Fields */}
                <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                  {mode === 'signup' && (
                    <>
                      {/* Full Name */}
                      <div>
                        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                          Full Name
                        </label>
                        <div className="relative">
                          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#00dfc4]">
                            <User className="h-4 w-4" />
                          </div>
                          <input
                            type="text"
                            required
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            placeholder="e.g. Ramesh Kumar"
                            className="w-full rounded-xl border border-slate-700/80 bg-[#0c1626] py-2.5 pl-10 pr-4 text-sm text-white placeholder:text-slate-500 focus:border-[#00dfc4] focus:bg-[#0f1d32] focus:outline-hidden focus:ring-2 focus:ring-[#00dfc4]/20 transition-all"
                          />
                        </div>
                      </div>

                      {/* Phone Number */}
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                            Mobile Number
                          </label>
                          <span className="text-[11px] text-[#00dfc4] font-medium">
                            Linked to Voice Booking
                          </span>
                        </div>
                        <div className="relative flex rounded-xl border border-slate-700/80 bg-[#0c1626] focus-within:border-[#00dfc4] focus-within:bg-[#0f1d32] focus-within:ring-2 focus-within:ring-[#00dfc4]/20 transition-all">
                          <div className="flex items-center pl-3.5 pr-2.5 text-[#00dfc4] text-xs font-bold border-r border-slate-700/80 bg-[#08121f] rounded-l-xl">
                            <Phone className="h-3.5 w-3.5 mr-1 text-[#00dfc4]" />
                            +91
                          </div>
                          <input
                            type="tel"
                            inputMode="numeric"
                            maxLength={10}
                            value={phone}
                            onChange={(e) =>
                              setPhone(e.target.value.replace(/\D/g, '').slice(0, 10))
                            }
                            placeholder="10-digit mobile number"
                            className="w-full rounded-r-xl border-none bg-transparent py-2.5 px-3.5 text-sm text-white placeholder:text-slate-500 focus:outline-hidden"
                          />
                        </div>
                      </div>
                    </>
                  )}

                  {/* Email */}
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                      Email Address
                    </label>
                    <div className="relative">
                      <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#00dfc4]">
                        <Mail className="h-4 w-4" />
                      </div>
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="patient@example.com"
                        className="w-full rounded-xl border border-slate-700/80 bg-[#0c1626] py-2.5 pl-10 pr-4 text-sm text-white placeholder:text-slate-500 focus:border-[#00dfc4] focus:bg-[#0f1d32] focus:outline-hidden focus:ring-2 focus:ring-[#00dfc4]/20 transition-all"
                      />
                    </div>
                  </div>

                  {/* Password */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                        Password
                      </label>
                      {mode === 'signup' && (
                        <span className="text-[11px] text-slate-500">At least 6 characters</span>
                      )}
                    </div>
                    <div className="relative">
                      <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#00dfc4]">
                        <Lock className="h-4 w-4" />
                      </div>
                      <input
                        type={showPassword ? 'text' : 'password'}
                        required
                        minLength={6}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        className="w-full rounded-xl border border-slate-700/80 bg-[#0c1626] py-2.5 pl-10 pr-10 text-sm text-white placeholder:text-slate-500 focus:border-[#00dfc4] focus:bg-[#0f1d32] focus:outline-hidden focus:ring-2 focus:ring-[#00dfc4]/20 transition-all"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-slate-400 hover:text-[#00dfc4] transition cursor-pointer"
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Submit Action Button (Luminous Cyan matching screenshot) */}
                  <button
                    type="submit"
                    disabled={loading}
                    className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-[#00dfc4] hover:bg-[#00f3d6] py-3 px-4 text-sm font-bold text-[#04201c] shadow-lg shadow-[#00dfc4]/25 hover:shadow-[#00dfc4]/40 active:scale-[0.99] transition-all disabled:opacity-60 cursor-pointer disabled:cursor-not-allowed"
                  >
                    {loading ? (
                      <div className="flex items-center gap-2">
                        <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#04201c] border-t-transparent" />
                        <span>{mode === 'signup' ? 'Creating Account...' : 'Signing In...'}</span>
                      </div>
                    ) : (
                      <>
                        <span>{mode === 'signup' ? 'Create Account' : 'Sign In to Voice Agent'}</span>
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </button>
                </form>

                {/* Mode Switch Helper */}
                <div className="mt-5 text-center text-xs text-slate-400">
                  {mode === 'signup' ? (
                    <p>
                      Already have an account?{' '}
                      <button
                        type="button"
                        onClick={() => {
                          setMode('login');
                          setErrorMessage(null);
                          setSuccessMessage(null);
                        }}
                        className="font-bold text-[#00dfc4] hover:underline cursor-pointer"
                      >
                        Sign In here
                      </button>
                    </p>
                  ) : (
                    <p>
                      Need an account?{' '}
                      <button
                        type="button"
                        onClick={() => {
                          setMode('signup');
                          setErrorMessage(null);
                          setSuccessMessage(null);
                        }}
                        className="font-bold text-[#00dfc4] hover:underline cursor-pointer"
                      >
                        Create one now
                      </button>
                    </p>
                  )}
                </div>
              </div>

              {/* Bottom Navigation */}
              <div className="mt-8 pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <Link
                  href="/"
                  className="inline-flex items-center gap-1.5 text-[#00dfc4] hover:text-[#00f3d6] font-semibold hover:underline"
                >
                  ← Back to Voice Call Screen
                </Link>

                <span className="text-[11px] text-slate-500">
                  Sir Ganga Ram Hospital • Voice OPD
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer subtle brand */}
      <footer className="relative z-10 py-3 text-center text-xs text-slate-500">
        Sir Ganga Ram City Hospital • Powered by Voice AI &amp; Supabase
      </footer>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#060b14] text-[#00dfc4]">
          <div className="h-8 w-8 animate-spin rounded-full border-3 border-[#00dfc4] border-t-transparent" />
        </div>
      }
    >
      <SignupForm />
    </Suspense>
  );
}

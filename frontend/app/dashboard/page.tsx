'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useTheme } from 'next-themes';
import {
  Activity,
  ArrowLeft,
  BarChart3,
  Beef,
  Bug,
  CheckCircle2,
  Clock,
  CloudSun,
  Database,
  Headphones,
  Landmark,
  Monitor,
  Moon,
  PhoneCall,
  Radio,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Sprout,
  Sun,
  TrendingUp,
  XCircle,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/shadcn/utils';

interface RecentCallLog {
  id: number;
  session_id: string;
  status: string;
  created_at: string;
}

interface AnalyticsData {
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  recent_logs?: RecentCallLog[];
}

// ==========================================
// Theme Toggle Component (Light / Dark / System)
// ==========================================
function ThemeToggleWidget({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className="h-8 w-20 rounded-full bg-emerald-100/60 dark:bg-emerald-950/40" />;
  }

  return (
    <div
      className={cn(
        'flex items-center divide-x divide-emerald-200/80 rounded-full border border-emerald-300/80 bg-white/80 p-0.5 shadow-sm backdrop-blur-md dark:divide-emerald-800/80 dark:border-emerald-700/60 dark:bg-emerald-950/80',
        className
      )}
    >
      <button
        type="button"
        onClick={() => setTheme('light')}
        title="Light Mode"
        className={cn(
          'cursor-pointer rounded-full p-1.5 transition-colors',
          theme === 'light'
            ? 'bg-emerald-500 text-white shadow-xs'
            : 'text-emerald-700 hover:text-emerald-950 dark:text-emerald-400'
        )}
      >
        <Sun className="size-3.5" />
      </button>
      <button
        type="button"
        onClick={() => setTheme('dark')}
        title="Dark Mode"
        className={cn(
          'cursor-pointer rounded-full p-1.5 transition-colors',
          theme === 'dark'
            ? 'bg-emerald-500 text-white shadow-xs'
            : 'text-emerald-700 hover:text-emerald-950 dark:text-emerald-400'
        )}
      >
        <Moon className="size-3.5" />
      </button>
      <button
        type="button"
        onClick={() => setTheme('system')}
        title="System Mode"
        className={cn(
          'cursor-pointer rounded-full p-1.5 transition-colors',
          theme === 'system'
            ? 'bg-emerald-500 text-white shadow-xs'
            : 'text-emerald-700 hover:text-emerald-950 dark:text-emerald-400'
        )}
      >
        <Monitor className="size-3.5" />
      </button>
    </div>
  );
}

// ==========================================
// 6 Core Agricultural Modules Monitored
// ==========================================
const MONITORED_SERVICES = [
  {
    titleHindi: 'मौसम पूर्वानुमान',
    titleEnglish: 'Weather Forecast',
    icon: <CloudSun className="size-5 text-amber-500 dark:text-amber-400" />,
    description: 'वास्तविक समय तापमान, बारिश और कृषि मौसमी अलर्ट',
    tag: 'Live Tool',
  },
  {
    titleHindi: 'फसल सलाह व बुवाई',
    titleEnglish: 'Crop Advisory',
    icon: <Sprout className="size-5 text-emerald-600 dark:text-emerald-400" />,
    description: 'मिट्टी अनुसार उन्नत बीज चयन, संतुलित खाद व सिंचाई प्रबंधन',
    tag: 'Smart Guide',
  },
  {
    titleHindi: 'दैनिक मंडी भाव',
    titleEnglish: 'Daily Mandi Rates',
    icon: <TrendingUp className="size-5 text-blue-500 dark:text-blue-400" />,
    description: 'देशभर की प्रमुख कृषि मंडियों में फसलों के लाइव भाव',
    tag: 'Daily Market',
  },
  {
    titleHindi: 'रोग व कीट नियंत्रण',
    titleEnglish: 'Disease Control',
    icon: <Bug className="size-5 text-rose-500 dark:text-rose-400" />,
    description: 'फसलों के कीट व फफूंद की पहचान एवं वैज्ञानिक जैविक उपचार',
    tag: 'Crop Health',
  },
  {
    titleHindi: 'पशुपालन व डेयरी',
    titleEnglish: 'Livestock Care',
    icon: <Beef className="size-5 text-orange-500 dark:text-orange-400" />,
    description: 'दुधारू पशुओं का संतुलित आहार, दूध वृद्धि व टीकाकरण',
    tag: 'Dairy Health',
  },
  {
    titleHindi: 'सरकारी कृषि योजनाएँ',
    titleEnglish: 'Govt Schemes',
    icon: <Landmark className="size-5 text-purple-500 dark:text-purple-400" />,
    description: 'पीएम किसान, फसल बीमा, सोलर पंप अनुदान व केसीसी सब्सिडी',
    tag: 'Govt Subsidy',
  },
];

export default function DashboardPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  const fetchAnalytics = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      const res = await fetch('/api/analytics', { cache: 'no-store' });
      if (res.ok) {
        const json: AnalyticsData = await res.json();
        setData({
          total_calls: json.total_calls ?? 0,
          successful_calls: json.successful_calls ?? 0,
          failed_calls: json.failed_calls ?? 0,
          recent_logs: json.recent_logs ?? [],
        });
        setLastUpdated(new Date());
      }
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
    } finally {
      setLoading(false);
      if (isManual) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  // Auto-refresh interval every 5 seconds if enabled
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchAnalytics(false);
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchAnalytics]);

  const totalCalls = data?.total_calls ?? 0;
  const successfulCalls = data?.successful_calls ?? 0;
  const failedCalls = data?.failed_calls ?? 0;
  const successRate = totalCalls > 0 ? Math.round((successfulCalls / totalCalls) * 100) : 0;
  const failRate = totalCalls > 0 ? Math.round((failedCalls / totalCalls) * 100) : 0;
  const recentLogs = data?.recent_logs ?? [];

  return (
    <div className="relative flex min-h-screen w-full flex-col justify-between overflow-x-hidden bg-gradient-to-b from-lime-50 via-emerald-50 to-lime-100 font-sans text-emerald-950 transition-colors duration-500 selection:bg-emerald-300 selection:text-emerald-950 dark:from-[#021810] dark:via-[#04261a] dark:to-[#021810] dark:text-emerald-50">
      {/* Dynamic Ambient Glow Orbs */}
      <div className="pointer-events-none absolute top-10 left-1/4 -z-10 size-96 -translate-x-1/2 rounded-full bg-emerald-400/15 blur-3xl dark:bg-emerald-500/10" />
      <div className="pointer-events-none absolute top-1/3 right-1/4 -z-10 size-96 translate-x-1/2 rounded-full bg-lime-400/15 blur-3xl dark:bg-lime-500/10" />
      <div className="pointer-events-none absolute -bottom-10 left-1/3 -z-10 size-96 rounded-full bg-yellow-400/10 blur-3xl dark:bg-emerald-600/10" />

      {/* ========================================== */}
      {/* 1. Top Navigation Bar (Header)             */}
      {/* ========================================== */}
      <header className="sticky top-0 z-40 w-full border-b border-emerald-200/60 bg-white/70 backdrop-blur-md transition-colors dark:border-emerald-900/50 dark:bg-[#021810]/70">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          {/* Left: Brand + Navigation Link */}
          <div className="flex items-center gap-3 sm:gap-4">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300/80 bg-white/90 px-3.5 py-1.5 text-xs font-bold text-emerald-900 shadow-xs transition-all duration-200 hover:scale-105 hover:bg-emerald-100 dark:border-emerald-700/60 dark:bg-emerald-950/80 dark:text-emerald-300 dark:hover:bg-emerald-900"
              title="मुख्य पेज पर वापस जाएं"
            >
              <ArrowLeft className="size-3.5 text-emerald-600 dark:text-emerald-400" />
              <span>🌾 मुख्य पेज (Voice Assistant)</span>
            </Link>

            <div className="hidden h-6 w-px bg-emerald-300/60 sm:block dark:bg-emerald-800/60" />

            <div className="flex items-center gap-2.5">
              <div className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-tr from-emerald-500 via-green-500 to-lime-400 text-lg text-white shadow-md shadow-emerald-500/20 select-none">
                🌾
              </div>
              <div className="hidden sm:block">
                <div className="flex items-center gap-1.5">
                  <h1 className="text-base font-black tracking-tight text-emerald-950 dark:text-emerald-50">
                    KisanMitra AI
                  </h1>
                  <span className="rounded-md border border-emerald-300/80 bg-emerald-100 px-2 py-0.5 text-[11px] font-bold text-emerald-800 dark:border-emerald-700 dark:bg-emerald-900/80 dark:text-emerald-300">
                    📊 कॉलिंग एनालिटिक्स
                  </span>
                </div>
                <p className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-400">
                  Developed by Rishabh Kumar
                </p>
              </div>
            </div>
          </div>

          {/* Right: Controls & Badges */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Live SQLite DB Status Badge */}
            <div className="hidden items-center gap-1.5 rounded-full border border-emerald-300/80 bg-emerald-100/90 px-3 py-1 text-xs font-bold text-emerald-900 shadow-xs md:flex dark:border-emerald-700/60 dark:bg-emerald-950/80 dark:text-emerald-300">
              <span className="relative flex size-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75"></span>
                <span className="relative inline-flex size-2 rounded-full bg-emerald-600 dark:bg-emerald-400"></span>
              </span>
              <span>SQLite WAL (Live DB)</span>
            </div>

            {/* Auto-Sync Toggle */}
            <button
              type="button"
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={cn(
                'flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-bold shadow-xs transition-all',
                autoRefresh
                  ? 'border-emerald-400 bg-emerald-500 text-white shadow-emerald-500/20'
                  : 'border-emerald-300/80 bg-white/80 text-emerald-800 hover:bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
              )}
              title={autoRefresh ? 'ऑटो-सिंक सक्रिय (5 सेकंड)' : 'ऑटो-सिंक रुका हुआ है'}
            >
              <Radio className={cn('size-3', autoRefresh ? 'animate-pulse' : '')} />
              <span className="hidden sm:inline">
                {autoRefresh ? 'ऑटो-सिंक ऑन' : 'ऑटो-सिंक ऑफ'}
              </span>
            </button>

            {/* Manual Refresh Button */}
            <button
              type="button"
              onClick={() => fetchAnalytics(true)}
              disabled={refreshing || loading}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-emerald-300/80 bg-white/90 px-3.5 py-1.5 text-xs font-bold text-emerald-900 shadow-xs transition-all duration-150 hover:bg-emerald-100 active:scale-95 disabled:opacity-50 dark:border-emerald-700/60 dark:bg-emerald-950/80 dark:text-emerald-200 dark:hover:bg-emerald-900"
              title="डेटा को पुनः ताज़ा करें"
            >
              <RefreshCw className={cn('size-3.5', refreshing ? 'animate-spin text-emerald-600 dark:text-emerald-400' : '')} />
              <span className="hidden sm:inline">रिफ्रेश</span>
            </button>

            {/* Theme Toggle Widget */}
            <ThemeToggleWidget />
          </div>
        </div>
      </header>

      {/* ========================================== */}
      {/* Main Content Area                          */}
      {/* ========================================== */}
      <main className="relative z-10 mx-auto w-full max-w-7xl grow space-y-8 px-4 py-8 sm:px-6 lg:px-8">
        {/* Welcome & Header Title Banner */}
        <section className="relative overflow-hidden rounded-3xl border border-emerald-200/80 bg-white/75 p-6 shadow-lg backdrop-blur-xl transition-all sm:p-8 dark:border-emerald-800/60 dark:bg-emerald-950/50">
          {/* Top Decorative Glow */}
          <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-emerald-500 via-lime-400 to-yellow-400" />

          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-300/90 bg-emerald-100/90 px-3.5 py-1 text-xs font-bold text-emerald-900 shadow-xs dark:border-emerald-700 dark:bg-emerald-900/70 dark:text-emerald-200">
                <Sparkles className="size-3.5 text-emerald-600 dark:text-emerald-400" />
                <span>✨ भारत का स्मार्ट कृषि सहायक • कॉलिंग एनालिटिक्स व परफ़ॉर्मेंस</span>
              </div>

              <h2 className="bg-gradient-to-r from-emerald-800 via-green-700 to-lime-600 bg-clip-text text-3xl font-black tracking-tight text-transparent sm:text-4xl dark:from-emerald-400 dark:via-lime-300 dark:to-yellow-400">
                KisanMitra AI Call Analytics
              </h2>

              <p className="max-w-2xl text-xs font-medium leading-relaxed text-emerald-900/80 sm:text-sm dark:text-emerald-200/80">
                भारतीय किसानों के लिए समर्पित एआई वॉइस कॉलिंग परफ़ॉर्मेंस, मौसम, मंडी भाव, फसल सलाह और
                विशेषज्ञ सहायता के कॉल्स का रियल-टाइम डेटा विश्लेषण।
              </p>
            </div>

            <div className="flex flex-col items-start gap-2.5 rounded-2xl border border-emerald-200/80 bg-emerald-50/80 p-4 text-xs font-semibold text-emerald-900 shadow-xs sm:items-end dark:border-emerald-800/60 dark:bg-emerald-900/40 dark:text-emerald-200">
              <div className="flex items-center gap-2">
                <Clock className="size-4 text-emerald-600 dark:text-emerald-400" />
                <span>
                  अंतिम अपडेट :{' '}
                  <span className="font-mono text-emerald-950 dark:text-emerald-100">
                    {lastUpdated
                      ? lastUpdated.toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })
                      : 'कनेक्ट हो रहा है...'}
                  </span>
                </span>
              </div>

              <div className="flex items-center gap-2 text-[11px] text-emerald-700 dark:text-emerald-400">
                <span className="inline-block size-2 rounded-full bg-emerald-500" />
                <span>ऑटो-सिंक अंतराल : 5 सेकंड</span>
              </div>
            </div>
          </div>
        </section>

        {/* ========================================== */}
        {/* 3 Large Metric Cards                       */}
        {/* ========================================== */}
        <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {/* 1. Total Calls */}
          <div className="group relative overflow-hidden rounded-3xl border border-emerald-200/80 bg-white/75 p-6 shadow-lg backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:border-emerald-400 hover:shadow-2xl dark:border-emerald-800/60 dark:bg-emerald-950/50 dark:hover:border-emerald-500/70">
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-blue-400 to-teal-400 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
            <div className="mb-4 flex items-center justify-between">
              <span className="text-xs font-bold tracking-wider text-emerald-800 uppercase dark:text-emerald-300">
                कुल कॉल्स (Total Calls)
              </span>
              <div className="flex size-11 items-center justify-center rounded-2xl border border-blue-200 bg-blue-50 text-blue-600 shadow-xs transition-transform duration-200 group-hover:scale-105 dark:border-blue-800/60 dark:bg-blue-950/50 dark:text-blue-400">
                <PhoneCall className="size-5" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-black tracking-tight text-emerald-950 sm:text-5xl dark:text-white">
                {loading ? '—' : totalCalls}
              </span>
              <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                सेशंस
              </span>
            </div>
            <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-emerald-800/80 dark:text-emerald-300/80">
              <Headphones className="size-3.5 text-blue-500" />
              <span>इनबाउंड वेब कॉल्स व लाइव वॉइस बातचीत</span>
            </p>
            <div className="mt-4 flex items-center justify-between border-t border-emerald-200/60 pt-3 text-xs font-semibold text-emerald-700 dark:border-emerald-800/60 dark:text-emerald-400">
              <span>स्थिति: SQLite में सुरक्षित</span>
              <span className="font-mono text-emerald-900 dark:text-emerald-200">100% Logged</span>
            </div>
          </div>

          {/* 2. Successful Calls */}
          <div className="group relative overflow-hidden rounded-3xl border border-emerald-300/80 bg-gradient-to-b from-white/90 to-emerald-50/80 p-6 shadow-lg backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:border-emerald-500 hover:shadow-2xl dark:border-emerald-700/60 dark:from-emerald-950/60 dark:to-emerald-900/30 dark:hover:border-emerald-400">
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-400 via-green-400 to-lime-400 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
            <div className="mb-4 flex items-center justify-between">
              <span className="text-xs font-bold tracking-wider text-emerald-800 uppercase dark:text-emerald-300">
                सफल कॉल्स (Successful Calls)
              </span>
              <div className="flex size-11 items-center justify-center rounded-2xl border border-emerald-300 bg-emerald-100 text-emerald-600 shadow-xs transition-transform duration-200 group-hover:scale-105 dark:border-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-400">
                <CheckCircle2 className="size-5" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-black tracking-tight text-emerald-600 sm:text-5xl dark:text-emerald-400">
                {loading ? '—' : successfulCalls}
              </span>
              <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300">
                हल हुए
              </span>
            </div>
            <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-emerald-800/90 dark:text-emerald-200/90">
              <TrendingUp className="size-3.5 text-emerald-600 dark:text-emerald-400" />
              <span>मौसम, मंडी भाव या विशेषज्ञ टिकट समाधान सत्यापित</span>
            </p>
            <div className="mt-4 flex items-center justify-between border-t border-emerald-200/80 pt-3 text-xs font-bold text-emerald-800 dark:border-emerald-800/80 dark:text-emerald-300">
              <span>सफलता दर (Success Rate)</span>
              <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 font-mono text-emerald-800 dark:bg-emerald-900/80 dark:text-emerald-200">
                {successRate}%
              </span>
            </div>
          </div>

          {/* 3. Failed / Dropped Calls */}
          <div className="group relative overflow-hidden rounded-3xl border border-rose-200/80 bg-gradient-to-b from-white/90 to-rose-50/40 p-6 shadow-lg backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:border-rose-400 hover:shadow-2xl dark:border-rose-900/40 dark:from-emerald-950/60 dark:to-rose-950/20 dark:hover:border-rose-700/60">
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-rose-400 to-amber-400 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
            <div className="mb-4 flex items-center justify-between">
              <span className="text-xs font-bold tracking-wider text-rose-800 uppercase dark:text-rose-300">
                विफल / लंबित (Failed / Dropped)
              </span>
              <div className="flex size-11 items-center justify-center rounded-2xl border border-rose-200 bg-rose-100 text-rose-600 shadow-xs transition-transform duration-200 group-hover:scale-105 dark:border-rose-800/60 dark:bg-rose-950/60 dark:text-rose-400">
                <XCircle className="size-5" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-black tracking-tight text-rose-600 sm:text-5xl dark:text-rose-400">
                {loading ? '—' : failedCalls}
              </span>
              <span className="text-xs font-bold text-rose-700 dark:text-rose-300">
                अधूरे
              </span>
            </div>
            <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-rose-800/80 dark:text-rose-300/80">
              <Activity className="size-3.5 text-rose-500" />
              <span>कॉल बीच में कटी या बिना सवाल पूछे डिस्कनेक्ट</span>
            </p>
            <div className="mt-4 flex items-center justify-between border-t border-rose-200/60 pt-3 text-xs font-bold text-rose-800 dark:border-rose-900/40 dark:text-rose-300">
              <span>ड्रॉप दर (Drop Rate)</span>
              <span className="rounded-full bg-rose-100 px-2.5 py-0.5 font-mono text-rose-800 dark:bg-rose-950/80 dark:text-rose-200">
                {failRate}%
              </span>
            </div>
          </div>
        </section>

        {/* ========================================== */}
        {/* Call Resolution Progress Ratio Bar         */}
        {/* ========================================== */}
        <section className="space-y-4 rounded-3xl border border-emerald-200/80 bg-white/75 p-6 shadow-lg backdrop-blur-xl dark:border-emerald-800/60 dark:bg-emerald-950/50">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Activity className="size-4 text-emerald-600 dark:text-emerald-400" />
              <h3 className="text-sm font-bold text-emerald-950 dark:text-emerald-100">
                कॉल समाधान अनुपात (Call Resolution Ratio)
              </h3>
            </div>
            <span className="text-xs font-bold text-emerald-800 dark:text-emerald-300">
              {successfulCalls} सफल • {failedCalls} लंबित/ड्रॉप • {totalCalls} कुल
            </span>
          </div>

          <div className="flex h-3.5 w-full overflow-hidden rounded-full bg-emerald-100 p-0.5 shadow-inner dark:bg-emerald-900/50">
            <div
              style={{ width: `${totalCalls > 0 ? successRate : 0}%` }}
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-green-500 to-teal-400 transition-all duration-500"
              title={`सफल: ${successRate}%`}
            />
            <div
              style={{ width: `${totalCalls > 0 ? failRate : 0}%` }}
              className="h-full rounded-full bg-rose-500 transition-all duration-500"
              title={`विफल/लंबित: ${failRate}%`}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs font-semibold text-emerald-800 dark:text-emerald-300">
            <div className="flex items-center gap-2">
              <span className="inline-block size-2.5 rounded-full bg-emerald-500" />
              <span>सफलतापूर्वक हल की गई कॉल्स ({successRate}%)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block size-2.5 rounded-full bg-rose-500" />
              <span>अपूर्ण / डिफ़ॉल्ट प्रारंभिक स्थिति ({failRate}%)</span>
            </div>
          </div>
        </section>

        {/* ========================================== */}
        {/* Recent Call Sessions Feed (SQLite Log)     */}
        {/* ========================================== */}
        <section className="space-y-4 rounded-3xl border border-emerald-200/80 bg-white/75 p-6 shadow-lg backdrop-blur-xl dark:border-emerald-800/60 dark:bg-emerald-950/50">
          <div className="flex items-center justify-between border-b border-emerald-200/60 pb-3 dark:border-emerald-800/60">
            <div className="flex items-center gap-2">
              <Database className="size-4 text-emerald-600 dark:text-emerald-400" />
              <h3 className="text-sm font-bold text-emerald-950 sm:text-base dark:text-emerald-100">
                हाल के वॉइस कॉल सेशंस (Live SQLite Call Logs)
              </h3>
            </div>
            <span className="rounded-full border border-emerald-300/80 bg-emerald-100 px-3 py-0.5 text-xs font-bold text-emerald-800 dark:border-emerald-700 dark:bg-emerald-900/80 dark:text-emerald-300">
              अंतिम {recentLogs.length} कॉल्स
            </span>
          </div>

          {recentLogs.length === 0 ? (
            <div className="py-8 text-center text-xs font-semibold text-emerald-700 dark:text-emerald-400">
              <span>🌾 अभी कोई कॉल डेटा उपलब्ध नहीं है। मुख्य पेज पर जाकर बातचीत शुरू करें।</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-emerald-200/60 text-emerald-700 dark:border-emerald-800/60 dark:text-emerald-400">
                    <th className="pb-2.5 font-bold">आईडी (ID)</th>
                    <th className="pb-2.5 font-bold">सेशन आईडी (Session ID)</th>
                    <th className="pb-2.5 font-bold">कॉल स्थिति (Status)</th>
                    <th className="pb-2.5 font-bold">दिनांक व समय (Timestamp)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-emerald-100 font-medium text-emerald-950 dark:divide-emerald-900/40 dark:text-emerald-100">
                  {recentLogs.map((log) => {
                    const isSuccess = log.status === 'success';
                    return (
                      <tr
                        key={log.id}
                        className="transition-colors hover:bg-emerald-50/50 dark:hover:bg-emerald-900/20"
                      >
                        <td className="py-2.5 font-mono text-emerald-700 dark:text-emerald-400">
                          #{log.id}
                        </td>
                        <td className="py-2.5 font-mono text-xs text-emerald-900 dark:text-emerald-200">
                          {log.session_id}
                        </td>
                        <td className="py-2.5">
                          <span
                            className={cn(
                              'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold shadow-2xs',
                              isSuccess
                                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/80 dark:text-emerald-200'
                                : 'bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300'
                            )}
                          >
                            {isSuccess ? (
                              <>
                                <CheckCircle2 className="size-3 text-emerald-600 dark:text-emerald-400" />
                                <span>सफल (Success)</span>
                              </>
                            ) : (
                              <>
                                <XCircle className="size-3 text-rose-600 dark:text-rose-400" />
                                <span>लंबित / विफल (Failed)</span>
                              </>
                            )}
                          </span>
                        </td>
                        <td className="py-2.5 text-emerald-700 dark:text-emerald-400">
                          {log.created_at || '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* ========================================== */}
        {/* 6 Monitored Agricultural Service Modules   */}
        {/* ========================================== */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-base font-bold text-emerald-950 sm:text-lg dark:text-emerald-100">
              <span>🌾</span> एआई वॉइस असिस्टेंट द्वारा समर्थित कृषि सेवाएँ
            </h3>
            <span className="hidden rounded-full border border-emerald-300 bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800 sm:inline-block dark:border-emerald-700 dark:bg-emerald-900/80 dark:text-emerald-300">
              6 सक्रिय टूल्स
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {MONITORED_SERVICES.map((svc) => (
              <div
                key={svc.titleEnglish}
                className="group relative overflow-hidden rounded-2xl border border-emerald-200/80 bg-white/70 p-5 shadow-md backdrop-blur-md transition-all duration-300 hover:-translate-y-1 hover:border-emerald-400 hover:shadow-xl dark:border-emerald-800/50 dark:bg-emerald-950/40 dark:hover:border-emerald-500/70"
              >
                <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-400 via-lime-400 to-yellow-400 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                <div className="mb-2.5 flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="flex size-9 items-center justify-center rounded-xl bg-emerald-100/80 shadow-xs dark:bg-emerald-900/60">
                      {svc.icon}
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-emerald-950 dark:text-emerald-50">
                        {svc.titleHindi}
                      </h4>
                      <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                        {svc.titleEnglish}
                      </span>
                    </div>
                  </div>
                  <span className="rounded-full border border-emerald-300/70 bg-emerald-100/90 px-2 py-0.5 text-[10px] font-bold text-emerald-800 uppercase dark:border-emerald-700/60 dark:bg-emerald-900/70 dark:text-emerald-300">
                    {svc.tag}
                  </span>
                </div>
                <p className="text-xs font-medium leading-relaxed text-emerald-900/80 dark:text-emerald-200/80">
                  {svc.description}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ========================================== */}
        {/* Privacy & Architecture Guarantee           */}
        {/* ========================================== */}
        <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Privacy Guarantee */}
          <div className="space-y-3 rounded-3xl border border-emerald-200/80 bg-white/75 p-6 shadow-lg backdrop-blur-xl dark:border-emerald-800/60 dark:bg-emerald-950/50">
            <div className="flex items-center gap-2.5 text-sm font-bold text-emerald-800 dark:text-emerald-300">
              <ShieldCheck className="size-5 text-emerald-600 dark:text-emerald-400" />
              <span>किसान डेटा गोपनीयता व सुरक्षा (Caller Privacy)</span>
            </div>
            <p className="text-xs font-medium leading-relaxed text-emerald-900/80 dark:text-emerald-200/80">
              यह एनालिटिक्स डैशबोर्ड पूर्णतः गोपनीय है। किसी भी किसान का व्यक्तिगत नाम, फ़ोन नंबर, या
              निजी जानकारी डैशबोर्ड पर सार्वजनिक नहीं की जाती है। केवल एआई परफ़ॉर्मेंस और कॉल समाधान का
              कुल डेटा ही संकलित होता है।
            </p>
            <div className="flex flex-wrap items-center gap-2 pt-2 text-[11px] font-bold">
              <span className="rounded-lg border border-emerald-300/80 bg-emerald-100/80 px-2.5 py-1 text-emerald-900 dark:border-emerald-700/60 dark:bg-emerald-900/70 dark:text-emerald-200">
                🔒 Zero PII Exposure
              </span>
              <span className="rounded-lg border border-emerald-300/80 bg-emerald-100/80 px-2.5 py-1 text-emerald-900 dark:border-emerald-700/60 dark:bg-emerald-900/70 dark:text-emerald-200">
                🛡️ DPDP & GDPR Ready
              </span>
            </div>
          </div>

          {/* Technology Architecture */}
          <div className="space-y-3 rounded-3xl border border-emerald-200/80 bg-white/75 p-6 shadow-lg backdrop-blur-xl dark:border-emerald-800/60 dark:bg-emerald-950/50">
            <div className="flex items-center gap-2.5 text-sm font-bold text-emerald-800 dark:text-emerald-300">
              <Zap className="size-5 text-amber-500" />
              <span>सिस्टम व टेक्नोलॉजी आर्किटेक्चर (Tech Specs)</span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-2xl border border-emerald-200/60 bg-emerald-50/70 p-3 dark:border-emerald-800/50 dark:bg-emerald-900/40">
                <span className="block text-[11px] font-semibold text-emerald-700 dark:text-emerald-400">
                  डेटाबेस
                </span>
                <span className="font-bold text-emerald-950 dark:text-emerald-100">
                  SQLite WAL (`call_logs`)
                </span>
              </div>
              <div className="rounded-2xl border border-emerald-200/60 bg-emerald-50/70 p-3 dark:border-emerald-800/50 dark:bg-emerald-900/40">
                <span className="block text-[11px] font-semibold text-emerald-700 dark:text-emerald-400">
                  TTS आवाज़ इंजन
                </span>
                <span className="font-bold text-emerald-950 dark:text-emerald-100">
                  Murf Falcon Hindi (Samar)
                </span>
              </div>
              <div className="rounded-2xl border border-emerald-200/60 bg-emerald-50/70 p-3 dark:border-emerald-800/50 dark:bg-emerald-900/40">
                <span className="block text-[11px] font-semibold text-emerald-700 dark:text-emerald-400">
                  एआई रीजनिंग (LLM)
                </span>
                <span className="font-bold text-emerald-950 dark:text-emerald-100">
                  Google Gemini 2.5 Flash
                </span>
              </div>
              <div className="rounded-2xl border border-emerald-200/60 bg-emerald-50/70 p-3 dark:border-emerald-800/50 dark:bg-emerald-900/40">
                <span className="block text-[11px] font-semibold text-emerald-700 dark:text-emerald-400">
                  स्पीच-टू-टेक्स्ट (STT)
                </span>
                <span className="font-bold text-emerald-950 dark:text-emerald-100">
                  Deepgram Nova-3 Multi
                </span>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ========================================== */}
      {/* Footer                                     */}
      {/* ========================================== */}
      <footer className="mt-12 w-full border-t border-emerald-200/60 bg-white/50 py-4 text-center text-xs font-semibold text-emerald-800/80 backdrop-blur-md dark:border-emerald-900/40 dark:bg-[#021810]/60 dark:text-emerald-400/80">
        <p>© 2026 KisanMitra AI — Developed by Rishabh Kumar • Powered by Murf Falcon & LiveKit Agents</p>
      </footer>
    </div>
  );
}

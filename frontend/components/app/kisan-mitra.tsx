'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
import { ConnectionState, TokenSource } from 'livekit-client';
import {
  Beef,
  Bug,
  CloudSun,
  Landmark,
  Monitor,
  Moon,
  RefreshCw,
  Sprout,
  Sun,
  TrendingUp,
} from 'lucide-react';
import { Toaster, toast } from 'sonner';
import {
  useChat,
  useConnectionState,
  useRoomContext,
  // <-- नया जोड़ा गया है आवाज़ को टेक्स्ट में पकड़ने के लिए
  useSession,
  useSessionContext,
  useVoiceAssistant,
} from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentControlBar } from '@/components/agents-ui/agent-control-bar';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';
import { cn } from '@/lib/shadcn/utils';
import { getSandboxTokenSource } from '@/lib/utils';

const CHAT_OPTIONS = { channelTopic: 'lk.chat' };

// ==========================================
// 6 Glassmorphism Agricultural Modules
// ==========================================
interface AgriculturalModule {
  id: string;
  emoji: string;
  titleHindi: string;
  titleEnglish: string;
  tag: string;
  description: string;
  samplePrompt: string;
  icon: React.ReactNode;
}

const AGRICULTURAL_MODULES: AgriculturalModule[] = [
  {
    id: 'weather',
    emoji: '⛅',
    titleHindi: 'मौसम',
    titleEnglish: 'Weather',
    tag: 'Live Forecast',
    description:
      'दैनिक तापमान, बारिश का सटीक पूर्वानुमान, आर्द्रता एवं वायु गति की वास्तविक समय जानकारी।',
    samplePrompt: 'आज मेरे क्षेत्र में बारिश की क्या संभावना है?',
    icon: <CloudSun className="size-6 text-amber-500 dark:text-amber-400" />,
  },
  {
    id: 'crop',
    emoji: '🌱',
    titleHindi: 'फसल सलाह',
    titleEnglish: 'Crop Guide',
    tag: 'Smart Farming',
    description:
      'मिट्टी अनुसार उन्नत बीज चयन, संतुलित खाद-उर्वरक प्रबंधन एवं वैज्ञानिक बुवाई तकनीक।',
    samplePrompt: 'गेहूं की फसल में पहली सिंचाई और यूरिया कब डालनी चाहिए?',
    icon: <Sprout className="size-6 text-emerald-600 dark:text-emerald-400" />,
  },
  {
    id: 'market',
    emoji: '📈',
    titleHindi: 'मंडी भाव',
    titleEnglish: 'Market Rates',
    tag: 'Daily Mandi',
    description:
      'देशभर की प्रमुख कृषि उपज मंडियों में अनाज, दलहन, तिलहन व सब्जियों के दैनिक ताज़ा भाव।',
    samplePrompt: 'आज स्थानीय मंडी में सरसों और सोयाबीन का क्या भाव है?',
    icon: <TrendingUp className="size-6 text-blue-500 dark:text-blue-400" />,
  },
  {
    id: 'disease',
    emoji: '🐛',
    titleHindi: 'रोग पहचान',
    titleEnglish: 'Disease Control',
    tag: 'Crop Health',
    description: 'फसलों के कीट, फफूंद व पत्तियों के पीलेपन की पहचान एवं जैविक व रासायनिक उपचार।',
    samplePrompt: 'धान की पत्तियों में भूरा धब्बा रोग लगा है, क्या उपाय करें?',
    icon: <Bug className="size-6 text-rose-500 dark:text-rose-400" />,
  },
  {
    id: 'livestock',
    emoji: '🐄',
    titleHindi: 'पशुपालन',
    titleEnglish: 'Livestock',
    tag: 'Dairy & Health',
    description: 'दुधारू पशुओं का संतुलित आहार, दूध वृद्धि, समय पर टीकाकरण एवं प्राथमिक चिकित्सा।',
    samplePrompt: 'दुधारू गाय का दूध उत्पादन बढ़ाने के लिए संतुलित आहार क्या दें?',
    icon: <Beef className="size-6 text-orange-500 dark:text-orange-400" />,
  },
  {
    id: 'schemes',
    emoji: '🏛️',
    titleHindi: 'योजनाएँ',
    titleEnglish: 'Schemes',
    tag: 'Govt Subsidy',
    description: 'पीएम किसान सम्मान निधि, फसल बीमा, सोलर पंप अनुदान, केसीसी व सरकारी कृषि सब्सिडी।',
    samplePrompt: 'पीएम कुसुम योजना के तहत सोलर पंप पर कितनी सब्सिडी मिलती है?',
    icon: <Landmark className="size-6 text-purple-500 dark:text-purple-400" />,
  },
];

// ==========================================
// Theme Toggle Component
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
// Central Voice Agent Controller (5 States)
// ==========================================
export function VoiceAgentController({
  micError,
  onRetryMic,
}: {
  micError: boolean;
  onRetryMic?: () => void;
}) {
  const connectionState = useConnectionState();
  const { state: agentState } = useVoiceAssistant();
  const { isConnected, start, end } = useSessionContext();
  const [isTranscriptOpen, setIsTranscriptOpen] = useState(false);

  // Determine explicit states:
  // STATE 1 & 5: Disconnected / Ready / Call Ended
  // STATE 2: Connecting (only during room connection)
  // STATE 3: Listening (active listening / idle / processing)
  // STATE 4: Speaking (agent speaking output)
  const isDisconnected =
    !isConnected ||
    connectionState === ConnectionState.Disconnected ||
    agentState === 'disconnected';

  const isConnecting =
    !isDisconnected &&
    !isConnected &&
    (connectionState === ConnectionState.Connecting ||
      connectionState === ConnectionState.Reconnecting ||
      agentState === 'connecting' ||
      agentState === 'initializing');

  const isSpeaking = isConnected && agentState === 'speaking';

  const isListening = isConnected && !isSpeaking && !isConnecting;

  const handleStartCall = async () => {
    try {
      await start();
    } catch (err) {
      console.error('Failed to start LiveKit session:', err);
      toast.error('बातचीत शुरू करने में समस्या आई। कृपया पुनः प्रयास करें।');
    }
  };

  const handleEndCall = async () => {
    try {
      await end();
    } catch (err) {
      console.error('Failed to end LiveKit session:', err);
    }
  };

  return (
    <div className="my-6 flex w-full flex-col items-center justify-center px-4 sm:my-8">
      {/* Requirement 3: Microphone Permission Error Banner */}
      {micError && (
        <div
          role="alert"
          className="animate-in fade-in slide-in-from-top-2 mb-6 flex w-full max-w-2xl items-center justify-between gap-3.5 rounded-2xl border-2 border-rose-400 bg-rose-50 p-4 text-rose-900 shadow-xl backdrop-blur-md duration-300 dark:border-rose-700/80 dark:bg-rose-950/80 dark:text-rose-100"
        >
          <div className="flex items-center gap-3">
            <span className="shrink-0 text-2xl">⚠️</span>
            <p className="text-sm leading-relaxed font-semibold md:text-base">
              ⚠️ माइक की अनुमति (Microphone Permission) बंद है। कृपया अपने ब्राउज़र में माइक की
              अनुमति चालू करें।
            </p>
          </div>
          {onRetryMic && (
            <button
              onClick={onRetryMic}
              type="button"
              className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-xl bg-rose-200 px-3 py-1.5 text-xs font-bold text-rose-900 transition hover:bg-rose-300 dark:bg-rose-900 dark:text-rose-100 dark:hover:bg-rose-800"
            >
              <RefreshCw className="size-3.5" /> पुनः जाँचें
            </button>
          )}
        </div>
      )}

      {/* STATE 1 & STATE 5: Disconnected / Ready / Call Ended */}
      {isDisconnected && !isConnecting && (
        <div className="animate-in fade-in zoom-in-95 flex w-full max-w-md flex-col items-center text-center duration-300">
          <button
            type="button"
            onClick={handleStartCall}
            className="group relative inline-flex cursor-pointer items-center justify-center gap-3.5 rounded-full border border-emerald-300/40 bg-gradient-to-r from-emerald-500 to-yellow-500 px-8 py-4 text-lg font-bold text-white shadow-xl transition-all duration-300 hover:scale-105 hover:from-emerald-600 hover:to-yellow-600 hover:shadow-emerald-500/40 active:scale-95 md:px-10 md:py-5 md:text-xl"
          >
            <span> बातचीत शुरू करें</span>
          </button>
          <p className="mt-4 flex items-center justify-center gap-1.5 text-xs font-medium text-emerald-800 md:text-sm dark:text-emerald-300/90">
            <span>🔸</span>
            <span>हिंदी में तुरंत वॉइस बातचीत शुरू करने के लिए बटन पर क्लिक करें</span>
          </p>
        </div>
      )}

      {/* STATE 2: Connecting */}
      {isConnecting && (
        <div className="animate-in fade-in zoom-in-95 flex w-full max-w-md flex-col items-center rounded-3xl border border-amber-300/80 bg-white/80 p-6 text-center shadow-xl backdrop-blur-md duration-300 dark:border-amber-600/50 dark:bg-emerald-950/60">
          <div className="flex items-center gap-3">
            <span className="relative flex size-4">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-amber-400 opacity-75"></span>
              <span className="relative inline-flex size-4 rounded-full bg-amber-500"></span>
            </span>
            <span className="text-base font-bold text-amber-900 md:text-lg dark:text-amber-200">
              किसानमित्र जुड़ रहा है... (Connecting...)
            </span>
          </div>
          <p className="mt-2 text-xs font-medium text-amber-700/90 dark:text-amber-300/80">
            कृपया प्रतीक्षा करें, लाइव कनेक्शन स्थापित हो रहा है...
          </p>
        </div>
      )}

      {/* STATE 3: Listening */}
      {!isConnecting && isListening && (
        <div className="animate-in fade-in zoom-in-95 flex w-full max-w-2xl flex-col items-center space-y-4 text-center duration-300">
          <div className="inline-flex items-center gap-3 rounded-full border border-emerald-400 bg-emerald-100/90 px-6 py-2.5 shadow-md dark:border-emerald-600/60 dark:bg-emerald-900/70">
            <span className="relative flex size-4">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex size-4 rounded-full bg-emerald-500"></span>
            </span>
            <span className="text-base font-bold text-emerald-950 md:text-lg dark:text-emerald-100">
              🎙️ किसानमित्र सुन रहा है (Listening)...
            </span>
          </div>

          <div className="flex w-full justify-center">
            <AgentControlBar
              variant="livekit"
              isConnected={true}
              onDisconnect={handleEndCall}
              isChatOpen={isTranscriptOpen}
              onIsChatOpenChange={(open) => setIsTranscriptOpen(open)}
              controls={{
                microphone: true,
                camera: false,
                screenShare: false,
                chat: true,
                leave: true,
              }}
              className="rounded-[32px] border border-emerald-300/80 bg-white/85 p-2 shadow-2xl backdrop-blur-xl dark:border-emerald-600/60 dark:bg-emerald-950/85"
            />
          </div>

          {/* Collapsible Transcript & Chat Section */}
          <div className="flex w-full flex-col items-center">
            <button
              type="button"
              onClick={() => setIsTranscriptOpen((prev) => !prev)}
              className="mt-1 inline-flex cursor-pointer items-center gap-2 rounded-full border border-emerald-300/80 bg-white/90 px-5 py-2 text-xs font-bold text-emerald-950 shadow-md backdrop-blur-md transition hover:scale-105 hover:bg-emerald-100 active:scale-95 md:text-sm dark:border-emerald-700/60 dark:bg-emerald-900/80 dark:text-emerald-100 dark:hover:bg-emerald-800"
            >
              <span>{isTranscriptOpen ? '🔼' : '💬'}</span>
              <span>
                {isTranscriptOpen
                  ? 'ट्रांसक्रिप्ट व चैट बंद करें (Close Transcript)'
                  : '💬 लाइव ट्रांसक्रिप्ट व चैट खोलें (Open Live Transcript)'}
              </span>
            </button>

            {isTranscriptOpen && <KisanMitraLiveTranscript />}
          </div>
        </div>
      )}

      {/* STATE 4: Speaking */}
      {!isConnecting && isSpeaking && (
        <div className="animate-in fade-in zoom-in-95 flex w-full max-w-2xl flex-col items-center space-y-4 text-center duration-300">
          <div className="inline-flex items-center gap-3 rounded-full border border-lime-400 bg-lime-100/90 px-6 py-2.5 shadow-md dark:border-yellow-600/60 dark:bg-yellow-950/70">
            <span className="relative flex size-4">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-lime-400 opacity-75"></span>
              <span className="relative inline-flex size-4 rounded-full bg-yellow-400"></span>
            </span>
            <span className="text-base font-bold text-lime-950 md:text-lg dark:text-yellow-100">
              🔊 किसानमित्र बोल रहा है (Speaking)...
            </span>
          </div>

          <div className="flex w-full justify-center">
            <AgentControlBar
              variant="livekit"
              isConnected={true}
              onDisconnect={handleEndCall}
              isChatOpen={isTranscriptOpen}
              onIsChatOpenChange={(open) => setIsTranscriptOpen(open)}
              controls={{
                microphone: true,
                camera: false,
                screenShare: false,
                chat: true,
                leave: true,
              }}
              className="rounded-[32px] border border-lime-300/80 bg-white/85 p-2 shadow-2xl backdrop-blur-xl dark:border-yellow-600/60 dark:bg-emerald-950/85"
            />
          </div>

          {/* Collapsible Transcript & Chat Section */}
          <div className="flex w-full flex-col items-center">
            <button
              type="button"
              onClick={() => setIsTranscriptOpen((prev) => !prev)}
              className="mt-1 inline-flex cursor-pointer items-center gap-2 rounded-full border border-emerald-300/80 bg-white/90 px-5 py-2 text-xs font-bold text-emerald-950 shadow-md backdrop-blur-md transition hover:scale-105 hover:bg-emerald-100 active:scale-95 md:text-sm dark:border-emerald-700/60 dark:bg-emerald-900/80 dark:text-emerald-100 dark:hover:bg-emerald-800"
            >
              <span>{isTranscriptOpen ? '🔼' : '💬'}</span>
              <span>
                {isTranscriptOpen
                  ? 'ट्रांसक्रिप्ट व चैट बंद करें (Close Transcript)'
                  : '💬 लाइव ट्रांसक्रिप्ट व चैट खोलें (Open Live Transcript)'}
              </span>
            </button>

            {isTranscriptOpen && <KisanMitraLiveTranscript />}
          </div>
        </div>
      )}
    </div>
  );
}

// ==========================================
// KisanMitra Live Transcript & Chat Component (UPDATED)
// ==========================================
function KisanMitraLiveTranscript() {
  const { chatMessages, send, isSending } = useChat(CHAT_OPTIONS);
  const { state: agentState } = useVoiceAssistant();
  const room = useRoomContext(); // माइक से बोले गए शब्दों (STT) को पकड़ने के लिए

  const [inputText, setInputText] = useState('');
  const [voiceTranscripts, setVoiceTranscripts] = useState<
    Record<string, { text: string; timestamp: number }>
  >({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 1. लाइव वॉइस ट्रांसक्रिप्शन (आवाज़ को टेक्स्ट में बदलना) सुनने का लॉजिक
  useEffect(() => {
    if (!room) return;

    const handleTranscription = (
      segments: Array<{ id: string; text?: string }>,
      participant?: { isLocal?: boolean }
    ) => {
      // सिर्फ आपकी (किसान की) आवाज़ को ट्रांसक्रिप्ट में जोड़े
      if (participant && participant.isLocal) {
        setVoiceTranscripts((prev) => {
          const newTranscripts = { ...prev };
          segments.forEach((seg) => {
            if (seg.text && seg.text.trim() !== '') {
              // टेक्स्ट और उसका समय सेव करें ताकि वो हमेशा लिखा रहे
              newTranscripts[seg.id] = {
                text: seg.text,
                timestamp: newTranscripts[seg.id]?.timestamp || Date.now(),
              };
            }
          });
          return newTranscripts;
        });
      }
    };

    room.on('transcriptionReceived', handleTranscription);
    return () => {
      room.off('transcriptionReceived', handleTranscription);
    };
  }, [room]);

  // 2. टाइप किए गए मैसेज और बोले गए मैसेज (Voice) को एक साथ मिलाना
  const allMessages = useMemo(() => {
    const msgs = chatMessages.map((msg) => ({
      id: msg.id,
      text: msg.message,
      isFarmer: msg.from?.isLocal,
      timestamp: msg.timestamp || Date.now(),
    }));

    // वॉइस वाले सवाल जोड़ें (डुप्लीकेट से बचते हुए)
    Object.entries(voiceTranscripts).forEach(([id, data]) => {
      const isDuplicate = msgs.some(
        (m) => m.isFarmer && m.text.toLowerCase() === data.text.toLowerCase()
      );
      if (!isDuplicate) {
        msgs.push({
          id: `voice-${id}`,
          text: data.text,
          isFarmer: true,
          timestamp: data.timestamp,
        });
      }
    });

    // समय के अनुसार छांट लें ताकि सवाल के बाद ही जवाब आए
    return msgs.sort((a, b) => a.timestamp - b.timestamp);
  }, [chatMessages, voiceTranscripts]);

  // हमेशा ताज़ा मैसेज पर स्क्रॉल करें
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [allMessages, agentState]);

  const handleSend = async (textToSend?: string) => {
    const message = (textToSend ?? inputText).trim();
    if (!message) return;
    setInputText('');
    try {
      await send(message);
    } catch (err) {
      console.error('Failed to send text message:', err);
      toast.error('मैसेज भेजने में समस्या आई');
    }
  };

  const quickPrompts = [
    '🌾 आज गेहूं और धान का मंडी भाव क्या है?',
    '🐛 टमाटर की फसल में पीले पत्ते और कीट का उपाय बताएं',
    '🌧️ आज का मौसम और सिंचाई सलाह क्या है?',
    '💰 पीएम किसान सम्मान निधि 17वीं किस्त की जानकारी दें',
  ];

  return (
    <div className="mt-4 flex w-full flex-col rounded-3xl border border-emerald-300/80 bg-white/90 p-4 text-left shadow-xl backdrop-blur-xl md:p-6 dark:border-emerald-700/60 dark:bg-emerald-950/90">
      {/* Transcript Header */}
      <div className="mb-3 flex items-center justify-between border-b border-emerald-200/60 pb-3 dark:border-emerald-800/60">
        <div className="flex items-center gap-2">
          <span className="text-xl">💬</span>
          <h3 className="text-sm font-bold text-emerald-950 md:text-base dark:text-emerald-100">
            लाइव बातचीत व लिखित उत्तर (Live Transcript)
          </h3>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-900/80 dark:text-emerald-200">
          <span className="size-2 animate-pulse rounded-full bg-emerald-500" />
          लाइव सक्रिय (Active)
        </span>
      </div>

      {/* Quick Prompts */}
      <div className="mb-3 flex flex-wrap gap-2">
        {quickPrompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => handleSend(prompt)}
            disabled={isSending}
            className="cursor-pointer rounded-xl border border-emerald-200/80 bg-emerald-50/90 px-3 py-1.5 text-xs font-semibold text-emerald-900 transition hover:bg-emerald-200 hover:shadow-xs disabled:opacity-50 dark:border-emerald-700/60 dark:bg-emerald-900/50 dark:text-emerald-200 dark:hover:bg-emerald-800"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Messages / Transcript Scroll Area */}
      <div className="scrollbar-thin flex max-h-80 min-h-40 w-full flex-col space-y-3 overflow-y-auto rounded-2xl bg-emerald-50/50 p-3.5 dark:bg-[#021810]/60">
        {allMessages.length === 0 ? (
          <div className="flex grow flex-col items-center justify-center py-6 text-center text-xs font-medium text-emerald-800/70 dark:text-emerald-300/70">
            <span className="mb-1.5 text-2xl">🌾</span>
            <p>आप बोलकर या नीचे लिखकर कोई भी सवाल पूछ सकते हैं।</p>
            <p className="mt-1 text-[11px] text-emerald-700/60 dark:text-emerald-400/60">
              उदा. &quot;टमाटर के रोग का उपाय&quot; या &quot;आज मंडी का भाव&quot;
            </p>
          </div>
        ) : (
          allMessages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                'flex w-full flex-col rounded-2xl border p-4 shadow-sm',
                msg.isFarmer
                  ? 'border-emerald-200 bg-emerald-100/60 dark:border-emerald-800 dark:bg-emerald-900/50'
                  : 'border-lime-200 bg-white dark:border-emerald-700 dark:bg-emerald-950'
              )}
            >
              <div className="mb-1.5 flex items-center gap-2 text-xs font-bold">
                {msg.isFarmer ? (
                  <span className="text-emerald-800 dark:text-emerald-300">🗣️ आपका सवाल :</span>
                ) : (
                  <span className="text-lime-700 dark:text-lime-400">✅ किसानमित्र का जवाब :</span>
                )}
              </div>
              <p
                className={cn(
                  'text-sm leading-relaxed whitespace-pre-wrap',
                  msg.isFarmer
                    ? 'font-medium text-emerald-950 dark:text-emerald-100'
                    : 'text-emerald-900 dark:text-emerald-50'
                )}
              >
                {msg.text}
              </p>
            </div>
          ))
        )}

        {/* Live Thinking / Typing indicator */}
        {(agentState === 'thinking' || isSending) && (
          <div className="mt-2 flex justify-start">
            <div className="flex items-center gap-2 rounded-2xl border border-emerald-300/80 bg-white px-4 py-2 text-xs font-semibold text-emerald-900 shadow-xs dark:border-emerald-700 dark:bg-emerald-900 dark:text-emerald-100">
              <span className="size-2 animate-ping rounded-full bg-emerald-500" />
              <span>🌱 किसानमित्र उत्तर तैयार कर रहा है...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Inline Text Chat Input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="mt-3 flex w-full items-center gap-2"
      >
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="अपना सवाल यहाँ टाइप करें..."
          disabled={isSending}
          className="flex-1 rounded-2xl border border-emerald-300/80 bg-white px-4 py-2.5 text-xs font-medium text-emerald-950 placeholder-emerald-800/50 shadow-xs transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-400/40 focus:outline-none md:text-sm dark:border-emerald-700/80 dark:bg-emerald-900/60 dark:text-emerald-100 dark:placeholder-emerald-400/50"
        />
        <button
          type="submit"
          disabled={isSending || !inputText.trim()}
          className="cursor-pointer rounded-2xl bg-gradient-to-r from-emerald-600 to-yellow-500 px-5 py-2.5 text-xs font-bold text-white shadow-md transition hover:from-emerald-700 hover:to-yellow-600 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
        >
          {isSending ? 'भेज रहे हैं...' : 'भेजें 🚀'}
        </button>
      </form>
    </div>
  );
}

// ==========================================
// Navbar Component
// ==========================================
function Navbar() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-emerald-200/60 bg-white/50 backdrop-blur-md transition-colors dark:border-emerald-900/50 dark:bg-[#021810]/70">
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Left: Wheat Icon + Title + Subtitle */}
        <div className="flex items-center gap-3.5">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-emerald-500 via-green-500 to-lime-400 text-2xl text-white shadow-md shadow-emerald-500/20 select-none">
            🌾
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-black tracking-tight text-emerald-950 sm:text-2xl dark:text-emerald-50">
                KisanMitra AI
              </h1>
              <span className="hidden rounded-md border border-emerald-300 bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-800 sm:inline-block dark:border-emerald-700 dark:bg-emerald-900/80 dark:text-emerald-300">
                कृषि मित्र
              </span>
            </div>
            <p className="text-xs font-semibold tracking-wide text-emerald-700 dark:text-emerald-400">
              Developed by Rishabh Kumar
            </p>
          </div>
        </div>

        {/* Right: Badge "Murf | LiveKit" + ThemeToggle */}
        <div className="flex items-center gap-3 sm:gap-4">
          <div className="flex items-center gap-1.5 rounded-full border border-emerald-300/80 bg-emerald-100/90 px-3.5 py-1.5 text-xs font-bold text-emerald-900 shadow-xs dark:border-emerald-700/60 dark:bg-emerald-950/80 dark:text-emerald-300">
            <span className="size-2 animate-pulse rounded-full bg-emerald-500"></span>
            <span>Murf</span>
            <span className="text-emerald-400 dark:text-emerald-600">|</span>
            <span>LiveKit</span>
          </div>

          <ThemeToggleWidget />
        </div>
      </div>
    </header>
  );
}

// ==========================================
// Hero Section
// ==========================================
function HeroSection() {
  return (
    <section className="mx-auto flex max-w-4xl flex-col items-center px-4 pt-8 pb-4 text-center">
      {/* Small Badge */}
      <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-300/90 bg-emerald-100/95 px-4 py-1.5 text-xs font-bold text-emerald-900 shadow-xs backdrop-blur-sm sm:mb-6 sm:text-sm dark:border-emerald-700 dark:bg-emerald-900/70 dark:text-emerald-200">
        <span>✨</span>
        <span>✨ भारत का सबसे एडवांस स्मार्ट कृषि सहायक</span>
      </div>

      {/* Massive Gradient Heading */}
      <h2 className="mb-4 bg-gradient-to-r from-emerald-700 via-green-600 to-lime-600 bg-clip-text pb-1 text-5xl font-black tracking-tight text-transparent drop-shadow-xs sm:text-6xl md:text-7xl lg:text-8xl dark:from-emerald-400 dark:via-lime-300 dark:to-yellow-400">
        KisanMitra AI
      </h2>

      {/* Short Hindi Description */}
      <p className="max-w-2xl text-base leading-relaxed font-medium text-emerald-900/90 sm:text-lg md:text-xl dark:text-emerald-200/90">
        भारतीय किसानों के लिए समर्पित एआई आवाज़ सहायक — मौसम का हाल, मंडी भाव, फसल सलाह, कीट
        नियंत्रण और सरकारी योजनाओं की सटीक जानकारी अपनी भाषा में तुरंत बातचीत करके पाएं।
      </p>
    </section>
  );
}

// ==========================================
// Bottom Grid: 6 Glassmorphism Cards
// ==========================================
function BottomGrid() {
  return (
    <section className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h3 className="flex items-center gap-2 text-lg font-bold text-emerald-950 sm:text-xl dark:text-emerald-100">
            <span>🌾</span> प्रमुख कृषि सेवाएँ एवं मॉड्यूल
          </h3>
          <p className="text-xs text-emerald-700 sm:text-sm dark:text-emerald-400">
            किसी भी विषय पर पूछने के लिए माइक बटन दबाकर सीधे बातचीत करें
          </p>
        </div>
        <span className="hidden rounded-full border border-emerald-300 bg-emerald-100 px-3.5 py-1 text-xs font-bold text-emerald-800 sm:inline-flex dark:border-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300">
          6 स्मार्ट मॉड्यूल
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3">
        {AGRICULTURAL_MODULES.map((module) => (
          <div
            key={module.id}
            className="group relative overflow-hidden rounded-2xl border border-emerald-200/80 bg-white/70 p-5 shadow-md backdrop-blur-md transition-all duration-300 hover:-translate-y-1 hover:border-emerald-400 hover:shadow-2xl sm:p-6 dark:border-emerald-800/50 dark:bg-emerald-950/40 dark:hover:border-emerald-500/70"
          >
            {/* Top Glow bar on hover */}
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-400 via-lime-400 to-yellow-400 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

            <div className="mb-3.5 flex items-start justify-between">
              <div className="flex items-center gap-3">
                <span className="text-3xl drop-shadow-xs select-none">{module.emoji}</span>
                <div>
                  <h4 className="text-base leading-tight font-bold text-emerald-950 sm:text-lg dark:text-emerald-50">
                    {module.titleHindi}
                  </h4>
                  <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                    {module.titleEnglish}
                  </span>
                </div>
              </div>
              <span className="rounded-full border border-emerald-300/70 bg-emerald-100/90 px-2.5 py-1 text-[10px] font-bold tracking-wider text-emerald-800 uppercase dark:border-emerald-700/60 dark:bg-emerald-900/70 dark:text-emerald-300">
                {module.tag}
              </span>
            </div>

            <p className="mb-4 text-xs leading-relaxed text-emerald-900/80 sm:text-sm dark:text-emerald-200/80">
              {module.description}
            </p>

            <div className="flex items-center justify-between border-t border-emerald-200/60 pt-3 text-[11px] font-medium text-emerald-700 dark:border-emerald-900/50 dark:text-emerald-400">
              <span className="truncate italic">&ldquo;{module.samplePrompt}&rdquo;</span>
              <span className="ml-1 shrink-0 font-bold text-emerald-600 dark:text-emerald-400">
                बोलें →
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ==========================================
// Inner Session View Component (Keyed by farmerUserId)
// ==========================================
function KisanMitraSessionView({
  farmerUserId,
  appConfig,
  micError,
  onRetryMic,
}: {
  farmerUserId: string;
  appConfig?: AppConfig;
  micError: boolean;
  onRetryMic: () => void;
}) {
  // Use custom TokenSource to guarantee userId is transmitted in POST body
  const tokenSource = useMemo(() => {
    return typeof process.env.NEXT_PUBLIC_CONN_DETAILS_ENDPOINT === 'string' && appConfig
      ? getSandboxTokenSource(appConfig)
      : TokenSource.custom(async () => {
          const res = await fetch('/api/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userId: farmerUserId }),
          });
          if (!res.ok) {
            throw new Error(`Token request failed: ${res.status}`);
          }
          return await res.json();
        });
  }, [appConfig, farmerUserId]);

  const sessionOptions = useMemo(() => {
    return appConfig?.agentName ? { agentName: appConfig.agentName } : undefined;
  }, [appConfig?.agentName]);

  const session = useSession(tokenSource, sessionOptions);

  return (
    <AgentSessionProvider session={session}>
      {/* 2. Central Voice Agent Controller (5 States & Error Banner) */}
      <VoiceAgentController micError={micError} onRetryMic={onRetryMic} />

      {/* Requirement 4: Critical Technical Fallback for Audio Autoplay */}
      <div className="fixed right-4 bottom-4 z-50">
        <StartAudioButton label="Start Audio" />
      </div>
    </AgentSessionProvider>
  );
}

// ==========================================
// Main KisanMitraAI Component
// ==========================================
interface KisanMitraAIProps {
  appConfig?: AppConfig;
}

export function KisanMitraAI({ appConfig }: KisanMitraAIProps) {
  const [micError, setMicError] = useState<boolean>(false);
  const [farmerUserId, setFarmerUserId] = useState<string>('user_123');

  // Requirement 3: Microphone Permission check on component mount
  const checkMicrophonePermission = useCallback(async () => {
    if (typeof window === 'undefined' || !navigator?.mediaDevices?.getUserMedia) {
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setMicError(false);
      // Immediately stop temporary tracks so the hardware is released
      stream.getTracks().forEach((track) => track.stop());
    } catch (err: unknown) {
      const errorObj = err as { name?: string; message?: string };
      const errorName = errorObj?.name || '';
      const errorMessage = errorObj?.message || '';

      if (
        errorName === 'NotAllowedError' ||
        errorName === 'PermissionDeniedError' ||
        errorMessage.toLowerCase().includes('denied') ||
        errorMessage.toLowerCase().includes('not allowed')
      ) {
        setMicError(true);
        toast.error(
          '⚠️ माइक की अनुमति (Microphone Permission) बंद है। कृपया अपने ब्राउज़र में माइक की अनुमति चालू करें।',
          {
            id: 'mic-permission-error',
            duration: 8000,
          }
        );
      }
    }
  }, []);

  useEffect(() => {
    checkMicrophonePermission();
  }, [checkMicrophonePermission]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('kisan_mitra_user_id');
      if (saved) {
        setFarmerUserId(saved);
      } else {
        setFarmerUserId('user_123');
        localStorage.setItem('kisan_mitra_user_id', 'user_123');
      }
    }
  }, []);

  const handleSwitchToNewFarmer = useCallback(() => {
    const newId = `user_${Math.floor(200 + Math.random() * 800)}`;
    setFarmerUserId(newId);
    if (typeof window !== 'undefined') {
      localStorage.setItem('kisan_mitra_user_id', newId);
    }
    toast.success(
      `✅ नया किसान प्रोफ़ाइल सक्रिय (${newId})! अब नए किसान अपनी जानकारी दर्ज कर सकते हैं।`
    );
  }, []);

  return (
    <div className="text-foreground relative flex min-h-screen w-full flex-col justify-between overflow-x-hidden bg-gradient-to-b from-lime-50 via-emerald-50 to-lime-100 transition-colors duration-500 selection:bg-emerald-300 selection:text-emerald-950 dark:from-[#021810] dark:via-[#04261a] dark:to-[#021810]">
      {/* Subtle Ambient Glow Orbs */}
      <div className="pointer-events-none absolute top-10 left-1/4 -z-10 size-96 -translate-x-1/2 rounded-full bg-emerald-400/15 blur-3xl dark:bg-emerald-500/10" />
      <div className="pointer-events-none absolute top-1/3 right-1/4 -z-10 size-96 translate-x-1/2 rounded-full bg-lime-400/15 blur-3xl dark:bg-lime-500/10" />

      {/* 1. Navbar */}
      <Navbar />

      {/* Main Content Area */}
      <main className="flex grow flex-col items-center justify-between pb-12">
        {/* 1. Hero Section */}
        <HeroSection />

        {/* Dynamic Caller ID & New Profile Bar */}
        <div className="mb-4 flex flex-wrap items-center justify-center gap-3">
          <div className="flex items-center gap-2 rounded-full border border-emerald-400/80 bg-emerald-950/80 px-4 py-1.5 text-xs font-bold text-emerald-200 shadow-md backdrop-blur-md">
            <span className="inline-block size-2 animate-pulse rounded-full bg-emerald-400" />
            <span>वर्तमान कॉलर आईडी:</span>
            <span className="font-mono text-emerald-300 underline underline-offset-2">
              {farmerUserId}
            </span>
          </div>

          <button
            type="button"
            onClick={handleSwitchToNewFarmer}
            title="दूसरे किसान के लिए नई कॉलर आईडी शुरू करें"
            className="group flex cursor-pointer items-center gap-1.5 rounded-full border border-amber-400 bg-gradient-to-r from-amber-500 to-yellow-600 px-4 py-1.5 text-xs font-bold text-white shadow-md transition-all duration-200 hover:scale-105 hover:from-amber-600 hover:to-yellow-700 active:scale-95"
          >
            <span>➕ दूसरा किसान (New Profile)</span>
          </button>
        </div>

        {/* 2. Central Voice Agent Controller with dynamic Key to guarantee new session */}
        <KisanMitraSessionView
          key={farmerUserId}
          farmerUserId={farmerUserId}
          appConfig={appConfig}
          micError={micError}
          onRetryMic={checkMicrophonePermission}
        />

        {/* 1. Bottom Grid (6 Glassmorphism Cards) */}
        <BottomGrid />
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-emerald-200/60 bg-white/40 py-4 text-center text-xs font-semibold text-emerald-800/80 backdrop-blur-md dark:border-emerald-900/40 dark:bg-[#021810]/60 dark:text-emerald-400/80">
        <p>© 2026 KisanMitra AI — Powered by Murf Falcon & LiveKit Agents</p>
      </footer>

      {/* Toast Notifications */}
      <Toaster position="top-center" richColors />
    </div>
  );
}

export default KisanMitraAI;

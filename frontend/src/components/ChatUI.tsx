"use client";

import { Settings, X, Mic, MicOff, WifiOff } from "lucide-react";
import { useAudioSocket } from "@/lib/useAudioSocket";

export default function ChatUI() {
  const { messages, isRecording, isConnected, toggleRecording } = useAudioSocket(
    // You can point this to the backend URL via env var for Vercel
    process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws"
  );

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto bg-[#faf6f3]">
      {/* Header */}
      <header className="flex items-center justify-between p-4 border-b border-[#ebd7cd] bg-[#fbf5f2]">
        <div>
          <h2 className="text-[#D35400] text-sm font-bold tracking-widest uppercase mb-1">
            Sauti
          </h2>
          <h1 className="text-xl font-serif text-gray-800 flex items-center gap-2">
            Ongea na Sauti
            {!isConnected && <WifiOff className="w-4 h-4 text-red-500" aria-label="Disconnected" />}
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Sauti yako → maandishi → majibu → sauti
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-1.5 text-sm font-medium text-[#D35400] bg-orange-50 rounded-full border border-orange-200 hover:bg-orange-100 transition-colors">
          <X className="w-4 h-4" />
          Maliza
        </button>
      </header>

      {/* Chat History */}
      <main className="flex-1 overflow-y-auto p-4 space-y-6">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            <p>Anza kuongea ili kuzungumza na Sauti.</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.role === "user" ? "items-end" : "items-start"
              }`}
            >
              <div
                className={`max-w-[85%] p-4 rounded-3xl ${
                  msg.role === "user"
                    ? "bg-[#1c1a17] text-white rounded-tr-sm"
                    : "bg-white text-gray-800 rounded-tl-sm border border-[#ebd7cd] shadow-sm"
                }`}
              >
                <p className="text-[15px] leading-relaxed">{msg.text}</p>

                <div className={`mt-3 flex items-center gap-2 ${msg.role === 'user' ? 'justify-start opacity-70' : 'justify-end text-orange-600 opacity-60'}`}>
                   <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-volume-2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
                </div>
              </div>
            </div>
          ))
        )}
      </main>

      {/* Settings FAB */}
      <div className="absolute right-4 bottom-32 hidden md:block">
        <button className="p-3 bg-[#2a2825] text-white rounded-full shadow-lg hover:bg-gray-800 transition-colors">
          <Settings className="w-5 h-5" />
        </button>
      </div>

      {/* Footer / Controls */}
      <footer className="p-6 bg-gradient-to-t from-[#fbf5f2] to-transparent pt-12 flex flex-col items-center justify-center relative">

        {/* Pulse Indicator */}
        <div className="relative flex items-center justify-center w-24 h-24 mb-4">
           {isRecording && (
              <div className="absolute inset-0 bg-[#D35400] opacity-20 rounded-full animate-ping"></div>
           )}
           <div className={`w-12 h-12 rounded-full ${isRecording ? 'bg-[#D35400]' : 'bg-[#D35400]'} shadow-lg transition-transform ${isRecording ? 'scale-110' : ''}`}></div>
        </div>

        <p className="text-[#a48472] text-xs font-semibold tracking-widest uppercase mb-2">
          {isRecording ? "INASIKILIZA..." : "TAYARI"}
        </p>
        <p className="text-gray-500 text-sm mb-6">
          Gusa maikrofoni kwa zamu inayofuata.
        </p>

        <button
          onClick={toggleRecording}
          disabled={!isConnected}
          className={`p-5 rounded-full shadow-xl transition-all duration-300 ${
            !isConnected ? "bg-gray-400 cursor-not-allowed text-gray-200" :
            isRecording ? "bg-red-500 text-white hover:bg-red-600" : "bg-[#1c1a17] text-white hover:bg-black"
          }`}
        >
          {isRecording ? <MicOff className="w-7 h-7" /> : <Mic className="w-7 h-7" />}
        </button>

        <p className="text-gray-400 text-xs mt-6">
          Bonyeza maikrofoni, sema, kisha nyamaza
        </p>
      </footer>
    </div>
  );
}

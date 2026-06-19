"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

export function useAudioSocket(url: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [streamingText, setStreamingText] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  const audioQueueRef = useRef<Float32Array[]>([]);
  const isPlayingRef = useRef(false);
  const nextStartTimeRef = useRef(0);
  const streamingTextRef = useRef("");
  const animFrameRef = useRef<number | null>(null);

  const stopPlayback = useCallback(() => {
    audioQueueRef.current = [];
    nextStartTimeRef.current = 0;
    isPlayingRef.current = false;
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setIsSpeaking(false);
  }, []);

  const processAudioQueue = useCallback(() => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;
    if (!audioContextRef.current) return;

    const ctx = audioContextRef.current;
    isPlayingRef.current = true;
    setIsSpeaking(true);

    const float32Array = audioQueueRef.current.shift()!;
    const audioBuffer = ctx.createBuffer(1, float32Array.length, 48000);
    audioBuffer.getChannelData(0).set(float32Array as any);

    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);

    const startTime = Math.max(ctx.currentTime, nextStartTimeRef.current);
    source.start(startTime);
    nextStartTimeRef.current = startTime + audioBuffer.duration;

    source.onended = () => {
      isPlayingRef.current = false;
      if (audioQueueRef.current.length > 0) {
        processAudioQueue();
      } else {
        setIsSpeaking(false);
      }
    };
  }, []);

  const playAudioChunk = useCallback(
    async (blob: Blob) => {
      if (
        !audioContextRef.current ||
        audioContextRef.current.state === "closed"
      ) {
        audioContextRef.current = new (window.AudioContext ||
          (window as any).webkitAudioContext)();
      }
      if (audioContextRef.current.state === "suspended") {
        audioContextRef.current.resume();
      }

      try {
        const arrayBuffer = await blob.arrayBuffer();
        const int16Array = new Int16Array(arrayBuffer);
        const float32Array = new Float32Array(int16Array.length);
        for (let i = 0; i < int16Array.length; i++) {
          float32Array[i] = int16Array[i] / 32768.0;
        }
        audioQueueRef.current.push(float32Array);
        processAudioQueue();
      } catch (e) {
        console.error("Error playing audio chunk:", e);
      }
    },
    [processAudioQueue]
  );

  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connectWs = () => {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onclose = () => {
        setIsConnected(false);
        reconnectTimer = setTimeout(connectWs, 3000);
      };

      ws.onmessage = async (event) => {
        if (event.data instanceof Blob) {
          playAudioChunk(event.data);
          return;
        }

        if (typeof event.data === "string") {
          try {
            const data = JSON.parse(event.data);

            if (data.type === "transcript") {
              setMessages((prev) => [
                ...prev,
                { id: `user-${Date.now()}`, role: "user", text: data.text },
              ]);
              setIsThinking(true);
              streamingTextRef.current = "";
              setStreamingText("");
            } else if (data.type === "text_delta") {
              streamingTextRef.current += data.text;
              if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
              animFrameRef.current = requestAnimationFrame(() => {
                setStreamingText(streamingTextRef.current);
              });
              setIsThinking(false);
            } else if (data.type === "llm_response") {
              const finalText = data.text || streamingTextRef.current;
              setMessages((prev) => [
                ...prev,
                {
                  id: `assistant-${Date.now()}`,
                  role: "assistant",
                  text: finalText,
                },
              ]);
              streamingTextRef.current = "";
              setStreamingText("");
              setIsThinking(false);
            } else if (data.type === "turn_complete") {
              // Turn finished
            } else if (data.type === "error") {
              console.error("Server error:", data.detail);
              setIsThinking(false);
            }
          } catch {
            // ignore parse errors
          }
        }
      };

      wsRef.current = ws;
    };

    connectWs();

    return () => {
      clearTimeout(reconnectTimer);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [url, playAudioChunk]);

  const startRecording = useCallback(async () => {
    // Barge-in: stop any current playback
    stopPlayback();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm",
      });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(e.data);
        }
      };

      audioQueueRef.current = [];
      nextStartTimeRef.current = 0;
      isPlayingRef.current = false;

      mediaRecorder.start(250);
      setIsRecording(true);
    } catch (err) {
      console.error("Error accessing microphone:", err);
    }
  }, [stopPlayback]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
      setIsRecording(false);

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "end_turn" }));
      }
    }
  }, [isRecording]);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  const sendText = useCallback(
    (text: string) => {
      if (!text.trim()) return;

      stopPlayback();

      setMessages((prev) => [
        ...prev,
        { id: `user-${Date.now()}`, role: "user", text: text.trim() },
      ]);
      setIsThinking(true);
      streamingTextRef.current = "";
      setStreamingText("");

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({ type: "text_input", text: text.trim() })
        );
      }
    },
    [stopPlayback]
  );

  return {
    messages,
    isRecording,
    isConnected,
    isThinking,
    isSpeaking,
    streamingText,
    toggleRecording,
    stopPlayback,
    sendText,
    setMessages,
  };
}

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

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  // Buffer and timing for audio playback
  const audioQueueRef = useRef<Float32Array[]>([]);
  const isPlayingRef = useRef(false);
  const nextStartTimeRef = useRef(0);

  // Use useCallback for playAudioChunk to fix the missing dependency warning
  const processAudioQueue = useCallback(() => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;

    if (!audioContextRef.current) return;
    const ctx = audioContextRef.current;
    isPlayingRef.current = true;

    const float32Array = audioQueueRef.current.shift()!;
    const audioBuffer = ctx.createBuffer(1, float32Array.length, 48000); // Backend uses 48kHz

    // Copy the data
    audioBuffer.getChannelData(0).set(float32Array as any);

    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);

    const currentTime = ctx.currentTime;
    // ensure gapless playback
    const startTime = Math.max(currentTime, nextStartTimeRef.current);
    source.start(startTime);

    nextStartTimeRef.current = startTime + audioBuffer.duration;

    source.onended = () => {
      isPlayingRef.current = false;
      processAudioQueue();
    };
  }, []);

  const playAudioChunk = useCallback(async (blob: Blob) => {
    if (!audioContextRef.current || audioContextRef.current.state === "closed") {
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    if (audioContextRef.current.state === "suspended") {
      audioContextRef.current.resume();
    }

    try {
      const arrayBuffer = await blob.arrayBuffer();
      // Convert int16 PCM to Float32
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
  }, [processAudioQueue]);


  useEffect(() => {
    const connectWs = () => {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log("WebSocket connected");
        setIsConnected(true);
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected");
        setIsConnected(false);
        setTimeout(connectWs, 3000); // Reconnect logic
      };

      ws.onmessage = async (event) => {
        if (event.data instanceof Blob) {
          playAudioChunk(event.data);
        } else if (typeof event.data === "string") {
          try {
            const data = JSON.parse(event.data);
            console.log("Received JSON:", data);

            if (data.type === "turn_complete") {
              console.log("Turn completed");
            } else if (data.type === "error") {
              console.error("Error from backend:", data.detail);
            } else if (data.type === "transcript" || data.type === "llm_response") {
              setMessages(prev => [...prev, {
                id: Date.now().toString(),
                role: data.role,
                text: data.text
              }]);
            }
          } catch (e) {
            console.warn("Could not parse JSON:", event.data);
          }
        }
      };

      wsRef.current = ws;
    };

    connectWs();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [url, playAudioChunk]);


  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(e.data);
        }
      };

      // Stop previous playback when starting new recording
      audioQueueRef.current = [];
      nextStartTimeRef.current = 0;
      isPlayingRef.current = false;

      // Send smaller chunks
      mediaRecorder.start(250);
      setIsRecording(true);
    } catch (err) {
      console.error("Error accessing microphone:", err);
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      setIsRecording(false);

      // Tell backend the turn is over
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

  return {
    messages,
    setMessages,
    isRecording,
    isConnected,
    toggleRecording,
  };
}

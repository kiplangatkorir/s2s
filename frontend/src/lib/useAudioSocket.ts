"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

// Resample float32 audio from one rate to another (simple linear interpolation)
function resampleFloat32(
  buffer: Float32Array,
  fromRate: number,
  toRate: number
): Float32Array {
  if (fromRate === toRate) return buffer;
  const ratio = fromRate / toRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  for (let i = 0; i < newLength; i++) {
    const srcIndex = i * ratio;
    const srcFloor = Math.floor(srcIndex);
    const srcCeil = Math.min(srcFloor + 1, buffer.length - 1);
    const frac = srcIndex - srcFloor;
    result[i] = buffer[srcFloor] * (1 - frac) + buffer[srcCeil] * frac;
  }
  return result;
}

// Convert Float32 [-1, 1] to Int16 PCM bytes
function float32ToInt16Bytes(float32: Float32Array): ArrayBuffer {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16.buffer;
}

export function useAudioSocket(url: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [streamingText, setStreamingText] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const pcmBufferRef = useRef<Float32Array[]>([]);

  const audioPlaybackContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<Float32Array[]>([]);
  const isPlayingRef = useRef(false);
  const nextStartTimeRef = useRef(0);
  const streamingTextRef = useRef("");
  const animFrameRef = useRef<number | null>(null);

  const stopPlayback = useCallback(() => {
    audioQueueRef.current = [];
    nextStartTimeRef.current = 0;
    isPlayingRef.current = false;
    if (
      audioPlaybackContextRef.current &&
      audioPlaybackContextRef.current.state !== "closed"
    ) {
      audioPlaybackContextRef.current.close();
      audioPlaybackContextRef.current = null;
    }
    setIsSpeaking(false);
  }, []);

  const processAudioQueue = useCallback(() => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;
    if (!audioPlaybackContextRef.current) return;

    const ctx = audioPlaybackContextRef.current;
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
        !audioPlaybackContextRef.current ||
        audioPlaybackContextRef.current.state === "closed"
      ) {
        audioPlaybackContextRef.current = new (window.AudioContext ||
          (window as any).webkitAudioContext)();
      }
      if (audioPlaybackContextRef.current.state === "suspended") {
        audioPlaybackContextRef.current.resume();
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
              if (animFrameRef.current)
                cancelAnimationFrame(animFrameRef.current);
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
    stopPlayback();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      micStreamRef.current = stream;

      // Create an AudioContext to capture raw PCM from the mic
      const audioCtx = new AudioContext();
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      sourceNodeRef.current = source;

      // ScriptProcessorNode captures raw PCM frames
      const bufferSize = 4096;
      const scriptNode = audioCtx.createScriptProcessor(bufferSize, 1, 1);
      scriptNodeRef.current = scriptNode;

      const nativeSampleRate = audioCtx.sampleRate; // usually 44100 or 48000
      const TARGET_RATE = 16000;

      scriptNode.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        // Copy the data (Float32Array is reused by the browser)
        const copy = new Float32Array(inputData);
        pcmBufferRef.current.push(copy);

        // Send PCM chunk immediately for low-latency streaming
        // Resample to 16kHz and convert to int16
        const resampled = resampleFloat32(copy, nativeSampleRate, TARGET_RATE);
        const pcmBytes = float32ToInt16Bytes(resampled);

        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(pcmBytes);
        }
      };

      source.connect(scriptNode);
      scriptNode.connect(audioCtx.destination);

      // Clear playback state
      audioQueueRef.current = [];
      nextStartTimeRef.current = 0;
      isPlayingRef.current = false;

      setIsRecording(true);
    } catch (err) {
      console.error("Error accessing microphone:", err);
    }
  }, [stopPlayback]);

  const stopRecording = useCallback(() => {
    if (!isRecording) return;

    // Disconnect the audio graph
    if (scriptNodeRef.current) {
      scriptNodeRef.current.disconnect();
      scriptNodeRef.current = null;
    }
    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    pcmBufferRef.current = [];
    setIsRecording(false);

    // Tell backend the turn is over
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "end_turn" }));
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

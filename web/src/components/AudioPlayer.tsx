"use client";

import { useState, useRef } from "react";

interface AudioPlayerProps {
  slug: string;
  region: string;
}

export function AudioPlayer({ slug, region }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState<"normal" | "slow">("normal");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const audioBase = process.env.NEXT_PUBLIC_AUDIO_BASE_URL || "/audio";
  const audioSrc = `${audioBase}/${region.toLowerCase()}/${slug}_${speed}.mp3`;

  const play = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }

    const audio = new Audio(audioSrc);
    audioRef.current = audio;

    audio.addEventListener("play", () => setIsPlaying(true));
    audio.addEventListener("ended", () => setIsPlaying(false));
    audio.addEventListener("error", () => setIsPlaying(false));

    audio.play().catch(() => setIsPlaying(false));
  };

  return (
    <div className="flex items-center gap-3">
      {/* Play button */}
      <button
        onClick={play}
        className="flex items-center justify-center w-14 h-14 rounded-full bg-brand-500 text-white
                   hover:bg-brand-600 active:scale-95 transition-all shadow-lg shadow-brand-200"
        aria-label="Play pronunciation"
      >
        {isPlaying ? (
          <svg className="w-6 h-6 animate-pulse" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="4" width="4" height="16" rx="1" />
            <rect x="14" y="4" width="4" height="16" rx="1" />
          </svg>
        ) : (
          <svg className="w-6 h-6 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
        )}
      </button>

      {/* Speed toggle */}
      <div className="flex rounded-full bg-gray-100 p-0.5">
        <button
          onClick={() => setSpeed("normal")}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
            speed === "normal"
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          1x
        </button>
        <button
          onClick={() => setSpeed("slow")}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
            speed === "slow"
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Slow
        </button>
      </div>
    </div>
  );
}

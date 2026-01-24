'use client';

import { useRef, useEffect, forwardRef, useImperativeHandle } from 'react';

interface AudioPlayerProps {
  src: string;
  onTimeUpdate?: (currentTime: number, duration: number) => void;
  onLoadedMetadata?: (duration: number) => void;
}

export interface AudioPlayerRef {
  seek: (time: number) => void;
  getCurrentTime: () => number;
  getDuration: () => number;
}

export const AudioPlayer = forwardRef<AudioPlayerRef, AudioPlayerProps>(
  function AudioPlayer({ src, onTimeUpdate, onLoadedMetadata }, ref) {
    const audioRef = useRef<HTMLAudioElement>(null);

    useImperativeHandle(ref, () => ({
      seek: (time: number) => {
        if (audioRef.current) {
          audioRef.current.currentTime = time;
        }
      },
      getCurrentTime: () => audioRef.current?.currentTime ?? 0,
      getDuration: () => audioRef.current?.duration ?? 0,
    }));

    useEffect(() => {
      const audio = audioRef.current;
      if (!audio) return;

      const handleTimeUpdate = () => {
        onTimeUpdate?.(audio.currentTime, audio.duration);
      };

      const handleLoadedMetadata = () => {
        onLoadedMetadata?.(audio.duration);
      };

      audio.addEventListener('timeupdate', handleTimeUpdate);
      audio.addEventListener('loadedmetadata', handleLoadedMetadata);

      return () => {
        audio.removeEventListener('timeupdate', handleTimeUpdate);
        audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      };
    }, [onTimeUpdate, onLoadedMetadata]);

    return (
      <audio
        ref={audioRef}
        src={src}
        controls
        className="w-full"
        preload="metadata"
      />
    );
  }
);

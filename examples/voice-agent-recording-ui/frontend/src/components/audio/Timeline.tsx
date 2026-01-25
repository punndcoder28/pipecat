'use client';

import { useState, useRef } from 'react';
import { TurnLatency, FreezeEvent } from '@/types/session';

interface TimelineProps {
  duration: number; // Total duration in seconds
  currentTime: number; // Current playback time in seconds
  turnLatencies: TurnLatency[];
  freezeEvents: FreezeEvent[];
  sessionStartTime: string; // ISO timestamp
  onSeek: (time: number) => void;
}

interface TooltipState {
  visible: boolean;
  x: number;
  content: string;
}

function getLatencyColor(latencyMs: number): string {
  // Color scale: green (fast) -> yellow -> orange -> red (slow)
  if (latencyMs < 500) return 'bg-green-400';
  if (latencyMs < 1000) return 'bg-yellow-400';
  if (latencyMs < 2000) return 'bg-orange-400';
  return 'bg-red-400';
}

function getLatencyHeight(latencyMs: number, maxLatency: number): number {
  // Height as percentage of max height (80%)
  const normalized = Math.min(latencyMs / maxLatency, 1);
  return 20 + normalized * 60; // 20% to 80% height
}

function formatLatency(ms: number): string {
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }
  return `${(ms / 1000).toFixed(2)}s`;
}

export function Timeline({
  duration,
  currentTime,
  turnLatencies,
  freezeEvents,
  sessionStartTime,
  onSeek,
}: TimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    content: '',
  });

  const sessionStart = new Date(sessionStartTime).getTime();
  const durationMs = duration * 1000;

  // Find max latency for scaling
  const maxLatency = Math.max(...turnLatencies.map((t) => t.latency_ms), 1000);

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    const seekTime = percentage * duration;
    onSeek(Math.max(0, Math.min(seekTime, duration)));
  };

  const handleMouseEnter = (e: React.MouseEvent, content: string) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();
    if (containerRect) {
      // Calculate x position relative to container
      let x = rect.left - containerRect.left + rect.width / 2;

      // Clamp x position to keep tooltip within bounds (with some padding)
      const tooltipWidth = 150; // Approximate max tooltip width
      const minX = tooltipWidth / 2 + 8;
      const maxX = containerRect.width - tooltipWidth / 2 - 8;
      x = Math.max(minX, Math.min(x, maxX));

      setTooltip({
        visible: true,
        x,
        content,
      });
    }
  };

  const handleMouseLeave = () => {
    setTooltip((prev) => ({ ...prev, visible: false }));
  };

  // Calculate position for each latency marker based on created_at time
  const getLatencyPosition = (latency: TurnLatency): number => {
    const latencyTime = new Date(latency.created_at).getTime();
    const offsetMs = latencyTime - sessionStart;
    return Math.max(0, Math.min((offsetMs / durationMs) * 100, 100));
  };

  // Calculate position and width for freeze events
  const getFreezePosition = (freeze: FreezeEvent): { left: number; width: number } => {
    const left = (freeze.start_time_ms / durationMs) * 100;
    const width = (freeze.duration_ms / durationMs) * 100;
    return {
      left: Math.max(0, Math.min(left, 100)),
      width: Math.max(0.5, Math.min(width, 100 - left)),
    };
  };

  // Playhead position
  const playheadPosition = duration > 0 ? (currentTime / duration) * 100 : 0;

  if (duration === 0) {
    return (
      <div className="h-20 bg-gray-100 rounded-lg flex items-center justify-center">
        <p className="text-gray-500 text-sm">Loading timeline...</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative h-20 bg-gray-100 rounded-lg cursor-pointer overflow-visible"
      onClick={handleClick}
    >
      {/* Tooltip - positioned at top of container */}
      {tooltip.visible && (
        <div
          className="absolute z-20 px-2 py-1 text-xs font-medium text-white bg-gray-900 rounded shadow-lg whitespace-nowrap pointer-events-none"
          style={{
            left: `${tooltip.x}px`,
            top: '-8px',
            transform: 'translate(-50%, -100%)',
          }}
        >
          {tooltip.content}
          <div
            className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-gray-900"
          />
        </div>
      )}

      {/* Freeze events (background layer) */}
      {freezeEvents.map((freeze) => {
        const { left, width } = getFreezePosition(freeze);
        return (
          <div
            key={freeze.id}
            className="absolute top-0 bottom-0 bg-red-200 opacity-60 hover:opacity-80 transition-opacity"
            style={{ left: `${left}%`, width: `${width}%` }}
            onMouseEnter={(e) => handleMouseEnter(e, `Freeze: ${formatLatency(freeze.duration_ms)}`)}
            onMouseLeave={handleMouseLeave}
          />
        );
      })}

      {/* Latency markers */}
      {turnLatencies.map((latency) => {
        const position = getLatencyPosition(latency);
        const height = getLatencyHeight(latency.latency_ms, maxLatency);
        const color = getLatencyColor(latency.latency_ms);
        const tooltipContent = `Turn ${latency.turn_number}: ${formatLatency(latency.latency_ms)} response time${latency.was_interrupted ? ' (interrupted)' : ''}`;

        return (
          <div
            key={latency.id}
            className={`absolute bottom-0 w-2 ${color} ${latency.was_interrupted ? 'opacity-50' : ''} hover:w-3 hover:opacity-100 transition-all cursor-pointer`}
            style={{
              left: `${position}%`,
              height: `${height}%`,
              transform: 'translateX(-50%)',
            }}
            onMouseEnter={(e) => handleMouseEnter(e, tooltipContent)}
            onMouseLeave={handleMouseLeave}
          />
        );
      })}

      {/* Playhead */}
      <div
        className="absolute top-0 bottom-0 w-0.5 bg-indigo-600 z-10 pointer-events-none"
        style={{ left: `${playheadPosition}%` }}
      />

      {/* Timeline labels */}
      <div className="absolute bottom-1 left-2 text-xs text-gray-500 pointer-events-none">0:00</div>
      <div className="absolute bottom-1 right-2 text-xs text-gray-500 pointer-events-none">
        {Math.floor(duration / 60)}:{String(Math.floor(duration % 60)).padStart(2, '0')}
      </div>
    </div>
  );
}

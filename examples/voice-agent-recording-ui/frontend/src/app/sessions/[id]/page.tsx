'use client';

import { useRef, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useSession, getAudioUrl } from '@/lib/api/sessions';
import { AudioPlayer, AudioPlayerRef, Timeline } from '@/components/audio';
import { DeleteSessionButton } from '@/components/sessions';
import { SessionDetail, TurnLatency, FreezeEvent, Transcript } from '@/types/session';

function formatDuration(createdAt: string, endedAt: string | null): string {
  if (!endedAt) return 'In progress';

  const start = new Date(createdAt).getTime();
  const end = new Date(endedAt).getTime();
  const durationMs = end - start;

  const seconds = Math.floor(durationMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  if (minutes === 0) {
    return `${remainingSeconds}s`;
  }
  return `${minutes}m ${remainingSeconds}s`;
}

function formatMs(ms: number): string {
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }
  return `${(ms / 1000).toFixed(2)}s`;
}

function StatusBadge({ status }: { status: SessionDetail['status'] }) {
  const colors = {
    active: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    error: 'bg-red-100 text-red-800',
  };

  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${colors[status]}`}>
      {status}
    </span>
  );
}

interface SessionInfoCardProps {
  session: SessionDetail;
}

function SessionInfoCard({ session }: SessionInfoCardProps) {
  const avgLatency = session.turn_latencies.length > 0
    ? session.turn_latencies.reduce((sum, t) => sum + t.latency_ms, 0) / session.turn_latencies.length
    : 0;

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Session Info</h2>
      <dl className="grid grid-cols-2 gap-4">
        <div>
          <dt className="text-sm font-medium text-gray-500">Session ID</dt>
          <dd className="mt-1 text-sm text-gray-900 font-mono">{session.id}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Status</dt>
          <dd className="mt-1"><StatusBadge status={session.status} /></dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Duration</dt>
          <dd className="mt-1 text-sm text-gray-900">{formatDuration(session.created_at, session.ended_at)}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Number of Turns</dt>
          <dd className="mt-1 text-sm text-gray-900">{session.turn_latencies.length}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Average Turn Latency</dt>
          <dd className="mt-1 text-sm text-gray-900">
            {session.turn_latencies.length > 0 ? formatMs(avgLatency) : 'N/A'}
          </dd>
        </div>
      </dl>
    </div>
  );
}

interface LatencyStatsProps {
  turnLatencies: TurnLatency[];
}

function LatencyStats({ turnLatencies }: LatencyStatsProps) {
  if (turnLatencies.length === 0) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Bot Response Time</h2>
        <p className="text-gray-500">No response time data available</p>
      </div>
    );
  }

  const latencies = turnLatencies.map((t) => t.latency_ms);
  const minLatency = Math.min(...latencies);
  const maxLatency = Math.max(...latencies);
  const avgLatency = latencies.reduce((sum, l) => sum + l, 0) / latencies.length;
  const interruptedCount = turnLatencies.filter((t) => t.was_interrupted).length;

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Bot Response Time</h2>
      <p className="text-xs text-gray-500 mb-3">Time for bot to start responding after user stops speaking</p>
      <dl className="grid grid-cols-2 gap-4">
        <div>
          <dt className="text-sm font-medium text-gray-500">Fastest</dt>
          <dd className="mt-1 text-sm text-gray-900">{formatMs(minLatency)}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Average</dt>
          <dd className="mt-1 text-sm text-gray-900">{formatMs(avgLatency)}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Slowest</dt>
          <dd className="mt-1 text-sm text-gray-900">{formatMs(maxLatency)}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Interrupted Turns</dt>
          <dd className="mt-1 text-sm text-gray-900">{interruptedCount}</dd>
        </div>
      </dl>
    </div>
  );
}

interface FreezeStatsProps {
  freezeEvents: FreezeEvent[];
}

function FreezeStats({ freezeEvents }: FreezeStatsProps) {
  if (freezeEvents.length === 0) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Freeze Events</h2>
        <p className="text-green-600">No freezes detected</p>
      </div>
    );
  }

  const durations = freezeEvents.map((f) => f.duration_ms);
  const minDuration = Math.min(...durations);
  const maxDuration = Math.max(...durations);
  const avgDuration = durations.reduce((sum, d) => sum + d, 0) / durations.length;

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Freeze Events</h2>
      <dl className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <dt className="text-sm font-medium text-gray-500">Total Freezes</dt>
          <dd className="mt-1 text-sm text-red-600 font-semibold">{freezeEvents.length}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Min Duration</dt>
          <dd className="mt-1 text-sm text-gray-900">{formatMs(minDuration)}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Average Duration</dt>
          <dd className="mt-1 text-sm text-gray-900">{formatMs(avgDuration)}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">Max Duration</dt>
          <dd className="mt-1 text-sm text-gray-900">{formatMs(maxDuration)}</dd>
        </div>
      </dl>
      <div className="mt-4">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Event List</h3>
        <ul className="space-y-1 max-h-32 overflow-y-auto">
          {freezeEvents.map((freeze, index) => (
            <li key={freeze.id} className="text-sm text-gray-600">
              #{index + 1}: {formatMs(freeze.start_time_ms)} - {formatMs(freeze.duration_ms)} duration
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

interface TranscriptsListProps {
  transcripts: Transcript[];
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function TranscriptsList({ transcripts }: TranscriptsListProps) {
  if (transcripts.length === 0) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Conversation Transcript</h2>
        <p className="text-gray-500">No transcript available for this session.</p>
      </div>
    );
  }

  // Sort transcripts by turn number
  const sortedTranscripts = [...transcripts].sort((a, b) => a.turn_number - b.turn_number);

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Conversation Transcript</h2>
      <div className="space-y-4 max-h-96 overflow-y-auto">
        {sortedTranscripts.map((transcript) => (
          <div
            key={transcript.id}
            className={`flex ${transcript.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${transcript.role === 'user'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-900'
                }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs font-medium ${transcript.role === 'user' ? 'text-indigo-200' : 'text-gray-500'
                  }`}>
                  {transcript.role === 'user' ? 'User' : 'Assistant'}
                </span>
                <span className={`text-xs ${transcript.role === 'user' ? 'text-indigo-200' : 'text-gray-400'
                  }`}>
                  {formatTime(transcript.timestamp)}
                </span>
              </div>
              <p className="text-sm whitespace-pre-wrap">{transcript.content}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="bg-gray-200 h-8 w-48 rounded"></div>
      <div className="bg-gray-200 h-32 rounded-lg"></div>
      <div className="bg-gray-200 h-12 rounded-lg"></div>
      <div className="bg-gray-200 h-20 rounded-lg"></div>
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-gray-200 h-40 rounded-lg"></div>
        <div className="bg-gray-200 h-40 rounded-lg"></div>
      </div>
    </div>
  );
}

function ErrorState({ error }: { error: Error }) {
  return (
    <div className="text-center py-12">
      <p className="text-red-600 text-lg">Failed to load session</p>
      <p className="text-gray-500 text-sm mt-1">{error.message}</p>
      <Link
        href="/sessions"
        className="mt-4 inline-block px-4 py-2 text-sm font-medium text-indigo-600 hover:text-indigo-700"
      >
        Back to Sessions
      </Link>
    </div>
  );
}

export default function SessionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const { data: session, isLoading, error } = useSession(sessionId);

  const audioPlayerRef = useRef<AudioPlayerRef>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const handleTimeUpdate = useCallback((time: number, dur: number) => {
    setCurrentTime(time);
    setDuration(dur);
  }, []);

  const handleLoadedMetadata = useCallback((dur: number) => {
    setDuration(dur);
  }, []);

  const handleSeek = useCallback((time: number) => {
    audioPlayerRef.current?.seek(time);
  }, []);

  const handleDeleted = () => {
    router.push('/sessions');
  };

  if (isLoading) {
    return (
      <div className="container mx-auto py-8 px-4 max-w-4xl">
        <LoadingSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-8 px-4 max-w-4xl">
        <ErrorState error={error} />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="container mx-auto py-8 px-4 max-w-4xl">
        <ErrorState error={new Error('Session not found')} />
      </div>
    );
  }

  // Calculate session duration in seconds from timestamps
  const sessionDurationSeconds = session.ended_at
    ? (new Date(session.ended_at).getTime() - new Date(session.created_at).getTime()) / 1000
    : 0;

  // Use audio duration if available, otherwise use session duration
  const effectiveDuration = duration > 0 ? duration : sessionDurationSeconds;

  return (
    <div className="container mx-auto py-8 px-4 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <Link
            href="/sessions"
            className="text-sm text-white-600 hover:text-indigo-700 mb-2 inline-block"
          >
            &larr; Back to Sessions
          </Link>
          <h1 className="text-2xl font-bold text-white-900">Session Details</h1>
        </div>
        <DeleteSessionButton sessionId={session.id} onDeleted={handleDeleted} />
      </div>

      <div className="space-y-6">
        {/* Session Info */}
        <SessionInfoCard session={session} />

        {/* Audio Player Section */}
        {session.audio_file_path && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Audio Recording</h2>
            <AudioPlayer
              ref={audioPlayerRef}
              src={getAudioUrl(session.id)}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
            />

            {/* Timeline with latency and freeze markers */}
            <div className="mt-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Timeline</h3>
              <Timeline
                duration={effectiveDuration}
                currentTime={currentTime}
                turnLatencies={session.turn_latencies}
                freezeEvents={session.freeze_events}
                sessionStartTime={session.created_at}
                onSeek={handleSeek}
              />
              <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-green-400 rounded"></span>
                  Fast (&lt;500ms)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-yellow-400 rounded"></span>
                  Moderate
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-red-400 rounded"></span>
                  Slow (&gt;2s)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-red-200 rounded"></span>
                  Freeze
                </span>
              </div>
            </div>
          </div>
        )}

        {/* No Audio Message */}
        {!session.audio_file_path && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Audio Recording</h2>
            <p className="text-gray-500">No audio recording available for this session.</p>
          </div>
        )}

        {/* Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <LatencyStats turnLatencies={session.turn_latencies} />
          <FreezeStats freezeEvents={session.freeze_events} />
        </div>

        {/* Transcripts */}
        <TranscriptsList transcripts={session.transcripts} />
      </div>
    </div>
  );
}

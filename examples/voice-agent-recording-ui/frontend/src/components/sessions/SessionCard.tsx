'use client';

import Link from 'next/link';
import { Session } from '@/types/session';
import { DeleteSessionButton } from './DeleteSessionButton';

interface SessionCardProps {
  session: Session;
}

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

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function truncateId(id: string): string {
  return id.substring(0, 8) + '...';
}

function StatusBadge({ status }: { status: Session['status'] }) {
  const colors = {
    active: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    error: 'bg-red-100 text-red-800',
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[status]}`}>
      {status}
    </span>
  );
}

function AudioIndicator({ hasAudio }: { hasAudio: boolean }) {
  if (!hasAudio) return null;

  return (
    <span className="inline-flex items-center text-gray-500" title="Has audio recording">
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
        />
      </svg>
    </span>
  );
}

export function SessionCard({ session }: SessionCardProps) {
  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4 whitespace-nowrap">
        <code className="text-sm font-mono text-gray-700">{truncateId(session.id)}</code>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
        {formatDate(session.created_at)}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
        {formatDuration(session.created_at, session.ended_at)}
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <StatusBadge status={session.status} />
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-center">
        <AudioIndicator hasAudio={session.has_audio} />
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
        <Link
          href={`/sessions/${session.id}`}
          className="px-3 py-1.5 text-sm font-medium text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50 rounded-md transition-colors"
        >
          View
        </Link>
        <DeleteSessionButton sessionId={session.id} />
      </td>
    </tr>
  );
}

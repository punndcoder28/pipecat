'use client';

import { SessionsList } from '@/components/sessions';

export default function SessionsPage() {
  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white-900">Recording Sessions</h1>
        <p className="mt-2 text-white-600">
          View and manage your voice agent recording sessions.
        </p>
      </div>
      <SessionsList />
    </div>
  );
}

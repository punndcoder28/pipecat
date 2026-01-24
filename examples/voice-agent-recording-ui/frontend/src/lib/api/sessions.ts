/**
 * Session API functions and React Query hooks.
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient, API_BASE_URL } from './client';
import { Session, SessionDetail, SessionListResponse } from '@/types/session';

// Query parameters for listing sessions
export interface SessionsParams {
  limit?: number;
  offset?: number;
  status?: 'active' | 'completed' | 'error' | null;
}

/**
 * Fetch paginated list of sessions.
 */
export async function getSessions(params: SessionsParams = {}): Promise<SessionListResponse> {
  const { limit = 20, offset = 0, status } = params;

  const queryParams: Record<string, string | number> = { limit, offset };
  if (status) {
    queryParams.status = status;
  }

  const { data } = await apiClient.get<SessionListResponse>('/api/sessions', {
    params: queryParams
  });
  return data;
}

/**
 * React Query hook for fetching sessions list.
 */
export function useSessions(params: SessionsParams = {}) {
  return useQuery({
    queryKey: ['sessions', params],
    queryFn: () => getSessions(params),
  });
}

/**
 * Fetch a single session with all related data.
 */
export async function getSession(id: string): Promise<SessionDetail> {
  const { data } = await apiClient.get<SessionDetail>(`/api/sessions/${id}`);
  return data;
}

/**
 * React Query hook for fetching a single session.
 */
export function useSession(id: string) {
  return useQuery({
    queryKey: ['session', id],
    queryFn: () => getSession(id),
    enabled: !!id,
  });
}

/**
 * Get the audio URL for a session.
 * Returns the full URL that can be used directly in audio elements.
 */
export function getAudioUrl(sessionId: string): string {
  return `${API_BASE_URL}/api/sessions/${sessionId}/audio`;
}

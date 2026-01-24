/**
 * TypeScript interfaces matching the backend API models.
 */

export interface Session {
  id: string;
  created_at: string;
  ended_at: string | null;
  status: 'active' | 'completed' | 'error';
  has_audio: boolean;
}

export interface Transcript {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  turn_number: number;
}

export interface TurnLatency {
  id: string;
  turn_number: number;
  latency_ms: number;
  was_interrupted: boolean;
  created_at: string;
}

export interface FreezeEvent {
  id: string;
  start_time_ms: number;
  duration_ms: number;
  detected_at: string;
}

export interface SessionDetail extends Session {
  transcripts: Transcript[];
  turn_latencies: TurnLatency[];
  freeze_events: FreezeEvent[];
}

export interface SessionListResponse {
  sessions: Session[];
  total: number;
}

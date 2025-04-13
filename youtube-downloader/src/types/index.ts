
export interface Video {
  id: string;
  name: string;
  path: string;
  modified_date: string;
  size: number;
  transcription_status?: 'none' | 'started' | 'ended' | 'error';
  transcription_path?: string;
}

export interface Audio {
  id: string;
  name: string;
  path: string;
  modified_date: string;
  size: number;
  transcription_status?: 'none' | 'started' | 'ended' | 'error';
  transcription_path?: string;
}

export interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface TranscriptionResponse {
  status: 'processing' | 'success' | 'error';
  message?: string;
  transcription_text?: string;
}

export interface AudioExistsResponse {
  exists: boolean;
  audio_info?: Audio;
}

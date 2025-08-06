
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Video, Audio, TranscriptionResponse, AudioExistsResponse } from '../types';

// Helper para garantir type casting correto do transcription_status
export const ensureTranscriptionStatus = (status: any): 'none' | 'started' | 'ended' | 'error' | undefined => {
  if (!status) return undefined;
  if (['none', 'started', 'ended', 'error'].includes(status)) {
    return status as 'none' | 'started' | 'ended' | 'error';
  }
  // Mapeamento de valores antigos para novos
  if (status === 'processing') return 'started';
  if (status === 'success') return 'ended';
  return 'error';
};

// Configuração do cliente axios
const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000, // 30 segundos
});

// Interceptor para adicionar o token de autenticação
api.interceptors.request.use(
  async (config) => {
    const token = await AsyncStorage.getItem('@auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Constantes
const CLIENT_ID = 'your_client_id';
const CLIENT_SECRET = 'your_client_secret';
const TOKEN_STORAGE_KEY = '@auth_token';

// Funções de autenticação
export const authenticate = async () => {
  try {
    console.log("Iniciando autenticação...");
    const response = await api.post('/auth/token', {
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET
    });
    
    const { access_token } = response.data;
    await AsyncStorage.setItem(TOKEN_STORAGE_KEY, access_token);
    console.log("Autenticação bem-sucedida!");
    
    return access_token;
  } catch (error) {
    console.error('Erro de autenticação:', error);
    throw error;
  }
};

// Funções para vídeos
export const fetchVideos = async (sortBy = 'none'): Promise<Video[]> => {
  try {
    const response = await api.get(`/videos?sort_by=${sortBy}`);
    const videos = response.data.videos || [];
    
    // Garantir que transcription_status tenha o tipo correto
    return videos.map((video: any) => ({
      ...video,
      transcription_status: ensureTranscriptionStatus(video.transcription_status)
    }));
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return fetchVideos(sortBy);
    }
    console.error('Erro ao buscar vídeos:', error);
    throw error;
  }
};

export const fetchVideoStream = async (videoId: string): Promise<Blob> => {
  try {
    const response = await api.get(`/video/${videoId}`, {
      responseType: 'blob'
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return fetchVideoStream(videoId);
    }
    console.error('Erro ao buscar stream de vídeo:', error);
    throw error;
  }
};

// Funções para áudios
export const fetchAudios = async (): Promise<Audio[]> => {
  try {
    console.log("Buscando lista de áudios...");
    const response = await api.get('/audio/list');
    console.log(`Áudios encontrados: ${response.data.audio_files?.length || 0}`);
    const audioFiles = response.data.audio_files || [];
    
    // Garantir que transcription_status tenha o tipo correto
    return audioFiles.map((audio: any) => ({
      ...audio,
      transcription_status: ensureTranscriptionStatus(audio.transcription_status)
    }));
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return fetchAudios();
    }
    console.error('Erro ao buscar áudios:', error);
    throw error;
  }
};

export const checkAudioExists = async (youtubeUrl: string): Promise<AudioExistsResponse> => {
  try {
    const response = await api.get(`/audio/check_exists`, {
      params: { youtube_url: youtubeUrl }
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return checkAudioExists(youtubeUrl);
    }
    console.error('Erro ao verificar existência de áudio:', error);
    throw error;
  }
};

export const downloadAudio = async (youtubeUrl: string, highQuality: boolean): Promise<{status: string}> => {
  try {
    const response = await api.post('/audio/download', {
      url: youtubeUrl,
      high_quality: highQuality
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return downloadAudio(youtubeUrl, highQuality);
    }
    console.error('Erro ao fazer download de áudio:', error);
    throw error;
  }
};

// Funções para transcrição
export const transcribeAudio = async (
  audioId: string, 
  provider: string = 'groq', 
  language: string = 'pt'
): Promise<TranscriptionResponse> => {
  try {
    console.log(`Iniciando transcrição do áudio ${audioId}...`);
    const response = await api.post('/audio/transcribe', {
      file_id: audioId,
      provider,
      language
    });
    console.log(`Resposta da transcrição:`, response.data);
    return {
      ...response.data,
      status: ensureTranscriptionStatus(response.data.status)
    };
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return transcribeAudio(audioId, provider, language);
    }
    console.error('Erro ao transcrever áudio:', error);
    throw error;
  }
};

export const checkTranscriptionStatus = async (audioId: string): Promise<{status: 'none' | 'started' | 'ended' | 'error'}> => {
  try {
    console.log(`Verificando status da transcrição para o áudio ${audioId}...`);
    const response = await api.get(`/audio/transcription_status/${audioId}`);
    console.log(`Status da transcrição: ${response.data.status}`);
    return {
      ...response.data,
      status: ensureTranscriptionStatus(response.data.status)
    };
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return checkTranscriptionStatus(audioId);
    }
    console.error('Erro ao verificar status da transcrição:', error);
    throw error;
  }
};

export const fetchTranscription = async (itemId: string): Promise<string> => {
  try {
    console.log(`Buscando texto da transcrição para o item ${itemId}...`);
    const response = await api.get(`/audio/transcription/${itemId}`, {
      responseType: 'text'
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return fetchTranscription(itemId);
    }
    console.error('Erro ao buscar transcrição:', error);
    throw error;
  }
};

// Funções para gerenciamento de fila de downloads (Fase 3)
export const getQueueStatus = async (): Promise<any> => {
  try {
    const response = await api.get('/downloads/queue/status');
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return getQueueStatus();
    }
    console.error('Erro ao obter status da fila:', error);
    throw error;
  }
};

export const getQueueTasks = async (status?: string, audioId?: string): Promise<any> => {
  try {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (audioId) params.append('audio_id', audioId);
    
    const response = await api.get(`/downloads/queue/tasks?${params.toString()}`);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return getQueueTasks(status, audioId);
    }
    console.error('Erro ao obter tasks da fila:', error);
    throw error;
  }
};

export const cancelDownloadTask = async (taskId: string): Promise<any> => {
  try {
    const response = await api.post(`/downloads/queue/cancel/${taskId}`);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return cancelDownloadTask(taskId);
    }
    console.error('Erro ao cancelar download:', error);
    throw error;
  }
};

export const retryDownloadTask = async (taskId: string): Promise<any> => {
  try {
    const response = await api.post(`/downloads/queue/retry/${taskId}`);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return retryDownloadTask(taskId);
    }
    console.error('Erro ao fazer retry do download:', error);
    throw error;
  }
};

export const cleanupQueue = async (maxAgeHours: number = 24): Promise<any> => {
  try {
    const response = await api.delete(`/downloads/queue/cleanup?max_age_hours=${maxAgeHours}`);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return cleanupQueue(maxAgeHours);
    }
    console.error('Erro ao limpar fila:', error);
    throw error;
  }
};

export default api;

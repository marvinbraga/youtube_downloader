
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
    try {
      const token = await AsyncStorage.getItem('@auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (error) {
      console.error('Erro ao obter token de autenticação:', error);
    }
    return config;
  },
  (error) => {
    console.error('Erro no interceptor de requisição:', error);
    return Promise.reject(error);
  }
);

// Interceptor para tratamento de respostas e retry automático
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Se é erro 401 e não é uma tentativa de retry
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        console.log('Token expirado, tentando reautenticar...');
        const newToken = await authenticate();
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (authError) {
        console.error('Erro na reautenticação:', authError);
        // Limpar token inválido
        try {
          await AsyncStorage.removeItem('@auth_token');
        } catch (storageError) {
          console.error('Erro ao limpar token:', storageError);
        }
        return Promise.reject(authError);
      }
    }
    
    // Log detalhado do erro para depuração
    console.error('Erro na API:', {
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      message: error.message,
      data: error.response?.data
    });
    
    return Promise.reject(error);
  }
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
    console.error('Erro ao buscar vídeos:', error);
    throw new Error('Falha ao carregar lista de vídeos');
  }
};

export const fetchVideoStream = async (videoId: string): Promise<Blob> => {
  try {
    const response = await api.get(`/video/${videoId}`, {
      responseType: 'blob'
    });
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar stream de vídeo:', error);
    throw new Error('Falha ao carregar stream do vídeo');
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
    console.error('Erro ao buscar áudios:', error);
    throw new Error('Falha ao carregar lista de áudios');
  }
};

export const checkAudioExists = async (youtubeUrl: string): Promise<AudioExistsResponse> => {
  try {
    const response = await api.get(`/audio/check_exists`, {
      params: { youtube_url: youtubeUrl }
    });
    return response.data;
  } catch (error) {
    console.error('Erro ao verificar existência de áudio:', error);
    throw new Error('Falha ao verificar se o áudio já existe');
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
    console.error('Erro ao fazer download de áudio:', error);
    throw new Error('Falha ao iniciar download do áudio');
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
    console.error('Erro ao transcrever áudio:', error);
    throw new Error('Falha ao iniciar transcrição do áudio');
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
    console.error('Erro ao verificar status da transcrição:', error);
    throw new Error('Falha ao verificar status da transcrição');
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
    console.error('Erro ao buscar transcrição:', error);
    throw new Error('Falha ao carregar texto da transcrição');
  }
};

// Funções para gerenciamento de fila de downloads (Fase 3)
export const getQueueStatus = async (): Promise<any> => {
  try {
    const response = await api.get('/downloads/queue/status');
    return response.data;
  } catch (error) {
    console.error('Erro ao obter status da fila:', error);
    throw new Error('Falha ao obter status da fila de downloads');
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
    console.error('Erro ao obter tasks da fila:', error);
    throw new Error('Falha ao obter tarefas da fila de downloads');
  }
};

export const cancelDownloadTask = async (taskId: string): Promise<any> => {
  try {
    const response = await api.post(`/downloads/queue/cancel/${taskId}`);
    return response.data;
  } catch (error) {
    console.error('Erro ao cancelar download:', error);
    throw new Error('Falha ao cancelar download');
  }
};

export const retryDownloadTask = async (taskId: string): Promise<any> => {
  try {
    const response = await api.post(`/downloads/queue/retry/${taskId}`);
    return response.data;
  } catch (error) {
    console.error('Erro ao fazer retry do download:', error);
    throw new Error('Falha ao tentar novamente o download');
  }
};

export const cleanupQueue = async (maxAgeHours: number = 24): Promise<any> => {
  try {
    const response = await api.delete(`/downloads/queue/cleanup?max_age_hours=${maxAgeHours}`);
    return response.data;
  } catch (error) {
    console.error('Erro ao limpar fila:', error);
    throw new Error('Falha ao limpar fila de downloads');
  }
};

export default api;

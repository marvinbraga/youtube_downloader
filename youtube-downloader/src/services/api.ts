
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Video, Audio, TranscriptionResponse, AudioExistsResponse } from '../types';

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
    const response = await api.post('/auth/token', {
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET
    });
    
    const { access_token } = response.data;
    await AsyncStorage.setItem(TOKEN_STORAGE_KEY, access_token);
    
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
    return response.data.videos || [];
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
    const response = await api.get('/audio/list');
    return response.data.audio_files || [];
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
    const response = await api.post('/audio/transcribe', {
      file_id: audioId,
      provider,
      language
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await authenticate();
      return transcribeAudio(audioId, provider, language);
    }
    console.error('Erro ao transcrever áudio:', error);
    throw error;
  }
};

export const checkTranscriptionStatus = async (audioId: string): Promise<{status: string}> => {
  try {
    const response = await api.get(`/audio/transcription_status/${audioId}`);
    return response.data;
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

export default api;

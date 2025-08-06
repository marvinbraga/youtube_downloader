import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { Alert } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuth } from './AuthContext';
import { cancelDownloadTask, getQueueTasks } from '../services/api';

interface DownloadProgress {
  audioId: string;
  status: 'pending' | 'downloading' | 'ready' | 'error';
  progress: number;
  message?: string;
  error?: string;
  timestamp: string;
  taskId?: string; // ID da task na fila
}

interface QueueTask {
  id: string;
  audioId: string;
  url: string;
  status: 'queued' | 'downloading' | 'completed' | 'failed' | 'cancelled' | 'retrying';
  progress: number;
  errorMessage?: string;
  retryCount: number;
  maxRetries: number;
}

interface DownloadContextType {
  downloads: Map<string, DownloadProgress>;
  isConnected: boolean;
  notificationsEnabled: boolean;
  startListening: () => void;
  stopListening: () => void;
  getDownloadProgress: (audioId: string) => DownloadProgress | undefined;
  clearDownload: (audioId: string) => void;
  cancelDownload: (audioId: string) => Promise<boolean>;
  retryDownload: (audioId: string) => Promise<boolean>;
  getQueueTasks: () => Promise<QueueTask[]>;
  setNotificationsEnabled: (enabled: boolean) => void;
}

const DownloadContext = createContext<DownloadContextType | undefined>(undefined);

export const useDownloads = () => {
  const context = useContext(DownloadContext);
  if (!context) {
    throw new Error('useDownloads must be used within a DownloadProvider');
  }
  return context;
};

interface DownloadProviderProps {
  children: React.ReactNode;
}

export const DownloadProvider: React.FC<DownloadProviderProps> = ({ children }) => {
  const { authState } = useAuth();
  const [downloads, setDownloads] = useState<Map<string, DownloadProgress>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);

  // Função para conectar ao SSE
  const connectToSSE = useCallback(async () => {
    if (!authState.isAuthenticated || !authState.token) {
      console.log('Não autenticado, pulando conexão SSE');
      return;
    }

    // Limpar conexão anterior se existir
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      const baseUrl = 'http://localhost:8000';
      const sseUrl = `${baseUrl}/audio/download-events?token=${encodeURIComponent(authState.token)}`;
      
      console.log('Conectando ao SSE:', sseUrl);
      
      // Criar EventSource (sem headers por limitação do EventSource)
      const eventSource = new EventSource(sseUrl);

      eventSourceRef.current = eventSource;

      // Evento de conexão aberta
      eventSource.onopen = () => {
        console.log('Conexão SSE estabelecida');
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
      };

      // Evento de conexão estabelecida
      eventSource.addEventListener('connected', (event: any) => {
        console.log('Evento connected recebido:', event.data);
      });

      // Evento de download iniciado
      eventSource.addEventListener('download_started', (event: any) => {
        try {
          const data = JSON.parse(event.data);
          console.log('Download iniciado:', data);
          
          setDownloads(prev => {
            const newMap = new Map(prev);
            newMap.set(data.audio_id, {
              audioId: data.audio_id,
              status: 'downloading',
              progress: 0,
              message: data.message,
              timestamp: data.timestamp
            });
            return newMap;
          });

          // Limpar cache de áudios para forçar atualização
          AsyncStorage.removeItem('@audio_list_cache');
        } catch (error) {
          console.error('Erro ao processar evento download_started:', error);
        }
      });

      // Evento de progresso do download
      eventSource.addEventListener('download_progress', (event: any) => {
        try {
          const data = JSON.parse(event.data);
          
          setDownloads(prev => {
            const newMap = new Map(prev);
            const existing = newMap.get(data.audio_id);
            newMap.set(data.audio_id, {
              audioId: data.audio_id,
              status: 'downloading',
              progress: data.progress || 0,
              message: data.message,
              timestamp: data.timestamp,
              error: existing?.error
            });
            return newMap;
          });
        } catch (error) {
          console.error('Erro ao processar evento download_progress:', error);
        }
      });

      // Evento de download concluído
      eventSource.addEventListener('download_completed', (event: any) => {
        try {
          const data = JSON.parse(event.data);
          console.log('Download concluído:', data);
          
          setDownloads(prev => {
            const newMap = new Map(prev);
            newMap.set(data.audio_id, {
              audioId: data.audio_id,
              status: 'ready',
              progress: 100,
              message: data.message,
              timestamp: data.timestamp
            });
            return newMap;
          });

          // Limpar cache de áudios para forçar atualização
          AsyncStorage.removeItem('@audio_list_cache');

          // Mostrar notificação se habilitada
          if (notificationsEnabled) {
            Alert.alert(
              'Download Concluído! 🎉',
              `O áudio foi baixado com sucesso e está pronto para transcrição.`,
              [
                {
                  text: 'OK',
                  style: 'default'
                }
              ]
            );
          }

          // Remover da lista após 5 segundos
          setTimeout(() => {
            setDownloads(prev => {
              const newMap = new Map(prev);
              newMap.delete(data.audio_id);
              return newMap;
            });
          }, 5000);
        } catch (error) {
          console.error('Erro ao processar evento download_completed:', error);
        }
      });

      // Evento de erro no download
      eventSource.addEventListener('download_error', (event: any) => {
        try {
          const data = JSON.parse(event.data);
          console.error('Erro no download:', data);
          
          setDownloads(prev => {
            const newMap = new Map(prev);
            newMap.set(data.audio_id, {
              audioId: data.audio_id,
              status: 'error',
              progress: 0,
              message: data.message,
              error: data.error,
              timestamp: data.timestamp
            });
            return newMap;
          });

          // Limpar cache de áudios para forçar atualização
          AsyncStorage.removeItem('@audio_list_cache');

          // Mostrar notificação de erro se habilitada
          if (notificationsEnabled) {
            Alert.alert(
              'Erro no Download ❌',
              `Ocorreu um erro durante o download: ${data.error}\n\nVocê pode tentar novamente.`,
              [
                {
                  text: 'OK',
                  style: 'default'
                }
              ]
            );
          }
        } catch (error) {
          console.error('Erro ao processar evento download_error:', error);
        }
      });

      // Evento de erro na conexão
      eventSource.onerror = (error: any) => {
        console.error('Erro na conexão SSE:', error);
        setIsConnected(false);
        eventSource.close();
        eventSourceRef.current = null;

        // Implementar reconnect com backoff exponencial
        reconnectAttemptsRef.current++;
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        
        console.log(`Tentando reconectar em ${delay}ms (tentativa ${reconnectAttemptsRef.current})`);
        
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        
        reconnectTimeoutRef.current = setTimeout(() => {
          connectToSSE();
        }, delay);
      };

    } catch (error) {
      console.error('Erro ao configurar SSE:', error);
      setIsConnected(false);
    }
  }, [authState.isAuthenticated, authState.token]);

  // Função para iniciar escuta
  const startListening = useCallback(() => {
    console.log('Iniciando escuta SSE');
    connectToSSE();
  }, [connectToSSE]);

  // Função para parar escuta
  const stopListening = useCallback(() => {
    console.log('Parando escuta SSE');
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setIsConnected(false);
  }, []);

  // Função para obter progresso de um download
  const getDownloadProgress = useCallback((audioId: string): DownloadProgress | undefined => {
    return downloads.get(audioId);
  }, [downloads]);

  // Função para limpar um download da lista
  const clearDownload = useCallback((audioId: string) => {
    setDownloads(prev => {
      const newMap = new Map(prev);
      newMap.delete(audioId);
      return newMap;
    });
  }, []);

  // Função para cancelar um download
  const cancelDownload = useCallback(async (audioId: string): Promise<boolean> => {
    try {
      // Encontrar o taskId pelo audioId
      const download = downloads.get(audioId);
      if (!download || !download.taskId) {
        console.warn(`Task ID não encontrado para audio ${audioId}`);
        return false;
      }

      const result = await cancelDownloadTask(download.taskId);
      console.log('Download cancelado:', result);
      return result.success;
    } catch (error) {
      console.error('Erro ao cancelar download:', error);
      return false;
    }
  }, [downloads]);

  // Função para fazer retry de um download
  const retryDownload = useCallback(async (audioId: string): Promise<boolean> => {
    try {
      // Buscar tasks para este audio
      const tasksResult = await getQueueTasks(undefined, audioId);
      const failedTasks = tasksResult.tasks.filter((task: any) => 
        task.audio_id === audioId && task.status === 'failed'
      );

      if (failedTasks.length === 0) {
        console.warn(`Nenhuma task falhada encontrada para audio ${audioId}`);
        return false;
      }

      // Retry da primeira task falhada
      const result = await retryDownload(failedTasks[0].id);
      console.log('Retry executado:', result);
      return result;
    } catch (error) {
      console.error('Erro ao fazer retry do download:', error);
      return false;
    }
  }, []);

  // Função para obter tasks da fila
  const getQueueTasksFunction = useCallback(async (): Promise<QueueTask[]> => {
    try {
      const result = await getQueueTasks();
      return result.tasks.map((task: any) => ({
        id: task.id,
        audioId: task.audio_id,
        url: task.url,
        status: task.status,
        progress: task.progress,
        errorMessage: task.error_message,
        retryCount: task.retry_count,
        maxRetries: task.max_retries
      }));
    } catch (error) {
      console.error('Erro ao obter tasks da fila:', error);
      return [];
    }
  }, []);

  // Conectar automaticamente quando autenticado
  useEffect(() => {
    if (authState.isAuthenticated) {
      startListening();
    } else {
      stopListening();
    }

    return () => {
      stopListening();
    };
  }, [authState.isAuthenticated, startListening, stopListening]);

  const value: DownloadContextType = {
    downloads,
    isConnected,
    notificationsEnabled,
    startListening,
    stopListening,
    getDownloadProgress,
    clearDownload,
    cancelDownload,
    retryDownload,
    getQueueTasks: getQueueTasksFunction,
    setNotificationsEnabled
  };

  return (
    <DownloadContext.Provider value={value}>
      {children}
    </DownloadContext.Provider>
  );
};

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  ScrollView, 
  ActivityIndicator,
  RefreshControl,
  Alert,
  TouchableOpacity
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { Audio as ExpoAudio } from 'expo-av';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fetchAudios, transcribeAudio, checkTranscriptionStatus, fetchTranscription, ensureTranscriptionStatus } from '../../services/api';
import { Audio as AudioType } from '../../types';
import AudioItem from '../../components/AudioItem';
import TranscriptionModal from '../../components/TranscriptionModal';
import StatusMessage from '../../components/StatusMessage';
import { Feather } from '@expo/vector-icons';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { useDownloads } from '../../context/DownloadContext';
import { useGlobalAudioPlayer } from '../../context/AudioPlayerContext';
import { Platform } from 'react-native';
import * as FileSystem from 'expo-file-system';

const AudioScreen: React.FC = () => {
  const { authState, login } = useAuth();
  const { colors, theme } = useTheme();
  const { downloads, isConnected, getDownloadProgress, cancelDownload, retryDownload } = useDownloads();
  const { registerPlayer, unregisterPlayer, stopAllOtherPlayers } = useGlobalAudioPlayer();
  const [audios, setAudios] = useState<AudioType[]>([]);
  const [filteredAudios, setFilteredAudios] = useState<AudioType[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentAudioId, setCurrentAudioId] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    message: string;
    type: 'error' | 'success' | 'info';
  } | null>(null);
  
  
  // Referências para o player de áudio
  const soundRef = useRef<ExpoAudio.Sound | null>(null);
  const htmlAudioRef = useRef<HTMLAudioElement | null>(null);
  const transcriptionCheckTimerRef = useRef<NodeJS.Timeout | null>(null);
  const simplePlayerIdRef = useRef<string>('simple-audio-screen-player');
  const isMountedRef = useRef(true);
  
  // Estado para o modal de transcrição
  const [transcriptionModal, setTranscriptionModal] = useState({
    visible: false,
    title: '',
    content: '',
    isLoading: false,
    itemId: ''
  });
  
  // Constantes de cache
  const AUDIO_CACHE_KEY = '@audio_list_cache';
  const CACHE_DURATION = 5 * 60 * 1000; // 5 minutos

  // Funções de cache memoizadas
  const cacheAudios = useCallback(async (data: AudioType[]) => {
    const cache = {
      timestamp: Date.now(),
      data
    };
    await AsyncStorage.setItem(AUDIO_CACHE_KEY, JSON.stringify(cache));
  }, []);
  
  const getCachedAudios = useCallback(async () => {
    const cache = await AsyncStorage.getItem(AUDIO_CACHE_KEY);
    if (!cache) return null;
    
    const { timestamp, data } = JSON.parse(cache);
    
    if (Date.now() - timestamp > CACHE_DURATION) {
      await AsyncStorage.removeItem(AUDIO_CACHE_KEY);
      return null;
    }
    
    return data;
  }, []);
  
  // Função de verificação de status memoizada
  const checkTranscriptionStatusForAllItems = useCallback((items: AudioType[]): AudioType[] => {
    return items.map(item => {
      // Migra has_transcription antigo para transcription_status
      if (item.has_transcription === true && !item.transcription_status) {
        console.log(`Atualizando áudio ${item.id}: has_transcription = true -> transcription_status = ended`);
        return { ...item, transcription_status: "ended" };
      }
      
      // Se tiver caminho de transcrição mas não tiver status, considera como "ended"
      if (item.transcription_path && (!item.transcription_status || item.transcription_status === "none")) {
        console.log(`Atualizando áudio ${item.id}: tem caminho de transcrição -> transcription_status = ended`);
        return { ...item, transcription_status: "ended" };
      }
      
      // Para compatibilidade, verifica se o arquivo corresponde a um MD no sistema
      if (!item.transcription_status || item.transcription_status === "none") {
        console.log(`Áudio ${item.id} (${item.name}) não possui status de transcrição definido`);
      }
      
      return item;
    });
  }, []);

  // Função para carregar os áudios otimizada
  const loadAudios = useCallback(async () => {
    if (!authState.isAuthenticated) {
      return;
    }
    
    try {
      setIsLoading(true);
      
      let cachedAudios;
      try {
        cachedAudios = await getCachedAudios();
      } catch (cacheError) {
        console.error('Erro ao acessar cache de áudios:', cacheError);
        // Continuar sem cache em caso de erro
        cachedAudios = null;
      }
      
      if (cachedAudios) {
        setAudios(cachedAudios);
        filterAudios(cachedAudios, searchQuery);
      } else {
        const fetchedAudios = await fetchAudios();
        
        // Verificamos e atualizamos o status de transcrição para cada áudio
        let processedAudios;
        try {
          processedAudios = checkTranscriptionStatusForAllItems(fetchedAudios);
        } catch (processError) {
          console.error('Erro ao processar status de transcrição:', processError);
          processedAudios = fetchedAudios; // Usar dados originais em caso de erro
        }
        
        setAudios(processedAudios);
        filterAudios(processedAudios, searchQuery);
        
        // Tentar salvar no cache
        try {
          await cacheAudios(processedAudios);
        } catch (cacheError) {
          console.error('Erro ao salvar cache de áudios:', cacheError);
          // Não bloquear execução se cache falhar
        }
        
        // Iniciar verificação para áudios em transcrição
        try {
          startTranscriptionStatusCheck(processedAudios);
        } catch (checkError) {
          console.error('Erro ao iniciar verificação de transcrição:', checkError);
          // Não bloquear execução se verificação falhar
        }
      }
    } catch (error) {
      console.error('Erro ao carregar áudios:', error);
      setStatusMessage({
        message: 'Erro ao carregar áudios. Verifique sua conexão e tente novamente.',
        type: 'error'
      });
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  }, [authState.isAuthenticated, searchQuery, getCachedAudios, cacheAudios, checkTranscriptionStatusForAllItems]);
  
  // Função para parar o player simples (para uso pelo contexto global)
  const stopSimplePlayer = useCallback(async () => {
    console.log('🎵 Simple player stopped by global context');
    await stopAudio();
  }, []);
  
  // Carregar áudios no início
  useEffect(() => {
    isMountedRef.current = true;
    
    // Registrar player simples no contexto global
    registerPlayer(simplePlayerIdRef.current, stopSimplePlayer);

    if (authState.isAuthenticated) {
      loadAudios();
    } else if (!authState.isLoading) {
      login();
    }
    
    // Limpeza: parar o player e os temporizadores
    return () => {
      isMountedRef.current = false;
      
      // Limpar timer de transcrição de forma segura
      if (transcriptionCheckTimerRef.current) {
        clearInterval(transcriptionCheckTimerRef.current);
        transcriptionCheckTimerRef.current = null;
      }
      
      // Desregistrar player
      unregisterPlayer(simplePlayerIdRef.current);
      
      // Parar áudio
      stopAudio();
    };
  }, [authState.isAuthenticated, authState.isLoading, login, loadAudios, registerPlayer, unregisterPlayer, stopSimplePlayer]);
  
  // Recarregar lista quando downloads mudam (via SSE)
  useEffect(() => {
    if (downloads.size > 0) {
      // Verificar se há downloads concluídos recentemente ou mudanças recentes
      const hasCompletedDownloads = Array.from(downloads.values()).some(download => 
        download.status === 'ready'
      );
      
      const hasRecentChanges = Array.from(downloads.values()).some(download => {
        const timeDiff = Date.now() - new Date(download.timestamp).getTime();
        return timeDiff < 15000; // Mudanças nos últimos 15 segundos
      });
      
      if (hasCompletedDownloads || hasRecentChanges) {
        console.log('Recarregando áudios devido a mudanças nos downloads (completed:', hasCompletedDownloads, 'recent:', hasRecentChanges, ')');
        loadAudios();
      }
    }
  }, [downloads, loadAudios]);
  
  // Recarregar lista quando a tela recebe foco (para garantir dados atualizados)
  useFocusEffect(
    useCallback(() => {
      if (authState.isAuthenticated) {
        console.log('Tela de áudio recebeu foco, recarregando lista');
        loadAudios();
      }
    }, [authState.isAuthenticated, loadAudios])
  );
  
  
  // Função para filtrar áudios otimizada
  const filterAudios = useCallback((audioList: AudioType[], query: string) => {
    if (!query.trim()) {
      setFilteredAudios(audioList);
      return;
    }
    
    const lowerCaseQuery = query.toLowerCase();
    const filtered = audioList.filter(audio => 
      audio.name.toLowerCase().includes(lowerCaseQuery) || 
      audio.path.toLowerCase().includes(lowerCaseQuery)
    );
    
    setFilteredAudios(filtered);
  }, []);
  
  // Atualizar filtro quando mudar a pesquisa - otimizado
  useEffect(() => {
    filterAudios(audios, searchQuery);
  }, [searchQuery, audios, filterAudios]);
  
  // Iniciar verificação periódica de transcrições em andamento
  const startTranscriptionStatusCheck = useCallback((audiosList: AudioType[]) => {
    // Limpar temporizador existente de forma segura
    if (transcriptionCheckTimerRef.current) {
      clearInterval(transcriptionCheckTimerRef.current);
      transcriptionCheckTimerRef.current = null;
    }
    
    const audiosInProgress = audiosList.filter(
      audio => audio.transcription_status === 'started'
    );
    
    if (audiosInProgress.length > 0 && isMountedRef.current) {
      console.log(`Iniciando verificação para ${audiosInProgress.length} áudios em transcrição`);
      
      transcriptionCheckTimerRef.current = setInterval(() => {
        // Verificar se o componente ainda está montado antes de executar as verificações
        if (!isMountedRef.current) {
          if (transcriptionCheckTimerRef.current) {
            clearInterval(transcriptionCheckTimerRef.current);
            transcriptionCheckTimerRef.current = null;
          }
          return;
        }
        
        audiosInProgress.forEach(audio => {
          checkAudioTranscriptionStatus(audio, false);
        });
      }, 10000); // Verifica a cada 10 segundos
    }
  }, []);
  
  // Verificar status da transcrição
  const checkAudioTranscriptionStatus = async (audio: AudioType, showMessages = true) => {
    // Verificar se o componente ainda está montado
    if (!isMountedRef.current) {
      return;
    }
    
    if (!authState.isAuthenticated) {
      if (showMessages && isMountedRef.current) {
        setStatusMessage({
          message: 'Erro de autenticação. Tentando reconectar...',
          type: 'error'
        });
      }
      try {
        await login();
      } catch (authError) {
        console.error('Erro na reautenticação:', authError);
        if (showMessages && isMountedRef.current) {
          setStatusMessage({
            message: 'Falha na autenticação. Verifique sua conexão.',
            type: 'error'
          });
        }
      }
      return;
    }
    
    try {
      if (showMessages) {
        setStatusMessage({
          message: 'Verificando status da transcrição...',
          type: 'info'
        });
      }
      
      const response = await checkTranscriptionStatus(audio.id);
      
      // Se o status mudou, atualiza a interface (apenas se o componente ainda estiver montado)
      if (response.status !== audio.transcription_status && isMountedRef.current) {
        console.log(`Status da transcrição mudou: ${audio.transcription_status} -> ${response.status}`);
        
        // Atualiza o áudio na lista
        const updatedAudios = audios.map(a => {
          if (a.id === audio.id) {
            return { ...a, transcription_status: ensureTranscriptionStatus(response.status) };
          }
          return a;
        });
        
        if (isMountedRef.current) {
          setAudios(updatedAudios);
          filterAudios(updatedAudios, searchQuery);
          cacheAudios(updatedAudios);
        }
        
        // Se a transcrição foi concluída e estamos mostrando mensagens
        if (response.status === 'ended' && showMessages && isMountedRef.current) {
          setStatusMessage({
            message: 'Transcrição concluída com sucesso!',
            type: 'success'
          });
          
          // Forçar recarregamento da lista para mostrar o novo status
          await AsyncStorage.removeItem(AUDIO_CACHE_KEY);
          if (isMountedRef.current) {
            loadAudios();
          }
          
          // Pergunta se o usuário quer visualizar a transcrição
          if (isMountedRef.current) {
            Alert.alert(
              'Transcrição Concluída',
              'Deseja visualizar a transcrição agora?',
              [
                {
                  text: 'Não',
                  style: 'cancel'
                },
                {
                  text: 'Sim',
                  onPress: () => viewTranscription({ ...audio, transcription_status: 'ended' })
                }
              ]
            );
          }
        } 
        // Se houve erro e estamos mostrando mensagens
        else if (response.status === 'error' && showMessages && isMountedRef.current) {
          setStatusMessage({
            message: 'Ocorreu um erro durante a transcrição. Você pode tentar novamente.',
            type: 'error'
          });
        }
      } else if (showMessages) {
        // Se o status não mudou, mas estamos mostrando mensagens
        if (response.status === 'started') {
          setStatusMessage({
            message: 'A transcrição ainda está em andamento. Por favor, aguarde.',
            type: 'info'
          });
        } else if (response.status === 'ended') {
          viewTranscription({ ...audio, transcription_status: 'ended' });
        }
      }
      
      return response.status;
    } catch (error) {
      console.error('Erro ao verificar status da transcrição:', error);
      if (showMessages && isMountedRef.current) {
        setStatusMessage({
          message: 'Erro ao verificar status da transcrição. Tente novamente.',
          type: 'error'
        });
      }
      return null;
    }
  };
  
  // Função para reproduzir áudio no web usando HTML5
  const playWebAudio = async (audio: AudioType) => {
    try {
      // Parar áudio atual se estiver tocando
      if (htmlAudioRef.current) {
        try {
          htmlAudioRef.current.pause();
        } catch (pauseError) {
          console.error('Erro ao pausar áudio anterior:', pauseError);
        }
        htmlAudioRef.current = null;
      }

      setStatusMessage({
        message: `Carregando ${audio.name}...`,
        type: 'info'
      });

      // Criar elemento HTML5 Audio
      const audioElement = new Audio();
      htmlAudioRef.current = audioElement;

      // Configurar eventos
      audioElement.addEventListener('loadstart', () => {
        console.log('Carregamento iniciado');
      });

      audioElement.addEventListener('canplay', () => {
        setStatusMessage({
          message: `Reproduzindo ${audio.name}`,
          type: 'success'
        });
      });

      audioElement.addEventListener('ended', () => {
        setCurrentAudioId(null);
        setIsPlaying(false);
        setStatusMessage({
          message: 'Reprodução finalizada',
          type: 'success'
        });
      });

      audioElement.addEventListener('error', (e) => {
        console.error('Erro no player HTML5:', e);
        setCurrentAudioId(null);
        setIsPlaying(false);
        setStatusMessage({
          message: 'Erro ao reproduzir áudio',
          type: 'error'
        });
      });

      // Configurar URL do áudio
      const physicalAudioUrl = `http://localhost:8000/audio/stream/${audio.id}`;
      console.log('Tentando reproduzir via URL:', physicalAudioUrl);
      
      audioElement.src = physicalAudioUrl;
      
      // Tentar reproduzir
      try {
        await audioElement.play();
        // Se chegou aqui, a reprodução iniciou com sucesso
        setCurrentAudioId(audio.id);
        setIsPlaying(true);
      } catch (playError) {
        // Se falhar, mostrar erro apropriado
        console.error('Erro ao iniciar reprodução:', playError);
        setCurrentAudioId(null);
        setIsPlaying(false);
        setStatusMessage({
          message: 'Erro ao reproduzir áudio. Verifique sua conexão com o servidor.',
          type: 'error'
        });
      }
      
    } catch (error) {
      console.error('Erro na reprodução web:', error);
      setCurrentAudioId(null);
      setIsPlaying(false);
      setStatusMessage({
        message: 'Erro ao reproduzir áudio.',
        type: 'error'
      });
    }
  };

  // Função para baixar arquivo de áudio via API (apenas mobile)
  const downloadAudioFile = async (audio: AudioType): Promise<string> => {
    try {
      const cacheDir = `${FileSystem.cacheDirectory}audio/`;
      const audioFilePath = `${cacheDir}${audio.id}.m4a`;
      
      // Verificar se o arquivo já existe no cache
      let fileInfo;
      try {
        fileInfo = await FileSystem.getInfoAsync(audioFilePath);
        if (fileInfo.exists) {
          console.log('Arquivo já existe no cache:', audioFilePath);
          return audioFilePath;
        }
      } catch (cacheError) {
        console.error('Erro ao verificar cache:', cacheError);
        // Continuar com download se não conseguir verificar cache
      }
      
      // Criar diretório se não existir
      try {
        await FileSystem.makeDirectoryAsync(cacheDir, { intermediates: true });
      } catch (dirError) {
        console.error('Erro ao criar diretório de cache:', dirError);
        throw new Error('Falha ao criar diretório de cache');
      }
      
      // Baixar arquivo via API
      setStatusMessage({
        message: `Baixando ${audio.name}...`,
        type: 'info'
      });
      
      let authToken;
      try {
        authToken = await AsyncStorage.getItem('@auth_token');
      } catch (tokenError) {
        console.error('Erro ao obter token de autenticação:', tokenError);
        throw new Error('Token de autenticação não disponível');
      }
      
      const downloadResult = await FileSystem.downloadAsync(
        `http://localhost:8000/audio/stream/${audio.id}`,
        audioFilePath,
        {
          headers: {
            Authorization: `Bearer ${authToken}`
          }
        }
      );
      
      if (downloadResult.status === 200) {
        console.log('Arquivo baixado com sucesso:', audioFilePath);
        return audioFilePath;
      } else {
        throw new Error(`Falha no download: status HTTP ${downloadResult.status}`);
      }
    } catch (error) {
      console.error('Erro ao baixar arquivo de áudio:', error);
      setStatusMessage({
        message: 'Erro ao baixar arquivo de áudio. Verifique sua conexão.',
        type: 'error'
      });
      throw error;
    }
  };

  // Função para reproduzir/pausar áudio
  const playAudio = async (audio: AudioType) => {
    try {
      if (!authState.isAuthenticated) {
        try {
          await login();
        } catch (authError) {
          console.error('Erro na autenticação:', authError);
          setStatusMessage({
            message: 'Erro de autenticação. Verifique sua conexão.',
            type: 'error'
          });
          return;
        }
      }
      
      // Verificar se é o mesmo áudio - toggle play/pause
      if (currentAudioId === audio.id) {
        if (Platform.OS === 'web') {
          if (htmlAudioRef.current) {
            if (isPlaying) {
              // Pausar
              htmlAudioRef.current.pause();
              setIsPlaying(false);
              setStatusMessage({
                message: `${audio.name} pausado`,
                type: 'info'
              });
            } else {
              // Retomar - parar outros players primeiro
              stopAllOtherPlayers(simplePlayerIdRef.current);
              await htmlAudioRef.current.play();
              setIsPlaying(true);
              setStatusMessage({
                message: `Reproduzindo ${audio.name}`,
                type: 'success'
              });
            }
            return;
          }
        } else {
          if (soundRef.current) {
            if (isPlaying) {
              // Pausar
              await soundRef.current.pauseAsync();
              setIsPlaying(false);
              setStatusMessage({
                message: `${audio.name} pausado`,
                type: 'info'
              });
            } else {
              // Retomar - parar outros players primeiro
              stopAllOtherPlayers(simplePlayerIdRef.current);
              await soundRef.current.playAsync();
              setIsPlaying(true);
              setStatusMessage({
                message: `Reproduzindo ${audio.name}`,
                type: 'success'
              });
            }
            return;
          }
        }
      }
      
      // Parar todos os outros players antes de iniciar novo áudio
      stopAllOtherPlayers(simplePlayerIdRef.current);
      
      // Parar áudio atual se estiver tocando outro
      await stopAudio();
      
      // Usar abordagem baseada na plataforma
      if (Platform.OS === 'web') {
        await playWebAudio(audio);
        // Estado é definido dentro de playWebAudio
      } else {
        setCurrentAudioId(audio.id);
        setIsPlaying(true);
        await playMobileAudio(audio);
      }
      
    } catch (error) {
      console.error('Erro ao reproduzir áudio:', error);
      setCurrentAudioId(null);
      setIsPlaying(false);
      setStatusMessage({
        message: 'Erro ao reproduzir áudio. Verifique a conexão.',
        type: 'error'
      });
    }
  };

  // Função para reproduzir áudio no mobile usando expo-av
  const playMobileAudio = async (audio: AudioType) => {
    try {
      setStatusMessage({
        message: `Preparando ${audio.name}...`,
        type: 'info'
      });
      
      // Obter URL/caminho do áudio
      const audioUrl = await downloadAudioFile(audio);
      console.log('Reproduzindo áudio mobile:', audioUrl);
      
      // Criar nova instância do Sound
      const { sound } = await ExpoAudio.Sound.createAsync(
        { uri: audioUrl },
        { shouldPlay: true, isLooping: false },
        null
      );
      
      soundRef.current = sound;
      
      // Configurar callback para quando o áudio terminar
      sound.setOnPlaybackStatusUpdate((status) => {
        if (status.isLoaded && status.didJustFinish) {
          setCurrentAudioId(null);
          setIsPlaying(false);
          setStatusMessage({
            message: 'Reprodução finalizada',
            type: 'success'
          });
        }
      });
      
      setStatusMessage({
        message: `Reproduzindo ${audio.name}`,
        type: 'success'
      });
      
      // Atualizar a UI
      setFilteredAudios(prev => 
        prev.map(a => ({...a})) // Forçar atualização da lista
      );
    } catch (error) {
      throw error;
    }
  };
  
  // Função para parar a reprodução do áudio
  const stopAudio = async () => {
    // Parar HTML5 Audio (web)
    if (htmlAudioRef.current) {
      try {
        htmlAudioRef.current.pause();
        htmlAudioRef.current.currentTime = 0;
        htmlAudioRef.current = null;
      } catch (error) {
        console.error('Erro ao parar áudio HTML5:', error);
      }
    }
    
    // Parar expo-av (mobile)
    if (soundRef.current) {
      try {
        const status = await soundRef.current.getStatusAsync();
        if (status.isLoaded) {
          await soundRef.current.unloadAsync();
        }
      } catch (error) {
        console.error('Erro ao parar áudio expo-av:', error);
      }
      soundRef.current = null;
    }
    
    setCurrentAudioId(null);
    setIsPlaying(false);
  };
  
  // Função para transcrever áudio - Ponto de entrada principal da lógica de transcrição
  const transcribeAudioFile = async (audio: AudioType) => {
    // Verifica o status atual da transcrição
    const transcriptionStatus = audio.transcription_status || 'none';
    
    console.log(`Solicitação de transcrição para áudio ${audio.id} com status: ${transcriptionStatus}`);
    
    // Escolhe a ação correta baseada no status atual
    switch (transcriptionStatus) {
      case 'ended':
        // Se já está concluída, visualiza a transcrição
        viewTranscription(audio);
        break;
        
      case 'started':
        // Se está em andamento, verifica o status atual
        setStatusMessage({
          message: 'Transcrição em andamento. Verificando status...',
          type: 'info'
        });
        await checkAudioTranscriptionStatus(audio, true);
        break;
        
      case 'error':
        // Se teve erro anteriormente, confirma se deseja tentar novamente
        Alert.alert(
          'Tentar Novamente',
          'Houve um erro na transcrição anterior. Deseja tentar novamente?',
          [
            {
              text: 'Cancelar',
              style: 'cancel'
            },
            {
              text: 'Sim, tentar novamente',
              onPress: () => startTranscription(audio)
            }
          ]
        );
        break;
        
      default:
        // Para 'none' ou qualquer outro status, inicia uma nova transcrição
        startTranscription(audio);
        break;
    }
  };
  
  // Iniciar processo de transcrição
  const startTranscription = async (audio: AudioType) => {
    try {
      if (!authState.isAuthenticated) {
        try {
          await login();
        } catch (authError) {
          console.error('Erro na autenticação:', authError);
          setStatusMessage({
            message: 'Erro de autenticação. Verifique sua conexão.',
            type: 'error'
          });
          return;
        }
      }
      
      setStatusMessage({
        message: 'Iniciando transcrição de áudio...',
        type: 'info'
      });
      
      const response = await transcribeAudio(audio.id, 'groq', 'pt');
      
      if (response.status === 'started') {
        setStatusMessage({
          message: 'Transcrição iniciada em segundo plano. Isso pode levar alguns minutos.',
          type: 'success'
        });
        
        // Atualiza o status na interface
        const updatedAudios: AudioType[] = audios.map(a => {
          if (a.id === audio.id) {
            return { ...a, transcription_status: 'started' as const };
          }
          return a;
        });
        
        setAudios(updatedAudios);
        filterAudios(updatedAudios, searchQuery);
        cacheAudios(updatedAudios);
        
        // Inicia verificação periódica do status
        startTranscriptionStatusCheck(updatedAudios);
      } else if (response.status === 'ended') {
        setStatusMessage({
          message: 'Transcrição já existe! Carregando visualização...',
          type: 'success'
        });
        
        // Atualiza o status na interface
        const updatedAudios: AudioType[] = audios.map(a => {
          if (a.id === audio.id) {
            return { ...a, transcription_status: 'ended' as const };
          }
          return a;
        });
        
        setAudios(updatedAudios);
        filterAudios(updatedAudios, searchQuery);
        cacheAudios(updatedAudios);
        
        // Mostrar a transcrição existente
        viewTranscription({ ...audio, transcription_status: 'ended' });
      } else {
        setStatusMessage({
          message: 'Falha ao iniciar a transcrição',
          type: 'error'
        });
      }
    } catch (error) {
      console.error('Erro ao transcrever áudio:', error);
      setStatusMessage({
        message: 'Erro ao transcrever áudio. Tente novamente.',
        type: 'error'
      });
    }
  };
  
  // Função para visualizar transcrição
  const viewTranscription = async (audio: AudioType) => {
    try {
      if (!authState.isAuthenticated) {
        try {
          await login();
        } catch (authError) {
          console.error('Erro na autenticação:', authError);
          setStatusMessage({
            message: 'Erro de autenticação. Verifique sua conexão.',
            type: 'error'
          });
          return;
        }
      }
      
      setTranscriptionModal({
        visible: true,
        title: `Transcrição: ${audio.name}`,
        content: '',
        isLoading: true,
        itemId: audio.id
      });
      
      const transcriptionText = await fetchTranscription(audio.id);
      
      setTranscriptionModal(prev => ({
        ...prev,
        content: transcriptionText,
        isLoading: false
      }));
    } catch (error) {
      console.error('Erro ao buscar transcrição:', error);
      setStatusMessage({
        message: 'Erro ao carregar transcrição. Tente novamente.',
        type: 'error'
      });
      setTranscriptionModal(prev => ({
        ...prev,
        visible: false
      }));
    }
  };
  
  // Função para baixar transcrição
  const downloadTranscription = () => {
    // Em um aplicativo móvel, isso poderia compartilhar o texto ou salvar como arquivo
    const transcriptionUrl = `http://localhost:8000/audio/transcription/${transcriptionModal.itemId}`;
    setStatusMessage({
      message: 'Transcrição disponível para download no navegador',
      type: 'info'
    });
  };
  
  // Função para lidar com a atualização via pull-to-refresh
  const onRefresh = useCallback(() => {
    setRefreshing(true);
    AsyncStorage.removeItem(AUDIO_CACHE_KEY).then(() => {
      loadAudios();
    });
  }, [loadAudios]);
  
  // Memoizar lista processada de áudios para evitar recálculos desnecessários
  const processedAudios = useMemo(() => {
    return filteredAudios.map((audio) => {
      // Obter dados de progresso do SSE se disponível
      const downloadProgress = getDownloadProgress(audio.id);
      
      // Combinar dados do áudio com dados de progresso em tempo real
      return {
        ...audio,
        download_status: downloadProgress?.status || audio.download_status,
        download_progress: downloadProgress?.progress ?? audio.download_progress,
        download_error: downloadProgress?.error || audio.download_error
      };
    });
  }, [filteredAudios, getDownloadProgress]);

  // Função para cancelar download
  const handleCancelDownload = useCallback(async (audio: AudioType) => {
    try {
      setStatusMessage({
        message: 'Cancelando download...',
        type: 'info'
      });

      const success = await cancelDownload(audio.id);
      
      if (success) {
        setStatusMessage({
          message: 'Download cancelado com sucesso',
          type: 'success'
        });
        // Recarregar lista
        await AsyncStorage.removeItem('@audio_list_cache');
        loadAudios();
      } else {
        setStatusMessage({
          message: 'Não foi possível cancelar o download',
          type: 'error'
        });
      }
    } catch (error) {
      console.error('Erro ao cancelar download:', error);
      setStatusMessage({
        message: 'Erro ao cancelar download. Tente novamente.',
        type: 'error'
      });
    }
  }, [cancelDownload, loadAudios]);

  // Função para retry de download
  const handleRetryDownload = useCallback(async (audio: AudioType) => {
    try {
      setStatusMessage({
        message: 'Tentando novamente...',
        type: 'info'
      });

      const success = await retryDownload(audio.id);
      
      if (success) {
        setStatusMessage({
          message: 'Download reiniciado com sucesso',
          type: 'success'
        });
        // Recarregar lista
        await AsyncStorage.removeItem('@audio_list_cache');
        loadAudios();
      } else {
        setStatusMessage({
          message: 'Não foi possível reiniciar o download',
          type: 'error'
        });
      }
    } catch (error) {
      console.error('Erro ao fazer retry do download:', error);
      setStatusMessage({
        message: 'Erro ao tentar novamente. Tente novamente.',
        type: 'error'
      });
    }
  }, [retryDownload, loadAudios]);
  
  return (
    <View style={[styles.container, { backgroundColor: colors.background.primary }]}>
      {statusMessage && (
        <StatusMessage
          message={statusMessage.message}
          type={statusMessage.type}
          onClose={() => setStatusMessage(null)}
        />
      )}
      
      <View style={[styles.controlsContainer, { backgroundColor: colors.background.secondary }]}>
        <TextInput
          style={[
            styles.searchInput, 
            { 
              backgroundColor: colors.background.primary,
              borderColor: colors.border,
              color: colors.text.primary
            }
          ]}
          placeholder="Digite para buscar áudios..."
          placeholderTextColor={colors.text.secondary}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>
      
      <View style={[
        styles.audioListContainer,
        { 
          borderColor: colors.border,
          backgroundColor: colors.background.primary
        }
      ]}>
        <View style={styles.listHeader}>
          <Text style={[styles.listTitle, { color: colors.text.primary }]}>Áudios Disponíveis</Text>
          <View style={styles.headerActions}>
            <TouchableOpacity
              style={[
                styles.refreshButton,
                { 
                  backgroundColor: colors.background.secondary,
                  borderColor: colors.border
                }
              ]}
              onPress={onRefresh}
              disabled={refreshing}
            >
              <Feather 
                name="refresh-cw" 
                size={16} 
                color={refreshing ? colors.text.secondary : colors.primary} 
              />
              <Text style={[
                styles.refreshButtonText,
                { color: refreshing ? colors.text.secondary : colors.primary }
              ]}>
                {refreshing ? 'Atualizando...' : 'Atualizar'}
              </Text>
            </TouchableOpacity>
            {isConnected && (
              <View style={styles.connectionIndicator}>
                <View style={[styles.connectionDot, { backgroundColor: colors.success }]} />
                <Text style={[styles.connectionText, { color: colors.text.secondary }]}>Tempo real</Text>
              </View>
            )}
          </View>
        </View>
        
        {isLoading && !refreshing ? (
          <View style={styles.centerLoading}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={[styles.loadingText, { color: colors.text.primary }]}>Carregando áudios...</Text>
          </View>
        ) : filteredAudios.length === 0 ? (
          <View style={styles.noResults}>
            <Feather name="inbox" size={48} color={colors.text.secondary} />
            <Text style={[styles.noResultsText, { color: colors.text.primary }]}>
              {searchQuery ? 'Nenhum áudio corresponde à sua busca.' : 'Nenhum áudio disponível.'}
            </Text>
          </View>
        ) : (
          <ScrollView
            style={styles.audiosList}
            contentContainerStyle={styles.audiosListContent}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={onRefresh}
                colors={[colors.primary]}
                tintColor={colors.primary}
              />
            }
          >
            {processedAudios.map((enrichedAudio: AudioType) => (
              <AudioItem
                key={enrichedAudio.id}
                audio={enrichedAudio}
                isActive={currentAudioId === enrichedAudio.id && isPlaying}
                onPress={() => setCurrentAudioId(enrichedAudio.id)}
                onPlay={playAudio}
                onTranscribe={transcribeAudioFile}
                onCancel={handleCancelDownload}
                onRetry={handleRetryDownload}
                showAudioPlayer={true}
              />
            ))}
          </ScrollView>
        )}
      </View>
      
      <TranscriptionModal
        visible={transcriptionModal.visible}
        title={transcriptionModal.title}
        content={transcriptionModal.content}
        isLoading={transcriptionModal.isLoading}
        onClose={() => setTranscriptionModal(prev => ({ ...prev, visible: false }))}
        onDownload={downloadTranscription}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
  },
  controlsContainer: {
    padding: 16,
    borderRadius: 8,
    marginBottom: 16,
  },
  searchInput: {
    padding: 10,
    borderRadius: 4,
    borderWidth: 1,
  },
  audioListContainer: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
  },
  listHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  listTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  refreshButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
    borderWidth: 1,
  },
  refreshButtonText: {
    marginLeft: 6,
    fontSize: 14,
    fontWeight: '500',
  },
  connectionIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  connectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  connectionText: {
    fontSize: 12,
    fontWeight: '500',
  },
  audiosList: {
    flex: 1,
  },
  audiosListContent: {
    paddingBottom: 12,
  },
  centerLoading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    textAlign: 'center',
  },
  noResults: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 40,
  },
  noResultsText: {
    marginTop: 16,
    textAlign: 'center',
    fontSize: 16,
  },
});

export default AudioScreen;

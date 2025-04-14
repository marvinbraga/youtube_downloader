
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  ScrollView, 
  TouchableOpacity, 
  ActivityIndicator,
  RefreshControl,
  Dimensions,
  Alert
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Video as VideoPlayer } from 'expo-av';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { 
  fetchVideos, 
  fetchVideoStream, 
  fetchTranscription, 
  transcribeAudio, 
  checkTranscriptionStatus 
} from '../../services/api';
import { Video } from '../../types';
import VideoItem from '../../components/VideoItem';
import TranscriptionModal from '../../components/TranscriptionModal';
import StatusMessage from '../../components/StatusMessage';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';

const { width } = Dimensions.get('window');

enum SortOption {
  NONE = 'none',
  TITLE = 'title',
  DATE = 'date'
}

const VideosScreen: React.FC = () => {
  const { authState, login } = useAuth();
  const { colors, theme } = useTheme();
  const videoPlayerRef = useRef<VideoPlayer>(null);
  const transcriptionCheckTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [filteredVideos, setFilteredVideos] = useState<Video[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentVideoId, setCurrentVideoId] = useState<string | null>(null);
  const [currentVideoTitle, setCurrentVideoTitle] = useState('Selecione um conteúdo para reproduzir');
  const [currentVideoUri, setCurrentVideoUri] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortOption>(SortOption.NONE);
  const [isLoading, setIsLoading] = useState(false);
  const [isPlayerLoading, setIsPlayerLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    message: string;
    type: 'error' | 'success' | 'info';
  } | null>(null);
  
  // Estado para o modal de transcrição
  const [transcriptionModal, setTranscriptionModal] = useState({
    visible: false,
    title: '',
    content: '',
    isLoading: false,
    itemId: ''
  });
  
  // Função para carregar os vídeos
  const loadVideos = useCallback(async () => {
    if (!authState.isAuthenticated) {
      return;
    }
    
    try {
      setIsLoading(true);
      const cachedVideos = await getCachedVideos();
      
      if (cachedVideos && cachedVideos.sortBy === sortBy) {
        setVideos(cachedVideos.data);
        filterVideos(cachedVideos.data, searchQuery);
        
        // Verificar se há algum vídeo em transcrição
        startTranscriptionStatusCheck(cachedVideos.data);
      } else {
        const fetchedVideos = await fetchVideos(sortBy);
        setVideos(fetchedVideos);
        filterVideos(fetchedVideos, searchQuery);
        cacheVideos(fetchedVideos, sortBy);
        
        // Verificar se há algum vídeo em transcrição
        startTranscriptionStatusCheck(fetchedVideos);
      }
    } catch (error) {
      console.error('Erro ao carregar vídeos:', error);
      setStatusMessage({
        message: 'Erro ao carregar vídeos. Tente novamente.',
        type: 'error'
      });
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  }, [authState.isAuthenticated, sortBy, searchQuery]);
  
  // Carregar vídeos no início e quando sortBy mudar
  useEffect(() => {
    if (authState.isAuthenticated) {
      loadVideos();
    } else if (!authState.isLoading) {
      login();
    }
    
    // Cleanup: stop timers when component unmounts
    return () => {
      if (transcriptionCheckTimerRef.current) {
        clearInterval(transcriptionCheckTimerRef.current);
        transcriptionCheckTimerRef.current = null;
      }
    };
  }, [authState.isAuthenticated, authState.isLoading, sortBy, login, loadVideos]);
  
  // Funções para cache
  const VIDEO_CACHE_KEY = '@video_list_cache';
  const CACHE_DURATION = 5 * 60 * 1000; // 5 minutos
  
  const cacheVideos = async (data: Video[], currentSortBy: SortOption) => {
    const cache = {
      timestamp: Date.now(),
      data,
      sortBy: currentSortBy
    };
    await AsyncStorage.setItem(VIDEO_CACHE_KEY, JSON.stringify(cache));
  };
  
  const getCachedVideos = async () => {
    const cache = await AsyncStorage.getItem(VIDEO_CACHE_KEY);
    if (!cache) return null;
    
    const { timestamp, data, sortBy } = JSON.parse(cache);
    
    if (Date.now() - timestamp > CACHE_DURATION) {
      await AsyncStorage.removeItem(VIDEO_CACHE_KEY);
      return null;
    }
    
    return { data, sortBy };
  };
  
  // Função para filtrar vídeos
  const filterVideos = (videoList: Video[], query: string) => {
    if (!query.trim()) {
      setFilteredVideos(videoList);
      return;
    }
    
    const lowerCaseQuery = query.toLowerCase();
    const filtered = videoList.filter(video => 
      video.name.toLowerCase().includes(lowerCaseQuery) || 
      video.path.toLowerCase().includes(lowerCaseQuery)
    );
    
    setFilteredVideos(filtered);
  };
  
  // Atualizar filtro quando mudar a pesquisa
  useEffect(() => {
    filterVideos(videos, searchQuery);
  }, [searchQuery, videos]);
  
  // Iniciar verificação periódica de transcrições em andamento
  const startTranscriptionStatusCheck = (videosList: Video[]) => {
    // Limpar temporizador existente
    if (transcriptionCheckTimerRef.current) {
      clearInterval(transcriptionCheckTimerRef.current);
    }
    
    const videosInProgress = videosList.filter(
      video => video.transcription_status === 'started'
    );
    
    if (videosInProgress.length > 0) {
      transcriptionCheckTimerRef.current = setInterval(() => {
        videosInProgress.forEach(video => {
          checkVideoTranscriptionStatus(video, false);
        });
      }, 10000); // Verifica a cada 10 segundos
      
      // Log para depuração
      console.log(`Iniciada verificação periódica para ${videosInProgress.length} vídeos em transcrição`);
    }
  };
  
  // Verificar status da transcrição
  const checkVideoTranscriptionStatus = async (video: Video, showMessages = true) => {
    if (!authState.isAuthenticated) {
      if (showMessages) {
        setStatusMessage({
          message: 'Erro de autenticação. Tentando reconectar...',
          type: 'error'
        });
      }
      await login();
      return;
    }
    
    try {
      if (showMessages) {
        setStatusMessage({
          message: 'Verificando status da transcrição...',
          type: 'info'
        });
      }
      
      const response = await checkTranscriptionStatus(video.id);
      
      // Se o status mudou, atualiza a interface
      if (response.status !== video.transcription_status) {
        console.log(`Status da transcrição mudou: ${video.transcription_status} -> ${response.status}`);
        
        // Atualiza o vídeo na lista
        const updatedVideos = videos.map(v => {
          if (v.id === video.id) {
            return { ...v, transcription_status: response.status };
          }
          return v;
        });
        
        setVideos(updatedVideos);
        filterVideos(updatedVideos, searchQuery);
        cacheVideos(updatedVideos, sortBy);
        
        // Se a transcrição foi concluída e estamos mostrando mensagens
        if (response.status === 'ended' && showMessages) {
          setStatusMessage({
            message: 'Transcrição concluída com sucesso!',
            type: 'success'
          });
          
          // Pergunta se o usuário quer visualizar a transcrição
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
                onPress: () => viewTranscription({ ...video, transcription_status: 'ended' })
              }
            ]
          );
        } 
        // Se houve erro e estamos mostrando mensagens
        else if (response.status === 'error' && showMessages) {
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
          viewTranscription({ ...video, transcription_status: 'ended' });
        }
      }
      
      return response.status;
    } catch (error) {
      if (showMessages) {
        console.error('Erro:', error);
        setStatusMessage({
          message: 'Erro ao verificar status da transcrição',
          type: 'error'
        });
      }
      return null;
    }
  };
  
  // Função para transcrever vídeo
  const transcribeVideo = async (video: Video) => {
    // Verifica o status atual da transcrição
    const transcriptionStatus = video.transcription_status || 'none';
    
    // Se já está concluída
    if (transcriptionStatus === 'ended') {
      viewTranscription(video);
      return;
    }
    
    // Se está em andamento
    if (transcriptionStatus === 'started') {
      setStatusMessage({
        message: 'Transcrição em andamento. Por favor, aguarde a conclusão.',
        type: 'info'
      });
      return;
    }
    
    // Se teve erro anteriormente, confirma se deseja tentar novamente
    if (transcriptionStatus === 'error') {
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
            onPress: () => startVideoTranscription(video)
          }
        ]
      );
      return;
    }
    
    // Iniciar nova transcrição
    startVideoTranscription(video);
  };
  
  // Iniciar processo de transcrição
  const startVideoTranscription = async (video: Video) => {
    try {
      if (!authState.isAuthenticated) {
        await login();
      }
      
      setStatusMessage({
        message: 'Iniciando transcrição de vídeo...',
        type: 'info'
      });
      
      // Reutiliza a API de transcrição de áudio (backend trata ambos da mesma forma)
      const response = await transcribeAudio(video.id, 'groq', 'pt');
      
      if (response.status === 'processing') {
        setStatusMessage({
          message: 'Transcrição iniciada em segundo plano. Isso pode levar alguns minutos.',
          type: 'success'
        });
        
        // Atualiza o status na interface
        const updatedVideos = videos.map(v => {
          if (v.id === video.id) {
            return { ...v, transcription_status: 'started' };
          }
          return v;
        });
        
        setVideos(updatedVideos);
        filterVideos(updatedVideos, searchQuery);
        cacheVideos(updatedVideos, sortBy);
        
        // Inicia verificação periódica do status
        startTranscriptionStatusCheck(updatedVideos);
      } else if (response.status === 'success') {
        setStatusMessage({
          message: 'Transcrição já existe! Carregando visualização...',
          type: 'success'
        });
        
        // Atualiza o status na interface
        const updatedVideos = videos.map(v => {
          if (v.id === video.id) {
            return { ...v, transcription_status: 'ended' };
          }
          return v;
        });
        
        setVideos(updatedVideos);
        filterVideos(updatedVideos, searchQuery);
        cacheVideos(updatedVideos, sortBy);
        
        // Mostrar a transcrição existente
        viewTranscription({ ...video, transcription_status: 'ended' });
      } else {
        setStatusMessage({
          message: 'Falha ao iniciar a transcrição',
          type: 'error'
        });
      }
    } catch (error) {
      console.error('Erro:', error);
      setStatusMessage({
        message: 'Erro ao transcrever vídeo. Tente novamente.',
        type: 'error'
      });
    }
  };
  
  async function playVideo(video: Video) {
    if (!authState.isAuthenticated) {
      setStatusMessage({
        message: 'Erro de autenticação. Tentando reconectar...',
        type: 'error'
      });
      return login();
    }

    try {
      setIsPlayerLoading(true);
      
      if (currentVideoId === video.id && currentVideoUri) {
        // Já está carregado, apenas reproduz
        if (videoPlayerRef.current) {
          await videoPlayerRef.current.playAsync();
        }
        setIsPlayerLoading(false);
        return;
      }
      
      setCurrentVideoId(video.id);
      setCurrentVideoTitle(video.name);
      
      // Em dispositivos móveis, não é possível usar Blob
      // Precisamos de uma abordagem diferente, como streaming direto da API
      // Este é um exemplo simplificado
      try {
        // Limpar o player atual
        if (videoPlayerRef.current) {
          await videoPlayerRef.current.unloadAsync();
        }
        
        // Em um cenário real, isso seria algo como:
        // const videoUri = `http://localhost:8000/video/${video.id}?token=${authState.token}`;
        // Em React Native, precisaríamos de um endpoint que aceite um token na URL
        // ou usar uma solução como React Native Blob Util para downloads complexos
        
        // Para simplificar o exemplo, vamos fingir que temos uma URL
        const videoUri = `http://localhost:8000/video/${video.id}`;
        setCurrentVideoUri(videoUri);
        
        // Atualizar o UI
        setFilteredVideos(prev => 
          prev.map(v => ({...v})) // Forçar atualização da lista
        );
      } catch (error) {
        console.error('Erro ao reproduzir vídeo:', error);
        setStatusMessage({
          message: 'Erro ao reproduzir vídeo. Tente novamente.',
          type: 'error'
        });
      } finally {
        setIsPlayerLoading(false);
      }
    } catch (error) {
      console.error('Erro:', error);
      setStatusMessage({
        message: 'Erro ao reproduzir vídeo. Tente novamente.',
        type: 'error'
      });
      setIsPlayerLoading(false);
    }
  }
  
  // Função para visualizar transcrição
  const viewTranscription = async (video: Video) => {
    try {
      if (!authState.isAuthenticated) {
        await login();
      }
      
      setTranscriptionModal({
        visible: true,
        title: `Transcrição: ${video.name}`,
        content: '',
        isLoading: true,
        itemId: video.id
      });
      
      const transcriptionText = await fetchTranscription(video.id);
      
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
    AsyncStorage.removeItem(VIDEO_CACHE_KEY).then(() => {
      loadVideos();
    });
  }, [loadVideos]);
  
  // Função para mudar a ordenação
  const changeSortOrder = (newSortBy: SortOption) => {
    if (sortBy !== newSortBy) {
      setSortBy(newSortBy);
    }
  };
  
  return (
    <View style={[styles.container, { backgroundColor: colors.background.primary }]}>
      {statusMessage && (
        <StatusMessage
          message={statusMessage.message}
          type={statusMessage.type}
          onClose={() => setStatusMessage(null)}
        />
      )}
      
      <View style={styles.videoContainer}>
        {isPlayerLoading && (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={styles.loadingText}>Carregando vídeo...</Text>
          </View>
        )}
        
        {currentVideoUri ? (
          <VideoPlayer
            ref={videoPlayerRef}
            style={styles.videoPlayer}
            source={{ uri: currentVideoUri }}
            useNativeControls
            resizeMode="contain"
            isLooping={false}
            onLoadStart={() => setIsPlayerLoading(true)}
            onLoad={() => setIsPlayerLoading(false)}
            onError={(error) => {
              console.error('Erro no player:', error);
              setIsPlayerLoading(false);
              setStatusMessage({
                message: 'Erro ao reproduzir vídeo. Tente novamente.',
                type: 'error'
              });
            }}
          />
        ) : (
          <View style={styles.videoPlaceholder}>
            <Feather name="video-off" size={48} color="#cccccc" />
            <Text style={styles.placeholderText}>
              Selecione um vídeo para reproduzir
            </Text>
          </View>
        )}
        
        <Text style={styles.videoTitle}>{currentVideoTitle}</Text>
      </View>
      
      <View style={[styles.controlsContainer, { backgroundColor: colors.background.secondary }]}>
        <TextInput
          style={[styles.searchInput, { 
            backgroundColor: colors.background.primary,
            borderColor: colors.border,
            color: colors.text.primary
          }]}
          placeholder="Digite para buscar vídeos..."
          placeholderTextColor={colors.text.secondary}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
        
        <Text style={[styles.sortLabel, { color: colors.text.primary }]}>Ordenar por:</Text>
        <View style={styles.sortButtons}>
          <TouchableOpacity
            style={[
              styles.sortButton, 
              { 
                backgroundColor: colors.background.primary,
                borderColor: colors.border 
              },
              sortBy === SortOption.NONE && [
                styles.activeSortButton, 
                { 
                  backgroundColor: colors.secondary,
                  borderColor: colors.secondary 
                }
              ]
            ]}
            onPress={() => changeSortOrder(SortOption.NONE)}
          >
            <Text style={[
              styles.sortButtonText, 
              { color: colors.text.primary },
              sortBy === SortOption.NONE && styles.activeSortButtonText
            ]}>
              Padrão
            </Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[
              styles.sortButton, 
              { 
                backgroundColor: colors.background.primary,
                borderColor: colors.border 
              },
              sortBy === SortOption.TITLE && [
                styles.activeSortButton, 
                { 
                  backgroundColor: colors.secondary,
                  borderColor: colors.secondary 
                }
              ]
            ]}
            onPress={() => changeSortOrder(SortOption.TITLE)}
          >
            <Text style={[
              styles.sortButtonText, 
              { color: colors.text.primary },
              sortBy === SortOption.TITLE && styles.activeSortButtonText
            ]}>
              Título
            </Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[
              styles.sortButton, 
              { 
                backgroundColor: colors.background.primary,
                borderColor: colors.border 
              },
              sortBy === SortOption.DATE && [
                styles.activeSortButton, 
                { 
                  backgroundColor: colors.secondary,
                  borderColor: colors.secondary 
                }
              ]
            ]}
            onPress={() => changeSortOrder(SortOption.DATE)}
          >
            <Text style={[
              styles.sortButtonText, 
              { color: colors.text.primary },
              sortBy === SortOption.DATE && styles.activeSortButtonText
            ]}>
              Data
            </Text>
          </TouchableOpacity>
        </View>
      </View>
      
      <View style={[
        styles.videoListContainer, 
        { 
          backgroundColor: colors.background.primary,
          borderColor: colors.border 
        }
      ]}>
        <Text style={[styles.listTitle, { color: colors.text.primary }]}>Vídeos Disponíveis</Text>
        
        {isLoading && !refreshing ? (
          <View style={styles.centerLoading}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={[styles.loadingText, { color: colors.text.primary }]}>Carregando vídeos...</Text>
          </View>
        ) : filteredVideos.length === 0 ? (
          <View style={styles.noResults}>
            <Feather name="inbox" size={48} color={colors.text.secondary} />
            <Text style={[styles.noResultsText, { color: colors.text.primary }]}>
              {searchQuery ? 'Nenhum vídeo corresponde à sua busca.' : 'Nenhum vídeo disponível.'}
            </Text>
          </View>
        ) : (
          <ScrollView
            style={styles.videosList}
            contentContainerStyle={styles.videosListContent}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={onRefresh}
                colors={[colors.primary]}
                tintColor={colors.primary}
              />
            }
          >
            {filteredVideos.map((video) => (
              <VideoItem
                key={video.id}
                video={video}
                isActive={currentVideoId === video.id}
                onPress={() => setCurrentVideoId(video.id)}
                onPlay={playVideo}
                onViewTranscription={video.transcription_status === 'ended' ? viewTranscription : undefined}
                onTranscribe={transcribeVideo}
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
  videoContainer: {
    backgroundColor: '#000',
    paddingVertical: 20,
    borderRadius: 8,
    marginBottom: 16,
    position: 'relative',
    overflow: 'hidden'
  },
  videoPlayer: {
    width: '100%',
    aspectRatio: 16 / 9,
  },
  videoPlaceholder: {
    width: '100%',
    aspectRatio: 16 / 9,
    backgroundColor: '#222',
    justifyContent: 'center',
    alignItems: 'center',
  },
  placeholderText: {
    color: '#cccccc',
    marginTop: 10,
    textAlign: 'center',
  },
  loadingOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 10,
  },
  loadingText: {
    marginTop: 10,
    textAlign: 'center',
  },
  videoTitle: {
    color: '#fff',
    padding: 10,
    fontSize: 16,
    textAlign: 'center',
    fontWeight: '500',
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
    marginBottom: 12,
  },
  sortLabel: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  sortButtons: {
    flexDirection: 'row',
  },
  sortButton: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 4,
    marginRight: 8,
    borderWidth: 1,
  },
  activeSortButton: {
    borderWidth: 1,
  },
  sortButtonText: {
  },
  activeSortButtonText: {
    color: '#fff',
    fontWeight: '500',
  },
  videoListContainer: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
  },
  listTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 12,
  },
  videosList: {
    flex: 1,
  },
  videosListContent: {
    paddingBottom: 12,
  },
  centerLoading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
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

export default VideosScreen;

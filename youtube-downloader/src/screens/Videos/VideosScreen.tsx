
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
  Dimensions
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Video as VideoPlayer } from 'expo-av';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fetchVideos, fetchVideoStream, fetchTranscription } from '../../services/api';
import { Video } from '../../types';
import VideoItem from '../../components/VideoItem';
import TranscriptionModal from '../../components/TranscriptionModal';
import StatusMessage from '../../components/StatusMessage';
import { theme } from '../../styles/theme';
import { useAuth } from '../../context/AuthContext';

const { width } = Dimensions.get('window');

enum SortOption {
  NONE = 'none',
  TITLE = 'title',
  DATE = 'date'
}

const VideosScreen: React.FC = () => {
  const { authState, login } = useAuth();
  const videoPlayerRef = useRef<VideoPlayer>(null);
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
      } else {
        const fetchedVideos = await fetchVideos(sortBy);
        setVideos(fetchedVideos);
        filterVideos(fetchedVideos, searchQuery);
        cacheVideos(fetchedVideos, sortBy);
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
  
  // Função para reproduzir vídeo
  const playVideo = async (video: Video) => {
    try {
      if (!authState.isAuthenticated) {
        await login();
      }
      
      if (currentVideoId === video.id && currentVideoUri) {
        // Já está carregado, apenas reproduz
        if (videoPlayerRef.current) {
          await videoPlayerRef.current.playAsync();
        }
        return;
      }
      
      setIsPlayerLoading(true);
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
  };
  
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
    <View style={styles.container}>
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
            <ActivityIndicator size="large" color={theme.colors.primary} />
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
      
      <View style={styles.controlsContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Digite para buscar vídeos..."
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
        
        <Text style={styles.sortLabel}>Ordenar por:</Text>
        <View style={styles.sortButtons}>
          <TouchableOpacity
            style={[styles.sortButton, sortBy === SortOption.NONE && styles.activeSortButton]}
            onPress={() => changeSortOrder(SortOption.NONE)}
          >
            <Text style={[styles.sortButtonText, sortBy === SortOption.NONE && styles.activeSortButtonText]}>
              Padrão
            </Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[styles.sortButton, sortBy === SortOption.TITLE && styles.activeSortButton]}
            onPress={() => changeSortOrder(SortOption.TITLE)}
          >
            <Text style={[styles.sortButtonText, sortBy === SortOption.TITLE && styles.activeSortButtonText]}>
              Título
            </Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[styles.sortButton, sortBy === SortOption.DATE && styles.activeSortButton]}
            onPress={() => changeSortOrder(SortOption.DATE)}
          >
            <Text style={[styles.sortButtonText, sortBy === SortOption.DATE && styles.activeSortButtonText]}>
              Data
            </Text>
          </TouchableOpacity>
        </View>
      </View>
      
      <View style={styles.videoListContainer}>
        <Text style={styles.listTitle}>Vídeos Disponíveis</Text>
        
        {isLoading && !refreshing ? (
          <View style={styles.centerLoading}>
            <ActivityIndicator size="large" color={theme.colors.primary} />
            <Text style={styles.loadingText}>Carregando vídeos...</Text>
          </View>
        ) : filteredVideos.length === 0 ? (
          <View style={styles.noResults}>
            <Feather name="inbox" size={48} color="#cccccc" />
            <Text style={styles.noResultsText}>
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
                colors={[theme.colors.primary]}
                tintColor={theme.colors.primary}
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
    backgroundColor: '#fff',
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
    color: theme.colors.textDark,
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
    backgroundColor: theme.colors.backgroundLight,
    padding: 16,
    borderRadius: 8,
    marginBottom: 16,
  },
  searchInput: {
    backgroundColor: '#fff',
    padding: 10,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: theme.colors.border,
    marginBottom: 12,
  },
  sortLabel: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
    color: theme.colors.textDark,
  },
  sortButtons: {
    flexDirection: 'row',
  },
  sortButton: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 4,
    backgroundColor: '#fff',
    marginRight: 8,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  activeSortButton: {
    backgroundColor: theme.colors.secondary,
    borderColor: theme.colors.secondary,
  },
  sortButtonText: {
    color: theme.colors.textDark,
  },
  activeSortButtonText: {
    color: '#fff',
    fontWeight: '500',
  },
  videoListContainer: {
    flex: 1,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 8,
    padding: 12,
    backgroundColor: '#fff',
  },
  listTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 12,
    color: theme.colors.textDark,
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
    color: theme.colors.textDark,
    marginTop: 16,
    textAlign: 'center',
    fontSize: 16,
  },
});

export default VideosScreen;

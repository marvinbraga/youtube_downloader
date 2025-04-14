
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  ScrollView, 
  ActivityIndicator,
  RefreshControl,
  Alert
} from 'react-native';
import { Audio as ExpoAudio } from 'expo-av';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fetchAudios, transcribeAudio, checkTranscriptionStatus, fetchTranscription } from '../../services/api';
import { Audio } from '../../types';
import AudioItem from '../../components/AudioItem';
import TranscriptionModal from '../../components/TranscriptionModal';
import StatusMessage from '../../components/StatusMessage';
import { Feather } from '@expo/vector-icons';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';

const AudioScreen: React.FC = () => {
  const { authState, login } = useAuth();
  const { colors, theme } = useTheme();
  const [audios, setAudios] = useState<Audio[]>([]);
  const [filteredAudios, setFilteredAudios] = useState<Audio[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentAudioId, setCurrentAudioId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    message: string;
    type: 'error' | 'success' | 'info';
  } | null>(null);
  
  // Referência para o player de áudio
  const soundRef = useRef<ExpoAudio.Sound | null>(null);
  const transcriptionCheckTimerRef = useRef<NodeJS.Timeout | null>(null);
  
  // Estado para o modal de transcrição
  const [transcriptionModal, setTranscriptionModal] = useState({
    visible: false,
    title: '',
    content: '',
    isLoading: false,
    itemId: ''
  });
  
  // Função para carregar os áudios
  const loadAudios = useCallback(async () => {
    if (!authState.isAuthenticated) {
      return;
    }
    
    try {
      setIsLoading(true);
      const cachedAudios = await getCachedAudios();
      
      if (cachedAudios) {
        setAudios(cachedAudios);
        filterAudios(cachedAudios, searchQuery);
      } else {
        const fetchedAudios = await fetchAudios();
        
        // Verificamos e atualizamos o status de transcrição para cada áudio
        const processedAudios = checkTranscriptionStatusForAllItems(fetchedAudios);
        
        setAudios(processedAudios);
        filterAudios(processedAudios, searchQuery);
        cacheAudios(processedAudios);
        
        // Iniciar verificação para áudios em transcrição
        startTranscriptionStatusCheck(processedAudios);
      }
    } catch (error) {
      console.error('Erro ao carregar áudios:', error);
      setStatusMessage({
        message: 'Erro ao carregar áudios. Tente novamente.',
        type: 'error'
      });
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  }, [authState.isAuthenticated, searchQuery]);
  
  // Carregar áudios no início
  useEffect(() => {
    if (authState.isAuthenticated) {
      loadAudios();
    } else if (!authState.isLoading) {
      login();
    }
    
    // Limpeza: parar o player e os temporizadores
    return () => {
      stopAudio();
      if (transcriptionCheckTimerRef.current) {
        clearInterval(transcriptionCheckTimerRef.current);
      }
    };
  }, [authState.isAuthenticated, authState.isLoading, login, loadAudios]);
  
  // Função para verificar o status de transcrição para todos os áudios
  const checkTranscriptionStatusForAllItems = (items: Audio[]): Audio[] => {
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
  };
  
  // Funções para cache
  const AUDIO_CACHE_KEY = '@audio_list_cache';
  const CACHE_DURATION = 5 * 60 * 1000; // 5 minutos
  
  const cacheAudios = async (data: Audio[]) => {
    const cache = {
      timestamp: Date.now(),
      data
    };
    await AsyncStorage.setItem(AUDIO_CACHE_KEY, JSON.stringify(cache));
  };
  
  const getCachedAudios = async () => {
    const cache = await AsyncStorage.getItem(AUDIO_CACHE_KEY);
    if (!cache) return null;
    
    const { timestamp, data } = JSON.parse(cache);
    
    if (Date.now() - timestamp > CACHE_DURATION) {
      await AsyncStorage.removeItem(AUDIO_CACHE_KEY);
      return null;
    }
    
    return data;
  };
  
  // Função para filtrar áudios
  const filterAudios = (audioList: Audio[], query: string) => {
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
  };
  
  // Atualizar filtro quando mudar a pesquisa
  useEffect(() => {
    filterAudios(audios, searchQuery);
  }, [searchQuery, audios]);
  
  // Iniciar verificação periódica de transcrições em andamento
  const startTranscriptionStatusCheck = (audiosList: Audio[]) => {
    // Limpar temporizador existente
    if (transcriptionCheckTimerRef.current) {
      clearInterval(transcriptionCheckTimerRef.current);
    }
    
    const audiosInProgress = audiosList.filter(
      audio => audio.transcription_status === 'started'
    );
    
    if (audiosInProgress.length > 0) {
      console.log(`Iniciando verificação para ${audiosInProgress.length} áudios em transcrição`);
      transcriptionCheckTimerRef.current = setInterval(() => {
        audiosInProgress.forEach(audio => {
          checkAudioTranscriptionStatus(audio, false);
        });
      }, 10000); // Verifica a cada 10 segundos
    }
  };
  
  // Verificar status da transcrição
  const checkAudioTranscriptionStatus = async (audio: Audio, showMessages = true) => {
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
      
      const response = await checkTranscriptionStatus(audio.id);
      
      // Se o status mudou, atualiza a interface
      if (response.status !== audio.transcription_status) {
        console.log(`Status da transcrição mudou: ${audio.transcription_status} -> ${response.status}`);
        
        // Atualiza o áudio na lista
        const updatedAudios = audios.map(a => {
          if (a.id === audio.id) {
            return { ...a, transcription_status: response.status };
          }
          return a;
        });
        
        setAudios(updatedAudios);
        filterAudios(updatedAudios, searchQuery);
        cacheAudios(updatedAudios);
        
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
                onPress: () => viewTranscription({ ...audio, transcription_status: 'ended' })
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
          viewTranscription({ ...audio, transcription_status: 'ended' });
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
  
  // Função para reproduzir áudio
  const playAudio = async (audio: Audio) => {
    try {
      if (!authState.isAuthenticated) {
        await login();
      }
      
      // Parar áudio atual se estiver tocando
      await stopAudio();
      
      setCurrentAudioId(audio.id);
      
      // Em um cenário real, isso seria implementado para reproduzir o áudio
      // usando o endpoint correto para streaming
      
      // Como é uma simulação, apenas mostramos uma mensagem
      setStatusMessage({
        message: `Reproduzindo ${audio.name}`,
        type: 'info'
      });
      
      // Atualizar a UI
      setFilteredAudios(prev => 
        prev.map(a => ({...a})) // Forçar atualização da lista
      );
    } catch (error) {
      console.error('Erro ao reproduzir áudio:', error);
      setStatusMessage({
        message: 'Erro ao reproduzir áudio. Tente novamente.',
        type: 'error'
      });
    }
  };
  
  // Função para parar a reprodução do áudio
  const stopAudio = async () => {
    if (soundRef.current) {
      try {
        const status = await soundRef.current.getStatusAsync();
        if (status.isLoaded) {
          await soundRef.current.unloadAsync();
        }
      } catch (error) {
        console.error('Erro ao parar áudio:', error);
      }
      soundRef.current = null;
    }
  };
  
  // Função para transcrever áudio - Ponto de entrada principal da lógica de transcrição
  const transcribeAudioFile = async (audio: Audio) => {
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
  const startTranscription = async (audio: Audio) => {
    try {
      if (!authState.isAuthenticated) {
        await login();
      }
      
      setStatusMessage({
        message: 'Iniciando transcrição de áudio...',
        type: 'info'
      });
      
      const response = await transcribeAudio(audio.id, 'groq', 'pt');
      
      if (response.status === 'processing') {
        setStatusMessage({
          message: 'Transcrição iniciada em segundo plano. Isso pode levar alguns minutos.',
          type: 'success'
        });
        
        // Atualiza o status na interface
        const updatedAudios = audios.map(a => {
          if (a.id === audio.id) {
            return { ...a, transcription_status: 'started' };
          }
          return a;
        });
        
        setAudios(updatedAudios);
        filterAudios(updatedAudios, searchQuery);
        cacheAudios(updatedAudios);
        
        // Inicia verificação periódica do status
        startTranscriptionStatusCheck(updatedAudios);
      } else if (response.status === 'success') {
        setStatusMessage({
          message: 'Transcrição já existe! Carregando visualização...',
          type: 'success'
        });
        
        // Atualiza o status na interface
        const updatedAudios = audios.map(a => {
          if (a.id === audio.id) {
            return { ...a, transcription_status: 'ended' };
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
      console.error('Erro:', error);
      setStatusMessage({
        message: 'Erro ao transcrever áudio. Tente novamente.',
        type: 'error'
      });
    }
  };
  
  // Função para visualizar transcrição
  const viewTranscription = async (audio: Audio) => {
    try {
      if (!authState.isAuthenticated) {
        await login();
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
        <Text style={[styles.listTitle, { color: colors.text.primary }]}>Áudios Disponíveis</Text>
        
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
            {filteredAudios.map((audio) => (
              <AudioItem
                key={audio.id}
                audio={audio}
                isActive={currentAudioId === audio.id}
                onPress={() => setCurrentAudioId(audio.id)}
                onPlay={playAudio}
                onTranscribe={transcribeAudioFile}
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
  listTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 12,
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

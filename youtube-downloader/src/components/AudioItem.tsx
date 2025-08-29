
import React, { useEffect, useRef, memo, useMemo, useCallback } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Animated } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Audio } from '../types';
import { useTheme } from '../context/ThemeContext';
import { AudioPlayerAdapter } from './AudioPlayer/AudioPlayerAdapter';

interface AudioItemProps {
  audio: Audio;
  isActive: boolean;
  isHighlighted?: boolean;
  onPress: (audio: Audio) => void;
  onPlay: (audio: Audio) => void;
  onTranscribe: (audio: Audio) => void;
  onCancel?: (audio: Audio) => void;
  onRetry?: (audio: Audio) => void;
  showAudioPlayer?: boolean;
}

interface TranscriptionStatusConfig {
  badgeText?: string;
  badgeClass?: string;
  badgeIcon?: string;
  buttonClass?: string;
  buttonIcon?: string;
  buttonText?: string;
  isDisabled?: boolean;
}

const AudioItem: React.FC<AudioItemProps> = memo(({
  audio,
  isActive,
  isHighlighted = false,
  onPress,
  onPlay,
  onTranscribe,
  onCancel,
  onRetry,
  showAudioPlayer = false
}) => {
  const { colors, theme } = useTheme();
  const spinValue = useRef(new Animated.Value(0)).current;
  const animationRef = useRef<Animated.CompositeAnimation | null>(null);
  const isMountedRef = useRef(true);
  
  // Cleanup geral quando o componente é desmontado
  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      
      // Garantir que a animação seja limpa na desmontagem
      if (animationRef.current) {
        animationRef.current.stop();
        animationRef.current = null;
      }
    };
  }, []);

  // Memoizar funções de formatação para evitar recriação desnecessária
  const formatDate = useCallback((dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  }, []);

  const formatFileSize = useCallback((bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)).toString());
    return Math.round(bytes / Math.pow(1024, i)) + ' ' + sizes[i];
  }, []);
  
  // Memoizar configurações de status para evitar recálculos desnecessários
  const statusConfig = useMemo((): TranscriptionStatusConfig => {
    const transcriptionStatus = audio.transcription_status || "none";
    
    switch (transcriptionStatus) {
      case "started":
        return {
          badgeText: "Transcrevendo",
          badgeClass: "warning",
          badgeIcon: "loader",
          buttonClass: "warning",
          buttonIcon: "loader",
          buttonText: "Transcrevendo...",
          isDisabled: true
        };
      case "ended":
        return {
          badgeText: "Transcrito",
          badgeClass: "success",
          badgeIcon: "check",
          buttonClass: "warning",
          buttonIcon: "file-text",
          buttonText: "Ver Transcrição",
          isDisabled: false
        };
      case "error":
        return {
          badgeText: "Erro",
          badgeClass: "error",
          badgeIcon: "alert-circle",
          buttonClass: "danger",
          buttonIcon: "refresh-cw",
          buttonText: "Tentar Novamente"
        };
      default:
        return {
          buttonClass: "success",
          buttonIcon: "mic",
          buttonText: "Transcrever"
        };
    }
  }, [audio.transcription_status]);
  
  // Memoizar cores para evitar recálculos a cada render
  const badgeColor = useMemo(() => {
    switch (statusConfig.badgeClass) {
      case 'warning':
        return colors.warning;
      case 'success':
        return colors.success;
      case 'error':
        return colors.error;
      default:
        return colors.info;
    }
  }, [statusConfig.badgeClass, colors]);
  
  // Verifica se deve animar - anima tanto o badge quanto o botão quando está transcrevendo
  const isTranscribing = audio.transcription_status === 'started';
  
  // Estados de download memoizados
  const downloadStates = useMemo(() => ({
    isDownloading: audio.download_status === 'downloading' || audio.download_status === 'pending',
    downloadError: audio.download_status === 'error',
    isReady: audio.download_status === 'ready' || !audio.download_status,
    isNotReady: !audio.download_status || (audio.download_status !== 'ready')
  }), [audio.download_status]);
  
  // Estados dos botões memoizados
  const buttonStates = useMemo(() => {
    const canPlay = downloadStates.isReady && !isTranscribing;
    const canTranscribe = downloadStates.isReady && !isTranscribing;
    const showCancelButton = downloadStates.isDownloading && !!onCancel;
    const showRetryButton = downloadStates.downloadError && !!onRetry;
    
    return { canPlay, canTranscribe, showCancelButton, showRetryButton };
  }, [downloadStates, isTranscribing, onCancel, onRetry]);
  
  const buttonColor = useMemo(() => {
    // Se não pode transcrever ou está desabilitado, usar cor de desabilitado
    if (!buttonStates.canTranscribe || statusConfig.isDisabled) {
      return '#6c757d';
    }
    
    switch (statusConfig.buttonClass) {
      case 'warning':
        return colors.warning;
      case 'success':
        return colors.success;
      case 'danger':
        return colors.error;
      default:
        return colors.success;
    }
  }, [statusConfig.buttonClass, statusConfig.isDisabled, buttonStates.canTranscribe, colors]);
  
  // Animação otimizada - só executa quando necessário
  useEffect(() => {
    if (isTranscribing && !animationRef.current) {
      // Só inicia nova animação se não houver uma rodando
      animationRef.current = Animated.loop(
        Animated.timing(spinValue, {
          toValue: 1,
          duration: 2000, // Aumentar duração para suavizar e reduzir CPU
          useNativeDriver: true,
        }),
        { iterations: -1 }
      );
      animationRef.current.start();
    } else if (!isTranscribing && animationRef.current) {
      // Para animação quando não necessária
      animationRef.current.stop();
      animationRef.current = null;
      spinValue.setValue(0);
    }
  }, [isTranscribing, spinValue]);

  // Memoizar interpolação da animação
  const spin = useMemo(() => spinValue.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  }), [spinValue]);
  
  // Estados de download e botões já memoizados acima
  const { isDownloading, downloadError, isReady } = downloadStates;
  const { canPlay, canTranscribe, showCancelButton, showRetryButton } = buttonStates;
  
  return (
    <TouchableOpacity
      style={[
        styles.container,
        { 
          backgroundColor: colors.background.secondary,
          borderLeftWidth: 4,
          borderLeftColor: 'transparent',
          ...theme.shadows.sm
        },
        isActive && [
          styles.activeContainer,
          { 
            borderLeftColor: colors.primary,
            backgroundColor: colors.tabActiveBg,
          }
        ],
        isHighlighted && [
          styles.highlightedContainer,
          theme.states.item.highlighted
        ]
      ]}
      onPress={() => onPress(audio)}
      activeOpacity={0.7}
    >
      {/* Overlay de status - prioriza download sobre erro */}
      {isDownloading && (
        <View style={[styles.downloadOverlay, { backgroundColor: colors.background.primary + 'E6' }]}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={[styles.downloadText, { color: colors.text.primary }]}>
            {audio.download_status === 'pending' ? 'Preparando download...' : 'Baixando áudio...'}
          </Text>
          
          {/* Barra de progresso */}
          {audio.download_progress !== undefined && audio.download_progress > 0 && (
            <View style={styles.progressContainer}>
              <View style={[styles.progressBar, { backgroundColor: colors.border }]}>
                <View 
                  style={[
                    styles.progressFill,
                    { 
                      backgroundColor: colors.primary,
                      width: `${audio.download_progress}%`
                    }
                  ]}
                />
              </View>
              <Text style={[styles.progressText, { color: colors.text.secondary }]}>
                {audio.download_progress}%
              </Text>
            </View>
          )}
        </View>
      )}
      
      {/* Indicador de erro no download - só mostra se não está baixando */}
      {!isDownloading && downloadError && (
        <View style={[styles.errorOverlay, { backgroundColor: colors.error + '20' }]}>
          <Feather name="alert-circle" size={24} color={colors.error} />
          <Text style={[styles.errorText, { color: colors.error }]}>
            Erro no download
          </Text>
          {audio.download_error && (
            <Text style={[styles.errorDetail, { color: colors.text.secondary }]} numberOfLines={2}>
              {audio.download_error}
            </Text>
          )}
        </View>
      )}
      
      <View style={styles.content} pointerEvents="box-none">
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text.primary }]} numberOfLines={1}>
            {audio.name}
          </Text>
          
          {statusConfig.badgeText && (
            <View style={[styles.badge, { backgroundColor: badgeColor }]}>
              {isTranscribing ? (
                <Animated.View style={{ transform: [{ rotate: spin }] }}>
                  <Feather 
                    name="loader" 
                    size={12} 
                    color="white" 
                  />
                </Animated.View>
              ) : (
                <Feather 
                  name={(statusConfig.badgeIcon as any) || 'info'} 
                  size={12} 
                  color="white" 
                />
              )}
              <Text style={styles.badgeText}>{statusConfig.badgeText}</Text>
            </View>
          )}
        </View>
        
        <View style={styles.info}>
          <Text style={[styles.infoText, { color: colors.text.secondary }]} numberOfLines={1}>
            Caminho: {audio.path}
          </Text>
          <Text style={[styles.infoText, { color: colors.text.secondary }]}>
            Modificado em: {formatDate(audio.modified_date)}
          </Text>
          <Text style={[styles.infoText, { color: colors.text.secondary }]}>
            Tamanho: {formatFileSize(audio.size)}
          </Text>
        </View>
        
        {/* Audio Player ou Botões de Ação */}
        {showAudioPlayer && isReady ? (
          <View style={styles.audioPlayerContainer}>
            <AudioPlayerAdapter
              audio={audio}
              onPlay={() => console.log('Advanced player started:', audio.name)}
              onPause={() => console.log('Advanced player paused:', audio.name)}
              onStop={() => console.log('Advanced player stopped:', audio.name)}
              onError={(error) => console.error('Erro no player de áudio:', error)}
              onEnded={() => console.log('Audio ended:', audio.name)}
              showTitle={false}
              compact={false}
              showProgress={true}
              disabled={!canPlay}
            />
          </View>
        ) : (
          <View style={styles.actions} pointerEvents="box-none">
            {/* Botão de Reproduzir/Pausar */}
            <TouchableOpacity 
              style={[
                styles.actionButton,
                { 
                  backgroundColor: isActive ? colors.primary : colors.background.primary,
                  borderColor: isActive ? colors.primary : colors.border 
                },
                !canPlay && styles.disabledButton
              ]}
              onPress={() => onPlay(audio)}
              disabled={!canPlay}
            >
              <Feather 
                name={isActive ? "pause" : "play"} 
                size={16} 
                color={!canPlay ? colors.text.secondary : isActive ? 'white' : colors.secondary} 
              />
              <Text style={[
                styles.actionButtonText, 
                { 
                  color: !canPlay ? colors.text.secondary : isActive ? 'white' : colors.secondary 
                }
              ]}>
                {isActive ? 'Pausar' : 'Reproduzir'}
              </Text>
            </TouchableOpacity>
            
            {/* Botão de Transcrição */}
            <TouchableOpacity 
              style={[
                styles.actionButton, 
                { 
                  backgroundColor: buttonColor, 
                  borderColor: buttonColor 
                },
                (!canTranscribe || statusConfig.isDisabled) && [
                  styles.disabledButton,
                  { backgroundColor: '#6c757d', borderColor: '#6c757d' }
                ]
              ]}
              onPress={() => onTranscribe(audio)}
              disabled={!canTranscribe || statusConfig.isDisabled}
            >
              {isTranscribing ? (
                <Animated.View style={{ transform: [{ rotate: spin }] }}>
                  <Feather 
                    name="loader" 
                    size={16} 
                    color="white" 
                  />
                </Animated.View>
              ) : (
                <Feather 
                  name={(statusConfig.buttonIcon as any) || 'mic'} 
                  size={16} 
                  color="white" 
                />
              )}
              <Text style={styles.transcriptionButtonText}>
                {statusConfig.buttonText || 'Transcrever'}
              </Text>
            </TouchableOpacity>
            
            {/* Botão de cancelar download */}
            {showCancelButton && (
              <TouchableOpacity
                style={[
                  styles.actionButton,
                  { 
                    backgroundColor: colors.error,
                    borderColor: colors.error
                  }
                ]}
                onPress={() => onCancel!(audio)}
              >
                <Feather name="x" size={16} color="white" />
                <Text style={[styles.actionButtonText, { color: 'white' }]}>Cancelar</Text>
              </TouchableOpacity>
            )}
            
            {/* Botão de tentar novamente */}
            {showRetryButton && (
              <TouchableOpacity
                style={[
                  styles.actionButton,
                  { 
                    backgroundColor: colors.warning,
                    borderColor: colors.warning
                  }
                ]}
                onPress={() => onRetry!(audio)}
              >
                <Feather name="refresh-cw" size={16} color="white" />
                <Text style={[styles.actionButtonText, { color: 'white' }]}>Tentar Novamente</Text>
              </TouchableOpacity>
            )}
          </View>
        )}
      </View>
    </TouchableOpacity>
  );
});

const styles = StyleSheet.create({
  container: {
    marginBottom: 12,
    padding: 12,
    borderRadius: 8,
  },
  activeContainer: {},
  highlightedContainer: {},
  content: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    flex: 1,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 12,
    marginLeft: 8,
  },
  badgeText: {
    color: 'white',
    fontSize: 12,
    fontWeight: '500',
    marginLeft: 4,
  },
  info: {
    marginBottom: 12,
  },
  infoText: {
    fontSize: 14,
    marginBottom: 4,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-start',
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 4,
    marginRight: 8,
    borderWidth: 1,
  },
  actionButtonText: {
    marginLeft: 6,
    fontSize: 14,
    fontWeight: '500',
  },
  transcriptionButtonText: {
    color: 'white',
    marginLeft: 6,
    fontSize: 14,
    fontWeight: '500',
  },
  animatedIcon: {
    // Esta propriedade será usada para implementar animação posteriormente
  },
  downloadOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 8,
    zIndex: 1,
  },
  downloadText: {
    marginTop: 12,
    fontSize: 16,
    fontWeight: '600',
  },
  progressContainer: {
    marginTop: 16,
    width: '80%',
    alignItems: 'center',
  },
  progressBar: {
    width: '100%',
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 3,
    minWidth: 2,
  },
  progressText: {
    marginTop: 8,
    fontSize: 14,
    fontWeight: '600',
  },
  errorOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 8,
    zIndex: 1,
    padding: 16,
  },
  errorText: {
    marginTop: 8,
    fontSize: 16,
    fontWeight: '600',
  },
  errorDetail: {
    marginTop: 4,
    fontSize: 12,
    textAlign: 'center',
  },
  disabledButton: {
    opacity: 0.5,
  },
  audioPlayerContainer: {
    marginTop: 8,
  }
});

// Comparação personalizada para React.memo - só re-renderiza se propriedades relevantes mudaram
const arePropsEqual = (prevProps: AudioItemProps, nextProps: AudioItemProps) => {
  return (
    prevProps.audio.id === nextProps.audio.id &&
    prevProps.audio.transcription_status === nextProps.audio.transcription_status &&
    prevProps.audio.download_status === nextProps.audio.download_status &&
    prevProps.audio.download_progress === nextProps.audio.download_progress &&
    prevProps.isActive === nextProps.isActive &&
    prevProps.isHighlighted === nextProps.isHighlighted &&
    prevProps.showAudioPlayer === nextProps.showAudioPlayer
  );
};

export default memo(AudioItem, arePropsEqual);

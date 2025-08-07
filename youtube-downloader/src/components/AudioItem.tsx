
import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Animated } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Audio } from '../types';
import { useTheme } from '../context/ThemeContext';

interface AudioItemProps {
  audio: Audio;
  isActive: boolean;
  isHighlighted?: boolean;
  onPress: (audio: Audio) => void;
  onPlay: (audio: Audio) => void;
  onTranscribe: (audio: Audio) => void;
  onCancel?: (audio: Audio) => void;
  onRetry?: (audio: Audio) => void;
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

const AudioItem: React.FC<AudioItemProps> = ({
  audio,
  isActive,
  isHighlighted = false,
  onPress,
  onPlay,
  onTranscribe,
  onCancel,
  onRetry
}) => {
  const { colors, theme } = useTheme();
  const spinValue = useRef(new Animated.Value(0)).current;

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  const formatFileSize = (bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)).toString());
    return Math.round(bytes / Math.pow(1024, i)) + ' ' + sizes[i];
  };
  
  // Definir configurações baseadas no status de transcrição
  const getTranscriptionStatusConfig = (): TranscriptionStatusConfig => {
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
          buttonText: "Ver Transcrição"
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
  };

  const statusConfig = getTranscriptionStatusConfig();
  
  const getBadgeColor = () => {
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
  };
  
  const getButtonColor = () => {
    if (statusConfig.isDisabled) return '#6c757d';
    
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
  };
  
  // Verifica se deve animar - anima tanto o badge quanto o botão quando está transcrevendo
  const isTranscribing = audio.transcription_status === 'started';
  
  // Animação de rotação para o ícone de loading
  useEffect(() => {
    if (isTranscribing) {
      const spinAnimation = Animated.loop(
        Animated.timing(spinValue, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
        { iterations: -1 } // Loop infinito explícito
      );
      spinAnimation.start();
      
      return () => {
        spinAnimation.stop();
        spinValue.setValue(0);
      };
    } else {
      spinValue.setValue(0);
    }
  }, [isTranscribing, spinValue]);

  const spin = spinValue.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });
  
  // Verificar status de download
  const isDownloading = audio.download_status === 'downloading' || audio.download_status === 'pending';
  const downloadError = audio.download_status === 'error';
  const isNotReady = audio.download_status && audio.download_status !== 'ready';
  
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
    >
      {/* Indicador de download em andamento */}
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
      
      {/* Indicador de erro no download */}
      {downloadError && (
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
      
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text.primary }]} numberOfLines={1}>
            {audio.name}
          </Text>
          
          {statusConfig.badgeText && (
            <View style={[styles.badge, { backgroundColor: getBadgeColor() }]}>
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
        
        <View style={styles.actions}>
          <TouchableOpacity 
            style={[
              styles.actionButton,
              { 
                backgroundColor: isActive ? colors.primary : colors.background.primary,
                borderColor: isActive ? colors.primary : colors.border 
              },
              isNotReady && styles.disabledButton
            ]}
            onPress={() => onPlay(audio)}
            disabled={isNotReady}
          >
            <Feather 
              name={isActive ? "pause" : "play"} 
              size={16} 
              color={isNotReady ? colors.text.secondary : isActive ? 'white' : colors.secondary} 
            />
            <Text style={[
              styles.actionButtonText, 
              { 
                color: isNotReady ? colors.text.secondary : isActive ? 'white' : colors.secondary 
              }
            ]}>
              {isActive ? 'Pausar' : 'Reproduzir'}
            </Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[
              styles.actionButton, 
              { 
                backgroundColor: getButtonColor(), 
                borderColor: getButtonColor() 
              },
              (statusConfig.isDisabled || isNotReady) && theme.states.button.disabled
            ]}
            onPress={() => onTranscribe(audio)}
            disabled={statusConfig.isDisabled || isNotReady}
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
          {isDownloading && onCancel && (
            <TouchableOpacity
              style={[
                styles.actionButton,
                { 
                  backgroundColor: colors.error,
                  borderColor: colors.error
                }
              ]}
              onPress={() => onCancel(audio)}
            >
              <Feather name="x" size={16} color="white" />
              <Text style={[styles.actionButtonText, { color: 'white' }]}>Cancelar</Text>
            </TouchableOpacity>
          )}
          
          {/* Botão de retry */}
          {downloadError && onRetry && (
            <TouchableOpacity
              style={[
                styles.actionButton,
                { 
                  backgroundColor: colors.warning,
                  borderColor: colors.warning
                }
              ]}
              onPress={() => onRetry(audio)}
            >
              <Feather name="refresh-cw" size={16} color="white" />
              <Text style={[styles.actionButtonText, { color: 'white' }]}>Tentar Novamente</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    </TouchableOpacity>
  );
};

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
  }
});

export default AudioItem;

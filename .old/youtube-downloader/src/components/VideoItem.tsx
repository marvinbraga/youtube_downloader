
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Video } from '../types';
import { useTheme } from '../context/ThemeContext';

interface VideoItemProps {
  video: Video;
  isActive: boolean;
  onPress: (video: Video) => void;
  onPlay: (video: Video) => void;
  onViewTranscription?: (video: Video) => void;
  onTranscribe?: (video: Video) => void; // Nova prop para transcrição
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

const VideoItem: React.FC<VideoItemProps> = ({
  video,
  isActive,
  onPress,
  onPlay,
  onViewTranscription,
  onTranscribe
}) => {
  const { colors, theme } = useTheme();

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
    const transcriptionStatus = video.transcription_status || "none";
    
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
  
  // Função para determinar o manipulador de transcrição
  const handleTranscriptionAction = () => {
    const transcriptionStatus = video.transcription_status || "none";
    
    if (transcriptionStatus === "ended" && onViewTranscription) {
      onViewTranscription(video);
    } else if (onTranscribe) {
      onTranscribe(video);
    }
  };
  
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
        ]
      ]}
      onPress={() => onPress(video)}
    >
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text.primary }]} numberOfLines={1}>
            {video.name}
          </Text>
          
          {statusConfig.badgeText && (
            <View style={[styles.badge, { backgroundColor: getBadgeColor() }]}>
              <Feather 
                name={(statusConfig.badgeIcon as any) || 'info'} 
                size={12} 
                color="white" 
              />
              <Text style={styles.badgeText}>{statusConfig.badgeText}</Text>
            </View>
          )}
        </View>
        
        <View style={styles.info}>
          <Text style={[styles.infoText, { color: colors.text.secondary }]} numberOfLines={1}>
            Caminho: {video.path}
          </Text>
          <Text style={[styles.infoText, { color: colors.text.secondary }]}>
            Modificado em: {formatDate(video.modified_date)}
          </Text>
          <Text style={[styles.infoText, { color: colors.text.secondary }]}>
            Tamanho: {formatFileSize(video.size)}
          </Text>
        </View>
        
        <View style={styles.actions}>
          <TouchableOpacity 
            style={[
              styles.actionButton,
              { 
                backgroundColor: colors.background.primary,
                borderColor: colors.border
              }
            ]}
            onPress={() => onPlay(video)}
          >
            <Feather name="play" size={16} color={colors.secondary} />
            <Text style={[styles.actionButtonText, { color: colors.secondary }]}>Reproduzir</Text>
          </TouchableOpacity>
          
          {/* Botão de transcrição (para qualquer status) */}
          {(onTranscribe || onViewTranscription) && (
            <TouchableOpacity 
              style={[
                styles.actionButton, 
                { 
                  backgroundColor: getButtonColor(), 
                  borderColor: getButtonColor() 
                },
                statusConfig.isDisabled && theme.states.button.disabled
              ]}
              onPress={handleTranscriptionAction}
              disabled={statusConfig.isDisabled}
            >
              <Feather 
                name={(statusConfig.buttonIcon as any) || 'mic'} 
                size={16} 
                color="white" 
              />
              <Text style={styles.transcriptionButtonText}>
                {statusConfig.buttonText || 'Transcrever'}
              </Text>
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
  activeContainer: {
  },
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
});

export default VideoItem;

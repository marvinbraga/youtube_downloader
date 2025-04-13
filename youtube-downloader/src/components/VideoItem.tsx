
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Video } from '../types';
import { theme } from '../styles/theme';

interface VideoItemProps {
  video: Video;
  isActive: boolean;
  onPress: (video: Video) => void;
  onPlay: (video: Video) => void;
  onViewTranscription?: (video: Video) => void;
}

interface TranscriptionStatusConfig {
  badgeText?: string;
  badgeClass?: string;
  badgeIcon?: string;
  buttonClass?: string;
  buttonIcon?: string;
  buttonText?: string;
}

const VideoItem: React.FC<VideoItemProps> = ({
  video,
  isActive,
  onPress,
  onPlay,
  onViewTranscription
}) => {
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
          buttonText: "Transcrevendo..."
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
        return {};
    }
  };

  const statusConfig = getTranscriptionStatusConfig();
  
  const getBadgeColor = () => {
    switch (statusConfig.badgeClass) {
      case 'warning':
        return theme.colors.warning;
      case 'success':
        return theme.colors.tertiary;
      case 'error':
        return theme.colors.error;
      default:
        return theme.colors.info;
    }
  };
  
  return (
    <TouchableOpacity
      style={[
        styles.container,
        isActive && styles.activeContainer
      ]}
      onPress={() => onPress(video)}
    >
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title} numberOfLines={1}>
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
          <Text style={styles.infoText} numberOfLines={1}>Caminho: {video.path}</Text>
          <Text style={styles.infoText}>Modificado em: {formatDate(video.modified_date)}</Text>
          <Text style={styles.infoText}>Tamanho: {formatFileSize(video.size)}</Text>
        </View>
        
        <View style={styles.actions}>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => onPlay(video)}
          >
            <Feather name="play" size={16} color={theme.colors.secondary} />
            <Text style={styles.actionButtonText}>Reproduzir</Text>
          </TouchableOpacity>
          
          {video.transcription_status === "ended" && onViewTranscription && (
            <TouchableOpacity 
              style={[styles.actionButton, styles.transcriptionButton]}
              onPress={() => onViewTranscription(video)}
            >
              <Feather name="file-text" size={16} color="white" />
              <Text style={styles.transcriptionButtonText}>Ver Transcrição</Text>
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
    backgroundColor: theme.colors.backgroundLight,
    borderLeftWidth: 4,
    borderLeftColor: 'transparent',
    ...theme.shadows.sm
  },
  activeContainer: {
    borderLeftColor: theme.colors.primary,
    backgroundColor: theme.colors.tabActiveBg,
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
    color: theme.colors.textDark,
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
    color: theme.colors.textDark,
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
    backgroundColor: '#fff',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 4,
    marginRight: 8,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  actionButtonText: {
    color: theme.colors.secondary,
    marginLeft: 6,
    fontSize: 14,
    fontWeight: '500',
  },
  transcriptionButton: {
    backgroundColor: theme.colors.warning,
    borderColor: theme.colors.warning,
  },
  transcriptionButtonText: {
    color: 'white',
    marginLeft: 6,
    fontSize: 14,
    fontWeight: '500',
  },
});

export default VideoItem;

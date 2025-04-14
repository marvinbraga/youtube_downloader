
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Audio } from '../types';
import { theme } from '../styles/theme';

interface AudioItemProps {
  audio: Audio;
  isActive: boolean;
  isHighlighted?: boolean;
  onPress: (audio: Audio) => void;
  onPlay: (audio: Audio) => void;
  onTranscribe: (audio: Audio) => void;
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
  onTranscribe
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
        return theme.colors.warning;
      case 'success':
        return theme.colors.tertiary;
      case 'error':
        return theme.colors.error;
      default:
        return theme.colors.info;
    }
  };
  
  const getButtonColor = () => {
    if (statusConfig.isDisabled) return '#6c757d';
    
    switch (statusConfig.buttonClass) {
      case 'warning':
        return theme.colors.warning;
      case 'success':
        return theme.colors.tertiary;
      case 'danger':
        return theme.colors.error;
      default:
        return theme.colors.tertiary;
    }
  };
  
  // Verifica se o ícone está animado (para o caso de loading)
  const isAnimatedIcon = statusConfig.buttonIcon === 'loader';
  
  return (
    <TouchableOpacity
      style={[
        styles.container,
        isActive && styles.activeContainer,
        isHighlighted && styles.highlightedContainer
      ]}
      onPress={() => onPress(audio)}
    >
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title} numberOfLines={1}>
            {audio.name}
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
          <Text style={styles.infoText} numberOfLines={1}>Caminho: {audio.path}</Text>
          <Text style={styles.infoText}>Modificado em: {formatDate(audio.modified_date)}</Text>
          <Text style={styles.infoText}>Tamanho: {formatFileSize(audio.size)}</Text>
        </View>
        
        <View style={styles.actions}>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => onPlay(audio)}
          >
            <Feather name="play" size={16} color={theme.colors.secondary} />
            <Text style={styles.actionButtonText}>Reproduzir</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[
              styles.actionButton, 
              { backgroundColor: getButtonColor(), borderColor: getButtonColor() },
              statusConfig.isDisabled && styles.disabledButton
            ]}
            onPress={() => onTranscribe(audio)}
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
    borderLeftColor: 'transparent'
  },
  activeContainer: {
    borderLeftColor: theme.colors.primary,
    backgroundColor: theme.colors.tabActiveBg,
  },
  highlightedContainer: {
    backgroundColor: 'rgba(255, 215, 0, 0.3)',
    borderLeftColor: 'goldenrod',
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
  transcriptionButtonText: {
    color: 'white',
    marginLeft: 6,
    fontSize: 14,
    fontWeight: '500',
  },
  disabledButton: {
    opacity: 0.65,
  },
  animatedIcon: {
    // Esta propriedade será usada para implementar animação posteriormente
  }
});

export default AudioItem;

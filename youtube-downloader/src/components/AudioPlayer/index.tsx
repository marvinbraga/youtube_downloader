import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, Animated } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Audio } from '../../types';
import { useAudioPlayer } from './useAudioPlayer';
import { PlayerControls } from './PlayerControls';
import { ProgressBar } from './ProgressBar';
import { TimeDisplay } from './TimeDisplay';
import { getPlayerTheme, getResponsiveSizes, animations } from './themes';

// Adaptação de tipos para compatibilidade com o sistema de temas existente
interface Theme {
  colors: {
    primary: string;
    onPrimary: string;
    surface: string;
    onSurface: string;
    background: string;
    outline: string;
    inverseSurface: string;
    inverseOnSurface: string;
    errorContainer: string;
    onErrorContainer: string;
    shadow: string;
  };
}

export interface AudioPlayerProps {
  audio: Audio;
  onPlay?: (audio: Audio) => void;
  onPause?: (audio: Audio) => void;
  onStop?: (audio: Audio) => void;
  onError?: (error: Error, audio: Audio) => void;
  onEnded?: (audio: Audio) => void;
  theme: Theme;
  apiBaseUrl?: string;
  compact?: boolean;
  showTitle?: boolean;
  showProgress?: boolean;
  disabled?: boolean;
  isDarkMode?: boolean;
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({
  audio,
  onPlay,
  onPause,
  onStop,
  onError,
  onEnded,
  theme,
  apiBaseUrl = 'http://localhost:8000',
  compact = false,
  showTitle = false,
  showProgress = false,
  disabled = false,
  isDarkMode = false,
}) => {
  const [authenticatedUrl, setAuthenticatedUrl] = useState<string | null>(null);
  const [fadeAnim] = useState(new Animated.Value(0));
  
  // Obter tema e tamanhos responsivos
  const playerColors = getPlayerTheme(isDarkMode);
  const responsiveSizes = getResponsiveSizes();

  // Gerar URL com token de autenticação
  useEffect(() => {
    const generateAuthenticatedUrl = async () => {
      try {
        const token = await AsyncStorage.getItem('@auth_token');
        if (token) {
          const url = `${apiBaseUrl}/audios/${audio.id}/stream/?token=${encodeURIComponent(token)}`;
          setAuthenticatedUrl(url);
          console.log('🎵 Generated authenticated URL:', url);
        } else {
          console.error('🚨 No auth token available');
        }
      } catch (error) {
        console.error('🚨 Error generating authenticated URL:', error);
      }
    };

    generateAuthenticatedUrl();
  }, [audio.id, apiBaseUrl]);
  
  // Animação de entrada
  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: animations.normal,
      useNativeDriver: true,
    }).start();
  }, []);

  const { state, play, pause, stop, seek } = useAudioPlayer(authenticatedUrl || '');

  const handlePlay = useCallback(async () => {
    try {
      await play();
      onPlay?.(audio);
    } catch (error) {
      onError?.(error as Error, audio);
    }
  }, [play, audio, onPlay, onError]);

  const handlePause = useCallback(async () => {
    try {
      await pause();
      onPause?.(audio);
    } catch (error) {
      onError?.(error as Error, audio);
    }
  }, [pause, audio, onPause, onError]);

  const handleStop = useCallback(async () => {
    try {
      await stop();
      onStop?.(audio);
    } catch (error) {
      onError?.(error as Error, audio);
    }
  }, [stop, audio, onStop, onError]);

  const handleSeek = useCallback(async (time: number) => {
    try {
      await seek(time);
    } catch (error) {
      onError?.(error as Error, audio);
    }
  }, [seek, audio, onError]);

  const containerPadding = compact ? responsiveSizes.padding - 4 : responsiveSizes.padding;
  const borderRadius = compact ? responsiveSizes.borderRadius - 2 : responsiveSizes.borderRadius;

  return (
    <Animated.View
      style={{
        backgroundColor: playerColors.surface,
        borderRadius,
        padding: containerPadding,
        marginVertical: compact ? 2 : 4,
        shadowColor: playerColors.shadowDark,
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: isDarkMode ? 0.3 : 0.1,
        shadowRadius: 4,
        elevation: 3,
        opacity: fadeAnim,
        transform: [
          {
            scale: fadeAnim.interpolate({
              inputRange: [0, 1],
              outputRange: [0.95, 1],
            }),
          },
        ],
      }}
    >
      {/* Title Row */}
      {showTitle && (
        <View
          style={{
            marginBottom: 8,
          }}
        >
          <Text
            numberOfLines={1}
            style={{
              color: playerColors.textPrimary,
              fontSize: compact ? responsiveSizes.fontSize - 2 : responsiveSizes.fontSize,
              fontWeight: '600',
            }}
          >
            {audio.name}
          </Text>
        </View>
      )}

      {/* Header Row - Controls and Time */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: compact ? 8 : 12,
        }}
      >
        <PlayerControls
          isPlaying={state.isPlaying}
          isLoading={state.isLoading}
          onPlay={handlePlay}
          onPause={handlePause}
          onStop={handleStop}
          theme={theme}
          compact={compact}
          disabled={disabled}
        />
        
        <TimeDisplay
          currentTime={state.currentTime}
          duration={state.duration}
          theme={theme}
          compact={compact}
          showProgress={showProgress}
        />
      </View>

      {/* Progress Bar */}
      <ProgressBar
        currentTime={state.currentTime}
        duration={state.duration}
        buffered={state.buffered}
        onSeek={disabled ? () => {} : handleSeek}
        theme={theme}
      />

      {/* Status Row */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginTop: 4,
          minHeight: 16,
        }}
      >
        {/* Loading/Playing Status */}
        {(state.isLoading || state.isPlaying) && (
          <Text
            style={{
              color: theme.colors.outline,
              fontSize: compact ? 10 : 11,
              fontWeight: '400',
            }}
          >
            {state.isLoading ? 'Carregando...' : state.isPlaying ? 'Reproduzindo' : ''}
          </Text>
        )}
        
        <View style={{ flex: 1 }} />
        
        {/* Audio Format/Quality Info */}
        {!state.error && (
          <Text
            style={{
              color: theme.colors.outline,
              fontSize: compact ? 10 : 11,
              fontWeight: '400',
            }}
          >
            Audio
          </Text>
        )}
      </View>

      {/* Error Display */}
      {state.error && (
        <View
          style={{
            marginTop: 8,
            padding: 8,
            backgroundColor: theme.colors.errorContainer,
            borderRadius: 6,
          }}
        >
          <Text
            style={{
              color: theme.colors.onErrorContainer,
              fontSize: compact ? 11 : 12,
              textAlign: 'center',
            }}
          >
            {state.error}
          </Text>
        </View>
      )}
    </Animated.View>
  );
};
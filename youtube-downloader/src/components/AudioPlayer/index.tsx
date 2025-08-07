import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, Animated } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Audio } from '../../types';
import { useAudioPlayer } from './useAudioPlayer';
import { PlayerControls } from './PlayerControls';
import { ProgressBar } from './ProgressBar';
import { TimeDisplay } from './TimeDisplay';
import { PlaybackSpeedControl } from './PlaybackSpeedControl';
import { VolumeControl } from './VolumeControl';
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

  const { state, play, pause, stop, seek, setPlaybackRate, setVolume } = useAudioPlayer(authenticatedUrl || '');

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

  const handleSpeedChange = useCallback(async (speed: number) => {
    try {
      await setPlaybackRate(speed);
    } catch (error) {
      onError?.(error as Error, audio);
    }
  }, [setPlaybackRate, audio, onError]);

  const handleVolumeChange = useCallback(async (volume: number) => {
    try {
      await setVolume(volume);
    } catch (error) {
      onError?.(error as Error, audio);
    }
  }, [setVolume, audio, onError]);

  const containerPadding = compact ? responsiveSizes.padding - 4 : responsiveSizes.padding;
  const borderRadius = compact ? responsiveSizes.borderRadius - 2 : responsiveSizes.borderRadius;

  return (
    <Animated.View
      style={{
        backgroundColor: playerColors.surface,
        borderRadius: 12,
        padding: 16,
        marginVertical: compact ? 2 : 4,
        shadowColor: isDarkMode ? 'rgba(0, 0, 0, 0.4)' : 'rgba(0, 0, 0, 0.1)',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 1,
        shadowRadius: 12,
        elevation: 6,
        opacity: fadeAnim,
        borderWidth: 1,
        borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.04)',
        transform: [
          {
            scale: fadeAnim.interpolate({
              inputRange: [0, 1],
              outputRange: [0.98, 1],
            }),
          },
          {
            translateY: fadeAnim.interpolate({
              inputRange: [0, 1],
              outputRange: [4, 0],
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

      {/* Main Controls Layout */}
      <View
        style={{
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        {/* Primary Controls */}
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 12,
          }}
        >
          <PlayerControls
            isPlaying={state.isPlaying}
            isLoading={state.isLoading}
            onPlay={handlePlay}
            onPause={handlePause}
            onStop={handleStop}
            onSeek={handleSeek}
            currentTime={state.currentTime}
            duration={state.duration}
            theme={theme}
            compact={true}
            disabled={disabled}
          />
        </View>
        
        {/* Secondary Controls Row */}
        <View 
          style={{ 
            flexDirection: 'row', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            width: '100%',
            paddingHorizontal: 8,
          }}
        >
          {/* Left Side - Volume */}
          <VolumeControl
            volume={state.volume}
            onVolumeChange={handleVolumeChange}
            theme={theme}
            compact={true}
            disabled={disabled}
          />
          
          {/* Center - Time Display */}
          <TimeDisplay
            currentTime={state.currentTime}
            duration={state.duration}
            theme={theme}
            compact={true}
            showProgress={showProgress}
          />
          
          {/* Right Side - Speed */}
          <PlaybackSpeedControl
            currentSpeed={state.playbackRate}
            onSpeedChange={handleSpeedChange}
            theme={theme}
            compact={true}
            disabled={disabled}
          />
        </View>
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
          justifyContent: 'center',
          marginTop: 6,
          minHeight: 16,
        }}
      >
        {/* Status Indicator */}
        {(state.isLoading || state.isPlaying) && (
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              paddingHorizontal: 8,
              paddingVertical: 3,
              backgroundColor: state.isPlaying ? theme.colors.primary + '20' : theme.colors.outline + '20',
              borderRadius: 6,
              borderWidth: 1,
              borderColor: state.isPlaying ? theme.colors.primary + '40' : theme.colors.outline + '40',
            }}
          >
            <View
              style={{
                width: 4,
                height: 4,
                borderRadius: 2,
                backgroundColor: state.isPlaying ? theme.colors.primary : theme.colors.outline,
                marginRight: 4,
              }}
            />
            <Text
              style={{
                color: state.isPlaying ? theme.colors.primary : theme.colors.outline,
                fontSize: 10,
                fontWeight: '600',
              }}
            >
              {state.isLoading ? 'Carregando...' : state.isPlaying ? 'Reproduzindo' : ''}
            </Text>
          </View>
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
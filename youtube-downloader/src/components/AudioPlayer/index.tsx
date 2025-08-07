import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, Animated, TouchableOpacity, ActivityIndicator } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
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
      if (state.isPlaying) {
        await pause();
        onPause?.(audio);
      } else {
        await play();
        onPlay?.(audio);
      }
    } catch (error) {
      onError?.(error as Error, audio);
    }
  }, [play, pause, state.isPlaying, audio, onPlay, onPause, onError]);

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

  const handleForwardPress = useCallback(() => {
    if (disabled || state.isLoading || !handleSeek) return;
    const newTime = Math.min(state.currentTime + 10, state.duration);
    handleSeek(newTime);
  }, [disabled, state.isLoading, state.currentTime, state.duration, handleSeek]);

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
        padding: compact ? 8 : 16,
        marginVertical: compact ? 1 : 4,
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
      {/* Progress Bar - Moved to top */}
      <ProgressBar
        currentTime={state.currentTime}
        duration={state.duration}
        buffered={state.buffered}
        onSeek={disabled ? () => {} : handleSeek}
        theme={theme}
      />

      {/* Title Row */}
      {showTitle && (
        <View
          style={{
            marginTop: 8,
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

      {/* Horizontal Controls Row - Grouped */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginTop: compact ? 8 : 12,
          paddingHorizontal: compact ? 2 : 4,
        }}
      >
        {/* Left Group - Main Playback Controls (Stop, Play, Forward) */}
        <View style={{ 
          flexDirection: 'row', 
          alignItems: 'center', 
          gap: compact ? 6 : 8,
          backgroundColor: theme.colors.surface,
          borderRadius: compact ? 20 : 24,
          paddingHorizontal: compact ? 8 : 12,
          paddingVertical: compact ? 4 : 6,
          borderWidth: 1,
          borderColor: theme.colors.outline + '20',
          shadowColor: 'rgba(0, 0, 0, 0.08)',
          shadowOffset: { width: 0, height: 2 },
          shadowOpacity: 1,
          shadowRadius: 4,
          elevation: 2,
        }}>
          {/* Stop Button */}
          <TouchableOpacity
            onPress={handleStop}
            disabled={disabled || state.isLoading}
            style={{
              width: compact ? 28 : 36,
              height: compact ? 28 : 36,
              borderRadius: compact ? 14 : 18,
              backgroundColor: theme.colors.outline + '15',
              alignItems: 'center',
              justifyContent: 'center',
              borderWidth: 1,
              borderColor: theme.colors.outline + '30',
              opacity: disabled ? 0.5 : 1,
            }}
            activeOpacity={0.8}
          >
            <Ionicons
              name="stop"
              size={compact ? 12 : 16}
              color={(disabled || state.isLoading) ? theme.colors.outline : theme.colors.onSurface}
            />
          </TouchableOpacity>

          {/* Play/Pause Button */}
          <TouchableOpacity
            onPress={handlePlay}
            disabled={disabled || state.isLoading}
            style={{
              width: compact ? 40 : 56,
              height: compact ? 40 : 56,
              borderRadius: compact ? 20 : 28,
              backgroundColor: state.isLoading ? theme.colors.outline : theme.colors.primary,
              alignItems: 'center',
              justifyContent: 'center',
              shadowColor: theme.colors.primary,
              shadowOffset: { width: 0, height: 3 },
              shadowOpacity: 0.3,
              shadowRadius: 8,
              elevation: 6,
              borderWidth: 2,
              borderColor: 'rgba(255, 255, 255, 0.15)',
              opacity: disabled ? 0.5 : 1,
            }}
            activeOpacity={0.85}
          >
            {state.isLoading ? (
              <ActivityIndicator
                size="small"
                color={theme.colors.onPrimary}
              />
            ) : (
              <Ionicons
                name={state.isPlaying ? "pause" : "play"}
                size={compact ? 18 : 24}
                color={theme.colors.onPrimary}
                style={{
                  marginLeft: state.isPlaying ? 0 : 2,
                }}
              />
            )}
          </TouchableOpacity>

          {/* Forward Button */}
          <TouchableOpacity
            onPress={handleForwardPress}
            disabled={disabled || state.isLoading || !handleSeek}
            style={{
              width: compact ? 28 : 36,
              height: compact ? 28 : 36,
              borderRadius: compact ? 14 : 18,
              backgroundColor: theme.colors.outline + '15',
              alignItems: 'center',
              justifyContent: 'center',
              borderWidth: 1,
              borderColor: theme.colors.outline + '30',
              opacity: (disabled || state.isLoading || !handleSeek) ? 0.5 : 1,
            }}
            activeOpacity={0.8}
          >
            <Ionicons
              name="play-forward"
              size={compact ? 12 : 16}
              color={(disabled || state.isLoading || !handleSeek) ? theme.colors.outline : theme.colors.onSurface}
            />
          </TouchableOpacity>
        </View>

        {/* Right Group - Secondary Controls (Speed, Volume) and Time */}
        <View style={{ 
          flexDirection: 'row', 
          alignItems: 'center', 
          gap: compact ? 8 : 12 
        }}>
          {/* Secondary Controls Group */}
          <View style={{ 
            flexDirection: 'row', 
            alignItems: 'center', 
            gap: compact ? 4 : 6,
            backgroundColor: theme.colors.surface,
            borderRadius: compact ? 16 : 20,
            paddingHorizontal: compact ? 6 : 8,
            paddingVertical: compact ? 4 : 6,
            borderWidth: 1,
            borderColor: theme.colors.outline + '20',
            shadowColor: 'rgba(0, 0, 0, 0.08)',
            shadowOffset: { width: 0, height: 2 },
            shadowOpacity: 1,
            shadowRadius: 4,
            elevation: 2,
          }}>
            {/* Speed Control */}
            <PlaybackSpeedControl
              currentSpeed={state.playbackRate}
              onSpeedChange={handleSpeedChange}
              theme={theme}
              compact={true}
              disabled={disabled}
            />
            
            {/* Volume Control */}
            <VolumeControl
              volume={state.volume}
              onVolumeChange={handleVolumeChange}
              theme={theme}
              compact={true}
              disabled={disabled}
            />
          </View>
          
          {/* Time Display - Separate */}
          <TimeDisplay
            currentTime={state.currentTime}
            duration={state.duration}
            theme={theme}
            compact={true}
            showProgress={showProgress}
          />
        </View>
      </View>

      {/* Status Row */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          marginTop: compact ? 3 : 6,
          minHeight: compact ? 12 : 16,
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
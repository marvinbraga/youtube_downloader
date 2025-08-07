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
        backgroundColor: isDarkMode ? 'rgba(15, 23, 42, 0.95)' : 'rgba(248, 250, 252, 0.95)',
        borderRadius: 12,
        padding: 12,
        marginVertical: 4,
        shadowColor: isDarkMode ? 'rgba(79, 70, 229, 0.3)' : 'rgba(59, 130, 246, 0.2)',
        shadowOffset: { width: 0, height: 3 },
        shadowOpacity: 1,
        shadowRadius: 8,
        elevation: 4,
        opacity: fadeAnim,
        borderWidth: 1,
        borderColor: isDarkMode 
          ? 'rgba(79, 70, 229, 0.2)' 
          : 'rgba(59, 130, 246, 0.15)',
        transform: [
          {
            scale: fadeAnim.interpolate({
              inputRange: [0, 1],
              outputRange: [0.98, 1],
            }),
          },
        ],
        overflow: 'hidden',
      }}
    >
      {/* Progress Bar - Compact */}
      <View style={{ marginBottom: 10 }}>
        <ProgressBar
          currentTime={state.currentTime}
          duration={state.duration}
          buffered={state.buffered}
          onSeek={disabled ? () => {} : handleSeek}
          theme={theme}
        />
      </View>

      {/* Status Indicator - Compact */}
      {(state.isLoading || state.isPlaying) && (
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'flex-start',
            marginBottom: 8,
          }}
        >
          <View
            style={{
              width: 4,
              height: 4,
              borderRadius: 2,
              backgroundColor: state.isPlaying 
                ? (isDarkMode ? '#4F46E5' : '#3b82f6')
                : (isDarkMode ? '#94a3b8' : '#64748b'),
              marginRight: 4,
            }}
          />
          <Text
            style={{
              color: state.isPlaying 
                ? (isDarkMode ? '#4F46E5' : '#3b82f6')
                : (isDarkMode ? '#94a3b8' : '#64748b'),
              fontSize: 10,
              fontWeight: '600',
            }}
          >
            {state.isLoading ? 'Carregando...' : state.isPlaying ? 'Reproduzindo' : ''}
          </Text>
        </View>
      )}

      {/* Compact Controls Row */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 4,
        }}
      >
        {/* Left Controls Group */}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          {/* Stop Button */}
          <TouchableOpacity
            onPress={handleStop}
            disabled={disabled || state.isLoading}
            style={{
              width: 24,
              height: 24,
              borderRadius: 3,
              backgroundColor: isDarkMode 
                ? 'rgba(148, 163, 184, 0.2)' 
                : 'rgba(100, 116, 139, 0.15)',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: disabled ? 0.5 : 1,
            }}
            activeOpacity={0.7}
          >
            <Ionicons
              name="stop"
              size={10}
              color={(disabled || state.isLoading) 
                ? (isDarkMode ? 'rgba(148, 163, 184, 0.6)' : 'rgba(100, 116, 139, 0.6)')
                : (isDarkMode ? '#94a3b8' : '#475569')
              }
            />
          </TouchableOpacity>

          {/* Play/Pause Button */}
          <TouchableOpacity
            onPress={handlePlay}
            disabled={disabled || state.isLoading}
            style={{
              width: 36,
              height: 36,
              borderRadius: 18,
              backgroundColor: state.isLoading 
                ? (isDarkMode ? 'rgba(148, 163, 184, 0.3)' : 'rgba(100, 116, 139, 0.2)')
                : (isDarkMode ? '#4F46E5' : '#3b82f6'),
              alignItems: 'center',
              justifyContent: 'center',
              opacity: disabled ? 0.5 : 1,
            }}
            activeOpacity={0.8}
          >
            {state.isLoading ? (
              <ActivityIndicator
                size="small"
                color="#ffffff"
              />
            ) : (
              <Ionicons
                name={state.isPlaying ? "pause" : "play"}
                size={16}
                color="#ffffff"
                style={{
                  marginLeft: state.isPlaying ? 0 : 1,
                }}
              />
            )}
          </TouchableOpacity>

          {/* Forward Button */}
          <TouchableOpacity
            onPress={handleForwardPress}
            disabled={disabled || state.isLoading || !handleSeek}
            style={{
              width: 28,
              height: 28,
              borderRadius: 14,
              backgroundColor: isDarkMode 
                ? 'rgba(148, 163, 184, 0.2)' 
                : 'rgba(100, 116, 139, 0.15)',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: (disabled || state.isLoading || !handleSeek) ? 0.5 : 1,
            }}
            activeOpacity={0.7}
          >
            <Ionicons
              name="play-forward"
              size={12}
              color={(disabled || state.isLoading || !handleSeek) 
                ? (isDarkMode ? 'rgba(148, 163, 184, 0.6)' : 'rgba(100, 116, 139, 0.6)')
                : (isDarkMode ? '#94a3b8' : '#475569')
              }
            />
          </TouchableOpacity>
        </View>

        {/* Center Controls Group */}
        <View style={{ 
          flexDirection: 'row', 
          alignItems: 'center', 
          gap: 4,
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
        
        {/* Right Time Display */}
        <TimeDisplay
          currentTime={state.currentTime}
          duration={state.duration}
          theme={theme}
          compact={true}
          showProgress={showProgress}
        />
      </View>


      {/* Error Display - Enhanced */}
      {state.error && (
        <View
          style={{
            marginTop: 8,
            padding: 12,
            backgroundColor: isDarkMode 
              ? 'rgba(239, 68, 68, 0.15)' 
              : 'rgba(239, 68, 68, 0.08)',
            borderRadius: 12,
            borderWidth: 1,
            borderColor: isDarkMode 
              ? 'rgba(239, 68, 68, 0.3)' 
              : 'rgba(239, 68, 68, 0.2)',
            shadowColor: 'rgba(239, 68, 68, 0.1)',
            shadowOffset: { width: 0, height: 2 },
            shadowOpacity: 1,
            shadowRadius: 4,
            elevation: 2,
          }}
        >
          <Text
            style={{
              color: isDarkMode ? '#ef4444' : '#dc2626',
              fontSize: compact ? 12 : 13,
              textAlign: 'center',
              fontWeight: '600',
              letterSpacing: 0.1,
            }}
          >
            {state.error}
          </Text>
        </View>
      )}
    </Animated.View>
  );
};
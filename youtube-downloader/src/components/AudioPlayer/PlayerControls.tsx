import React, { useState, useRef, useEffect } from 'react';
import { View, TouchableOpacity, ActivityIndicator, Animated } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { animations } from './themes';
// import { Theme } from '@/styles/theme';
interface Theme {
  colors: {
    onSurface: string;
    outline: string;
    primary: string;
    onPrimary: string;
    shadow: string;
  };
}

interface PlayerControlsProps {
  isPlaying: boolean;
  isLoading: boolean;
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  onSeek?: (time: number) => void;
  currentTime?: number;
  duration?: number;
  theme: Theme;
  disabled?: boolean;
  compact?: boolean;
}

export const PlayerControls: React.FC<PlayerControlsProps> = ({
  isPlaying,
  isLoading,
  onPlay,
  onPause,
  onStop,
  onSeek,
  currentTime = 0,
  duration = 0,
  theme,
  disabled = false,
  compact = false,
}) => {
  const [stopPressed, setStopPressed] = useState(false);
  const [playPressed, setPlayPressed] = useState(false);
  
  // Animações
  const playButtonScale = useRef(new Animated.Value(1)).current;
  const stopButtonScale = useRef(new Animated.Value(1)).current;
  const rotateAnim = useRef(new Animated.Value(0)).current;
  
  const iconColor = theme.colors.onSurface;
  const iconSize = compact ? 20 : 24;
  const buttonSize = compact ? 36 : 44;
  
  // Animação de rotação para loading
  useEffect(() => {
    if (isLoading) {
      Animated.loop(
        Animated.timing(rotateAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        })
      ).start();
    } else {
      rotateAnim.setValue(0);
    }
  }, [isLoading]);

  const handleStopPress = () => {
    if (disabled || isLoading) return;
    
    // Animação de press
    Animated.sequence([
      Animated.timing(stopButtonScale, {
        toValue: 0.9,
        duration: animations.fast / 2,
        useNativeDriver: true,
      }),
      Animated.timing(stopButtonScale, {
        toValue: 1,
        duration: animations.fast / 2,
        useNativeDriver: true,
      }),
    ]).start();
    
    setStopPressed(true);
    onStop();
    setTimeout(() => setStopPressed(false), animations.fast);
  };

  const handlePlayPausePress = () => {
    if (disabled || isLoading) return;
    
    // Animação de press
    Animated.sequence([
      Animated.timing(playButtonScale, {
        toValue: 0.9,
        duration: animations.fast / 2,
        useNativeDriver: true,
      }),
      Animated.timing(playButtonScale, {
        toValue: 1,
        duration: animations.fast / 2,
        useNativeDriver: true,
      }),
    ]).start();
    
    setPlayPressed(true);
    isPlaying ? onPause() : onPlay();
    setTimeout(() => setPlayPressed(false), animations.fast);
  };

  const handleForwardPress = () => {
    if (disabled || isLoading || !onSeek) return;
    
    // Avançar 10 segundos
    const newTime = Math.min(currentTime + 10, duration);
    onSeek(newTime);
  };

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: compact ? 8 : 16,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {/* Stop Button */}
      <Animated.View
        style={{
          transform: [{ scale: stopButtonScale }],
        }}
      >
        <TouchableOpacity
          onPress={handleStopPress}
          disabled={disabled || isLoading}
          style={{
            width: compact ? 28 : 36,
            height: compact ? 28 : 36,
            borderRadius: compact ? 14 : 18,
            backgroundColor: stopPressed ? theme.colors.outline + '30' : theme.colors.outline + '15',
            alignItems: 'center',
            justifyContent: 'center',
            borderWidth: 1,
            borderColor: theme.colors.outline + '30',
            shadowColor: 'rgba(0, 0, 0, 0.1)',
            shadowOffset: { width: 0, height: 1 },
            shadowOpacity: 1,
            shadowRadius: 2,
            elevation: 1,
          }}
          activeOpacity={0.8}
        >
          <Ionicons
            name="stop"
            size={compact ? 12 : 16}
            color={(disabled || isLoading) ? theme.colors.outline : iconColor}
          />
        </TouchableOpacity>
      </Animated.View>

      {/* Play/Pause Button - Main Control */}
      <Animated.View
        style={{
          transform: [{ scale: playButtonScale }],
        }}
      >
        <TouchableOpacity
          onPress={handlePlayPausePress}
          disabled={disabled || isLoading}
          style={{
            width: compact ? 40 : 56,
            height: compact ? 40 : 56,
            borderRadius: compact ? 20 : 28,
            backgroundColor: isLoading ? theme.colors.outline : theme.colors.primary,
            alignItems: 'center',
            justifyContent: 'center',
            shadowColor: theme.colors.primary,
            shadowOffset: { width: 0, height: 3 },
            shadowOpacity: 0.3,
            shadowRadius: 8,
            elevation: 6,
            borderWidth: 2,
            borderColor: 'rgba(255, 255, 255, 0.15)',
          }}
          activeOpacity={0.85}
        >
        {isLoading ? (
          <ActivityIndicator
            size="small"
            color={theme.colors.onPrimary}
          />
        ) : (
          <Ionicons
            name={isPlaying ? "pause" : "play"}
            size={compact ? 18 : 24}
            color={theme.colors.onPrimary}
            style={{
              marginLeft: isPlaying ? 0 : 2, // Visual balance for play icon
            }}
          />
        )}
        </TouchableOpacity>
      </Animated.View>

      {/* Forward 10s Button */}
      <Animated.View
        style={{
          transform: [{ scale: stopButtonScale }],
        }}
      >
        <TouchableOpacity
          onPress={handleForwardPress}
          disabled={disabled || isLoading || !onSeek}
          style={{
            width: compact ? 28 : 36,
            height: compact ? 28 : 36,
            borderRadius: compact ? 14 : 18,
            backgroundColor: theme.colors.outline + '15',
            alignItems: 'center',
            justifyContent: 'center',
            borderWidth: 1,
            borderColor: theme.colors.outline + '30',
            shadowColor: 'rgba(0, 0, 0, 0.1)',
            shadowOffset: { width: 0, height: 1 },
            shadowOpacity: 1,
            shadowRadius: 2,
            elevation: 1,
          }}
          activeOpacity={0.8}
        >
          <Ionicons
            name="play-forward"
            size={compact ? 12 : 16}
            color={(disabled || isLoading || !onSeek) ? theme.colors.outline : iconColor}
          />
        </TouchableOpacity>
      </Animated.View>

      {/* Status Indicator - Pulse animation when playing */}
      {isPlaying && (
        <View
          style={{
            position: 'absolute',
            left: '50%',
            marginLeft: -2,
            top: compact ? -6 : -8,
            width: 4,
            height: 4,
            borderRadius: 2,
            backgroundColor: theme.colors.primary,
          }}
        />
      )}
    </View>
  );
};
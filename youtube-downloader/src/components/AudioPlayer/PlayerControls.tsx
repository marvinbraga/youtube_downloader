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

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: compact ? 8 : 12,
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
            padding: compact ? 6 : 8,
            borderRadius: compact ? 16 : 20,
            backgroundColor: stopPressed ? theme.colors.outline + '20' : 'transparent',
          }}
          activeOpacity={0.7}
        >
          <Ionicons
            name="stop"
            size={iconSize}
            color={(disabled || isLoading) ? theme.colors.outline : iconColor}
          />
        </TouchableOpacity>
      </Animated.View>

      {/* Play/Pause Button */}
      <Animated.View
        style={{
          transform: [{ scale: playButtonScale }],
        }}
      >
        <TouchableOpacity
          onPress={handlePlayPausePress}
          disabled={disabled || isLoading}
          style={{
            width: buttonSize,
            height: buttonSize,
            borderRadius: buttonSize / 2,
            backgroundColor: isLoading ? theme.colors.outline : theme.colors.primary,
            alignItems: 'center',
            justifyContent: 'center',
            shadowColor: theme.colors.shadow,
            shadowOffset: { width: 0, height: 2 },
            shadowOpacity: 0.15,
            shadowRadius: 3,
            elevation: 3,
          }}
          activeOpacity={0.8}
        >
        {isLoading ? (
          <ActivityIndicator
            size={compact ? "small" : "small"}
            color={theme.colors.onPrimary}
          />
        ) : (
          <Ionicons
            name={isPlaying ? "pause" : "play"}
            size={iconSize}
            color={theme.colors.onPrimary}
            style={{
              marginLeft: isPlaying ? 0 : 2, // Slight offset for play icon visual balance
            }}
          />
        )}
        </TouchableOpacity>
      </Animated.View>

      {/* Status Indicator */}
      {isPlaying && (
        <View
          style={{
            width: 4,
            height: 4,
            borderRadius: 2,
            backgroundColor: theme.colors.primary,
            marginLeft: -4,
          }}
        />
      )}
    </View>
  );
};
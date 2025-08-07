import React, { useState } from 'react';
import { View, TouchableOpacity, Text, LayoutChangeEvent } from 'react-native';
// import { Theme } from '@/styles/theme';
interface Theme {
  colors: {
    surface: string;
    outline: string;
    primary: string;
    background: string;
    shadow: string;
    inverseSurface: string;
    inverseOnSurface: string;
  };
}

interface ProgressBarProps {
  currentTime: number;
  duration: number;
  buffered: number;
  onSeek: (time: number) => void;
  theme: Theme;
  disabled?: boolean;
  showTooltip?: boolean;
  height?: number;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  currentTime,
  duration,
  buffered,
  onSeek,
  theme,
  disabled = false,
  showTooltip = true,
  height = 6,
}) => {
  const [barWidth, setBarWidth] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [previewTime, setPreviewTime] = useState<number | null>(null);
  const [isHovering, setIsHovering] = useState(false);

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;
  const bufferedProgress = duration > 0 ? (buffered / duration) * 100 : 0;
  

  const handleLayout = (event: LayoutChangeEvent) => {
    setBarWidth(event.nativeEvent.layout.width);
  };

  const handlePress = (event: any) => {
    if (disabled || barWidth === 0 || duration === 0) {
      console.log('🚨 Cannot seek: disabled=', disabled, 'barWidth=', barWidth, 'duration=', duration);
      return;
    }

    // Compatibilidade React Native Web - usar diferentes métodos para obter posição X
    let touchX = event.nativeEvent.locationX;
    
    // Fallback para React Native Web
    if (touchX === undefined && event.nativeEvent.changedTouches) {
      // Touch events
      const touch = event.nativeEvent.changedTouches[0];
      const target = event.target;
      const rect = target.getBoundingClientRect();
      touchX = touch.clientX - rect.left;
    } else if (touchX === undefined && event.nativeEvent.clientX !== undefined) {
      // Mouse events
      const target = event.target;
      const rect = target.getBoundingClientRect();
      touchX = event.nativeEvent.clientX - rect.left;
    }

    // Verificar se conseguimos obter uma posição válida
    if (touchX === undefined || isNaN(touchX)) {
      console.log('🚨 Cannot determine touch position:', { 
        locationX: event.nativeEvent.locationX,
        clientX: event.nativeEvent.clientX,
        changedTouches: event.nativeEvent.changedTouches 
      });
      return;
    }

    const percentage = Math.max(0, Math.min(1, touchX / barWidth));
    const newTime = percentage * duration;
    
    console.log('🎵 Seek requested:', { touchX, percentage, newTime, duration });
    onSeek(newTime);
    setPreviewTime(null);
  };

  const handleMouseMove = (event: any) => {
    if (disabled || !showTooltip || barWidth === 0 || duration === 0) return;
    
    // Compatibilidade React Native Web - usar diferentes métodos para obter posição X
    let touchX = event.nativeEvent.locationX;
    
    // Fallback para React Native Web
    if (touchX === undefined && event.nativeEvent.clientX !== undefined) {
      // Mouse events
      const target = event.target;
      const rect = target.getBoundingClientRect();
      touchX = event.nativeEvent.clientX - rect.left;
    }

    // Verificar se conseguimos obter uma posição válida
    if (touchX === undefined || isNaN(touchX)) return;

    const percentage = Math.max(0, Math.min(1, touchX / barWidth));
    const previewTime = percentage * duration;
    
    setPreviewTime(previewTime);
  };

  const formatTime = (time: number): string => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <View style={{
      width: '100%',
      paddingVertical: 12,
    }}>
      <TouchableOpacity
        onPress={handlePress}
        onLayout={handleLayout}
        disabled={disabled}
        style={{
          height: 32,
          justifyContent: 'center',
          paddingVertical: 12,
        }}
        activeOpacity={disabled ? 1 : 0.9}
      >
        {/* Background Track */}
        <View
          style={{
            height: 6,
            backgroundColor: theme.colors.outline + '20',
            borderRadius: 3,
            position: 'relative',
            opacity: disabled ? 0.4 : 1,
            shadowColor: 'rgba(0, 0, 0, 0.1)',
            shadowOffset: { width: 0, height: 1 },
            shadowOpacity: 1,
            shadowRadius: 2,
            elevation: 1,
          }}
        >
          {/* Buffered Track */}
          <View
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              height: '100%',
              width: `${Math.min(bufferedProgress, 100)}%`,
              backgroundColor: theme.colors.outline + '40',
              borderRadius: 3,
            }}
          />
          
          {/* Progress Track */}
          <View
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              height: '100%',
              width: `${Math.min(progress, 100)}%`,
              backgroundColor: theme.colors.primary,
              borderRadius: 3,
              shadowColor: theme.colors.primary,
              shadowOffset: { width: 0, height: 0 },
              shadowOpacity: 0.4,
              shadowRadius: 4,
              elevation: 2,
            }}
          />
          
          {/* Progress Handle */}
          {duration > 0 && (
            <View
              style={{
                position: 'absolute',
                left: `${Math.min(progress, 100)}%`,
                top: -6,
                width: 18,
                height: 18,
                backgroundColor: theme.colors.primary,
                borderRadius: 9,
                marginLeft: -9,
                borderWidth: 3,
                borderColor: theme.colors.background,
                shadowColor: 'rgba(0, 0, 0, 0.3)',
                shadowOffset: { width: 0, height: 2 },
                shadowOpacity: 1,
                shadowRadius: 4,
                elevation: 4,
                opacity: disabled ? 0.5 : 1,
              }}
            />
          )}
        </View>
      </TouchableOpacity>
      
      {/* Preview Time Tooltip */}
      {showTooltip && previewTime !== null && isHovering && (
        <View
          style={{
            position: 'absolute',
            top: -45,
            backgroundColor: theme.colors.inverseSurface,
            paddingHorizontal: 12,
            paddingVertical: 6,
            borderRadius: 8,
            alignSelf: 'center',
            shadowColor: 'rgba(0, 0, 0, 0.4)',
            shadowOffset: { width: 0, height: 4 },
            shadowOpacity: 1,
            shadowRadius: 8,
            elevation: 8,
            borderWidth: 1,
            borderColor: 'rgba(255, 255, 255, 0.1)',
          }}
        >
          <Text
            style={{
              color: theme.colors.inverseOnSurface,
              fontSize: 12,
              fontWeight: '600',
              fontVariant: ['tabular-nums'],
            }}
          >
            {formatTime(previewTime)}
          </Text>
        </View>
      )}
    </View>
  );
};
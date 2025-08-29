import React, { memo, useMemo, useCallback } from 'react';
import { View, Text } from 'react-native';
// import { Theme } from '@/styles/theme';
interface Theme {
  colors: {
    onSurface: string;
    outline: string;
  };
}

interface TimeDisplayProps {
  currentTime: number;
  duration: number;
  theme: Theme;
  compact?: boolean;
  showRemaining?: boolean;
  showProgress?: boolean;
}

const TimeDisplayComponent: React.FC<TimeDisplayProps> = ({
  currentTime,
  duration,
  theme,
  compact = false,
  showRemaining = false,
  showProgress = false,
}) => {
  const formatTime = useCallback((time: number): string => {
    if (!isFinite(time) || isNaN(time)) {
      return '00:00';
    }

    const totalSeconds = Math.floor(time);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }, []);

  // Memoizar valores calculados
  const timeData = useMemo(() => {
    const currentTimeFormatted = formatTime(currentTime);
    const durationFormatted = formatTime(duration);
    const remainingTime = duration > 0 ? duration - currentTime : 0;
    const remainingTimeFormatted = formatTime(remainingTime);
    const progressPercentage = duration > 0 ? Math.round((currentTime / duration) * 100) : 0;
    
    return {
      currentTimeFormatted,
      durationFormatted,
      remainingTimeFormatted,
      progressPercentage
    };
  }, [currentTime, duration, formatTime]);
  
  // Memoizar estilos
  const containerStyle = useMemo(() => ({
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    paddingVertical: compact ? 2 : 6,
    paddingHorizontal: compact ? 6 : 14,
    backgroundColor: theme.colors.outline + '08',
    borderRadius: compact ? 8 : 10,
    borderWidth: 1,
    borderColor: theme.colors.outline + '20',
  }), [compact, theme.colors.outline]);
  
  const timeTextStyle = useMemo(() => ({
    color: theme.colors.onSurface,
    fontSize: compact ? 11 : 15,
    fontWeight: '700' as const,
    fontVariant: ['tabular-nums' as const],
    letterSpacing: 0.3,
  }), [theme.colors.onSurface, compact]);

  return (
    <View style={containerStyle}>
      {/* Main Time Display */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Text style={timeTextStyle}>
          {showRemaining && duration > 0 ? `-${timeData.remainingTimeFormatted}` : timeData.currentTimeFormatted}
        </Text>
        
        {!showRemaining && (
          <>
            <Text
              style={{
                color: theme.colors.outline,
                fontSize: compact ? 10 : 13,
                fontWeight: '400',
                marginHorizontal: compact ? 4 : 5,
              }}
            >
              •
            </Text>
            
            <Text
              style={{
                color: theme.colors.outline,
                fontSize: compact ? 10 : 13,
                fontWeight: '500',
                fontVariant: ['tabular-nums' as const], // Monospace numbers for consistent width
              }}
            >
              {timeData.durationFormatted}
            </Text>
          </>
        )}
      </View>

      {/* Progress Percentage */}
      {showProgress && duration > 0 && (
        <View
          style={{
            marginTop: 4,
            paddingHorizontal: 8,
            paddingVertical: 2,
            backgroundColor: theme.colors.outline + '10',
            borderRadius: 6,
          }}
        >
          <Text
            style={{
              color: theme.colors.outline,
              fontSize: 10,
              fontWeight: '600',
              fontVariant: ['tabular-nums' as const],
            }}
          >
            {timeData.progressPercentage}%
          </Text>
        </View>
      )}
    </View>
  );
};

// Comparação otimizada para React.memo
const arePropsEqual = (prevProps: TimeDisplayProps, nextProps: TimeDisplayProps) => {
  return (
    prevProps.currentTime === nextProps.currentTime &&
    prevProps.duration === nextProps.duration &&
    prevProps.compact === nextProps.compact &&
    prevProps.showRemaining === nextProps.showRemaining &&
    prevProps.showProgress === nextProps.showProgress &&
    prevProps.theme.colors.onSurface === nextProps.theme.colors.onSurface &&
    prevProps.theme.colors.outline === nextProps.theme.colors.outline
  );
};

export const TimeDisplay = memo(TimeDisplayComponent, arePropsEqual);
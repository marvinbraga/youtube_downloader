import React from 'react';
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

export const TimeDisplay: React.FC<TimeDisplayProps> = ({
  currentTime,
  duration,
  theme,
  compact = false,
  showRemaining = false,
  showProgress = false,
}) => {
  const formatTime = (time: number): string => {
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
  };

  const currentTimeFormatted = formatTime(currentTime);
  const durationFormatted = formatTime(duration);
  const remainingTime = duration > 0 ? duration - currentTime : 0;
  const remainingTimeFormatted = formatTime(remainingTime);
  const progressPercentage = duration > 0 ? Math.round((currentTime / duration) * 100) : 0;

  const fontSize = compact ? 12 : 14;
  const minWidth = compact ? 60 : 80;

  return (
    <View
      style={{
        alignItems: 'center',
        minWidth,
      }}
    >
      {/* Main Time Display */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
        }}
      >
        <Text
          style={{
            color: theme.colors.onSurface,
            fontSize,
            fontWeight: '500',
            fontVariant: ['tabular-nums'], // Monospace numbers for consistent width
          }}
        >
          {showRemaining && duration > 0 ? `-${remainingTimeFormatted}` : currentTimeFormatted}
        </Text>
        
        {!showRemaining && (
          <>
            <Text
              style={{
                color: theme.colors.outline,
                fontSize,
                fontWeight: '400',
                marginHorizontal: 4,
              }}
            >
              /
            </Text>
            
            <Text
              style={{
                color: theme.colors.outline,
                fontSize,
                fontWeight: '400',
                fontVariant: ['tabular-nums'], // Monospace numbers for consistent width
              }}
            >
              {durationFormatted}
            </Text>
          </>
        )}
      </View>

      {/* Progress Percentage */}
      {showProgress && duration > 0 && (
        <Text
          style={{
            color: theme.colors.outline,
            fontSize: compact ? 10 : 11,
            fontWeight: '400',
            marginTop: 2,
            fontVariant: ['tabular-nums'],
          }}
        >
          {progressPercentage}%
        </Text>
      )}
    </View>
  );
};
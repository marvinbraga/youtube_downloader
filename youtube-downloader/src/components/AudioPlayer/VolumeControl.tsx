import React, { useState, useCallback, useRef } from 'react';
import { View, Text, TouchableOpacity, LayoutChangeEvent } from 'react-native';
import { Feather } from '@expo/vector-icons';

interface Theme {
  colors: {
    primary: string;
    surface: string;
    onSurface: string;
    background: string;
    outline: string;
    inverseSurface: string;
    inverseOnSurface: string;
  };
}

interface VolumeControlProps {
  volume: number; // 0.0 to 1.0
  onVolumeChange: (volume: number) => void;
  theme: Theme;
  compact?: boolean;
  disabled?: boolean;
}

export const VolumeControl: React.FC<VolumeControlProps> = ({
  volume,
  onVolumeChange,
  theme,
  compact = false,
  disabled = false,
}) => {
  const [showSlider, setShowSlider] = useState(false);
  const [sliderWidth, setSliderWidth] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  // Determinar ícone baseado no volume
  const getVolumeIcon = () => {
    if (volume === 0) return 'volume-x';
    if (volume < 0.3) return 'volume';
    if (volume < 0.7) return 'volume-1';
    return 'volume-2';
  };

  const handleLayout = (event: LayoutChangeEvent) => {
    setSliderWidth(event.nativeEvent.layout.width);
  };

  const handleSliderPress = useCallback((event: any) => {
    if (disabled || sliderWidth === 0) return;

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
    if (touchX === undefined || isNaN(touchX)) return;

    const percentage = Math.max(0, Math.min(1, touchX / sliderWidth));
    onVolumeChange(percentage);
  }, [disabled, sliderWidth, onVolumeChange]);

  const handleMuteToggle = () => {
    if (disabled) return;
    onVolumeChange(volume === 0 ? 1.0 : 0);
  };

  const volumePercentage = volume * 100;
  const iconSize = compact ? 16 : 18;

  return (
    <View style={{ position: 'relative' }}>
      {/* Volume Button */}
      <TouchableOpacity
        style={{
          width: compact ? 24 : 32,
          height: compact ? 24 : 32,
          borderRadius: compact ? 12 : 16,
          backgroundColor: showSlider ? theme.colors.primary + '20' : theme.colors.surface,
          borderWidth: 1,
          borderColor: showSlider ? theme.colors.primary : theme.colors.outline + '40',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: disabled ? 0.5 : 1,
          shadowColor: 'rgba(0, 0, 0, 0.1)',
          shadowOffset: { width: 0, height: 1 },
          shadowOpacity: showSlider ? 1 : 0,
          shadowRadius: 2,
          elevation: showSlider ? 2 : 0,
        }}
        onPress={() => {
          if (!disabled) {
            if (showSlider) {
              handleMuteToggle();
            } else {
              setShowSlider(true);
            }
          }
        }}
        onLongPress={() => !disabled && handleMuteToggle()}
        disabled={disabled}
        activeOpacity={disabled ? 1 : 0.8}
      >
        <Feather
          name={getVolumeIcon() as any}
          size={compact ? 12 : 16}
          color={showSlider ? theme.colors.primary : (disabled ? theme.colors.outline : theme.colors.onSurface)}
        />
      </TouchableOpacity>

      {/* Volume Slider - Aparece quando showSlider é true */}
      {showSlider && (
        <View
          style={{
            position: 'absolute',
            top: -60,
            left: '50%',
            marginLeft: -65, // half of slider width
            width: 130,
            backgroundColor: theme.colors.inverseSurface,
            borderRadius: 12,
            paddingVertical: 16,
            paddingHorizontal: 20,
            shadowColor: 'rgba(0, 0, 0, 0.3)',
            shadowOffset: { width: 0, height: 8 },
            shadowOpacity: 1,
            shadowRadius: 16,
            elevation: 12,
            zIndex: 1000,
            borderWidth: 1,
            borderColor: 'rgba(255, 255, 255, 0.1)',
          }}
        >
          {/* Seta para baixo */}
          <View
            style={{
              position: 'absolute',
              bottom: -6,
              left: '50%',
              marginLeft: -6,
              width: 0,
              height: 0,
              borderLeftWidth: 6,
              borderRightWidth: 6,
              borderTopWidth: 6,
              borderLeftColor: 'transparent',
              borderRightColor: 'transparent',
              borderTopColor: theme.colors.inverseSurface,
            }}
          />

          {/* Slider Track */}
          <TouchableOpacity
            style={{
              height: 20,
              justifyContent: 'center',
              paddingHorizontal: 4,
            }}
            onPress={handleSliderPress}
            onLayout={handleLayout}
            activeOpacity={1}
          >
            {/* Background Track */}
            <View
              style={{
                height: 4,
                backgroundColor: theme.colors.outline + '40',
                borderRadius: 2,
                position: 'relative',
              }}
            >
              {/* Progress Track */}
              <View
                style={{
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  height: '100%',
                  width: `${volumePercentage}%`,
                  backgroundColor: theme.colors.primary,
                  borderRadius: 2,
                }}
              />

              {/* Handle */}
              <View
                style={{
                  position: 'absolute',
                  left: `${volumePercentage}%`,
                  top: -4,
                  width: 12,
                  height: 12,
                  backgroundColor: theme.colors.primary,
                  borderRadius: 6,
                  marginLeft: -6,
                  borderWidth: 2,
                  borderColor: theme.colors.inverseOnSurface,
                  shadowColor: '#000',
                  shadowOffset: { width: 0, height: 1 },
                  shadowOpacity: 0.3,
                  shadowRadius: 2,
                  elevation: 3,
                }}
              />
            </View>
          </TouchableOpacity>

          {/* Volume Percentage */}
          <View
            style={{
              marginTop: 8,
              alignItems: 'center',
            }}
          >
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <Feather
                name={getVolumeIcon() as any}
                size={12}
                color={theme.colors.inverseOnSurface}
              />
              <View
                style={{
                  paddingHorizontal: 6,
                  paddingVertical: 2,
                  backgroundColor: theme.colors.primary + '20',
                  borderRadius: 4,
                  minWidth: 32,
                  alignItems: 'center',
                }}
              >
                <Text
                  style={{
                    color: theme.colors.inverseOnSurface,
                    fontSize: 11,
                    fontWeight: '600',
                    fontVariant: ['tabular-nums'],
                  }}
                >
                  {Math.round(volumePercentage)}%
                </Text>
              </View>
            </View>
          </View>
        </View>
      )}

      {/* Overlay para fechar o slider */}
      {showSlider && (
        <TouchableOpacity
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 999,
          }}
          onPress={() => setShowSlider(false)}
          activeOpacity={1}
        />
      )}
    </View>
  );
};
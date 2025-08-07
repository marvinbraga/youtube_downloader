import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Modal } from 'react-native';
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

interface PlaybackSpeedControlProps {
  currentSpeed: number;
  onSpeedChange: (speed: number) => void;
  theme: Theme;
  compact?: boolean;
  disabled?: boolean;
}

const SPEED_OPTIONS = [
  { value: 0.5, label: '0.5x' },
  { value: 0.75, label: '0.75x' },
  { value: 1.0, label: '1x' },
  { value: 1.25, label: '1.25x' },
  { value: 1.5, label: '1.5x' },
  { value: 2.0, label: '2x' },
];

export const PlaybackSpeedControl: React.FC<PlaybackSpeedControlProps> = ({
  currentSpeed,
  onSpeedChange,
  theme,
  compact = false,
  disabled = false,
}) => {
  const [showModal, setShowModal] = useState(false);

  const currentSpeedLabel = SPEED_OPTIONS.find(option => option.value === currentSpeed)?.label || '1x';

  const handleSpeedSelect = (speed: number) => {
    onSpeedChange(speed);
    setShowModal(false);
  };

  return (
    <>
      <TouchableOpacity
        style={{
          width: compact ? 28 : 36,
          height: compact ? 24 : 32,
          borderRadius: compact ? 12 : 16,
          backgroundColor: theme.colors.surface,
          borderWidth: 1,
          borderColor: theme.colors.outline + '40',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: disabled ? 0.5 : 1,
          shadowColor: 'rgba(0, 0, 0, 0.1)',
          shadowOffset: { width: 0, height: 1 },
          shadowOpacity: 1,
          shadowRadius: 2,
          elevation: 1,
        }}
        onPress={() => !disabled && setShowModal(true)}
        disabled={disabled}
        activeOpacity={disabled ? 1 : 0.8}
      >
        <Text
          style={{
            color: theme.colors.onSurface,
            fontSize: compact ? 9 : 11,
            fontWeight: '700',
            fontVariant: ['tabular-nums'],
          }}
        >
          {currentSpeedLabel}
        </Text>
      </TouchableOpacity>

      <Modal
        visible={showModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowModal(false)}
      >
        <View
          style={{
            flex: 1,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            justifyContent: 'center',
            alignItems: 'center',
          }}
        >
          <View
            style={{
              backgroundColor: theme.colors.surface,
              borderRadius: 8,
              padding: 16,
              minWidth: 200,
              maxWidth: 280,
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 4 },
              shadowOpacity: 0.3,
              shadowRadius: 8,
              elevation: 8,
            }}
          >
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                marginBottom: 16,
                paddingBottom: 12,
                borderBottomWidth: 1,
                borderBottomColor: theme.colors.outline + '40',
              }}
            >
              <Feather name="zap" size={20} color={theme.colors.primary} />
              <Text
                style={{
                  color: theme.colors.onSurface,
                  fontSize: 16,
                  fontWeight: '600',
                  marginLeft: 8,
                }}
              >
                Velocidade de Reprodução
              </Text>
            </View>

            <View style={{ gap: 4 }}>
              {SPEED_OPTIONS.map((option) => (
                <TouchableOpacity
                  key={option.value}
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    paddingVertical: 12,
                    paddingHorizontal: 16,
                    borderRadius: 6,
                    backgroundColor:
                      currentSpeed === option.value
                        ? theme.colors.primary + '20'
                        : 'transparent',
                    borderWidth: currentSpeed === option.value ? 1 : 0,
                    borderColor: currentSpeed === option.value ? theme.colors.primary : 'transparent',
                  }}
                  onPress={() => handleSpeedSelect(option.value)}
                  activeOpacity={0.7}
                >
                  <View
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: 8,
                      borderWidth: 2,
                      borderColor: theme.colors.primary,
                      backgroundColor:
                        currentSpeed === option.value ? theme.colors.primary : 'transparent',
                      marginRight: 12,
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {currentSpeed === option.value && (
                      <View
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: 3,
                          backgroundColor: 'white',
                        }}
                      />
                    )}
                  </View>
                  <Text
                    style={{
                      color: theme.colors.onSurface,
                      fontSize: 15,
                      fontWeight: currentSpeed === option.value ? '600' : '400',
                      fontVariant: ['tabular-nums'],
                    }}
                  >
                    {option.label}
                  </Text>
                  <View style={{ flex: 1 }} />
                  {option.value === 1.0 && (
                    <Text
                      style={{
                        color: theme.colors.outline,
                        fontSize: 12,
                        fontStyle: 'italic',
                      }}
                    >
                      Normal
                    </Text>
                  )}
                </TouchableOpacity>
              ))}
            </View>

            <TouchableOpacity
              style={{
                marginTop: 16,
                paddingVertical: 10,
                paddingHorizontal: 16,
                backgroundColor: theme.colors.outline + '20',
                borderRadius: 6,
                alignItems: 'center',
              }}
              onPress={() => setShowModal(false)}
              activeOpacity={0.7}
            >
              <Text
                style={{
                  color: theme.colors.onSurface,
                  fontSize: 14,
                  fontWeight: '500',
                }}
              >
                Fechar
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </>
  );
};
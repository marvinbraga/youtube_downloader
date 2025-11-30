import { StyleSheet, Dimensions } from 'react-native';

interface Theme {
  colors: {
    surface: string;
    shadow: string;
    primary: string;
    primaryContainer: string;
    onSurface: string;
    outline: string;
    background: string;
    inverseSurface: string;
    inverseOnSurface: string;
    errorContainer: string;
    onErrorContainer: string;
  };
}

const { width: screenWidth } = Dimensions.get('window');

export const createAudioPlayerStyles = (theme: Theme) => StyleSheet.create({
  container: {
    backgroundColor: theme.colors.surface,
    borderRadius: 12,
    padding: 16,
    marginVertical: 4,
    shadowColor: theme.colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },

  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },

  // Player Controls
  controlsContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },

  controlButton: {
    padding: 8,
    borderRadius: 20,
    backgroundColor: 'transparent',
  },

  playPauseButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: theme.colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: theme.colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 3,
    elevation: 3,
  },

  playPauseButtonPressed: {
    backgroundColor: theme.colors.primaryContainer,
    transform: [{ scale: 0.95 }],
  },

  // Time Display
  timeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    minWidth: 80,
  },

  timeText: {
    color: theme.colors.onSurface,
    fontSize: 14,
    fontWeight: '500',
    fontVariant: ['tabular-nums'] as any,
  },

  timeSeparator: {
    color: theme.colors.outline,
    fontSize: 14,
    fontWeight: '400',
    marginHorizontal: 4,
  },

  durationText: {
    color: theme.colors.outline,
    fontSize: 14,
    fontWeight: '400',
    fontVariant: ['tabular-nums'] as any,
  },

  // Progress Bar
  progressContainer: {
    width: '100%',
    paddingVertical: 8,
  },

  progressTouchArea: {
    height: 20,
    justifyContent: 'center',
    paddingVertical: 8,
  },

  progressTrack: {
    height: 4,
    backgroundColor: theme.colors.surface,
    borderRadius: 2,
    position: 'relative',
  },

  bufferedTrack: {
    position: 'absolute',
    left: 0,
    top: 0,
    height: '100%',
    backgroundColor: theme.colors.outline,
    borderRadius: 2,
  },

  progressFill: {
    position: 'absolute',
    left: 0,
    top: 0,
    height: '100%',
    backgroundColor: theme.colors.primary,
    borderRadius: 2,
  },

  progressHandle: {
    position: 'absolute',
    top: -4,
    width: 12,
    height: 12,
    backgroundColor: theme.colors.primary,
    borderRadius: 6,
    marginLeft: -6,
    borderWidth: 2,
    borderColor: theme.colors.background,
    shadowColor: theme.colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 2,
    elevation: 2,
  },

  progressHandleActive: {
    transform: [{ scale: 1.2 }],
    backgroundColor: theme.colors.primaryContainer,
  },

  // Preview Tooltip
  previewTooltip: {
    position: 'absolute',
    top: -30,
    backgroundColor: theme.colors.inverseSurface,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    alignSelf: 'center',
  },

  previewText: {
    color: theme.colors.inverseOnSurface,
    fontSize: 12,
    fontWeight: '500',
  },

  // Error Display
  errorContainer: {
    marginTop: 8,
    padding: 8,
    backgroundColor: theme.colors.errorContainer,
    borderRadius: 8,
  },

  errorText: {
    color: theme.colors.onErrorContainer,
    fontSize: 12,
    textAlign: 'center',
  },

  // Loading State
  loadingContainer: {
    padding: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },

  loadingText: {
    color: theme.colors.onSurface,
    fontSize: 14,
    marginTop: 8,
  },

  // Compact Mode (Mobile)
  compactContainer: {
    paddingVertical: 12,
    paddingHorizontal: 12,
  },

  compactHeaderRow: {
    marginBottom: 8,
  },

  compactControlsContainer: {
    gap: 8,
  },

  compactPlayPauseButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
  },

  compactTimeContainer: {
    minWidth: 70,
  },

  compactTimeText: {
    fontSize: 12,
  },

});
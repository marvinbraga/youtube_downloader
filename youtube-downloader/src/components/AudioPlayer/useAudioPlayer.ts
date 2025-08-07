import { useState, useRef, useEffect, useCallback } from 'react';
import { Platform } from 'react-native';
import { Audio as ExpoAudio } from 'expo-av';
import { useGlobalAudioPlayer } from '../../context/AudioPlayerContext';

export interface AudioPlayerState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  buffered: number;
  volume: number;
  playbackRate: number;
  isLoading: boolean;
  error: string | null;
}

interface UseAudioPlayerReturn {
  state: AudioPlayerState;
  play: () => Promise<void>;
  pause: () => Promise<void>;
  stop: () => Promise<void>;
  seek: (time: number) => Promise<void>;
  setVolume: (volume: number) => Promise<void>;
  setPlaybackRate: (rate: number) => Promise<void>;
}

export const useAudioPlayer = (audioUrl: string): UseAudioPlayerReturn => {
  const [state, setState] = useState<AudioPlayerState>({
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    buffered: 0,
    volume: 1.0,
    playbackRate: 1.0,
    isLoading: false,
    error: null,
  });

  const soundRef = useRef<ExpoAudio.Sound | null>(null);
  const htmlAudioRef = useRef<HTMLAudioElement | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const isWeb = Platform.OS === 'web';
  
  // Global audio player context
  const { registerPlayer, unregisterPlayer, stopAllOtherPlayers } = useGlobalAudioPlayer();
  const playerIdRef = useRef<string>(Math.random().toString(36).substr(2, 9));

  // Stop function for global player context
  const stopPlayer = useCallback(async () => {
    try {
      if (isWeb && htmlAudioRef.current) {
        htmlAudioRef.current.pause();
        htmlAudioRef.current.currentTime = 0;
      } else if (!isWeb && soundRef.current) {
        await soundRef.current.stopAsync();
        await soundRef.current.setPositionAsync(0);
      }
      setState(prev => ({
        ...prev,
        isPlaying: false,
        currentTime: 0,
      }));
    } catch (error) {
      console.error('🚨 Failed to stop player:', error);
    }
  }, [isWeb]);

  // Cleanup function
  const cleanup = useCallback(() => {
    // Unregister from global context
    unregisterPlayer(playerIdRef.current);
    
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (isWeb && htmlAudioRef.current) {
      // Cleanup blob URL if exists
      if (htmlAudioRef.current.src && htmlAudioRef.current.src.startsWith('blob:')) {
        URL.revokeObjectURL(htmlAudioRef.current.src);
      }
      htmlAudioRef.current.pause();
      htmlAudioRef.current.src = '';
      htmlAudioRef.current = null;
    } else if (soundRef.current) {
      soundRef.current.unloadAsync().catch(console.error);
      soundRef.current = null;
    }
  }, [isWeb, unregisterPlayer]);

  // Initialize audio based on platform
  useEffect(() => {
    if (!audioUrl) {
      console.log('🎵 No audio URL provided, skipping initialization');
      return;
    }

    console.log('🎵 Initializing audio for platform:', Platform.OS, 'URL:', audioUrl);
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    // Register player with global context
    registerPlayer(playerIdRef.current, stopPlayer);

    if (isWeb) {
      initializeWebAudio();
    } else {
      initializeMobileAudio();
    }

    return cleanup;
  }, [audioUrl, isWeb, cleanup, registerPlayer, stopPlayer]);

  const initializeWebAudio = useCallback(async () => {
    try {
      console.log('🎵 Web: Starting audio initialization for URL:', audioUrl);
      
      const audio = new Audio();
      htmlAudioRef.current = audio;

      // Setup event listeners
      audio.addEventListener('loadedmetadata', () => {
        console.log('🎵 Web: Metadata loaded, duration:', audio.duration);
        setState(prev => ({
          ...prev,
          duration: isFinite(audio.duration) ? audio.duration : 0,
          isLoading: false,
          error: null,
        }));
      });

      audio.addEventListener('timeupdate', () => {
        setState(prev => ({
          ...prev,
          currentTime: audio.currentTime,
          buffered: audio.buffered.length > 0 ? audio.buffered.end(0) : 0,
        }));
      });

      audio.addEventListener('play', () => {
        setState(prev => ({ ...prev, isPlaying: true }));
      });

      audio.addEventListener('pause', () => {
        setState(prev => ({ ...prev, isPlaying: false }));
      });

      audio.addEventListener('ended', () => {
        setState(prev => ({
          ...prev,
          isPlaying: false,
          currentTime: 0,
        }));
      });

      audio.addEventListener('error', (e) => {
        console.error('🚨 Web: Audio error:', e);
        setState(prev => ({
          ...prev,
          isLoading: false,
          isPlaying: false,
          error: `Erro ao carregar áudio`,
        }));
      });

      // Extract audio ID to try different URL formats
      const audioIdMatch = audioUrl.match(/\/audios\/([^\/]+)\/stream/);
      const audioId = audioIdMatch ? audioIdMatch[1] : null;
      
      // Try AudioScreen format first (seems to work better)
      const urlToTry = audioId ? `http://localhost:8000/audio/stream/${audioId}` : audioUrl;
      
      console.log('🎵 Web: Trying URL:', urlToTry);
      audio.src = urlToTry;
      audio.load();

    } catch (error) {
      console.error('🚨 Web: Failed to initialize audio:', error);
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: `Failed to initialize audio: ${error}`,
      }));
    }
  }, [audioUrl]);

  const initializeMobileAudio = useCallback(async () => {
    try {
      // Configure audio mode for mobile
      await ExpoAudio.setAudioModeAsync({
        allowsRecordingIOS: false,
        staysActiveInBackground: true,
        playsInSilentModeIOS: true,
        shouldDuckAndroid: true,
        playThroughEarpieceAndroid: false,
      });

      const { sound } = await ExpoAudio.Sound.createAsync(
        { uri: audioUrl },
        { shouldPlay: false, isLooping: false },
        onPlaybackStatusUpdate
      );

      console.log('🎵 Mobile: Audio loaded successfully');
      soundRef.current = sound;
      setState(prev => ({ ...prev, isLoading: false }));

      // Force initial status update
      setTimeout(async () => {
        if (soundRef.current) {
          const status = await soundRef.current.getStatusAsync();
          if (status.isLoaded) {
            onPlaybackStatusUpdate(status);
          }
        }
      }, 100);

    } catch (error) {
      console.error('🚨 Mobile: Failed to load audio:', error);
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: `Failed to load audio: ${error}`,
      }));
    }
  }, [audioUrl]);

  const onPlaybackStatusUpdate = useCallback((status: any) => {
    if (status.isLoaded) {
      const currentTime = Math.max(0, (status.positionMillis || 0) / 1000);
      const duration = Math.max(0, (status.durationMillis || 0) / 1000);
      const buffered = status.playableDurationMillis ? status.playableDurationMillis / 1000 : 0;

      console.log('🎵 Mobile: Playback status update:', {
        currentTime,
        duration,
        isPlaying: status.isPlaying,
        buffered,
      });

      setState(prev => ({
        ...prev,
        currentTime,
        duration,
        isPlaying: status.isPlaying || false,
        buffered,
        error: null,
      }));

      if (status.didJustFinish) {
        setState(prev => ({
          ...prev,
          isPlaying: false,
          currentTime: 0,
        }));
      }
    } else if (status.error) {
      setState(prev => ({
        ...prev,
        error: `Playback error: ${status.error}`,
        isPlaying: false,
      }));
    }
  }, []);

  const play = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, error: null }));

      // Stop all other players before starting this one
      stopAllOtherPlayers(playerIdRef.current);

      if (isWeb && htmlAudioRef.current) {
        await htmlAudioRef.current.play();
      } else if (!isWeb && soundRef.current) {
        soundRef.current.setOnPlaybackStatusUpdate(onPlaybackStatusUpdate);
        await soundRef.current.playAsync();
      }
    } catch (error) {
      console.error('🚨 Failed to play:', error);
      setState(prev => ({
        ...prev,
        error: `Failed to play: ${error}`,
        isPlaying: false,
      }));
    }
  }, [isWeb, onPlaybackStatusUpdate, stopAllOtherPlayers]);

  const pause = useCallback(async () => {
    try {
      if (isWeb && htmlAudioRef.current) {
        htmlAudioRef.current.pause();
      } else if (!isWeb && soundRef.current) {
        await soundRef.current.pauseAsync();
      }
    } catch (error) {
      console.error('🚨 Failed to pause:', error);
      setState(prev => ({
        ...prev,
        error: `Failed to pause: ${error}`,
      }));
    }
  }, [isWeb]);

  const stop = useCallback(async () => {
    try {
      if (isWeb && htmlAudioRef.current) {
        htmlAudioRef.current.pause();
        htmlAudioRef.current.currentTime = 0;
        setState(prev => ({
          ...prev,
          isPlaying: false,
          currentTime: 0,
        }));
      } else if (!isWeb && soundRef.current) {
        await soundRef.current.stopAsync();
        await soundRef.current.setPositionAsync(0);
        setState(prev => ({
          ...prev,
          isPlaying: false,
          currentTime: 0,
        }));
      }
    } catch (error) {
      console.error('🚨 Failed to stop:', error);
      setState(prev => ({
        ...prev,
        error: `Failed to stop: ${error}`,
      }));
    }
  }, [isWeb]);

  const seek = useCallback(async (time: number) => {
    try {
      console.log('🎵 Seeking to time:', time, 'platform:', Platform.OS);
      
      if (isWeb && htmlAudioRef.current) {
        if (isFinite(htmlAudioRef.current.duration) && htmlAudioRef.current.duration > 0) {
          htmlAudioRef.current.currentTime = Math.max(0, Math.min(time, htmlAudioRef.current.duration));
        } else {
          console.log('🚨 Web: Cannot seek - duration not available');
          setState(prev => ({ ...prev, error: 'Duração do áudio ainda não foi carregada' }));
        }
      } else if (!isWeb && soundRef.current) {
        const status = await soundRef.current.getStatusAsync();
        if (!status.isLoaded) {
          console.log('🚨 Mobile: Sound is not loaded yet, cannot seek');
          setState(prev => ({ ...prev, error: 'Áudio ainda não foi carregado completamente' }));
          return;
        }

        const timeInMillis = Math.max(0, time * 1000);
        console.log('🎵 Mobile: Seeking to position (ms):', timeInMillis);
        await soundRef.current.setPositionAsync(timeInMillis);

        setState(prev => ({
          ...prev,
          currentTime: time,
          error: null,
        }));
      }

      console.log('🎵 Seek completed');
    } catch (error) {
      console.error('🚨 Seek failed:', error);
      setState(prev => ({
        ...prev,
        error: `Failed to seek: ${error}`,
      }));
    }
  }, [isWeb]);

  const setVolume = useCallback(async (volume: number) => {
    try {
      const clampedVolume = Math.max(0, Math.min(1, volume));
      
      if (isWeb && htmlAudioRef.current) {
        htmlAudioRef.current.volume = clampedVolume;
      } else if (!isWeb && soundRef.current) {
        await soundRef.current.setVolumeAsync(clampedVolume);
      }
      
      setState(prev => ({ ...prev, volume: clampedVolume }));
    } catch (error) {
      console.error('🚨 Failed to set volume:', error);
      setState(prev => ({
        ...prev,
        error: `Failed to set volume: ${error}`,
      }));
    }
  }, [isWeb]);

  const setPlaybackRate = useCallback(async (rate: number) => {
    try {
      const clampedRate = Math.max(0.25, Math.min(4.0, rate));
      
      if (isWeb && htmlAudioRef.current) {
        htmlAudioRef.current.playbackRate = clampedRate;
        console.log('🎵 Web: Playback rate set to', clampedRate);
      } else if (!isWeb && soundRef.current) {
        await soundRef.current.setRateAsync(clampedRate, true);
        console.log('🎵 Mobile: Playback rate set to', clampedRate);
      }
      
      setState(prev => ({ ...prev, playbackRate: clampedRate }));
    } catch (error) {
      console.error('🚨 Failed to set playback rate:', error);
      setState(prev => ({
        ...prev,
        error: `Failed to set playback rate: ${error}`,
      }));
    }
  }, [isWeb]);

  return {
    state,
    play,
    pause,
    stop,
    seek,
    setVolume,
    setPlaybackRate,
  };
};
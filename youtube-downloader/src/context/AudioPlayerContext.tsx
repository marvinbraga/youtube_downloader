import React, { createContext, useContext, useCallback, useRef } from 'react';

interface AudioPlayerContextType {
  registerPlayer: (id: string, stopFn: () => void) => void;
  unregisterPlayer: (id: string) => void;
  stopAllOtherPlayers: (currentId: string) => void;
}

const AudioPlayerContext = createContext<AudioPlayerContextType>({
  registerPlayer: () => {},
  unregisterPlayer: () => {},
  stopAllOtherPlayers: () => {},
});

export const useGlobalAudioPlayer = () => useContext(AudioPlayerContext);

export const AudioPlayerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const playersRef = useRef<Map<string, () => void>>(new Map());

  const registerPlayer = useCallback((id: string, stopFn: () => void) => {
    playersRef.current.set(id, stopFn);
    console.log('🎵 Global: Registered player', id, 'Total players:', playersRef.current.size);
  }, []);

  const unregisterPlayer = useCallback((id: string) => {
    playersRef.current.delete(id);
    console.log('🎵 Global: Unregistered player', id, 'Total players:', playersRef.current.size);
  }, []);

  const stopAllOtherPlayers = useCallback((currentId: string) => {
    console.log('🎵 Global: Stopping all players except', currentId);
    playersRef.current.forEach((stopFn, id) => {
      if (id !== currentId) {
        console.log('🎵 Global: Stopping player', id);
        stopFn();
      }
    });
  }, []);

  return (
    <AudioPlayerContext.Provider value={{ registerPlayer, unregisterPlayer, stopAllOtherPlayers }}>
      {children}
    </AudioPlayerContext.Provider>
  );
};
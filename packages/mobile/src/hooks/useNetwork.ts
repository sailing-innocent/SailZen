import { useState, useEffect, useCallback } from 'react';
import NetInfo, { NetInfoState } from '@react-native-community/netinfo';

interface NetworkStatus {
  isConnected: boolean;
  isInternetReachable: boolean | null;
  connectionType: string | null;
  isWifi: boolean;
  isCellular: boolean;
}

/**
 * Hook for monitoring network connectivity status
 */
export function useNetworkStatus(): NetworkStatus {
  const [networkState, setNetworkState] = useState<NetworkStatus>({
    isConnected: true,
    isInternetReachable: null,
    connectionType: null,
    isWifi: false,
    isCellular: false,
  });

  useEffect(() => {
    // Get initial state
    const checkInitialState = async () => {
      const state = await NetInfo.fetch();
      updateNetworkState(state);
    };

    checkInitialState();

    // Subscribe to network changes
    const unsubscribe = NetInfo.addEventListener((state) => {
      updateNetworkState(state);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const updateNetworkState = (state: NetInfoState) => {
    setNetworkState({
      isConnected: state.isConnected ?? false,
      isInternetReachable: state.isInternetReachable,
      connectionType: state.type,
      isWifi: state.type === 'wifi',
      isCellular: state.type === 'cellular',
    });
  };

  return networkState;
}

/**
 * Hook that returns a function to check if network is available
 */
export function useNetworkCheck(): () => Promise<boolean> {
  const checkNetwork = useCallback(async (): Promise<boolean> => {
    const state = await NetInfo.fetch();
    return state.isConnected === true && state.isInternetReachable !== false;
  }, []);

  return checkNetwork;
}

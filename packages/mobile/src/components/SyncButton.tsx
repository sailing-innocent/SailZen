import React, { useState, useEffect } from 'react';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { Badge, IconButton, useTheme, Menu, Text, Portal, Dialog, ProgressBar } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useNetworkStatus } from '../hooks/useNetwork';
import { useSyncStore } from '../stores/syncStore';
import { syncService } from '../services/syncService';

interface SyncButtonProps {
  variant?: 'icon' | 'button';
}

export function SyncButton({ variant = 'icon' }: SyncButtonProps) {
  const theme = useTheme();
  const { isConnected } = useNetworkStatus();
  const { pendingCount, isSyncing, lastSyncTime, syncError } = useSyncStore();
  const [menuVisible, setMenuVisible] = useState(false);
  const [showStatusDialog, setShowStatusDialog] = useState(false);
  const [syncProgress, setSyncProgress] = useState(0);

  const handleSync = async () => {
    if (!isConnected) {
      setShowStatusDialog(true);
      return;
    }

    if (isSyncing) return;

    setSyncProgress(0);
    try {
      await syncService.syncAll((progress) => {
        setSyncProgress(progress);
      });
    } catch (error) {
      console.error('Sync failed:', error);
    }
  };

  const getLastSyncText = () => {
    if (!lastSyncTime) return '从未同步';
    const diff = Date.now() - lastSyncTime.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    if (hours < 1) return '刚刚';
    if (hours < 24) return `${hours}小时前`;
    return `${Math.floor(hours / 24)}天前`;
  };

  const getStatusColor = () => {
    if (!isConnected) return '#F44336';
    if (syncError) return '#FF9800';
    if (pendingCount > 0) return '#2196F3';
    return '#4CAF50';
  };

  const getStatusIcon = () => {
    if (!isConnected) return 'wifi-off';
    if (isSyncing) return 'sync';
    if (syncError) return 'alert-circle';
    if (pendingCount > 0) return 'cloud-upload';
    return 'cloud-check';
  };

  if (variant === 'button') {
    return (
      <>
        <TouchableOpacity
          style={[styles.buttonContainer, { borderColor: getStatusColor() }]}
          onPress={handleSync}
          disabled={isSyncing}
        >
          <View style={styles.buttonContent}>
            <MaterialCommunityIcons
              name={getStatusIcon()}
              size={20}
              color={getStatusColor()}
              style={isSyncing ? styles.spinning : undefined}
            />
            <Text style={[styles.buttonText, { color: getStatusColor() }]}>
              {isSyncing ? '同步中...' : pendingCount > 0 ? `同步 (${pendingCount})` : '已同步'}
            </Text>
          </View>

          {!isConnected && (
            <View style={[styles.offlineIndicator, { backgroundColor: '#F44336' }]} />
          )}
        </TouchableOpacity>

        <Portal>
          <Dialog visible={showStatusDialog} onDismiss={() => setShowStatusDialog(false)}>
            <Dialog.Title>同步状态</Dialog.Title>
            <Dialog.Content>
              <View style={styles.statusContent}>
                <View style={styles.statusRow}>
                  <MaterialCommunityIcons
                    name={isConnected ? 'wifi' : 'wifi-off'}
                    size={24}
                    color={isConnected ? '#4CAF50' : '#F44336'}
                  />
                  <Text style={styles.statusText}>
                    {isConnected ? '网络已连接' : '网络未连接'}
                  </Text>
                </View>

                <View style={styles.statusRow}>
                  <MaterialCommunityIcons
                    name="cloud-upload"
                    size={24}
                    color={pendingCount > 0 ? '#2196F3' : '#4CAF50'}
                  />
                  <Text style={styles.statusText}>
                    待同步记录: {pendingCount} 条
                  </Text>
                </View>

                <View style={styles.statusRow}>
                  <MaterialCommunityIcons name="clock-outline" size={24} color="#757575" />
                  <Text style={styles.statusText}>
                    上次同步: {getLastSyncText()}
                  </Text>
                </View>

                {syncError && (
                  <View style={styles.errorContainer}>
                    <MaterialCommunityIcons name="alert-circle" size={20} color="#FF9800" />
                    <Text style={styles.errorText}>{syncError}</Text>
                  </View>
                )}
              </View>
            </Dialog.Content>
            <Dialog.Actions>
              <Button onPress={() => setShowStatusDialog(false)}>关闭</Button>
              {isConnected && pendingCount > 0 && (
                <Button onPress={handleSync} mode="contained" loading={isSyncing}>
                  立即同步
                </Button>
              )}
            </Dialog.Actions>
          </Dialog>
        </Portal>
      </>
    );
  }

  return (
    <>
      <Menu
        visible={menuVisible}
        onDismiss={() => setMenuVisible(false)}
        anchor={
          <View style={styles.iconContainer}>
            <IconButton
              icon={() => (
                <MaterialCommunityIcons
                  name={getStatusIcon()}
                  size={24}
                  color={getStatusColor()}
                />
              )}
              size={24}
              onPress={() => setMenuVisible(true)}
            />
            {pendingCount > 0 && (
              <Badge style={styles.badge}>{pendingCount}</Badge>
            )}
            {!isConnected && (
              <View style={[styles.offlineDot, { backgroundColor: '#F44336' }]} />
            )}
          </View>
        }
      >
        <Menu.Item
          title={`待同步: ${pendingCount} 条`}
          leadingIcon="cloud-upload"
          disabled
        />
        <Menu.Item
          title={`上次同步: ${getLastSyncText()}`}
          leadingIcon="clock-outline"
          disabled
        />
        <Menu.Item
          title={`网络状态: ${isConnected ? '在线' : '离线'}`}
          leadingIcon={isConnected ? 'wifi' : 'wifi-off'}
          disabled
        />
        <Menu.Item
          onPress={() => {
            setMenuVisible(false);
            handleSync();
          }}
          title={isSyncing ? '同步中...' : '立即同步'}
          leadingIcon="sync"
          disabled={!isConnected || isSyncing}
        />
      </Menu>

      <Portal>
        <Dialog visible={isSyncing && syncProgress > 0 && syncProgress < 100} dismissable={false}>
          <Dialog.Title>正在同步...</Dialog.Title>
          <Dialog.Content>
            <ProgressBar progress={syncProgress / 100} color={theme.colors.primary} />
            <Text style={styles.progressText}>{Math.round(syncProgress)}%</Text>
          </Dialog.Content>
        </Dialog>
      </Portal>
    </>
  );
}

// Need to import Button
import { Button } from 'react-native-paper';

const styles = StyleSheet.create({
  iconContainer: {
    position: 'relative',
  },
  badge: {
    position: 'absolute',
    top: 4,
    right: 4,
  },
  offlineDot: {
    position: 'absolute',
    bottom: 4,
    right: 4,
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  buttonContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderWidth: 1,
    borderRadius: 8,
    position: 'relative',
  },
  buttonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  buttonText: {
    fontWeight: '600',
  },
  offlineIndicator: {
    position: 'absolute',
    right: -4,
    top: -4,
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#fff',
  },
  spinning: {
    transform: [{ rotate: '0deg' }],
  },
  statusContent: {
    gap: 16,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  statusText: {
    fontSize: 16,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#FFF3E0',
    padding: 12,
    borderRadius: 8,
    marginTop: 8,
  },
  errorText: {
    color: '#FF9800',
    flex: 1,
  },
  progressText: {
    textAlign: 'center',
    marginTop: 8,
    color: '#757575',
  },
});

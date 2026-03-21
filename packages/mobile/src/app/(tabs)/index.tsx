import React, { useEffect, useState, useCallback } from 'react';
import { View, StyleSheet, ScrollView, RefreshControl } from 'react-native';
import { Text, useTheme, Snackbar } from 'react-native-paper';
import { useWeights } from '../../hooks/useWeights';
import { useMigrations } from '../../hooks/useDatabase';
import { QuickWeightRecord } from '../../components/QuickWeightRecord';
import { WeightStatistics } from '../../components/WeightStatistics';
import { WeightHistoryList } from '../../components/WeightHistoryList';
import { WeightEditDialog, WeightDeleteDialog } from '../../components/WeightDialogs';
import { WeightRecord } from '../../db/schema';

export default function WeightScreen() {
  const theme = useTheme();
  const { isReady: isDbReady } = useMigrations();
  const {
    weights,
    isLoading,
    error,
    fetchWeights,
    addWeight,
    updateWeight,
    deleteWeight,
    getStatistics,
  } = useWeights();

  const [stats, setStats] = useState({
    avg: null as number | null,
    min: null as number | null,
    max: null as number | null,
    count: 0,
  });
  const [selectedPeriod, setSelectedPeriod] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  // Edit/Delete dialog states
  const [editingWeight, setEditingWeight] = useState<WeightRecord | null>(null);
  const [editDialogVisible, setEditDialogVisible] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deleteDialogVisible, setDeleteDialogVisible] = useState(false);

  // Load data when DB is ready
  useEffect(() => {
    if (isDbReady) {
      loadData();
    }
  }, [isDbReady]);

  // Load statistics when period changes
  useEffect(() => {
    if (isDbReady) {
      loadStatistics();
    }
  }, [selectedPeriod, weights]);

  const loadData = async () => {
    await fetchWeights({ limit: 50 });
  };

  const loadStatistics = async () => {
    const stats = await getStatistics(selectedPeriod || undefined);
    if (stats) {
      setStats(stats);
    } else {
      setStats({ avg: null, min: null, max: null, count: 0 });
    }
  };

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, []);

  const handleAddWeight = async (value: number) => {
    try {
      await addWeight(value);
      setSnackbarMessage('体重记录已保存');
      setSnackbarVisible(true);
    } catch (err) {
      setSnackbarMessage('保存失败: ' + (err instanceof Error ? err.message : '未知错误'));
      setSnackbarVisible(true);
    }
  };

  const handleEdit = (weight: WeightRecord) => {
    setEditingWeight(weight);
    setEditDialogVisible(true);
  };

  const handleEditSave = async (id: number, value: number) => {
    try {
      await updateWeight(id, value);
      setEditDialogVisible(false);
      setEditingWeight(null);
      setSnackbarMessage('记录已更新');
      setSnackbarVisible(true);
    } catch (err) {
      setSnackbarMessage('更新失败: ' + (err instanceof Error ? err.message : '未知错误'));
      setSnackbarVisible(true);
    }
  };

  const handleDelete = (id: number) => {
    setDeletingId(id);
    setDeleteDialogVisible(true);
  };

  const handleDeleteConfirm = async () => {
    if (deletingId === null) return;
    
    try {
      await deleteWeight(deletingId);
      setDeleteDialogVisible(false);
      setDeletingId(null);
      setSnackbarMessage('记录已删除');
      setSnackbarVisible(true);
    } catch (err) {
      setSnackbarMessage('删除失败: ' + (err instanceof Error ? err.message : '未知错误'));
      setSnackbarVisible(true);
    }
  };

  if (!isDbReady) {
    return (
      <View style={styles.centered}>
        <Text>正在初始化数据库...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
      >
        <QuickWeightRecord
          onSave={handleAddWeight}
          loading={isLoading}
          lastWeight={weights[0]?.value ?? null}
        />

        <WeightStatistics
          avg={stats.avg}
          min={stats.min}
          max={stats.max}
          count={stats.count}
          selectedPeriod={selectedPeriod}
          onPeriodChange={setSelectedPeriod}
        />

        <WeightHistoryList
          weights={weights}
          onEdit={handleEdit}
          onDelete={handleDelete}
          loading={isLoading}
        />
      </ScrollView>

      <WeightEditDialog
        visible={editDialogVisible}
        weight={editingWeight}
        onDismiss={() => {
          setEditDialogVisible(false);
          setEditingWeight(null);
        }}
        onSave={handleEditSave}
        loading={isLoading}
      />

      <WeightDeleteDialog
        visible={deleteDialogVisible}
        onDismiss={() => {
          setDeleteDialogVisible(false);
          setDeletingId(null);
        }}
        onConfirm={handleDeleteConfirm}
        loading={isLoading}
      />

      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={2000}
      >
        {snackbarMessage}
      </Snackbar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});

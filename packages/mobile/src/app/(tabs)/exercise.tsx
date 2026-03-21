import React, { useEffect, useState, useCallback } from 'react';
import { View, StyleSheet, ScrollView, RefreshControl } from 'react-native';
import { Text, useTheme, Snackbar, Button, Portal, Dialog } from 'react-native-paper';
import { useExercises } from '../../hooks/useExercises';
import { useMigrations } from '../../hooks/useDatabase';
import { ExerciseTypeSelector } from '../../components/ExerciseTypeSelector';
import { DurationInput } from '../../components/DurationInput';
import { CalorieDisplay } from '../../components/CalorieDisplay';
import { ExerciseStatistics } from '../../components/ExerciseStatistics';
import { ExerciseHistoryList } from '../../components/ExerciseHistoryList';
import { ExerciseRecord, ExerciseType } from '../../db/schema';
import { format, subDays, startOfWeek, startOfMonth, startOfYear } from 'date-fns';

export default function ExerciseScreen() {
  const theme = useTheme();
  const { isReady: isDbReady } = useMigrations();
  const {
    exercises,
    isLoading,
    error,
    fetchExercises,
    addExercise,
    updateExercise,
    deleteExercise,
    getStatistics,
    calculateCalories,
  } = useExercises();

  const [selectedType, setSelectedType] = useState<ExerciseType | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [calories, setCalories] = useState<number | null>(null);
  const [statsPeriod, setStatsPeriod] = useState<'week' | 'month' | 'year'>('week');
  const [stats, setStats] = useState({
    totalDuration: null as number | null,
    totalCalories: null as number | null,
    count: 0,
  });
  const [refreshing, setRefreshing] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [showAddDialog, setShowAddDialog] = useState(false);

  // Edit/Delete dialog states
  const [editingExercise, setEditingExercise] = useState<ExerciseRecord | null>(null);
  const [editDialogVisible, setEditDialogVisible] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deleteDialogVisible, setDeleteDialogVisible] = useState(false);

  // Edit form states
  const [editType, setEditType] = useState<ExerciseType | null>(null);
  const [editDuration, setEditDuration] = useState<number | null>(null);
  const [editCalories, setEditCalories] = useState<number | null>(null);

  useEffect(() => {
    if (isDbReady) {
      loadData();
    }
  }, [isDbReady]);

  useEffect(() => {
    if (isDbReady) {
      loadStatistics();
    }
  }, [statsPeriod, exercises]);

  useEffect(() => {
    // Auto-calculate calories when type or duration changes
    if (selectedType && duration) {
      const calculated = calculateCalories(selectedType, duration);
      setCalories(calculated);
    }
  }, [selectedType, duration, calculateCalories]);

  const loadData = async () => {
    await fetchExercises({ limit: 50 });
  };

  const loadStatistics = async () => {
    let days: number;
    switch (statsPeriod) {
      case 'week':
        days = 7;
        break;
      case 'month':
        days = 30;
        break;
      case 'year':
        days = 365;
        break;
      default:
        days = 7;
    }

    const stats = await getStatistics(days);
    if (stats) {
      setStats(stats);
    } else {
      setStats({ totalDuration: null, totalCalories: null, count: 0 });
    }
  };

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, []);

  const handleAddExercise = async () => {
    if (!selectedType || !duration) {
      setSnackbarMessage('请选择运动类型和时长');
      setSnackbarVisible(true);
      return;
    }

    try {
      await addExercise(selectedType, duration, calories || undefined);
      setSnackbarMessage('运动记录已保存');
      setSnackbarVisible(true);
      setShowAddDialog(false);
      // Reset form
      setSelectedType(null);
      setDuration(null);
      setCalories(null);
    } catch (err) {
      setSnackbarMessage('保存失败: ' + (err instanceof Error ? err.message : '未知错误'));
      setSnackbarVisible(true);
    }
  };

  const handleEdit = (exercise: ExerciseRecord) => {
    setEditingExercise(exercise);
    setEditType(exercise.type);
    setEditDuration(exercise.duration);
    setEditCalories(exercise.calories);
    setEditDialogVisible(true);
  };

  const handleEditSave = async () => {
    if (!editingExercise || !editType || !editDuration) return;

    try {
      await updateExercise(editingExercise.id, {
        type: editType,
        duration: editDuration,
        calories: editCalories || calculateCalories(editType, editDuration),
      });
      setEditDialogVisible(false);
      setEditingExercise(null);
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
      await deleteExercise(deletingId);
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
        <Button
          mode="contained"
          onPress={() => setShowAddDialog(true)}
          style={styles.addButton}
          icon="plus"
        >
          记录运动
        </Button>

        <ExerciseStatistics
          totalDuration={stats.totalDuration}
          totalCalories={stats.totalCalories}
          count={stats.count}
          period={statsPeriod}
          onPeriodChange={setStatsPeriod}
        />

        <ExerciseHistoryList
          exercises={exercises}
          onEdit={handleEdit}
          onDelete={handleDelete}
          loading={isLoading}
        />
      </ScrollView>

      {/* Add Exercise Dialog */}
      <Portal>
        <Dialog visible={showAddDialog} onDismiss={() => setShowAddDialog(false)} style={styles.dialog}>
          <Dialog.Title>记录运动</Dialog.Title>
          <Dialog.ScrollArea style={styles.dialogScroll}>
            <ScrollView contentContainerStyle={styles.dialogContent}>
              <ExerciseTypeSelector selectedType={selectedType} onSelect={setSelectedType} />

              <DurationInput value={duration} onChange={setDuration} />

              {selectedType && duration && (
                <CalorieDisplay
                  type={selectedType}
                  duration={duration}
                  value={calories}
                  onChange={setCalories}
                  editable={true}
                />
              )}
            </ScrollView>
          </Dialog.ScrollArea>
          <Dialog.Actions>
            <Button onPress={() => setShowAddDialog(false)}>取消</Button>
            <Button
              onPress={handleAddExercise}
              mode="contained"
              disabled={!selectedType || !duration}
              loading={isLoading}
            >
              保存
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* Edit Dialog */}
      <Portal>
        <Dialog visible={editDialogVisible} onDismiss={() => setEditDialogVisible(false)} style={styles.dialog}>
          <Dialog.Title>编辑运动记录</Dialog.Title>
          <Dialog.ScrollArea style={styles.dialogScroll}>
            <ScrollView contentContainerStyle={styles.dialogContent}>
              <ExerciseTypeSelector selectedType={editType} onSelect={setEditType} />

              <DurationInput value={editDuration} onChange={setEditDuration} />

              {editType && editDuration && (
                <CalorieDisplay
                  type={editType}
                  duration={editDuration}
                  value={editCalories}
                  onChange={setEditCalories}
                  editable={true}
                />
              )}
            </ScrollView>
          </Dialog.ScrollArea>
          <Dialog.Actions>
            <Button onPress={() => setEditDialogVisible(false)}>取消</Button>
            <Button
              onPress={handleEditSave}
              mode="contained"
              disabled={!editType || !editDuration}
              loading={isLoading}
            >
              保存
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* Delete Dialog */}
      <Portal>
        <Dialog visible={deleteDialogVisible} onDismiss={() => setDeleteDialogVisible(false)}>
          <Dialog.Title>删除确认</Dialog.Title>
          <Dialog.Content>
            <Text>确定要删除这条运动记录吗？此操作无法撤销。</Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setDeleteDialogVisible(false)} disabled={isLoading}>取消</Button>
            <Button onPress={handleDeleteConfirm} loading={isLoading} disabled={isLoading} textColor="#F44336">
              删除
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

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
  addButton: {
    margin: 16,
    marginTop: 8,
  },
  dialog: {
    maxHeight: '80%',
  },
  dialogScroll: {
    paddingHorizontal: 0,
  },
  dialogContent: {
    paddingHorizontal: 24,
    paddingBottom: 16,
  },
});

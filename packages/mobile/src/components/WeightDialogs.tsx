import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Button, Dialog, Portal, Text } from 'react-native-paper';
import { WeightInputForm } from './WeightInputForm';
import { WeightRecord } from '../db/schema';

interface WeightEditDialogProps {
  visible: boolean;
  weight: WeightRecord | null;
  onDismiss: () => void;
  onSave: (id: number, value: number) => void;
  loading?: boolean;
}

export function WeightEditDialog({
  visible,
  weight,
  onDismiss,
  onSave,
  loading,
}: WeightEditDialogProps) {
  const handleSubmit = (value: number) => {
    if (weight) {
      onSave(weight.id, value);
    }
  };

  return (
    <Portal>
      <Dialog visible={visible} onDismiss={onDismiss} style={styles.dialog}>
        <Dialog.Title>编辑体重记录</Dialog.Title>
        <Dialog.Content>
          {weight && (
            <>
              <Text variant="bodySmall" style={styles.recordInfo}>
                记录时间: {weight.recordTime.toLocaleString('zh-CN')}
              </Text>
              <WeightInputForm
                initialValue={weight.value}
                onSubmit={handleSubmit}
                onCancel={onDismiss}
                loading={loading}
              />
            </>
          )}
        </Dialog.Content>
      </Dialog>
    </Portal>
  );
}

interface WeightDeleteDialogProps {
  visible: boolean;
  onDismiss: () => void;
  onConfirm: () => void;
  loading?: boolean;
}

export function WeightDeleteDialog({
  visible,
  onDismiss,
  onConfirm,
  loading,
}: WeightDeleteDialogProps) {
  return (
    <Portal>
      <Dialog visible={visible} onDismiss={onDismiss}>
        <Dialog.Title>删除确认</Dialog.Title>
        <Dialog.Content>
          <Text>确定要删除这条体重记录吗？此操作无法撤销。</Text>
        </Dialog.Content>
        <Dialog.Actions>
          <Button onPress={onDismiss} disabled={loading}>取消</Button>
          <Button onPress={onConfirm} loading={loading} disabled={loading} textColor="#F44336">
            删除
          </Button>
        </Dialog.Actions>
      </Dialog>
    </Portal>
  );
}

const styles = StyleSheet.create({
  dialog: {
    maxHeight: '80%',
  },
  recordInfo: {
    color: '#757575',
    marginBottom: 12,
  },
});

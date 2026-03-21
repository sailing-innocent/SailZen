import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { Card, Text, Button, TextInput, useTheme, Portal, Dialog } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface QuickWeightRecordProps {
  onSave: (value: number) => void;
  loading?: boolean;
  lastWeight?: number | null;
}

export function QuickWeightRecord({ onSave, loading, lastWeight }: QuickWeightRecordProps) {
  const theme = useTheme();
  const [value, setValue] = useState('');
  const [showConfirm, setShowConfirm] = useState(false);

  const handleQuickSave = () => {
    const numValue = parseFloat(value);
    if (!isNaN(numValue) && numValue > 0 && numValue <= 500) {
      setShowConfirm(true);
    }
  };

  const confirmSave = () => {
    const numValue = parseFloat(value);
    onSave(numValue);
    setValue('');
    setShowConfirm(false);
  };

  const useLastWeight = () => {
    if (lastWeight) {
      setValue(lastWeight.toString());
    }
  };

  return (
    <>
      <Card style={styles.container}>
        <Card.Content>
          <View style={styles.header}>
            <MaterialCommunityIcons
              name="scale"
              size={32}
              color={theme.colors.primary}
            />
            <Text variant="titleMedium" style={styles.title}>
              快速记录体重
            </Text>
          </View>

          <View style={styles.inputContainer}>
            <TextInput
              label="今日体重"
              value={value}
              onChangeText={setValue}
              keyboardType="decimal-pad"
              mode="outlined"
              style={styles.input}
              disabled={loading}
              placeholder={lastWeight ? `上次: ${lastWeight} kg` : '输入体重'}
              right={<TextInput.Affix text="kg" />}
            />
            {lastWeight && (
              <Button
                mode="text"
                onPress={useLastWeight}
                style={styles.useLastButton}
                compact
              >
                使用上次体重
              </Button>
            )}
          </View>

          <Button
            mode="contained"
            onPress={handleQuickSave}
            loading={loading}
            disabled={loading || !value || isNaN(parseFloat(value))}
            style={styles.saveButton}
            icon="check"
          >
            保存记录
          </Button>
        </Card.Content>
      </Card>

      <Portal>
        <Dialog visible={showConfirm} onDismiss={() => setShowConfirm(false)}>
          <Dialog.Title>确认记录</Dialog.Title>
          <Dialog.Content>
            <Text>
              确认记录体重: <Text style={{ fontWeight: 'bold' }}>{value} kg</Text>?
            </Text>
            <Text variant="bodySmall" style={{ marginTop: 8, color: '#757575' }}>
              记录时间: {new Date().toLocaleString('zh-CN')}
            </Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setShowConfirm(false)}>取消</Button>
            <Button onPress={confirmSave} mode="contained">确认</Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    margin: 16,
    marginTop: 8,
    elevation: 2,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  title: {
    marginLeft: 12,
    fontWeight: '600',
  },
  inputContainer: {
    marginBottom: 16,
  },
  input: {
    fontSize: 18,
  },
  useLastButton: {
    alignSelf: 'flex-start',
    marginTop: 4,
  },
  saveButton: {
    borderRadius: 8,
  },
});

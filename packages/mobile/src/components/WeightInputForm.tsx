import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { TextInput, Button, HelperText, useTheme } from 'react-native-paper';

interface WeightInputFormProps {
  initialValue?: number;
  onSubmit: (value: number) => void;
  onCancel?: () => void;
  loading?: boolean;
}

export function WeightInputForm({ initialValue, onSubmit, onCancel, loading = false }: WeightInputFormProps) {
  const theme = useTheme();
  const [value, setValue] = useState(initialValue ? initialValue.toString() : '');
  const [error, setError] = useState<string | null>(null);

  const validateAndSubmit = () => {
    const numValue = parseFloat(value);
    
    if (isNaN(numValue) || value.trim() === '') {
      setError('请输入有效的体重数值');
      return;
    }

    if (numValue <= 0 || numValue > 500) {
      setError('体重必须在 0-500 kg 之间');
      return;
    }

    setError(null);
    onSubmit(numValue);
  };

  return (
    <View style={styles.container}>
      <TextInput
        label="体重 (kg)"
        value={value}
        onChangeText={setValue}
        keyboardType="decimal-pad"
        mode="outlined"
        style={styles.input}
        disabled={loading}
        autoFocus
        right={<TextInput.Affix text="kg" />}
      />
      {error && <HelperText type="error">{error}</HelperText>}
      
      <View style={styles.buttonContainer}>
        {onCancel && (
          <Button
            mode="outlined"
            onPress={onCancel}
            style={[styles.button, { borderColor: theme.colors.outline }]}
            disabled={loading}
          >
            取消
          </Button>
        )}
        <Button
          mode="contained"
          onPress={validateAndSubmit}
          loading={loading}
          disabled={loading || !value}
          style={styles.button}
        >
          保存
        </Button>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
  },
  input: {
    fontSize: 20,
  },
  buttonContainer: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: 16,
    gap: 8,
  },
  button: {
    minWidth: 100,
  },
});

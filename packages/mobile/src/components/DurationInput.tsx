import React, { useState, useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { TextInput, Text, Button, useTheme } from 'react-native-paper';

interface DurationInputProps {
  value: number | null;
  onChange: (value: number) => void;
  label?: string;
}

const QUICK_DURATIONS = [15, 30, 45, 60];

export function DurationInput({
  value,
  onChange,
  label = '运动时长',
}: DurationInputProps) {
  const theme = useTheme();
  const [inputValue, setInputValue] = useState(value?.toString() || '');

  useEffect(() => {
    setInputValue(value?.toString() || '');
  }, [value]);

  const handleInputChange = (text: string) => {
    // Only allow numbers
    const numericValue = text.replace(/[^0-9]/g, '');
    setInputValue(numericValue);
    
    const num = parseInt(numericValue, 10);
    if (!isNaN(num) && num > 0) {
      onChange(num);
    }
  };

  const handleQuickSelect = (duration: number) => {
    setInputValue(duration.toString());
    onChange(duration);
  };

  return (
    <View style={styles.container}>
      <TextInput
        label={label}
        value={inputValue}
        onChangeText={handleInputChange}
        keyboardType="number-pad"
        mode="outlined"
        style={styles.input}
        right={<TextInput.Affix text="分钟" />}
        placeholder="输入分钟数"
      />

      <View style={styles.quickSelectContainer}>
        <Text variant="bodySmall" style={styles.quickLabel}>
          快速选择
        </Text>
        <View style={styles.quickButtons}>
          {QUICK_DURATIONS.map((duration) => (
            <Button
              key={duration}
              mode={value === duration ? 'contained' : 'outlined'}
              onPress={() => handleQuickSelect(duration)}
              style={styles.quickButton}
              compact
            >
              {duration}分钟
            </Button>
          ))}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
  },
  input: {
    fontSize: 18,
  },
  quickSelectContainer: {
    marginTop: 12,
  },
  quickLabel: {
    marginBottom: 8,
    color: '#757575',
  },
  quickButtons: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  quickButton: {
    flex: 1,
    minWidth: 70,
  },
});

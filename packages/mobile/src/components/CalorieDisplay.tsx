import React, { useState, useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { Card, Text, TextInput, useTheme } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { ExerciseType } from '../db/schema';

// MET values for calorie calculation
const MET_VALUES: Record<ExerciseType, number> = {
  running: 10,
  swimming: 8,
  cycling: 7,
  fitness: 6,
  yoga: 3,
  other: 4,
};

interface CalorieDisplayProps {
  type: ExerciseType | null;
  duration: number | null;
  value: number | null;
  onChange: (value: number) => void;
  editable?: boolean;
}

/**
 * Calculate estimated calories based on MET value and duration
 * Formula: Calories = MET × 3.5 × weight(kg) × duration(min) / 200
 * Using average weight of 70kg
 */
function calculateCalories(type: ExerciseType, duration: number): number {
  const met = MET_VALUES[type] || 4;
  const avgWeight = 70; // kg
  const calories = (met * 3.5 * avgWeight * duration) / 200;
  return Math.round(calories);
}

export function CalorieDisplay({
  type,
  duration,
  value,
  onChange,
  editable = false,
}: CalorieDisplayProps) {
  const theme = useTheme();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState('');

  const calculatedCalories = type && duration 
    ? calculateCalories(type, duration) 
    : null;

  useEffect(() => {
    if (calculatedCalories !== null && value === null) {
      onChange(calculatedCalories);
    }
  }, [calculatedCalories]);

  const handleEditStart = () => {
    if (!editable) return;
    setEditValue(value?.toString() || '');
    setIsEditing(true);
  };

  const handleEditComplete = () => {
    const numValue = parseInt(editValue, 10);
    if (!isNaN(numValue) && numValue >= 0) {
      onChange(numValue);
    }
    setIsEditing(false);
  };

  const displayValue = value ?? calculatedCalories ?? '-';

  return (
    <Card style={styles.container}>
      <Card.Content style={styles.content}>
        <MaterialCommunityIcons
          name="fire"
          size={24}
          color={theme.colors.primary}
        />
        <View style={styles.info}>
          <Text variant="bodySmall" style={styles.label}>
            预估消耗
          </Text>
          {isEditing ? (
            <TextInput
              value={editValue}
              onChangeText={setEditValue}
              keyboardType="number-pad"
              mode="flat"
              style={styles.editInput}
              onBlur={handleEditComplete}
              autoFocus
              right={<TextInput.Affix text="kcal" />}
            />
          ) : (
            <TouchableOpacity onPress={handleEditStart} disabled={!editable}>
              <Text variant="titleMedium" style={styles.value}>
                {typeof displayValue === 'number' ? `${displayValue} kcal` : displayValue}
              </Text>
              {editable && <Text variant="bodySmall" style={styles.editHint}>点击修改</Text>}
            </TouchableOpacity>
          )}
        </View>

        {calculatedCalories !== null && type && (
          <View style={styles.calculation}>
            <Text variant="bodySmall" style={styles.calcText}>
              {MET_VALUES[type]} MET × {duration}分钟
            </Text>
          </View>
        )}
      </Card.Content>
    </Card>
  );
}

// Need to import TouchableOpacity
import { TouchableOpacity } from 'react-native';

const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
    backgroundColor: '#FFF3E0',
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  info: {
    marginLeft: 12,
    flex: 1,
  },
  label: {
    color: '#757575',
  },
  value: {
    fontWeight: 'bold',
    marginTop: 2,
  },
  editInput: {
    height: 40,
    fontSize: 16,
  },
  editHint: {
    color: '#757575',
    marginTop: 2,
  },
  calculation: {
    alignItems: 'flex-end',
  },
  calcText: {
    color: '#FF9800',
  },
});

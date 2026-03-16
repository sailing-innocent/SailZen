import { View, StyleSheet } from 'react-native';
import { Text, Card, Button } from 'react-native-paper';

export default function ExerciseScreen() {
  return (
    <View style={styles.container}>
      <Card style={styles.card}>
        <Card.Title title="运动记录" />
        <Card.Content>
          <Text variant="bodyLarge">今日运动: -- 分钟</Text>
        </Card.Content>
        <Card.Actions>
          <Button mode="contained">记录运动</Button>
        </Card.Actions>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#f5f5f5',
  },
  card: {
    marginBottom: 16,
  },
});

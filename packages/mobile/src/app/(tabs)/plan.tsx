import { View, StyleSheet } from 'react-native';
import { Text, Card, Button } from 'react-native-paper';

export default function PlanScreen() {
  return (
    <View style={styles.container}>
      <Card style={styles.card}>
        <Card.Title title="健康目标" />
        <Card.Content>
          <Text variant="bodyLarge">当前目标: --</Text>
        </Card.Content>
        <Card.Actions>
          <Button mode="contained">设置目标</Button>
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

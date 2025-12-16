# 金钱管理

# Transaction Statistics API Documentation

## GET /finance/transaction/stats/

This endpoint provides transaction statistics with flexible filtering options. It always returns summary statistics, and optionally includes transaction data based on the `return_list` parameter.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Number of records to skip (for pagination) |
| `limit` | int | -1 | Maximum number of records to return (-1 for no limit) |
| `from_time` | float | None | Start timestamp for time period filtering |
| `to_time` | float | None | End timestamp for time period filtering |
| `tags` | str | "" | Comma-separated list of tags to filter by |
| `tag_op` | str | "and" | Tag operation: "and" or "or" |
| `description` | str | None | Description filter (partial match) |
| `min_value` | float | None | Minimum transaction value |
| `max_value` | float | None | Maximum transaction value |
| `return_list` | bool | False | If True, include transaction data in response; if False, only return stats |

### Response Format

The response always includes summary statistics, and optionally includes transaction data:

#### When `return_list=false` (default):
```json
{
  "total_count": 10,
  "income_count": 6,
  "expense_count": 4,
  "income_total": "1500.00",
  "expense_total": "800.00",
  "net_total": "700.00"
}
```

#### When `return_list=true`:
```json
{
  "total_count": 10,
  "income_count": 6,
  "expense_count": 4,
  "income_total": "1500.00",
  "expense_total": "800.00",
  "net_total": "700.00",
  "data": [
    {
      "id": 1,
      "from_acc_id": -1,
      "to_acc_id": 1,
      "value": "100.00",
      "description": "Salary",
      "tags": "income,salary",
      "htime": 1640995200.0,
      "ctime": "2024-01-01T00:00:00",
      "mtime": "2024-01-01T00:00:00"
    }
  ]
}
```

### Income and Expense Classification

- **Income**: Transactions where `from_acc_id=-1` and `to_acc_id>0`
- **Expense**: Transactions where `from_acc_id>0` and `to_acc_id=-1`

### Example Usage

#### Get summary statistics for all transactions:
```
GET /finance/transaction/stats/
```
Response:
```json
{
  "total_count": 10,
  "income_count": 6,
  "expense_count": 4,
  "income_total": "1500.00",
  "expense_total": "800.00",
  "net_total": "700.00"
}
```

#### Get summary statistics with transaction data for specific tags:
```
GET /finance/transaction/stats/?tags=food,groceries&tag_op=or&return_list=true
```
Response:
```json
{
  "total_count": 5,
  "income_count": 0,
  "expense_count": 5,
  "income_total": "0.00",
  "expense_total": "200.00",
  "net_total": "-200.00",
  "data": [
    {
      "id": 1,
      "from_acc_id": 1,
      "to_acc_id": -1,
      "value": "50.00",
      "description": "Grocery shopping",
      "tags": "food,groceries",
      "htime": 1640995200.0,
      "ctime": "2024-01-01T00:00:00",
      "mtime": "2024-01-01T00:00:00"
    }
  ]
}
```

#### Get summary for a specific time period:
```
GET /finance/transaction/stats/?from_time=1640995200&to_time=1643673600
```

#### Get high-value transactions with data:
```
GET /finance/transaction/stats/?min_value=1000&return_list=true
```

#### Get paginated transaction data:
```
GET /finance/transaction/stats/?skip=0&limit=10&return_list=true
```

### Error Responses

- **500 Internal Server Error**: When there's an error processing the request
  ```json
  {
    "detail": "Error getting transaction stats: [error message]"
  }
  ```

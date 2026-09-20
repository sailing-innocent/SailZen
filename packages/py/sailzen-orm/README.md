# sailzen-orm

SailZen 共享数据库结构声明层（SQLAlchemy ORM）。

`sail_server`（服务端）与 `sailzen-cli`（命令行工具）共用同一套 ORM 模型，确保数据库 schema 声明单一来源。

```python
from sailzen_orm import Account, Transaction, ORMBase
```

# PostgreSQL 数据库使用说明

## 连接信息

| 项目 | 值 |
|------|-----|
| 主机 | 123.45.67.89 |
| 端口 | 5433 |
| 数据库名 | student |
| 用户名 | student2026 |
| 密码 | student2026 |

## 快速连接

### 命令行连接

```bash
psql -h localhost -p 5433 -U student2026 -d student
# 输入密码后即可进入数据库交互界面
```

### 使用环境变量连接（避免每次输入密码）

```bash
export PGDATABASE=student
export PGPORT=5433
export PGHOST=localhost
export PGUSER=student2026
export PGPASSWORD=student2026

# 之后直接运行 psql 即可连接
psql
```

### 一行命令连接

```bash
PGPASSWORD='student2026' psql -h localhost -p 5433 -U student2026 -d student
```

## 常用 SQL 操作

### 创建表

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    age INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 插入数据

```sql
INSERT INTO users (name, age) VALUES ('张三', 20);
INSERT INTO users (name, age) VALUES ('李四', 22);
```

### 查询数据

```sql
-- 查看所有数据
SELECT * FROM users;

-- 条件查询
SELECT * FROM users WHERE age > 20;

-- 统计
SELECT COUNT(*) FROM users;
```

### 更新数据

```sql
UPDATE users SET age = 21 WHERE name = '张三';
```

### 删除数据

```sql
DELETE FROM users WHERE id = 1;
```

### 删除表

```sql
DROP TABLE users;
```

## psql 常用命令

| 命令 | 说明 |
|------|------|
| `\l` | 列出所有数据库 |
| `\d` | 列出当前数据库的所有表 |
| `\d 表名` | 查看表结构 |
| `\dt` | 列出所有表 |
| `\q` | 退出 psql |
| `\c 数据库名` | 切换数据库 |
| `\i 文件.sql` | 执行 SQL 文件 |
| `\h` | SQL 命令帮助 |
| `\?` | psql 命令帮助 |

## Python 连接示例

```python
import psycopg2

# 连接数据库
conn = psycopg2.connect(
    host='localhost',
    port=5433,
    database='student',
    user='student2026',
    password='student2026'
)

# 创建游标
cur = conn.cursor()

# 执行查询
cur.execute('SELECT version();')
print(cur.fetchone())

# 提交事务（如果有修改操作）
conn.commit()

# 关闭连接
cur.close()
conn.close()
```

## Node.js 连接示例

```javascript
const { Client } = require('pg');

const client = new Client({
  host: 'localhost',
  port: 5433,
  database: 'student',
  user: 'student2026',
  password: 'student2026'
});

(async () => {
  await client.connect();
  const res = await client.query('SELECT $1::text as message', ['Hello PostgreSQL!']);
  console.log(res.rows[0].message);
  await client.end();
})();
```

## 注意事项

1. **密码安全**：在生产环境中请使用更安全的密码，并考虑使用 `.pgpass` 文件或环境变量管理密码
2. **备份**：重要数据请定期备份
3. **权限**：当前用户拥有完整读写权限，请谨慎操作
4. **端口**：本系统有两个 PostgreSQL 实例，端口 5433 是 PostgreSQL 17 版本，端口 5432 是 PostgreSQL 16 版本

---

*文档更新时间：2026-07-21*

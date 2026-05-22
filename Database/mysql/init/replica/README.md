# replica 初始化脚本

`01-configure-replication.sh` 会在 MySQL 数据目录第一次初始化时自动执行：

- 等待 `mysql-primary` 可访问
- 读取 `MYSQL_REPLICATION_USER`
- 读取 `MYSQL_REPLICATION_PASSWORD`
- 执行 `CHANGE REPLICATION SOURCE TO`
- 执行 `START REPLICA`

注意：

- 如果 volume 已经存在，`/docker-entrypoint-initdb.d` 不会重跑。
- `MYSQL_REPLICATION_PASSWORD` 不能为空，否则脚本会失败。
- 如果 primary 初始化比 replica 更慢，脚本会循环等待。

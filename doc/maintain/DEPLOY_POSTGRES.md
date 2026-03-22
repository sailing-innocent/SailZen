## PostgreSQL安装

```bash 
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
sudo apt update
sudo apt install postgresql-17
```

PostgreSQL stores its data in the $PGDATA directory, typically located at /var/lib/postgresql/17/main

```base
sudo mkdir -p /postgres/pgdata
sudo chown ubuntu:ubuntu /postgres/pgdata
/usr/lib/postgresql/17/bin/initdb -D /postgres/pgdata
sudo mkdir -p /var/run/postgresql

/usr/lib/postgresql/17/bin/pg_ctl -D /home/ubuntu/postgres/pgdata -l logfile start
```

Validate

```bash
sudo systemctl restart postgresql
sudo systemctl start postgresql
sudo systemctl status postgresql*

psql
CREATE ROLE postgres WITH SUPERUSER CREATEDB CREATEROLE LOGIN;

```

进入psql
- ` sudo -u postgres psql`
- 查询配置文件路径 `SHOW hba_file;SHOW config_file;`
`ALTER USER postgres PASSWORD 'zzh666';`
-  pg_hba.conf支持远程连接
`host    all    all    0.0.0.0/0    md5`



#### 锁文件权限错误

```bash
# 1. 创建并修复锁文件目录权限
sudo mkdir -p /var/run/postgresql
sudo chown postgres:postgres /var/run/postgresql
sudo chmod 0755 /var/run/postgresql

# 2. 创建PID文件目录（/run通常是tmpfs，需要确保目录存在）
sudo mkdir -p /run/postgresql
sudo chown postgres:postgres /run/postgresql
sudo chmod 0755 /run/postgresql

# 3. 启动服务
sudo systemctl start postgresql@17-main

# 4. 检查状态
sudo systemctl status postgresql@17-main
```

检查其他postgresql正在运行

```bash
# 检查PostgreSQL进程
ps aux | grep postgres | grep -v grep

# 检查端口占用
sudo lsof -i :5432
# 或
sudo ss -tulpn | grep 5432
```

清除残留文件并重启

```bash
# 停止所有PostgreSQL相关服务
sudo systemctl stop postgresql@17-main
sudo systemctl stop postgresql

# 如果有残留进程，强制结束
sudo pkill -9 postgres

# 清理锁文件和PID文件
sudo rm -f /var/run/postgresql/.s.PGSQL.5432.lock
sudo rm -f /run/postgresql/17-main.pid
sudo rm -f /var/run/postgresql/17-main.pid

# 确保目录存在且权限正确
sudo mkdir -p /var/run/postgresql /run/postgresql
sudo chown postgres:postgres /var/run/postgresql /run/postgresql
sudo chmod 0755 /var/run/postgresql /run/postgresql

# 等待几秒确保进程完全停止
sleep 2

# 重新启动
sudo systemctl start postgresql@17-main
```

测试本地连接
```bash
# 1. 检查服务状态（应该是active (running)）
sudo systemctl status postgresql@17-main

# 2. 检查进程
ps aux | grep postgres | grep -v grep

# 3. 检查端口
sudo ss -tuln | grep 5432

# 4. 测试本地连接
sudo -u postgres psql -c "SELECT version();"

# 5. 检查锁文件是否创建成功
ls -la /var/run/postgresql/
```


### 配置postgresql监听地址

/etc/postgresql/17/main/postgresql.conf

`listen_addresses = '*'`


### 验证配置
```bash
# 检查监听地址
sudo ss -tuln | grep 5432
# 应该显示 0.0.0.0:5432 或 *:5432

# 检查pg_hba.conf配置
sudo grep -E '^[^#]*host' /etc/postgresql/17/main/pg_hba.conf
```

## 基础安装

- install npm 
- install uv
- install pnpm
- setup 

install python on ubuntu: [[Ubuntu Install Python3|dev-env.system.ubuntu#ubuntu-install-python3]]

- [[Ubuntu Install NodeJS|dev-env.system.ubuntu#ubuntu-install-nodejs]]

### 安装SailZen

- pnpm build-site

### 配置my_service

`sudo systemctl restart my-server.service`

`/etc/systemd/system/my-server.service`

修改之后记得 `systemctl daemon-reload`


```ini
[Unit]
Description=FastAPI Server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/repos/SailZen
ExecStart=/home/ubuntu/pyv_ws/bin/uv run /home/ubuntu/repos/SailZen/server.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

`sudo systemctl daemon-reload`
`sudo systemctl enable SERVICE-NAME.service`
check enabled 
`sudo systemctl is-enabled SERVICE-NAME.service`
start 
`sudo systemctl stop my-server.service`
`sudo systemctl start my-server.service`
`sudo systemctl enable my-server.service`

```sh
sudo systemctl daemon-reload
sudo systemctl enable my-server.service
sudo systemctl start my-server.service
sudo systemctl restart my-server.service
#check
sudo systemctl is-enabled my-server.service
```

check journal

sudo journalctl -u my-server.service

Reload

Look at port 

`lsof -i:PORT_NUMBER`

add softlink for data 

ln -s data ~/data


查看端口占用程序并kill

## Trouble Shooting 

### key-id already exists

通常是没有修复到主键

```sql
SELECT setval(
    pg_get_serial_sequence('weights', 'id'), 
    (SELECT COALESCE(MAX(id), 1) FROM weights)
);
```
# 消息归档功能使用指南

## 概述

消息归档功能将完整的 Savant Message 序列化后存储到文件系统，支持完整的数据重放和调试。

## 架构

```
实时处理流程：
  视频源 → Router → 模块 → [PostgreSQL Sink + Redis Stream Sink + 消息归档 Sink]
                              ↓              ↓                    ↓
                          数据分析      实时监控              完整归档

重放流程：
  消息归档 Source → Router → 模块 → ...
```

## 功能特性

- ✅ 保留 100% 完整的消息内容（视频帧 + 检测结果 + 元数据）
- ✅ 支持按 source_id 分组存储
- ✅ 自动清理旧文件（可配置保留数量）
- ✅ 支持完整重放和调试
- ✅ 支持按帧率控制重放速度
- ✅ 支持循环重放

## 启用归档功能

### 方法 1：使用 Docker Compose Profile

```bash
# 启动归档服务
docker-compose --profile archive up -d message-archive-sink

# 查看归档日志
docker-compose logs -f message-archive-sink

# 停止归档服务
docker-compose stop message-archive-sink
```

### 方法 2：修改 docker-compose.yml

移除 `message-archive-sink` 服务中的 `profiles` 配置，使其默认启动：

```yaml
  message-archive-sink:
    image: ghcr.io/insight-platform/savant-adapters-py:0.6.0
    restart: unless-stopped
    # profiles:  # 注释掉这行
    #   - archive
    volumes:
    - zmq_sockets:/tmp/zmq-sockets
    - ./adapters:/opt/adapters
    - ./data/message_archive:/data/message_archive
    ...
```

然后重启服务：

```bash
docker-compose up -d
```

## 配置选项

### 归档 Sink 配置

环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ZMQ_ENDPOINT` | ZeroMQ 源端点 | `sub+connect:ipc:///tmp/zmq-sockets/output-yolov8.ipc` |
| `ARCHIVE_DIR` | 归档目录 | `/data/message_archive` |
| `MAX_FILES_PER_SOURCE` | 每个 source 最多保留的文件数 | `1000` |

### 重放 Source 配置

环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ZMQ_ENDPOINT` | ZeroMQ 目标端点 | `pub+bind:ipc:///tmp/zmq-sockets/replay.ipc` |
| `ARCHIVE_DIR` | 归档目录 | `/data/message_archive` |
| `SOURCE_ID` | 只重放指定 source_id（可选） | 无 |
| `FPS` | 重放帧率（可选，0 表示尽快发送） | `0` |
| `LOOP` | 是否循环重放 | `false` |

## 使用示例

### 1. 重放归档消息

```bash
# 重放所有归档消息（尽快发送）
docker-compose run --rm \
  -e ZMQ_ENDPOINT=pub+bind:ipc:///tmp/zmq-sockets/replay.ipc \
  -e ARCHIVE_DIR=/data/message_archive \
  message-archive-sink \
  python /opt/adapters/message_archive_source.py

# 重放指定 source_id 的消息
docker-compose run --rm \
  -e SOURCE_ID=video1 \
  -e ARCHIVE_DIR=/data/message_archive \
  message-archive-sink \
  python /opt/adapters/message_archive_source.py

# 以 25 fps 重放
docker-compose run --rm \
  -e FPS=25 \
  -e ARCHIVE_DIR=/data/message_archive \
  message-archive-sink \
  python /opt/adapters/message_archive_source.py

# 循环重放
docker-compose run --rm \
  -e LOOP=true \
  -e ARCHIVE_DIR=/data/message_archive \
  message-archive-sink \
  python /opt/adapters/message_archive_source.py
```

### 2. 清理旧归档

```bash
# 清理 7 天前的归档（默认）
bash scripts/cleanup_archive.sh

# 清理 3 天前的归档
bash scripts/cleanup_archive.sh --keep 3

# 只清理 video1 的归档
bash scripts/cleanup_archive.sh --source video1

# Dry-run 模式（查看将要删除的文件）
bash scripts/cleanup_archive.sh --dry-run

# 查看帮助
bash scripts/cleanup_archive.sh --help
```

### 3. 定期清理（Cron）

添加到 crontab：

```bash
# 每天凌晨 2 点清理 7 天前的归档
0 2 * * * cd /path/to/ai_video_analysis && bash scripts/cleanup_archive.sh
```

## 存储管理

### 存储空间估算

- 每帧大小：约 100KB - 1MB（取决于分辨率和压缩）
- 1 小时视频（25fps）：约 9GB - 90GB
- 建议保留时间：1-7 天

### 目录结构

```
data/message_archive/
├── video1/
│   ├── 20260315_100000_00000001.msg
│   ├── 20260315_100000_00000002.msg
│   └── ...
├── video2/
│   ├── 20260315_100000_00000001.msg
│   └── ...
└── video3/
    └── ...
```

### 自动清理策略

归档 Sink 会自动清理旧文件：
- 每处理 100 帧检查一次
- 保留最近的 N 个文件（默认 1000）
- 按修改时间删除最旧的文件

## 监控

### 查看归档状态

```bash
# 查看归档文件数量
find ./data/message_archive -name "*.msg" | wc -l

# 查看归档占用空间
du -sh ./data/message_archive

# 按 source_id 统计
for dir in ./data/message_archive/*/; do
  echo "$(basename $dir): $(find $dir -name "*.msg" | wc -l) 个文件"
done

# 查看最新的归档文件
find ./data/message_archive -name "*.msg" -type f -exec ls -lht {} + | head -10
```

### 查看日志

```bash
# 归档 Sink 日志
docker-compose logs -f message-archive-sink

# 查看最近 100 行
docker-compose logs --tail=100 message-archive-sink
```

## 故障排查

### 问题 1：归档文件过多，磁盘空间不足

**解决方案：**
1. 减少 `MAX_FILES_PER_SOURCE` 的值
2. 运行清理脚本：`bash scripts/cleanup_archive.sh --keep 1`
3. 增加磁盘空间

### 问题 2：重放时找不到文件

**检查：**
```bash
# 检查归档目录
ls -la ./data/message_archive/

# 检查文件权限
ls -la ./data/message_archive/video1/

# 检查容器内的路径
docker-compose run --rm message-archive-sink ls -la /data/message_archive/
```

### 问题 3：重放速度太快或太慢

**调整 FPS：**
```bash
# 慢速重放（10 fps）
docker-compose run --rm -e FPS=10 message-archive-sink python /opt/adapters/message_archive_source.py

# 快速重放（尽快发送）
docker-compose run --rm -e FPS=0 message-archive-sink python /opt/adapters/message_archive_source.py
```

## 最佳实践

1. **生产环境**：默认不启用归档，按需启用（使用 profile）
2. **开发环境**：可以默认启用，便于调试
3. **存储管理**：定期清理旧归档，避免磁盘空间不足
4. **监控告警**：监控归档目录大小，设置告警阈值
5. **备份策略**：重要的归档可以备份到对象存储（S3/MinIO）

## 与其他持久化方案对比

| 功能 | 消息归档 | PostgreSQL | Redis Stream |
|------|---------|-----------|--------------|
| 完整性 | 100% | 60% | 5% |
| 存储成本 | 高 | 低 | 极低 |
| 重放能力 | 完整 | 部分 | 无 |
| 查询能力 | 无 | 强 | 弱 |
| 适用场景 | 调试/重放 | 数据分析 | 实时监控 |

**推荐组合：**
- PostgreSQL：数据分析和查询
- Redis Stream：实时监控和追踪
- 消息归档：调试和完整重放

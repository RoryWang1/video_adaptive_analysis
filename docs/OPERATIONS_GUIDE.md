# 系统运维指南

本文档整合了系统的监控、归档、故障排查等运维相关内容。

---

## 目录

1. [监控系统](#监控系统)
2. [消息归档](#消息归档)
3. [故障排查](#故障排查)
4. [最佳实践](#最佳实践)

---

## 监控系统

### 概述

系统使用 Prometheus + Grafana 进行实时监控，可以监控：
- 模块 FPS（帧率）
- Pipeline 延迟
- GPU 利用率
- 吞吐量
- 对象检测数量

### 架构

```
Savant 模块 (YOLOv8/PeopleNet)
    ↓ 暴露 Prometheus 指标
Prometheus (采集和存储)
    ↓ 提供数据源
Grafana (可视化面板)
```

### 配置

**模块配置** (`modules/*/module.yml`):
```yaml
parameters:
  metrics:
    frame_period: 1000      # 每 1000 帧报告一次
    time_period: 10         # 每 10 秒报告一次
    prometheus:
      port: 8000            # YOLOv8 使用 8000，PeopleNet 使用 8001
```

**Prometheus 配置** (`monitoring/prometheus.yml`):
- 采集间隔: 10 秒
- 采集目标: yolov8-module:8000, peoplenet-module:8001

### 部署

```bash
# 本地验证配置
docker-compose config

# 检查 Prometheus 配置
docker run --rm -v $(pwd)/monitoring:/etc/prometheus \
  prom/prometheus:latest \
  promtool check config /etc/prometheus/prometheus.yml

# 启动服务
docker-compose up -d
```

### 访问

**Prometheus**: http://localhost:9090

常用查询:
```promql
# 模块 FPS
rate(savant_frame_counter[1m])

# Pipeline 延迟
savant_pipeline_latency_ms

# 对象检测数量
rate(savant_object_counter[1m])
```

**Grafana**: http://localhost:3000
- 默认用户名: admin
- 默认密码: admin

### 监控指标

| 指标名称 | 说明 | 单位 |
|---------|------|------|
| savant_frame_counter | 处理的帧数 | 帧 |
| savant_object_counter | 检测的对象数 | 个 |
| savant_pipeline_latency_ms | Pipeline 延迟 | 毫秒 |
| savant_fps | 实时 FPS | 帧/秒 |
| savant_batch_size | 批处理大小 | 帧 |

### 性能目标

| 指标 | 目标值 |
|------|--------|
| YOLOv8 FPS | > 40 |
| PeopleNet FPS | > 20 |
| 端到端延迟 | < 100ms |
| GPU 利用率 | > 60% |

---

## 消息归档

### 概述

消息归档功能将完整的 Savant Message 序列化后存储到文件系统，支持完整的数据重放和调试。

### 功能特性

- ✅ 保留 100% 完整的消息内容（视频帧 + 检测结果 + 元数据）
- ✅ 支持按 source_id 分组存储
- ✅ 自动清理旧文件（可配置保留数量）
- ✅ 支持完整重放和调试
- ✅ 支持按帧率控制重放速度
- ✅ 支持循环重放

### 启用归档

**方法 1：使用 Docker Compose Profile**

```bash
# 启动归档服务
docker-compose --profile archive up -d message-archive-sink

# 查看归档日志
docker-compose logs -f message-archive-sink

# 停止归档服务
docker-compose stop message-archive-sink
```

**方法 2：修改 docker-compose.yml**

移除 `message-archive-sink` 服务中的 `profiles` 配置，使其默认启动。

### 配置选项

**归档 Sink 环境变量**:

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ZMQ_ENDPOINT` | ZeroMQ 源端点 | `sub+connect:ipc:///tmp/zmq-sockets/output-yolov8.ipc` |
| `ARCHIVE_DIR` | 归档目录 | `/data/message_archive` |
| `MAX_FILES_PER_SOURCE` | 每个 source 最多保留的文件数 | `1000` |

**重放 Source 环境变量**:

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ZMQ_ENDPOINT` | ZeroMQ 目标端点 | `pub+bind:ipc:///tmp/zmq-sockets/replay.ipc` |
| `ARCHIVE_DIR` | 归档目录 | `/data/message_archive` |
| `SOURCE_ID` | 只重放指定 source_id（可选） | 无 |
| `FPS` | 重放帧率（可选，0 表示尽快发送） | `0` |
| `LOOP` | 是否循环重放 | `false` |

### 使用示例

**重放归档消息**:

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

**清理旧归档**:

```bash
# 清理 7 天前的归档（默认）
bash scripts/cleanup_archive.sh

# 清理 3 天前的归档
bash scripts/cleanup_archive.sh --keep 3

# 只清理 video1 的归档
bash scripts/cleanup_archive.sh --source video1

# Dry-run 模式（查看将要删除的文件）
bash scripts/cleanup_archive.sh --dry-run
```

**定期清理（Cron）**:

```bash
# 每天凌晨 2 点清理 7 天前的归档
0 2 * * * cd /path/to/ai_video_analysis && bash scripts/cleanup_archive.sh
```

### 存储管理

**存储空间估算**:
- 每帧大小：约 100KB - 1MB（取决于分辨率和压缩）
- 1 小时视频（25fps）：约 9GB - 90GB
- 建议保留时间：1-7 天

**目录结构**:
```
data/message_archive/
├── video1/
│   ├── 20260315_100000_00000001.msg
│   ├── 20260315_100000_00000002.msg
│   └── ...
├── video2/
│   └── ...
```

**自动清理策略**:
- 每处理 100 帧检查一次
- 保留最近的 N 个文件（默认 1000）
- 按修改时间删除最旧的文件

### 监控归档

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

# 查看日志
docker-compose logs -f message-archive-sink
```

### 与其他持久化方案对比

| 功能 | 消息归档 | PostgreSQL | Redis Stream |
|------|---------|-----------|--------------|
| 完整性 | 100% | 60% | 5% |
| 存储成本 | 高 | 低 | 极低 |
| 重放能力 | 完整 | 部分 | 无 |
| 查询能力 | 无 | 强 | 弱 |
| 适用场景 | 调试/重放 | 数据分析 | 实时监控 |

**推荐组合**:
- PostgreSQL：数据分析和查询
- Redis Stream：实时监控和追踪
- 消息归档：调试和完整重放

---

## 故障排查

### 监控相关

**Prometheus 无法采集指标**:

```bash
# 检查模块是否暴露指标端口
curl http://localhost:8000/metrics
curl http://localhost:8001/metrics

# 检查 Prometheus 日志
docker logs <prometheus_container_id>
```

**Grafana 无法连接 Prometheus**:

```bash
# 检查 Prometheus 是否运行
docker ps | grep prometheus

# 检查网络连接
docker exec <grafana_container_id> curl http://prometheus:9090/api/v1/status/config
```

**模块指标端口冲突**:

如果端口 8000/8001 已被占用：
1. 修改 `modules/*/module.yml` 中的 `prometheus.port`
2. 修改 `docker-compose.yml` 中的端口映射
3. 修改 `monitoring/prometheus.yml` 中的采集目标

### 归档相关

**归档文件过多，磁盘空间不足**:

1. 减少 `MAX_FILES_PER_SOURCE` 的值
2. 运行清理脚本：`bash scripts/cleanup_archive.sh --keep 1`
3. 增加磁盘空间

**重放时找不到文件**:

```bash
# 检查归档目录
ls -la ./data/message_archive/

# 检查文件权限
ls -la ./data/message_archive/video1/

# 检查容器内的路径
docker-compose run --rm message-archive-sink ls -la /data/message_archive/
```

**重放速度太快或太慢**:

```bash
# 慢速重放（10 fps）
docker-compose run --rm -e FPS=10 message-archive-sink python /opt/adapters/message_archive_source.py

# 快速重放（尽快发送）
docker-compose run --rm -e FPS=0 message-archive-sink python /opt/adapters/message_archive_source.py
```

---

## 最佳实践

### 监控

1. **定期检查监控面板**
   - 关注 GPU 利用率和显存占用
   - 监控推理延迟趋势
   - 设置告警阈值

2. **性能基线**
   - 记录不同配置下的性能数据
   - 建立性能基线
   - 定期对比验证

3. **告警规则**
   - GPU 利用率 < 20% 或 > 90%
   - 推理延迟 > 200ms
   - 帧率下降 > 20%

### 归档

1. **生产环境**
   - 默认不启用归档，按需启用（使用 profile）
   - 定期清理旧归档，避免磁盘空间不足

2. **开发环境**
   - 可以默认启用，便于调试
   - 使用较小的 `MAX_FILES_PER_SOURCE` 值

3. **存储管理**
   - 监控归档目录大小，设置告警阈值
   - 重要的归档可以备份到对象存储（S3/MinIO）
   - 定期清理过期数据

### 故障恢复

1. **自动重启**
   - 配置容器重启策略：`restart: unless-stopped`
   - 监控服务健康状态

2. **数据恢复**
   - 使用消息归档进行数据重放
   - 从 PostgreSQL 查询历史数据
   - 从 Redis Stream 获取最近数据

3. **性能恢复**
   - 调整批处理大小
   - 优化 TensorRT 引擎配置
   - 增加 GPU 显存分配


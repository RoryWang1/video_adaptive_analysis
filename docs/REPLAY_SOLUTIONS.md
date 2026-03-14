# 数据重放方案对比

## 背景

原始的 `redis-stream-source` 设计存在问题：Redis Stream 只存储帧元数据，无法重构完整的 Savant Message 对象进行重放。

## 方案对比

### 方案 1：完整消息归档（推荐 ⭐⭐⭐⭐⭐）

**实现：**
- `message_archive_sink.py` - 将完整的 Savant Message 序列化后存储到文件
- `message_archive_source.py` - 从文件读取并重放完整消息

**优点：**
- ✅ 保留完整的消息内容（视频帧、检测结果、所有元数据）
- ✅ 重放时无需重构，直接反序列化即可
- ✅ 实现简单，可靠性高
- ✅ 支持完整的管道重放和调试
- ✅ 可以按 source_id 分组存储和重放

**缺点：**
- ❌ 存储空间占用较大（包含视频帧数据）
- ❌ 需要额外的磁盘空间

**适用场景：**
- 调试和测试
- 管道性能测试
- 完整数据备份
- 离线处理

**存储估算：**
- 每帧约 100KB - 1MB（取决于分辨率和压缩）
- 1小时视频（25fps）：约 9GB - 90GB

---

### 方案 2：PostgreSQL 数据重放（推荐 ⭐⭐⭐）

**实现：**
- `postgres_replay_source.py` - 从 PostgreSQL 读取检测结果，重构消息

**优点：**
- ✅ 利用现有的 PostgreSQL 数据
- ✅ 支持灵活的查询和过滤
- ✅ 存储空间小（只存储检测结果）
- ✅ 适合数据分析和可视化

**缺点：**
- ❌ 无法重构完整的视频帧数据
- ❌ 需要实现复杂的 VideoFrame 构造逻辑
- ❌ 可能丢失部分元数据

**适用场景：**
- 数据分析和统计
- 结果可视化
- 历史数据查询
- 不需要视频帧的场景

---

### 方案 3：Redis Stream + 外部存储（混合方案）⭐⭐⭐⭐

**实现：**
- Redis Stream 存储元数据（快速查询）
- 对象存储（S3/MinIO）存储完整消息
- 通过元数据索引查找完整消息

**优点：**
- ✅ 快速的元数据查询
- ✅ 可扩展的存储
- ✅ 支持完整重放
- ✅ 成本优化（冷热数据分离）

**缺点：**
- ❌ 架构复杂
- ❌ 需要额外的对象存储服务

**适用场景：**
- 大规模生产环境
- 需要长期存储
- 需要快速查询 + 完整重放

---

### 方案 4：当前方案（Redis Stream 仅元数据）⭐⭐

**实现：**
- 当前的 `redis-stream-sink` - 只存储元数据

**优点：**
- ✅ 实现简单
- ✅ 存储空间极小
- ✅ 适合实时监控

**缺点：**
- ❌ 无法重放完整数据
- ❌ 只能用于监控和追踪

**适用场景：**
- 实时监控
- 帧处理状态追踪
- 不需要重放的场景

---

## 推荐方案

### 小规模/开发环境
**方案 1：完整消息归档**
- 简单可靠
- 完整重放能力
- 便于调试

### 中等规模/生产环境
**方案 1 + 方案 4 组合**
- Redis Stream 用于实时监控
- 消息归档用于调试和重放
- PostgreSQL 用于数据分析

### 大规模/企业环境
**方案 3：混合方案**
- Redis Stream 快速查询
- 对象存储长期保存
- PostgreSQL 结构化分析

---

## 实施建议

### 立即实施（推荐）

**添加消息归档功能：**

1. 在 docker-compose.yml 中添加服务：

```yaml
  message-archive-sink:
    image: ghcr.io/insight-platform/savant-adapters-py:0.6.0
    restart: unless-stopped
    volumes:
      - zmq_sockets:/tmp/zmq-sockets
      - ./adapters:/opt/adapters
      - ./data/message_archive:/data/message_archive
    environment:
      - ZMQ_ENDPOINT=sub+connect:ipc:///tmp/zmq-sockets/output-yolov8.ipc
      - ARCHIVE_DIR=/data/message_archive
    command: python /opt/adapters/message_archive_sink.py
    depends_on:
      - yolov8-module
```

2. 需要时启动重放：

```bash
docker-compose run --rm message-archive-source \
  -e ZMQ_ENDPOINT=pub+bind:ipc:///tmp/zmq-sockets/replay.ipc \
  -e ARCHIVE_DIR=/data/message_archive \
  -e SOURCE_ID=video1
```

### 可选优化

**添加存储管理：**
- 定期清理旧归档（保留最近 N 天）
- 压缩归档文件
- 按日期/source_id 组织目录结构

**示例清理脚本：**

```bash
#!/bin/bash
# 清理 7 天前的归档
find /data/message_archive -name "*.msg" -mtime +7 -delete
```

---

## 总结

| 方案 | 实现难度 | 存储成本 | 重放完整性 | 推荐度 |
|------|---------|---------|-----------|--------|
| 完整消息归档 | 低 | 高 | 100% | ⭐⭐⭐⭐⭐ |
| PostgreSQL 重放 | 中 | 低 | 60% | ⭐⭐⭐ |
| 混合方案 | 高 | 中 | 100% | ⭐⭐⭐⭐ |
| 仅元数据 | 低 | 极低 | 0% | ⭐⭐ |

**最终建议：**
1. **保留当前的 Redis Stream Sink**（用于实时监控）
2. **添加消息归档 Sink**（用于调试和重放）
3. **保留 PostgreSQL Sink**（用于数据分析）
4. **移除 redis-stream-source**（替换为 message-archive-source）

这样可以获得：
- ✅ 实时监控能力（Redis Stream）
- ✅ 完整重放能力（消息归档）
- ✅ 数据分析能力（PostgreSQL）
- ✅ 灵活的存储策略

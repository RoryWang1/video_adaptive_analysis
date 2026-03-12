# 数据持久化层设计文档

## 概述

本文档描述 AI 视频分析系统的数据持久化架构，包括两个层次：
1. **Redis Stream**: 数据流持久化（短期缓冲）
2. **PostgreSQL**: 检测结果持久化（长期存储）

---

## 架构图

```
┌─────────────────┐
│ Source Adapter  │ (视频源)
│ video1, video2  │
└────────┬────────┘
         │ ZeroMQ
         ▼
┌─────────────────┐
│ Redis Stream    │ ← 数据流持久化
│ Sink Adapter    │    - 帧数据缓冲
└────────┬────────┘    - 元数据队列
         │              - TTL=60s
         ▼
┌─────────────────┐
│ Redis           │
│ (Stream)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Redis Stream    │
│ Source Adapter  │
└────────┬────────┘
         │ ZeroMQ
         ▼
┌─────────────────┐
│ Router          │ (流量分发)
└────────┬────────┘
         │
         ├──────────────┬──────────────┐
         ▼              ▼              ▼
    ┌────────┐     ┌────────┐     ┌────────┐
    │YOLOv8  │     │PeopleNet│    │ ...    │
    │Module  │     │Module   │    │        │
    └────┬───┘     └────┬────┘    └────┬───┘
         │              │              │
         └──────────────┴──────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │ Result Sink     │
              │ (多路输出)       │
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    ┌────────┐   ┌──────────┐  ┌────────┐
    │ JSON   │   │PostgreSQL│  │ WebSocket│
    │ File   │   │ Sink     │  │ (未来)  │
    └────────┘   └────┬─────┘  └────────┘
                      │
                      ▼
              ┌──────────────┐
              │ PostgreSQL   │ ← 结果持久化
              │ (检测结果)    │    - 长期存储
              └──────┬───────┘    - 支持查询
                     │
                     ▼
              ┌──────────────┐
              │ FastAPI      │ (查询接口)
              │ (未来)        │
              └──────────────┘
```

---

## 数据流持久化（Redis Stream）

### 设计目标

1. **防止数据丢失**: 服务重启时数据可恢复
2. **背压缓冲**: GPU 处理慢时缓冲视频帧
3. **解耦服务**: Source 和 Module 独立运行
4. **高性能**: 支持 10 路视频并发

### Redis Stream 特性

| 特性 | 说明 |
|------|------|
| 持久化 | AOF/RDB 持久化到磁盘 |
| 消费者组 | 支持多消费者负载均衡 |
| 自动 ID | 自动生成唯一消息 ID |
| 背压控制 | MAXLEN 限制队列长度 |
| 高性能 | 单机 10万+ QPS |

### 数据结构

**核心原则**: Redis Stream 只存储元数据，不存储帧数据

**为什么不存储帧数据？**
- 视频帧是大量二进制数据（1920x1080 ≈ 2MB/帧）
- 10 路视频 × 30fps × 2MB = 600MB/秒，Redis 内存会迅速耗尽
- Savant 通过 ZeroMQ 直接传输帧数据（零拷贝），无需在 Redis 中缓存

**数据流架构**:
```
Source Adapter → ZeroMQ (帧数据，零拷贝) → Router → Modules
                    ↓
              Redis Stream (仅元数据，协调层)
```

**Stream Key**: `savant:video_stream`

**消息格式**:
```
XADD savant:video_stream MAXLEN ~ 1000 *
  source_id video1
  frame_num 12345
  pts 123456789
  timestamp 1678901234.567
  width 1920
  height 1080
  fps 30.0
```

**字段说明**:
- `source_id`: 视频源 ID
- `frame_num`: 帧序号
- `pts`: Presentation Timestamp（微秒）
- `timestamp`: Unix 时间戳（秒）
- `width/height`: 帧尺寸
- `fps`: 帧率
- **注意**: 不包含 frame_data 字段

**数据大小**:
- 单条消息：~50 bytes
- 1000 条消息：~50KB
- 10 路视频 × 30fps：15KB/秒（完全可接受）

### Redis 配置

```yaml
redis:
  image: redis:7-alpine
  command: >
    redis-server
    --appendonly yes
    --appendfsync everysec
    --maxmemory 2gb
    --maxmemory-policy allkeys-lru
    --save 60 1000
  volumes:
    - redis_data:/data
  ports:
    - "6379:6379"
```

**参数说明**:
- `appendonly yes`: 启用 AOF 持久化
- `appendfsync everysec`: 每秒同步一次（平衡性能和安全）
- `maxmemory 2gb`: 最大内存 2GB
- `maxmemory-policy allkeys-lru`: 内存满时使用 LRU 淘汰
- `save 60 1000`: 60 秒内有 1000 次写入则保存 RDB

### Adapter 实现

**Sink Adapter** (Source → Redis):
```python
# adapters/redis_stream_sink.py
import redis
import base64
from savant_rs.primitives import VideoFrame

class RedisStreamSink:
    def __init__(self, redis_host, redis_port, stream_key, maxlen):
        self.redis = redis.Redis(host=redis_host, port=redis_port)
        self.stream_key = stream_key
        self.maxlen = maxlen

    def process_frame(self, frame: VideoFrame):
        # 编码帧数据
        frame_data = base64.b64encode(frame.content).decode('utf-8')

        # 写入 Redis Stream
        self.redis.xadd(
            self.stream_key,
            {
                'source_id': frame.source_id,
                'frame_num': frame.idx,
                'timestamp': frame.pts / 1000000.0,
                'pts': frame.pts,
                'frame_width': frame.width,
                'frame_height': frame.height,
                'frame_data': frame_data,
                'metadata': frame.json()
            },
            maxlen=self.maxlen,
            approximate=True
        )
```

**Source Adapter** (Redis → Router):
```python
# adapters/redis_stream_source.py
import redis
import base64
from savant_rs.primitives import VideoFrame

class RedisStreamSource:
    def __init__(self, redis_host, redis_port, stream_key, group_name, consumer_name):
        self.redis = redis.Redis(host=redis_host, port=redis_port)
        self.stream_key = stream_key
        self.group_name = group_name
        self.consumer_name = consumer_name

        # 创建消费者组
        try:
            self.redis.xgroup_create(stream_key, group_name, id='0', mkstream=True)
        except redis.ResponseError:
            pass  # 组已存在

    def read_frames(self):
        while True:
            # 读取消息
            messages = self.redis.xreadgroup(
                self.group_name,
                self.consumer_name,
                {self.stream_key: '>'},
                count=1,
                block=1000
            )

            if not messages:
                continue

            for stream, msgs in messages:
                for msg_id, data in msgs:
                    # 解码帧数据
                    frame_data = base64.b64decode(data[b'frame_data'])

                    # 构建 VideoFrame
                    frame = VideoFrame(
                        source_id=data[b'source_id'].decode(),
                        idx=int(data[b'frame_num']),
                        pts=int(data[b'pts']),
                        width=int(data[b'frame_width']),
                        height=int(data[b'frame_height']),
                        content=frame_data
                    )

                    yield frame

                    # 确认消息
                    self.redis.xack(self.stream_key, self.group_name, msg_id)
```

---

## 结果持久化（PostgreSQL）

### 设计目标

1. **长期存储**: 保存所有检测结果
2. **高效查询**: 支持按时间、source_id、对象类型查询
3. **数据分析**: 支持统计和聚合查询
4. **可扩展**: 支持未来添加更多字段

### 数据库表结构

**设计原则**:
1. **规范化设计**: 减少数据冗余，使用外键
2. **分离关注点**: 帧级别和对象级别分开存储
3. **查询优化**: 合理的索引策略
4. **数据完整性**: 唯一约束防止重复

**1. sources 表** (视频源信息):
```sql
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100),
    location VARCHAR(255),
    type VARCHAR(20) CHECK (type IN ('file', 'rtsp', 'usb', 'http')),
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sources_source_id ON sources(source_id);
CREATE INDEX idx_sources_enabled ON sources(enabled);
```

**2. models 表** (AI 模型信息):
```sql
CREATE TABLE models (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(50) UNIQUE NOT NULL,
    model_type VARCHAR(50),  -- detector, classifier, tracker
    version VARCHAR(20),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_models_model_name ON models(model_name);
```

**3. frame_detections 表** (帧级别检测结果):
```sql
CREATE TABLE frame_detections (
    id BIGSERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    model_id INTEGER NOT NULL REFERENCES models(id),
    frame_num INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    fps FLOAT,
    object_count INTEGER DEFAULT 0,
    processing_time_ms FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_id, model_id, frame_num, timestamp)
);

-- 索引
CREATE INDEX idx_frame_detections_source ON frame_detections(source_id);
CREATE INDEX idx_frame_detections_model ON frame_detections(model_id);
CREATE INDEX idx_frame_detections_timestamp ON frame_detections(timestamp DESC);
CREATE INDEX idx_frame_detections_source_time ON frame_detections(source_id, timestamp DESC);
```

**字段说明**:
- `source_id`: 外键引用 sources 表
- `model_id`: 外键引用 models 表
- `frame_num`: 帧序号
- `timestamp`: 帧时间戳
- `object_count`: 检测到的对象数量（冗余字段，用于快速统计）
- `UNIQUE` 约束: 防止重复插入同一帧

**4. detected_objects 表** (对象级别检测结果):
```sql
CREATE TABLE detected_objects (
    id BIGSERIAL PRIMARY KEY,
    frame_detection_id BIGINT NOT NULL REFERENCES frame_detections(id) ON DELETE CASCADE,
    object_class VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    bbox_x INTEGER NOT NULL,
    bbox_y INTEGER NOT NULL,
    bbox_width INTEGER NOT NULL CHECK (bbox_width > 0),
    bbox_height INTEGER NOT NULL CHECK (bbox_height > 0),
    track_id INTEGER,
    attributes JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_detected_objects_frame ON detected_objects(frame_detection_id);
CREATE INDEX idx_detected_objects_class ON detected_objects(object_class);
CREATE INDEX idx_detected_objects_confidence ON detected_objects(confidence);
CREATE INDEX idx_detected_objects_track ON detected_objects(track_id) WHERE track_id IS NOT NULL;
CREATE INDEX idx_detected_objects_class_confidence ON detected_objects(object_class, confidence);
```

**字段说明**:
- `frame_detection_id`: 外键引用 frame_detections 表
- `object_class`: 对象类别（person, car, etc.）
- `confidence`: 置信度（0-1）
- `bbox_*`: 边界框坐标
- `track_id`: 可选，用于对象追踪
- `attributes`: 可选，额外属性（JSONB 格式）
- `ON DELETE CASCADE`: 删除帧时自动删除关联对象

**5. hourly_statistics 表** (小时级统计):
```sql
CREATE TABLE hourly_statistics (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    model_id INTEGER NOT NULL REFERENCES models(id),
    stat_hour TIMESTAMP NOT NULL,
    total_frames INTEGER DEFAULT 0,
    total_objects INTEGER DEFAULT 0,
    object_class_counts JSONB,
    avg_confidence FLOAT,
    avg_processing_time_ms FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_id, model_id, stat_hour)
);

CREATE INDEX idx_hourly_stats_hour ON hourly_statistics(stat_hour DESC);
CREATE INDEX idx_hourly_stats_source_model ON hourly_statistics(source_id, model_id);
```

**字段说明**:
- `stat_hour`: 统计时间（精确到小时）
- `object_class_counts`: 对象类别计数（JSONB 格式）
  ```json
  {"person": 100, "car": 50, "bicycle": 20}
  ```

**数据大小估算**:

| 表 | 每条记录 | 每天记录数 | 每天大小 | 30天大小 |
|----|---------|-----------|---------|---------|
| frame_detections | ~100 bytes | 2600万 | 2.5GB | 75GB |
| detected_objects | ~80 bytes | 1.3亿 | 10GB | 300GB |
| hourly_statistics | ~200 bytes | 240 | 48KB | 1.4MB |
| **总计** | - | - | **12.5GB/天** | **375GB** |

**优化策略**:
- 定期清理旧数据（保留 30 天）
- 使用表分区（数据量大时）
- 定期 VACUUM 和 ANALYZE

### PostgreSQL 配置

```yaml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: savant_video_analysis
    POSTGRES_USER: savant
    POSTGRES_PASSWORD: savant_password
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
  ports:
    - "5432:5432"
  command: >
    postgres
    -c shared_buffers=256MB
    -c max_connections=100
    -c work_mem=4MB
```

### 查询示例

**查询 1: 获取某个视频源的最近检测结果**
```sql
SELECT
    fd.id,
    s.source_id,
    m.model_name,
    fd.frame_num,
    fd.timestamp,
    fd.object_count,
    fd.processing_time_ms
FROM frame_detections fd
JOIN sources s ON fd.source_id = s.id
JOIN models m ON fd.model_id = m.id
WHERE s.source_id = 'video1'
ORDER BY fd.timestamp DESC
LIMIT 100;
```

**查询 2: 获取某帧的所有检测对象**
```sql
SELECT
    do.object_class,
    do.confidence,
    do.bbox_x,
    do.bbox_y,
    do.bbox_width,
    do.bbox_height,
    do.track_id
FROM detected_objects do
WHERE do.frame_detection_id = 12345
ORDER BY do.confidence DESC;
```

**查询 3: 统计某个时间段内检测到的人数**
```sql
SELECT COUNT(*) as person_count
FROM detected_objects do
JOIN frame_detections fd ON do.frame_detection_id = fd.id
WHERE fd.timestamp BETWEEN '2026-03-12 00:00' AND '2026-03-12 23:59'
AND do.object_class = 'person'
AND do.confidence >= 0.8;
```

**查询 4: 追踪某个对象的轨迹**
```sql
SELECT
    fd.timestamp,
    s.source_id,
    do.bbox_x,
    do.bbox_y,
    do.bbox_width,
    do.bbox_height,
    do.confidence
FROM detected_objects do
JOIN frame_detections fd ON do.frame_detection_id = fd.id
JOIN sources s ON fd.source_id = s.id
WHERE do.track_id = 123
ORDER BY fd.timestamp;
```

**查询 5: 获取小时级统计**
```sql
SELECT
    s.source_id,
    m.model_name,
    hs.stat_hour,
    hs.total_frames,
    hs.total_objects,
    hs.object_class_counts,
    hs.avg_confidence,
    hs.avg_processing_time_ms
FROM hourly_statistics hs
JOIN sources s ON hs.source_id = s.id
JOIN models m ON hs.model_id = m.id
WHERE hs.stat_hour >= NOW() - INTERVAL '24 hours'
ORDER BY hs.stat_hour DESC;
```

**查询 6: 按对象类别统计（今天）**
```sql
SELECT
    do.object_class,
    COUNT(*) as count,
    AVG(do.confidence) as avg_confidence,
    MIN(do.confidence) as min_confidence,
    MAX(do.confidence) as max_confidence
FROM detected_objects do
JOIN frame_detections fd ON do.frame_detection_id = fd.id
WHERE fd.timestamp >= CURRENT_DATE
GROUP BY do.object_class
ORDER BY count DESC;
```

```python
# adapters/postgres_sink.py
import asyncpg
import json
from datetime import datetime

class PostgresSink:
    def __init__(self, db_url):
        self.db_url = db_url
        self.pool = None

    async def init(self):
        self.pool = await asyncpg.create_pool(self.db_url)

    async def process_result(self, result):
        """处理检测结果"""
        async with self.pool.acquire() as conn:
            # 插入检测结果
            await conn.execute("""
                INSERT INTO detection_results
                (source_id, model_name, frame_num, timestamp, fps, objects, processing_time_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                result['source_id'],
                result['model_name'],
                result['frame_num'],
                datetime.fromtimestamp(result['timestamp']),
                result.get('fps'),
                json.dumps(result['objects']),
                result.get('processing_time_ms')
            )

    async def get_results(self, source_id=None, start_time=None, end_time=None, limit=100):
        """查询检测结果"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT * FROM detection_results
                WHERE 1=1
            """
            params = []

            if source_id:
                params.append(source_id)
                query += f" AND source_id = ${len(params)}"

            if start_time:
                params.append(start_time)
                query += f" AND timestamp >= ${len(params)}"

            if end_time:
                params.append(end_time)
                query += f" AND timestamp <= ${len(params)}"

            query += f" ORDER BY timestamp DESC LIMIT {limit}"

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
```

---

## 配置集成

### config.yml 扩展

```yaml
# 数据持久化配置
persistence:
  # Redis Stream 配置
  redis:
    enabled: true
    host: redis
    port: 6379
    stream_key: savant:video_stream
    maxlen: 1000  # 队列最大长度
    consumer_group: savant_group
    memory_limit: 2gb

  # PostgreSQL 配置
  postgres:
    enabled: true
    host: postgres
    port: 5432
    database: savant_video_analysis
    user: savant
    password: savant_password
    max_connections: 100
```

---

## 性能指标

### Redis Stream

| 指标 | 目标值 |
|------|--------|
| 吞吐量 | 10,000 帧/秒 |
| 延迟 | < 1ms |
| 内存占用 | < 2GB |
| 队列长度 | 1000 帧 |

### PostgreSQL

| 指标 | 目标值 |
|------|--------|
| 写入吞吐量 | 1,000 条/秒 |
| 查询延迟 | < 100ms |
| 存储空间 | 按需扩展 |

---

## 数据保留策略

### Redis Stream
- **保留时间**: 60 秒
- **清理策略**: MAXLEN 自动淘汰旧数据
- **备份**: 不需要（临时数据）

### PostgreSQL
- **保留时间**: 30 天（可配置）
- **清理策略**: 定时任务删除旧数据
- **备份**: 每日备份

```sql
-- 清理 30 天前的数据
DELETE FROM detection_results
WHERE timestamp < NOW() - INTERVAL '30 days';
```

---

## 故障恢复

### Redis Stream 故障
1. Redis 重启后自动从 AOF/RDB 恢复
2. 消费者组自动重连
3. 未确认的消息自动重新投递

### PostgreSQL 故障
1. 使用 WAL 日志恢复
2. 主从复制（未来）
3. 定期备份恢复

---

## 监控指标

### Redis Stream
- `redis_stream_length`: 队列长度
- `redis_stream_lag`: 消费延迟
- `redis_memory_used`: 内存使用
- `redis_commands_processed`: 命令处理数

### PostgreSQL
- `postgres_connections`: 连接数
- `postgres_insert_rate`: 插入速率
- `postgres_query_time`: 查询耗时
- `postgres_table_size`: 表大小

---

## 下一步

1. ✅ 设计完成
2. ⏳ 实现 Redis Stream Adapter
3. ⏳ 实现 PostgreSQL Sink
4. ⏳ 更新配置生成工具
5. ⏳ 测试和验证

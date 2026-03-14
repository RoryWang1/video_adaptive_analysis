# 持久化功能修复总结

## 修复时间
2026-03-14

## 问题概述
AI 视频分析系统在云端部署后，PostgreSQL 和 Redis 持久化功能出现多个错误，导致数据无法正常存储。

## 修复的问题

### 1. Router 配置错误
**问题：**
- Python 缩进错误
- 错误的 import 路径
- `init()` 函数签名不匹配
- 配置文件缺少必需字段

**解决方案：**
- 修复 `config/router_handler.py` 的缩进
- 使用正确的 import：`from savant_rs.utils.serialization import Message`
- 修改 `init()` 接受 `params` 参数，使用 `register_handler()` 注册
- 修复 `config/router_config.json`，添加 `handler` 字段和正确的 `common` 结构

### 2. PostgreSQL Sink 错误
**问题：**
- 容器启动时 pip install 卡住
- 使用了不存在的 Savant API
- Message 对象属性访问错误
- frame_num 提取错误（获取到 "25/1" 字符串而不是整数）
- model_name 始终为 "unknown"

**解决方案：**
- 创建 `adapters/Dockerfile.postgres-sink`，预装 psycopg2-binary
- 使用清华镜像源加速安装
- 使用 `savant_rs.zmq.BlockingReader` 读取消息
- 修复 frame_num 提取逻辑，尝试多个属性（keyframe_id, idx, frame_num）
- 从环境变量 `MODEL_NAME` 获取模型名称
- 在 docker-compose.yml 中为每个 sink 设置 MODEL_NAME

### 3. Redis Stream Sink 错误
**问题：**
- 连接到错误的 ZeroMQ 端点（input-video.ipc）
- frame_num 提取错误

**解决方案：**
- 修改配置连接到 `output-yolov8.ipc`
- 修复 frame_num 提取逻辑

### 4. 消息归档功能（新增）
**功能：**
- 将完整的 Savant Message 序列化后存储到文件系统
- 支持完整的数据重放和调试

**实现：**
- `message_archive_sink.py` - 归档完整消息
- `message_archive_source.py` - 重放归档消息
- 自动清理旧文件，避免磁盘空间不足

**解决方案：**
- 使用 Docker Compose Profile 按需启用
- 保留 100% 完整的消息内容
- 支持按 source_id 分组存储和重放
- 详见 `docs/MESSAGE_ARCHIVE_GUIDE.md`

## 技术要点

### Savant 0.6.0 API 使用
```python
# 正确的 ZeroMQ 读取方式
from savant_rs.zmq import BlockingReader, ReaderConfigBuilder

config = ReaderConfigBuilder(zmq_endpoint).build()
reader = BlockingReader(config)
reader.start()

result = reader.receive()
message = result.message  # Message 对象
frame = message.as_video_frame()  # VideoFrame 对象
```

### VideoFrame 属性访问
```python
# 帧编号（尝试多个可能的属性）
frame_num = 0
if hasattr(frame, 'keyframe_id'):
    frame_num = frame.keyframe_id
elif hasattr(frame, 'idx'):
    frame_num = frame.idx
elif hasattr(frame, 'frame_num'):
    frame_num = frame.frame_num

# 其他属性
source_id = frame.source_id
pts = frame.pts
width = frame.width
height = frame.height
```

### 对象访问
```python
from savant_rs.primitives import VideoObjectsQuery

query = VideoObjectsQuery.any()
objects = frame.access_objects(query)

for obj in objects:
    bbox = obj.detection_box
    label = obj.label
    confidence = obj.confidence
```

## 部署改进

### 自定义 Dockerfile
创建 `adapters/Dockerfile.postgres-sink`：
```dockerfile
FROM ghcr.io/insight-platform/savant-adapters-py:0.6.0

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple psycopg2-binary

WORKDIR /opt/adapters
CMD ["python", "/opt/adapters/postgres_sink.py"]
```

### 部署脚本更新
修改 `scripts/deploy.sh`，添加镜像构建步骤：
```bash
docker-compose build postgres-sink-yolov8 postgres-sink-peoplenet
```

## 验证结果

### 服务状态
- ✅ postgres-sink-yolov8: 运行中
- ✅ postgres-sink-peoplenet: 运行中
- ✅ redis-stream-sink: 运行中
- 💤 message-archive-sink: 按需启用（使用 `--profile archive`）

### 数据统计（2026-03-14 15:56）
- PostgreSQL frame_detections: 45,700+ 条记录
- PostgreSQL detected_objects: 117,762+ 条记录
- Redis Stream: ~1,000 条记录（maxlen 限制）

### 数据示例
```sql
-- 查看最近的检测记录
SELECT s.source_id, m.model_name, fd.frame_num, fd.object_count, fd.created_at
FROM frame_detections fd
JOIN sources s ON fd.source_id = s.id
JOIN models m ON fd.model_id = m.id
ORDER BY fd.created_at DESC
LIMIT 5;

-- 结果
 source_id | model_name | frame_num | object_count |         created_at
-----------+------------+-----------+--------------+----------------------------
 video2    | yolov8     |         0 |            0 | 2026-03-14 15:48:48.1415
 video1    | yolov8     |         0 |           21 | 2026-03-14 15:48:48.134506
```

## 数据流架构

```
视频源 (video1, video2, video3)
    ↓
Router (路由到不同模块)
    ↓
┌───────────────┬───────────────┬───────────────┐
│               │               │               │
YOLOv8 模块    PeopleNet 模块  │               │
│               │               │               │
├───────────────┼───────────────┼───────────────┤
│               │               │               │
PostgreSQL     PostgreSQL      Redis Stream   消息归档
Sink (YOLOv8)  Sink (PeopleNet) Sink          Sink (可选)
│               │               │               │
└───────────────┴───────────────┴───────────────┘
         ↓              ↓              ↓              ↓
    PostgreSQL      PostgreSQL    Redis Stream   文件系统
    (frame_detections, detected_objects)  (元数据)    (完整消息)
         ↓              ↓              ↓              ↓
    数据分析        数据分析      实时监控        调试/重放
```

**重放流程：**
```
消息归档 Source → Router → 模块 → ...
```

## 文件清单

### 修改的文件
- `config/router_handler.py` - Router 处理器
- `config/router_config.json` - Router 配置
- `adapters/postgres_sink.py` - PostgreSQL Sink
- `adapters/redis_stream_sink.py` - Redis Stream Sink
- `docker-compose.yml` - Docker Compose 配置
- `scripts/deploy.sh` - 部署脚本

### 新增的文件
- `adapters/Dockerfile.postgres-sink` - PostgreSQL Sink 自定义镜像
- `adapters/message_archive_sink.py` - 消息归档 Sink
- `adapters/message_archive_source.py` - 消息归档重放 Source
- `scripts/cleanup_archive.sh` - 归档清理脚本
- `docs/MESSAGE_ARCHIVE_GUIDE.md` - 消息归档使用指南
- `docs/REPLAY_SOLUTIONS.md` - 数据重放方案对比

### 删除的文件
- `adapters/redis_stream_source.py` - 已删除（设计缺陷）
- `adapters/postgres_replay_source.py` - 已删除（暂不需要）

## 经验教训

1. **依赖安装**：不要在容器启动时安装依赖，应该预先构建镜像
2. **API 文档**：Savant 0.6.0 的 API 与文档不完全一致，需要实际测试
3. **错误处理**：添加详细的日志和错误处理，便于调试
4. **属性访问**：使用 `hasattr()` 检查属性是否存在，避免 AttributeError
5. **镜像源**：使用国内镜像源（清华源）加速 pip 安装
6. **容器清理**：遇到 ContainerConfig 错误时，需要停止并删除旧容器

## 后续优化建议

1. **消息归档管理**
   - 配置定期清理任务（Cron）
   - 监控归档目录大小
   - 考虑备份到对象存储（S3/MinIO）

2. **监控告警**
   - 添加数据写入失败的告警机制
   - 监控磁盘空间使用率
   - 监控服务健康状态

3. **性能优化**
   - 调整批量插入大小
   - 优化数据库索引
   - 考虑使用 TimescaleDB 优化时序数据

4. **数据清理**
   - 添加定期清理旧数据的任务
   - 实现数据归档策略
   - 配置数据保留策略

5. **备份策略**
   - 配置 PostgreSQL 自动备份
   - 定期备份重要的归档消息
   - 测试恢复流程

## 参考资料

- Savant 官方文档: https://docs.savant-ai.io/
- savant_rs Python 绑定: https://github.com/insight-platform/savant-rs
- PostgreSQL 文档: https://www.postgresql.org/docs/
- Redis Streams 文档: https://redis.io/docs/data-types/streams/

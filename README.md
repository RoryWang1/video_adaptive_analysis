# AI 视频分析系统

基于 Savant 框架的生产级 AI 视频流分析系统，支持多路视频源、多模型智能路由、实时检测和结果可视化。

## 系统架构

```
┌─────────────────┐
│  视频源适配器    │  video1.mp4, video2.mp4, video3.mp4
└────────┬────────┘
         │ ZeroMQ
         ▼
┌─────────────────┐
│  Savant Router  │  根据 source_id 智能路由
└────┬────────┬───┘
     │        │
     ▼        ▼
┌─────────┐ ┌──────────────┐
│ YOLOv8  │ │  PeopleNet   │  GPU 推理模块
│ Module  │ │   Module     │
└────┬────┘ └──────┬───────┘
     │             │
     ▼             ▼
┌──────────────────────────┐
│   PostgreSQL Sink        │  检测结果持久化
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│   Grafana Dashboard      │  可视化监控
└──────────────────────────┘
```

## 技术栈

### 核心框架
- **Savant 0.6.0**: 视频处理框架
- **DeepStream 7.1**: NVIDIA GPU 推理引擎
- **TensorRT**: 模型加速

### AI 模型
- **YOLOv8**: 通用目标检测（80 类 COCO 数据集）
- **PeopleNet**: 人脸检测（ResNet34）

### 数据存储
- **PostgreSQL 15**: 检测结果持久化存储
- **Redis 7**: 数据流缓存（可选）

### 监控可视化
- **Grafana**: 检测结果可视化
- **Prometheus**: 性能指标采集

### 容器化
- **Docker & Docker Compose**: 服务编排
- **NVIDIA Container Runtime**: GPU 支持

## 核心特性

### 1. 智能路由分发

通过 Savant Router 实现视频源到模型的智能路由：

**配置文件**: `config/router_config.json`

```json
{
  "ingress": [{
    "name": "from_video_sources",
    "socket": {
      "url": "sub+bind:ipc:///tmp/zmq-sockets/input-video.ipc"
    }
  }],
  "egress": [
    {
      "name": "to_yolov8",
      "socket": {
        "url": "pub+bind:ipc:///tmp/zmq-sockets/yolov8.ipc"
      },
      "matcher": "video1,video2"
    },
    {
      "name": "to_peoplenet",
      "socket": {
        "url": "pub+bind:ipc:///tmp/zmq-sockets/peoplenet.ipc"
      },
      "matcher": "video3"
    }
  ]
}
```

**工作原理**:
- 视频源通过 `source_id` 标识（如 video1, video2, video3）
- Router 根据 `matcher` 规则将视频流路由到对应模型
- 支持一对多、多对一的灵活路由配置

**示例**:
- `video1` 和 `video2` → YOLOv8（通用目标检测）
- `video3` → PeopleNet（人脸检测）

### 2. 检测结果持久化

使用 PostgreSQL 存储所有检测结果，支持历史查询和数据分析。

**数据库结构**:

```sql
-- 视频源表
sources (id, source_id, created_at)

-- 模型表
models (id, model_id, created_at)

-- 帧检测结果表
frame_detections (
  id, source_id, model_id, frame_num,
  timestamp, fps, object_count,
  processing_time_ms, created_at
)

-- 检测对象详情表
detected_objects (
  id, frame_detection_id, object_class,
  confidence, bbox_x, bbox_y,
  bbox_width, bbox_height, track_id,
  attributes, created_at
)
```

**持久化效果**:
- ✅ 系统重启后数据不丢失
- ✅ 支持历史数据查询和统计
- ✅ 可追溯每一帧的检测详情
- ✅ 支持按视频源、模型、时间范围查询

### 3. Grafana 可视化监控

实时展示检测结果和系统性能指标。

**访问地址**: `http://<server-ip>:3000`
**默认账号**: admin / admin

**Dashboard 面板**:

1. **检测对象总数**: 累计检测到的所有对象数量
2. **有检测结果的帧数**: 实际检测到对象的帧数统计
3. **按视频源和模型统计**:
   - 显示每个视频源使用的模型
   - 处理帧数和检测对象数
4. **检测对象类别分布**:
   - Top 10 对象类别统计
   - 自动映射类别 ID 到名称（car, person, bus 等）
5. **最近检测结果**: 最新 100 条检测记录详情

**对象类别映射**:
```
YOLOv8 (COCO 数据集):
- 0: person
- 2: car
- 3: motorcycle
- 5: bus
- 6: train
- 7: truck
- 9: traffic light
- 12: stop sign
- 67: cell phone

PeopleNet:
- person: 人脸
```

## 快速开始

### 前置要求

- NVIDIA GPU (支持 CUDA)
- Docker & Docker Compose
- NVIDIA Container Runtime

### 启动系统

```bash
# 克隆项目
git clone https://github.com/RoryWang1/video_adaptive_analysis.git
cd video_adaptive_analysis

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 访问监控

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **YOLOv8 API**: http://localhost:8000/status
- **PeopleNet API**: http://localhost:8001/status

## 配置说明

### 添加新视频源

1. 修改 `docker-compose.yml`，添加新的 source adapter：

```yaml
source-adapter-video4:
  image: ghcr.io/insight-platform/savant-adapters-gstreamer:0.6.0
  volumes:
    - ./videos:/videos
    - zmq_sockets:/tmp/zmq-sockets
  environment:
    - LOCATION=/videos/video4.mp4
    - ZMQ_ENDPOINT=pub+connect:ipc:///tmp/zmq-sockets/input-video.ipc
    - SOURCE_ID=video4
    - SYNC_OUTPUT=True
  entrypoint: /opt/savant/adapters/gst/sources/video_loop.sh
```

2. 修改 `config/router_config.json`，配置路由规则：

```json
{
  "egress": [
    {
      "name": "to_yolov8",
      "matcher": "video1,video2,video4"
    }
  ]
}
```

### 添加新模型

1. 准备模型文件（ONNX 格式）
2. 创建模块配置 `modules/<model_name>/module.yml`
3. 在 `docker-compose.yml` 中添加模块服务
4. 配置 Router 路由规则

## 性能指标

- **吞吐量**: 支持 10+ 路视频同时处理
- **延迟**: 端到端延迟 < 100ms
- **GPU 利用率**: > 60%
- **数据持久化**: 支持百万级检测记录

## 项目结构

```
.
├── config/                 # 配置文件
│   ├── router_config.json  # Router 路由配置
│   └── sources.yml         # 视频源配置
├── modules/                # AI 模型模块
│   ├── yolov8/
│   │   └── module.yml      # YOLOv8 配置
│   └── peoplenet/
│       └── module.yml      # PeopleNet 配置
├── adapters/               # 自定义适配器
│   └── postgres_sink.py    # PostgreSQL 存储适配器
├── monitoring/             # 监控配置
│   ├── prometheus.yml      # Prometheus 配置
│   └── grafana/
│       ├── datasources.yml           # 数据源配置
│       ├── dashboards.yml            # Dashboard 配置
│       └── dashboard-detection-results.json  # 检测结果仪表板
├── database/               # 数据库初始化脚本
│   └── init/
│       └── 01_init.sql     # 表结构定义
├── videos/                 # 视频文件目录
├── docker-compose.yml      # 服务编排配置
└── README.md
```


# AI 视频流分析系统

基于 Savant 框架的生产级 AI 视频流分析系统，支持实时多路视频处理、多模型推理、数据持久化和完整监控。

## 📋 项目概述

**系统特点**:
- ✅ 多 Module 架构（每个模型独立，避免显存浪费）
- ✅ Redis Stream + PostgreSQL 数据持久化（支持重启不丢失）
- ✅ 统一配置管理（config.yml 自动生成 Docker Compose）
- ✅ Savant Router 流量分发（按 source_id 路由）
- ✅ 完整监控体系（Prometheus+Grafana）
- ✅ 消息归档功能（完整数据重放和调试）
- ✅ 自动化部署脚本

**技术栈**:
- Savant 0.6.0 (视频处理框架)
- DeepStream 7.1 (GPU推理引擎)
- TensorRT (模型加速)
- Redis 7 (数据流持久化)
- PostgreSQL 15 (结果存储)
- Prometheus + Grafana (监控)

---

## 🚀 快速开始

### 本地开发环境

**系统要求**:
- macOS (Apple Silicon 或 Intel)
- Anaconda/Miniconda
- Docker Desktop
- Python 3.10

**Python 虚拟环境**:
```bash
# 激活环境
conda activate savant-video-analysis

# 已安装的包
- ultralytics
- onnx
- onnxslim
- onnxruntime
- pyyaml
```

### 云端部署环境

**系统要求**:
- Ubuntu 22.04
- NVIDIA GPU (T4 / RTX 3060+)
- NVIDIA Driver >= 525
- Docker + nvidia-container-toolkit
- 显存 >= 8GB

---

## 📁 项目结构

```
ai_video_analysis/
├── CLAUDE.md                      # Claude 工作规范
├── README.md                      # 本文件
├── config.yml                     # 统一配置文件（核心配置）
├── docker-compose.yml             # 生产环境配置（由 config.yml 生成）
│
├── config/                        # 配置文件目录
│   └── router_config.json         # Router 路由配置（由 generate_config.py 生成）
│
├── modules/                       # Savant 模块配置
│   ├── yolov8/
│   │   └── module.yml             # YOLOv8 检测模块
│   └── peoplenet/
│       └── module.yml             # PeopleNet 人脸检测模块
│
├── models/                        # AI 模型文件
│   ├── yolov8n.onnx               # YOLOv8 ONNX 模型
│   └── peoplenet/                 # PeopleNet 模型文件
│
├── adapters/                      # 自定义适配器（Python）
│   ├── postgres_sink.py           # PostgreSQL 结果存储
│   ├── redis_stream_sink.py       # Redis Stream 数据流
│   ├── message_archive_sink.py    # 消息归档 Sink
│   ├── message_archive_source.py  # 消息重放 Source
│   └── requirements.txt           # Python 依赖
│
├── database/                      # 数据库相关
│   └── init/                      # 初始化脚本
│       └── *.sql                  # 数据库初始化 SQL
│
├── monitoring/                    # 监控配置
│   ├── prometheus.yml             # Prometheus 配置
│   ├── grafana-dashboard.json     # Grafana 面板
│   └── grafana-dashboard-savant.json
│
├── scripts/                       # 工具脚本
│   ├── generate_config.py         # 从 config.yml 生成 Docker Compose
│   ├── validate_config.py         # 验证配置文件
│   ├── deploy.sh                  # 云端部署脚本
│   ├── cleanup_archive.sh         # 归档清理脚本
│   ├── convert_model.sh           # 模型转换脚本
│   ├── verify_local.sh            # 本地验证脚本
│   └── test_persistence.sh        # 持久化测试脚本
│
├── videos/                        # 测试视频文件
│   ├── video1.mp4
│   ├── video2.mp4
│   └── video3.mp4
│
├── output/                        # 输出结果目录
│
└── docs/                          # 文档目录
    ├── README.md                  # 文档导航
    ├── ARCHITECTURE_DESIGN.md     # 架构设计
    ├── DEVELOPMENT_PLAN_MVP.md    # MVP 开发计划
    ├── ADD_NEW_MODEL.md           # 添加新模型指南
    ├── ADD_NEW_VIDEO_SOURCE.md    # 添加新视频源指南
    ├── UNIFIED_CONFIG.md          # 统一配置管理指南
    ├── OPERATIONS_GUIDE.md        # 系统运维指南
    ├── TROUBLESHOOTING.md         # 故障排查指南
    └── savant-reference/          # Savant 官方示例
```

---

## 🏗️ 系统架构

### 完整架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    视频源层 (Video Sources)                      │
│  video1.mp4, video2.mp4, video3.mp4 (本地文件)                   │
│  或 RTSP 摄像头流                                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         Savant Source Adapter (多路视频) - Savant原生            │
│  - 硬件解码(NVDEC)                                               │
│  - 背压感知(backpressure-aware)                                  │
│  - 自动重连、健康检查                                             │
└────────────────────────┬────────────────────────────────────────┘
                         │ ZeroMQ (IPC)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         Savant Router - 按 source_id 分发                        │
│  - video1, video2 → yolov8                                       │
│  - video3 → peoplenet                                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
      ┌──────────────┐      ┌──────────────┐
      │ YOLOv8       │      │ PeopleNet    │
      │ Module       │      │ Module       │
      │ GPU 推理     │      │ GPU 推理     │
      └──────┬───────┘      └──────┬───────┘
             │                     │
             └──────────┬──────────┘
                        ▼
         ┌──────────────────────────────┐
         │ 多个 Sink 并行处理            │
         ├──────────────────────────────┤
         │ 1. PostgreSQL Sink           │ → 结果存储
         │ 2. Redis Stream Sink         │ → 数据流持久化
         │ 3. Message Archive Sink      │ → 完整消息归档
         │ 4. JSON Sink                 │ → JSON 文件输出
         └──────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
    ┌─────────┐   ┌─────────┐   ┌──────────┐
    │PostgreSQL│  │ Redis   │   │ 文件系统  │
    │ 结果存储  │  │ 数据流  │   │ 消息归档  │
    └─────────┘   └─────────┘   └──────────┘
         │              │              │
         └──────────────┼──────────────┘
                        ▼
         ┌──────────────────────────────┐
         │ Prometheus + Grafana         │
         │ 实时监控和可视化              │
         └──────────────────────────────┘
```

### 数据流

1. **视频接入** → Source Adapter 读取视频文件或 RTSP 流
2. **流量分发** → Router 根据 source_id 路由到不同模块
3. **GPU 推理** → YOLOv8/PeopleNet 进行目标检测
4. **多路输出**:
   - PostgreSQL: 检测结果存储
   - Redis Stream: 数据流持久化
   - Message Archive: 完整消息归档
   - JSON: 文件输出
5. **监控** → Prometheus 采集指标，Grafana 可视化

---

## ⚙️ 配置管理

### 统一配置文件 (config.yml)

项目使用单一的 `config.yml` 文件管理所有配置：

```yaml
# 视频源配置
video_sources:
  - id: video1
    type: file  # file, rtsp, usb, http
    location: /videos/video1.mp4
    route_to: yolov8  # 路由到哪个模型

# AI 模型配置
models:
  - name: yolov8
    module_path: modules/yolov8/module.yml
    batch_size: 8
    prometheus_port: 8000

# 监控配置
monitoring:
  prometheus:
    enabled: true
    port: 9090

# 数据持久化配置
persistence:
  redis:
    enabled: true
    memory_limit: 2gb
  postgres:
    enabled: true
    retention_days: 30
```

### 自动生成配置

```bash
# 从 config.yml 生成 Docker Compose 和 Router 配置
python scripts/generate_config.py

# 验证配置文件
python scripts/validate_config.py
```

### 配置文件说明

| 文件 | 说明 | 生成方式 |
|------|------|---------|
| config.yml | 统一配置（手动编辑） | 手动 |
| docker-compose.yml | Docker 服务配置 | 由 generate_config.py 生成 |
| config/router_config.json | Router 路由规则 | 由 generate_config.py 生成 |

---

## 🔧 模块配置

### YOLOv8 模块

文件: `modules/yolov8/module.yml`

```yaml
name: yolov8_detector

parameters:
  batch_size: 8        # 批处理大小
  frame:
    width: 1280        # 帧宽度
    height: 720        # 帧高度

  # Prometheus 监控
  metrics:
    frame_period: 1000  # 每 1000 帧报告一次
    time_period: 1      # 每 1 秒报告一次

pipeline:
  elements:
    - element: nvinfer@detector
      name: yolov8
      model:
        format: onnx
        model_file: /models/yolov8n.onnx
        batch_size: 8
        precision: fp16  # 使用 FP16 精度
```

### PeopleNet 模块

文件: `modules/peoplenet/module.yml`

```yaml
name: peoplenet_detector

parameters:
  batch_size: 4

pipeline:
  elements:
    - element: nvinfer@detector
      name: peoplenet
      model:
        format: onnx
        model_file: /models/peoplenet/resnet34_peoplenet.onnx
        batch_size: 4
```

---

## 🚀 部署步骤

### 本地验证

```bash
# 1. 验证配置和文件
bash scripts/verify_local.sh

# 2. 生成 Docker Compose 配置
python scripts/generate_config.py

# 3. 验证配置文件
python scripts/validate_config.py
```

### 云端部署

```bash
# 1. 使用部署脚本
bash scripts/deploy.sh root@<server_ip>

# 或手动部署：

# 2. 上传项目文件
scp -r . root@<server_ip>:/root/ai_video_analysis/

# 3. 生成配置
ssh root@<server_ip> "cd /root/ai_video_analysis && \
  python scripts/generate_config.py"

# 4. 启动服务
ssh root@<server_ip> "cd /root/ai_video_analysis && \
  docker-compose up -d"

# 5. 检查服务状态
ssh root@<server_ip> "cd /root/ai_video_analysis && \
  docker-compose ps"

# 6. 查看日志
ssh root@<server_ip> "cd /root/ai_video_analysis && \
  docker-compose logs -f"
```

---

## 📊 监控和运维

### 监控系统

访问 Grafana: http://localhost:3000
- 默认用户名: admin
- 默认密码: admin

**关键面板**:
- 实时 FPS (按 source_id)
- GPU 利用率/显存占用
- 推理延迟分布 (P50/P95/P99)
- 检测对象数量
- 系统资源使用

### 数据持久化

**Redis Stream**:
- 实时数据流持久化
- 支持消费者组
- 自动清理旧数据

```bash
# 查看 Redis 数据
redis-cli
> XLEN savant:video_stream
> XRANGE savant:video_stream - +
```

**PostgreSQL**:
- 检测结果存储
- 支持历史查询
- 自动数据清理

```bash
# 连接数据库
psql -h localhost -U savant -d savant_video_analysis

# 查看检测结果
SELECT * FROM detection_results LIMIT 10;
```

### 消息归档

启用消息归档功能进行数据重放和调试：

```bash
# 启动归档服务
docker-compose --profile archive up -d message-archive-sink

# 重放归档消息
docker-compose run --rm \
  -e FPS=25 \
  message-archive-sink \
  python /opt/adapters/message_archive_source.py

# 清理旧归档
bash scripts/cleanup_archive.sh --keep 3
```

---

## 📈 性能指标

### 性能目标

| 指标 | 目标值 |
|------|--------|
| YOLOv8 FPS | > 40 |
| PeopleNet FPS | > 20 |
| 端到端延迟 | < 100ms |
| GPU 利用率 | > 60% |

### 资源配置

**Docker Compose 资源限制**:

```yaml
# Redis
memory_limit: 2gb
memory_reservation: 512M

# PostgreSQL
memory_limit: 1gb
memory_reservation: 256M

# YOLOv8 Module
GPU: 1 (nvidia)

# PeopleNet Module
GPU: 1 (nvidia)
```

---

## 🔄 开发工作流

### 添加新模型

1. 准备 ONNX 模型文件
2. 创建 `modules/<model_name>/module.yml`
3. 在 `config.yml` 中添加模型配置
4. 运行 `python scripts/generate_config.py`
5. 本地验证
6. 云端部署

详见 [ADD_NEW_MODEL.md](docs/ADD_NEW_MODEL.md)

### 添加新视频源

1. 在 `config.yml` 中添加视频源配置
2. 运行 `python scripts/generate_config.py`
3. 本地验证
4. 云端部署

详见 [ADD_NEW_VIDEO_SOURCE.md](docs/ADD_NEW_VIDEO_SOURCE.md)

### 配置管理

所有配置都在 `config.yml` 中管理，修改后运行：

```bash
python scripts/generate_config.py
```

详见 [UNIFIED_CONFIG.md](docs/UNIFIED_CONFIG.md)

---

## 📖 文档导航

### 核心文档

- **[ARCHITECTURE_DESIGN.md](docs/ARCHITECTURE_DESIGN.md)** - 完整架构设计
- **[DEVELOPMENT_PLAN_MVP.md](docs/DEVELOPMENT_PLAN_MVP.md)** - MVP 开发计划

### 用户指南

- **[ADD_NEW_MODEL.md](docs/ADD_NEW_MODEL.md)** - 如何添加新模型
- **[ADD_NEW_VIDEO_SOURCE.md](docs/ADD_NEW_VIDEO_SOURCE.md)** - 如何添加新视频源
- **[UNIFIED_CONFIG.md](docs/UNIFIED_CONFIG.md)** - 统一配置管理
- **[OPERATIONS_GUIDE.md](docs/OPERATIONS_GUIDE.md)** - 系统运维指南
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - 故障排查指南

---

## 🎯 适用场景

✅ 10 路以内视频流
✅ 2-5 个 AI 模型
✅ 实时性要求 (<100ms)
✅ 单机/小集群 GPU 部署
✅ 需要数据持久化
✅ 需要完整的监控和调试

❌ 100+ 路视频流 (需要分布式架构)
❌ 10+ 个模型 (需要更复杂的调度)
❌ 极致低延迟 (<10ms, 需要边缘计算)

---

## 📚 参考资源

- **Savant 官方文档**: https://docs.savant-ai.io/
- **Savant GitHub**: https://github.com/insight-platform/Savant
- **官方示例**: `docs/savant-reference/`

---

## 🤝 贡献指南

详见 [CLAUDE.md](CLAUDE.md) 中的开发规范

---

## 📝 许可证

本项目仅用于学习和研究目的。

---

## 📞 联系方式

如有问题，请查看文档或提交 Issue。


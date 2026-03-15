# AI 视频流分析系统

基于 Savant 框架的生产级 AI 视频流分析系统，支持实时多路视频处理、多模型推理、数据持久化和完整监控。

## 📋 项目概述

**系统特点**:
- ✅ 多 Module 架构（每个模型独立，避免显存浪费）
- ✅ Kafka+Redis 数据持久化（支持重启不丢失）
- ✅ Etcd 动态配置（运行时调整参数）
- ✅ Savant Router 流量分发（按 source_id 路由）
- ✅ 完整监控体系（Prometheus+Grafana+Watchdog）
- ✅ 消息归档功能（完整数据重放和调试）

**技术栈**:
- Savant 0.6.0+ (视频处理框架)
- DeepStream 7.1+ (GPU推理引擎)
- TensorRT (模型加速)
- Kafka 3.6+ (消息队列)
- Redis 7.0+ (帧缓存)
- Etcd 3.5+ (配置中心)
- PostgreSQL 15+ (结果存储)
- FastAPI (查询API)
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
# 环境名称
savant-video-analysis

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
├── docker-compose.yml             # 生产环境配置
├── config.yml                     # 统一配置文件
│
├── config/                        # 配置文件目录
│   ├── router_config.json         # Router 路由配置
│   └── router_handler.py          # Router 自定义处理逻辑
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
├── adapters/                      # 自定义适配器
│   ├── message_archive_sink.py    # 消息归档 Sink
│   └── message_archive_source.py  # 消息重放 Source
│
├── database/                      # 数据库相关
│   └── init.sql                   # 数据库初始化脚本
│
├── monitoring/                    # 监控配置
│   ├── prometheus.yml             # Prometheus 配置
│   └── grafana_dashboards/        # Grafana 面板
│
├── scripts/                       # 工具脚本
│   ├── convert_model.sh           # 模型转换脚本
│   ├── verify_local.sh            # 本地验证脚本
│   └── cleanup_archive.sh         # 归档清理脚本
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
    ├── ARCHITECTURE_DESIGN.md     # 架构设计（完整版）
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

### 完整架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    视频源层 (Video Sources)                      │
│  RTSP Camera 1-10                                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         Savant Source Adapter (多路RTSP) - Savant原生            │
│  - 硬件解码(NVDEC)                                               │
│  - 背压感知(backpressure-aware)                                  │
│  - 自动重连、健康检查                                             │
└────────────────────────┬────────────────────────────────────────┘
                         │ ZeroMQ
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         Kafka-Redis Sink Adapter - Savant原生                    │
│  - 帧数据 → Redis (TTL=60s)                                      │
│  - 元数据 → Kafka (retention=1h)                                 │
│  - 数据持久化,支持重启不丢失                                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
      │    Kafka     │      │    Redis     │      │     Etcd     │
      │  (metadata)  │      │   (frames)   │      │   (config)   │
      │  消息队列     │      │   帧缓存      │      │   配置中心    │
      └──────┬───────┘      └──────┬───────┘      └──────┬───────┘
             │                     │                     │
             └─────────────────────┼─────────────────────┘
                                   ▼
                          ┌─────────────────┐
                          │ Kafka-Redis     │
                          │ Source Adapter  │ - Savant原生
                          └────────┬────────┘
                                   │ ZeroMQ
                                   ▼
                          ┌─────────────────┐
                          │ Savant Router   │ - Savant原生
                          │ 按source_id分发  │
                          └────────┬────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                ▼                  ▼                  ▼
        ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
        │ Savant       │   │ Savant       │   │ Savant       │
        │ Module:      │   │ Module:      │   │ Module:      │
        │ YOLOv8       │   │ Face Rec     │   │ Behavior     │
        │ (replicas=2) │   │ (replicas=1) │   │ (replicas=1) │
        │ GPU 0        │   │ GPU 0        │   │ GPU 1        │
        └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
               │                  │                  │
               └──────────────────┼──────────────────┘
                                  ▼
                         ┌─────────────────┐
                         │ Result Sink     │ - Savant原生
                         │ Adapter         │
                         └────────┬────────┘
                                  │
                   ┌──────────────┼──────────────┐
                   ▼              ▼              ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
           │ PostgreSQL   │ │  FastAPI     │ │  WebSocket   │
           │ (历史数据)    │ │  (查询API)   │ │  (实时推送)  │
           └──────────────┘ └──────────────┘ └──────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ Prometheus      │
                         │ + Grafana       │
                         │ + Watchdog      │
                         └─────────────────┘
```

### MVP 简化架构

```
视频文件 → Source Adapter → ZeroMQ → YOLOv8 Module → JSON Sink
```

---

## 📖 文档导航

### 核心文档

- **[ARCHITECTURE_DESIGN.md](docs/ARCHITECTURE_DESIGN.md)** - 完整架构设计
  - 架构演进历程、设计决策、性能优化、鲁棒性设计

- **[DEVELOPMENT_PLAN_MVP.md](docs/DEVELOPMENT_PLAN_MVP.md)** - MVP 开发计划
  - 分阶段开发计划、任务清单、验证方法

### 用户指南

- **[ADD_NEW_MODEL.md](docs/ADD_NEW_MODEL.md)** - 如何添加新模型
  - 模型转换、配置编写、本地验证、云端部署

- **[ADD_NEW_VIDEO_SOURCE.md](docs/ADD_NEW_VIDEO_SOURCE.md)** - 如何添加新视频源
  - RTSP 流接入、本地文件接入、多路视频管理

- **[UNIFIED_CONFIG.md](docs/UNIFIED_CONFIG.md)** - 统一配置管理
  - 配置文件结构、环境变量、动态配置、配置验证

- **[OPERATIONS_GUIDE.md](docs/OPERATIONS_GUIDE.md)** - 系统运维指南
  - 监控系统、消息归档、故障排查、最佳实践

- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - 故障排查指南
  - 常见问题、日志分析、性能诊断、调试技巧

---

## 🔧 配置说明

### YOLOv8 模块配置

文件: `modules/yolov8/module.yml`

```yaml
name: yolov8_detector

parameters:
  batch_size: 4        # 批处理大小
  frame:
    width: 1280        # 帧宽度
    height: 720        # 帧高度

  # Prometheus 监控配置
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
        batch_size: 4
        precision: fp16  # 使用 FP16 精度
```

### Docker Compose 配置

文件: `docker-compose.yml`

**核心服务**:
- Kafka: 消息队列
- Redis: 帧缓存
- Etcd: 配置中心
- PostgreSQL: 结果存储
- Prometheus: 指标采集
- Grafana: 可视化
- Savant 模块: GPU 推理

---

## 🚀 部署步骤

### 本地验证

```bash
# 1. 验证配置和文件
bash scripts/verify_local.sh

# 应该看到：
# ✅ 本地验证完成！
# 🚀 准备就绪，可以部署到云端 GPU 实例！
```

### 云端部署

```bash
# 1. 上传项目文件
scp -r . root@<server_ip>:/root/ai_video_analysis/

# 2. 启动服务
ssh root@<server_ip> "cd /root/ai_video_analysis && \
  docker-compose up -d"

# 3. 检查服务状态
ssh root@<server_ip> "docker-compose ps"

# 4. 查看日志
ssh root@<server_ip> "docker-compose logs -f"
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
- Kafka 消息积压
- Redis 内存使用

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

### 故障排查

详见 [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

常见问题:
- GPU 推理异常
- 消息队列堆积
- 内存泄漏
- 性能下降

---

## 📈 性能指标

### 性能目标

| 指标 | 目标值 |
|------|--------|
| YOLOv8 FPS | > 40 |
| PeopleNet FPS | > 20 |
| 端到端延迟 | < 100ms |
| GPU 利用率 | > 60% |

### 资源估算

**GPU 显存分配**:
- YOLOv8n Engine: ~500MB
- Face Rec Engine: ~800MB
- Behavior Engine: ~1.2GB
- Frame Buffer: ~500MB
- **总计**: ~3GB / 8GB (37.5%)

**CPU/内存**:
- 总计: ~7.5GB

---

## 🔄 开发工作流

### 添加新模型

1. 准备 ONNX 模型文件
2. 创建 `modules/<model_name>/module.yml`
3. 更新 Router 配置
4. 本地验证
5. 云端部署

详见 [ADD_NEW_MODEL.md](docs/ADD_NEW_MODEL.md)

### 添加新视频源

1. 配置视频源信息
2. 更新 `config/sources.yml`
3. 更新 Router 路由规则
4. 本地验证
5. 云端部署

详见 [ADD_NEW_VIDEO_SOURCE.md](docs/ADD_NEW_VIDEO_SOURCE.md)

### 配置管理

使用 Etcd 进行动态配置：

```bash
# 查看配置
etcdctl get /savant/models/yolov8/confidence_threshold

# 更新配置
etcdctl put /savant/models/yolov8/confidence_threshold 0.5

# 删除配置
etcdctl del /savant/models/yolov8/confidence_threshold
```

详见 [UNIFIED_CONFIG.md](docs/UNIFIED_CONFIG.md)

---

## 🎯 适用场景

✅ 10 路以内视频流
✅ 2-5 个 AI 模型
✅ 实时性要求 (<100ms)
✅ 单机/小集群 GPU 部署
✅ 需要数据持久化
✅ 需要动态配置

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


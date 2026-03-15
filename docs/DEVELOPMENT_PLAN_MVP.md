# AI 视频流分析系统 — MVP 开发计划

## 项目概述

基于 Savant 框架构建**最小可运行系统（MVP）**，优先实现核心功能，后续再添加生产特性。

**MVP 目标**:
- ✅ 让视频通过 AI 模型处理
- ✅ 看到检测结果
- ✅ 验证技术可行性

**不包含**:
- ❌ Kafka+Redis 持久化
- ❌ Etcd 动态配置
- ❌ PostgreSQL 存储
- ❌ FastAPI 查询服务
- ❌ Prometheus+Grafana 监控
- ❌ Watchdog 健康检查

---

## MVP 架构

### 简化架构图

```
┌─────────────┐
│  视频文件    │
│ (test.mp4)  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Source Adapter  │  (Savant 原生)
│ 读取视频文件     │
└──────┬──────────┘
       │ ZeroMQ (IPC)
       ▼
┌─────────────────┐
│ Savant Module   │  (YOLOv8)
│ GPU 推理        │
└──────┬──────────┘
       │ ZeroMQ (IPC)
       ▼
┌─────────────────┐
│  JSON Sink      │  (Savant 原生)
│ 输出结果到文件   │
└─────────────────┘
```

### 对比完整架构

| 组件 | MVP 版本 | 完整版本 |
|------|---------|---------|
| 视频输入 | 本地文件 | RTSP 多路流 |
| 消息队列 | ZeroMQ 直连 | Kafka+Redis |
| 配置管理 | 静态 YAML | Etcd 动态配置 |
| 推理模块 | 单个 Module | 多个 Module + Router |
| 结果输出 | JSON 文件 | PostgreSQL + API |
| 监控 | 日志 | Prometheus+Grafana |

---

## MVP Phase 1: 最小可运行系统（本地开发）

**时间**: 1 天

**目标**: 在本地完成配置，验证语法正确性

### 1.1 项目结构

```
ai_video_analysis/
├── modules/
│   └── yolov8/
│       └── module.yml          # YOLOv8 模块配置
├── config/
│   └── source.yml              # 视频源配置（单个文件）
├── videos/
│   └── test.mp4                # 测试视频
├── output/
│   └── results.json            # 输出结果
├── docker-compose.mvp.yml      # MVP 版 Docker Compose
├── .gitignore
└── README.md
```

### 1.2 任务清单

**任务 1: 创建项目目录结构**
```bash
mkdir -p modules/yolov8
mkdir -p config
mkdir -p videos
mkdir -p output
```

**任务 2: 编写 YOLOv8 module.yml**

基于官方示例: `docs/savant-reference/peoplenet_detector/module.yml`

```yaml
name: yolov8_detector

parameters:
  batch_size: 1  # MVP 先用 batch=1
  frame:
    width: 1280
    height: 720

pipeline:
  elements:
    - element: nvinfer@detector
      name: yolov8
      model:
        format: onnx
        model_file: /models/yolov8n.onnx
        batch_size: 1
        precision: fp16
        input:
          shape: [3, 640, 640]
          scale_factor: 0.0039215697906911373
        output:
          layer_names: [output]
          num_detected_classes: 80
```

**任务 3: 编写 docker-compose.mvp.yml**

```yaml
version: '3.8'

services:
  # 视频源适配器
  source-adapter:
    image: ghcr.io/insight-platform/savant-adapters-gstreamer:latest
    volumes:
      - ./videos:/videos
      - zmq_sockets:/tmp/zmq-sockets
    command: >
      gst-source-adapter
        --source-id test-video
        --location file:///videos/test.mp4
        --zmq-endpoint pub+bind:ipc:///tmp/zmq-sockets/input.ipc
        --sync-output false

  # YOLOv8 推理模块
  yolov8-module:
    image: ghcr.io/insight-platform/savant-deepstream:latest
    runtime: nvidia
    volumes:
      - zmq_sockets:/tmp/zmq-sockets
      - ./modules/yolov8:/opt/savant/modules/yolov8
      - ./models:/models
    environment:
      - MODULE_PATH=/opt/savant/modules/yolov8/module.yml
      - ZMQ_SRC_ENDPOINT=sub+connect:ipc:///tmp/zmq-sockets/input.ipc
      - ZMQ_SINK_ENDPOINT=pub+bind:ipc:///tmp/zmq-sockets/output.ipc
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    depends_on:
      - source-adapter

  # JSON 结果输出
  json-sink:
    image: ghcr.io/insight-platform/savant-adapters-py:latest
    volumes:
      - zmq_sockets:/tmp/zmq-sockets
      - ./output:/output
    command: >
      json-sink
        --zmq-endpoint sub+connect:ipc:///tmp/zmq-sockets/output.ipc
        --output-file /output/results.json
    depends_on:
      - yolov8-module

volumes:
  zmq_sockets:
```

**任务 4: 编写 .gitignore**

```
# 模型文件
models/
*.onnx
*.engine

# 输出文件
output/
*.json

# 视频文件
videos/
*.mp4
*.avi

# Python
__pycache__/
*.pyc

# Docker
.DS_Store
```

**任务 5: 本地验证配置**

```bash
# 验证 module.yml 语法
docker run --rm -v $(pwd):/workspace \
  ghcr.io/insight-platform/savant-deepstream:latest \
  python -m savant.config.validator /workspace/modules/yolov8/module.yml

# 验证 docker-compose 语法
docker-compose -f docker-compose.mvp.yml config
```

### 1.3 验证清单

- [ ] 项目目录结构创建完成
- [ ] module.yml 语法正确
- [ ] docker-compose.mvp.yml 语法正确
- [ ] .gitignore 创建完成

---

## MVP Phase 2: 云端 GPU 验证

**时间**: 1 天

**目标**: 在云端 GPU 上运行推理，看到检测结果

### 2.1 准备工作

**任务 1: 准备 YOLOv8 ONNX 模型**

```bash
# 本地导出 ONNX（如果有 PyTorch 环境）
python export_yolov8.py

# 或者下载预训练模型
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.onnx
```

**任务 2: 准备测试视频**

```bash
# 下载测试视频或使用自己的视频
cp /path/to/test.mp4 videos/
```

### 2.2 云端部署

**任务 1: 上传文件到云端**

```bash
# 上传项目文件
scp -r ai_video_analysis/ user@gpu-instance:/path/to/

# 上传模型文件
scp yolov8n.onnx user@gpu-instance:/path/to/ai_video_analysis/models/
```

**任务 2: 启动服务**

```bash
# SSH 到云端
ssh user@gpu-instance

# 进入项目目录
cd /path/to/ai_video_analysis

# 启动服务
docker-compose -f docker-compose.mvp.yml up -d

# 查看日志
docker-compose -f docker-compose.mvp.yml logs -f
```

**任务 3: 验证结果**

```bash
# 等待处理完成（视频长度决定）
sleep 60

# 查看输出结果
cat output/results.json

# 检查是否有检测结果
jq '.objects' output/results.json
```

### 2.3 验证清单

- [ ] ONNX 模型准备完成
- [ ] 测试视频准备完成
- [ ] 服务成功启动
- [ ] 看到 JSON 输出结果
- [ ] 检测结果合理（有 bbox、class、confidence）

### 2.4 预期结果

**成功标志**:
```json
{
  "source_id": "test-video",
  "frame_num": 100,
  "objects": [
    {
      "class": "person",
      "confidence": 0.85,
      "bbox": [100, 200, 300, 400]
    },
    {
      "class": "car",
      "confidence": 0.92,
      "bbox": [500, 300, 700, 500]
    }
  ]
}
```

---

## MVP Phase 3: 多路视频 + 多模型（可选）

**时间**: 1-2 天

**目标**: 支持多路视频和多个模型

### 3.1 添加 Router

**任务 1: 创建 router_config.json**

```json
{
  "ingress": [{
    "name": "from_source",
    "socket": {
      "url": "sub+bind:ipc:///tmp/zmq-sockets/input.ipc"
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
      "name": "to_face_rec",
      "socket": {
        "url": "pub+bind:ipc:///tmp/zmq-sockets/face_rec.ipc"
      },
      "matcher": "video3"
    }
  ]
}
```

**任务 2: 更新 docker-compose**

添加 Router 服务和第二个 Module。

### 3.2 验证清单

- [ ] Router 配置正确
- [ ] 多路视频正确分发
- [ ] 多个模型并发推理
- [ ] 结果正确输出

---

## 成本控制

### 云端 GPU 使用时间

| Phase | 预计时间 | 说明 |
|-------|---------|------|
| Phase 1 | 0 小时 | 本地开发，无需 GPU |
| Phase 2 | 2-3 小时 | 首次验证 + 调试 |
| Phase 3 | 2-3 小时 | 多模块验证 |
| **总计** | **4-6 小时** | 使用 Spot 实例降低成本 |

### 节省成本的方法

1. **本地充分验证** - 确保配置正确再上云
2. **使用 Spot 实例** - 成本降低 60-90%
3. **及时关机** - 验证完立即关机
4. **批量测试** - 一次性测试多个场景

---

## 后续扩展路径

### 何时添加生产特性

**Kafka+Redis 持久化**:
- 触发条件: 需要重启不丢数据
- 预计时间: 1 天

**Etcd 动态配置**:
- 触发条件: 需要运行时调整参数
- 预计时间: 0.5 天

**PostgreSQL + API**:
- 触发条件: 需要查询历史数据
- 预计时间: 1 天

**监控系统**:
- 触发条件: 需要性能监控和告警
- 预计时间: 1 天

---

## 验证检查清单

### MVP Phase 1 验证
- [ ] 项目结构创建完成
- [ ] module.yml 语法正确
- [ ] docker-compose.mvp.yml 语法正确
- [ ] 配置验证通过

### MVP Phase 2 验证
- [ ] 模型和视频准备完成
- [ ] 服务成功启动
- [ ] 看到 JSON 输出
- [ ] 检测结果合理
- [ ] GPU 推理正常

### MVP Phase 3 验证（可选）
- [ ] Router 正确分发
- [ ] 多模块并发推理
- [ ] 结果正确输出

---

## 常见问题

### Q1: 为什么不用 Kafka+Redis？
**A**: MVP 阶段优先验证核心功能，ZeroMQ 直连足够。等核心功能验证通过后，再根据需要添加持久化。

### Q2: 为什么只用单个模型？
**A**: 先验证单个模型能跑通，再扩展到多模型。避免一开始就做复杂的架构。

### Q3: 如何查看推理结果？
**A**: 查看 `output/results.json` 文件，或者使用 `jq` 工具格式化输出。

### Q4: GPU 显存不足怎么办？
**A**:
- 降低 batch_size（改为 1）
- 使用更小的模型（yolov8n 而不是 yolov8x）
- 降低输入分辨率

### Q5: 如何调试？
**A**:
```bash
# 查看日志
docker-compose -f docker-compose.mvp.yml logs -f yolov8-module

# 进入容器
docker-compose -f docker-compose.mvp.yml exec yolov8-module bash

# 检查 ZeroMQ 通信
docker-compose -f docker-compose.mvp.yml logs source-adapter
```

---

## 总结

**MVP 开发路径**:
```
Phase 1 (本地): 配置开发 + 语法验证
  ↓
Phase 2 (云端): GPU 推理验证 + 结果输出
  ↓
Phase 3 (可选): 多路视频 + 多模型
  ↓
（按需）添加生产特性
```

**核心原则**:
- ✅ 先做必须的，后做锦上添花的
- ✅ 先验证核心功能，再扩展
- ✅ 先简单架构，后复杂架构
- ✅ 先本地验证，再云端验证

**预计时间**:
- MVP Phase 1-2: 2 天
- MVP Phase 3: 1-2 天（可选）
- 总计: 2-4 天

遵循这个 MVP 计划，可以快速验证技术可行性，避免过早优化！

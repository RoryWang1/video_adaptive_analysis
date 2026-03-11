# 添加新模型指南

本文档说明如何向 Savant 视频分析系统添加新的 AI 模型。

## 前提条件

- 模型已转换为 ONNX 格式
- 了解模型的输入输出规格
- 熟悉 Savant Module 配置

## 步骤概览

1. 准备模型文件
2. 创建 Module 配置
3. 更新 Router 配置
4. 更新 Docker Compose
5. 验证和部署

---

## 详细步骤

### 步骤 1：准备模型文件

将 ONNX 模型文件放置到 `models/` 目录：

```bash
# 创建模型目录
mkdir -p models/your_model_name

# 复制模型文件
cp /path/to/your_model.onnx models/your_model_name/

# 如果有其他配置文件（如 labels.txt），也一并复制
cp /path/to/labels.txt models/your_model_name/
```

**目录结构示例**：
```
models/
├── yolov8n.onnx
├── peoplenet/
│   ├── resnet34_peoplenet.onnx
│   └── labels.txt
└── your_model_name/
    ├── your_model.onnx
    └── labels.txt
```

### 步骤 2：创建 Module 配置

创建 `modules/your_model_name/module.yml`：

```yaml
name: your_model_detector

parameters:
  batch_size: 4  # 根据 GPU 显存调整
  frame:
    width: 1280
    height: 720

  # Telemetry 配置（用于 Prometheus 监控）
  telemetry:
    metrics:
      frame_period: 1000
      time_period: 1
      history: 100
      extra_labels:
        module: your_model
        model: your_model_name

pipeline:
  elements:
    - element: nvinfer@detector
      name: your_model
      model:
        format: onnx
        model_file: /models/your_model_name/your_model.onnx
        batch_size: 4
        precision: fp16  # 或 fp32

        input:
          # 根据模型实际输入配置
          shape: [3, 640, 640]  # [channels, height, width]
          scale_factor: 0.003921568627451  # 1/255
          offsets: [0.0, 0.0, 0.0]
          color_format: rgb  # 或 bgr

        output:
          num_detected_classes: 80  # 根据模型实际类别数
          layer_names: ['output0']  # 根据模型输出层名称

          # 如果是 YOLO 系列模型
          converter:
            module: savant.converter.yolo
            class_name: TensorToBBoxConverter
            kwargs:
              confidence_threshold: 0.25
              nms_iou_threshold: 0.45

          # 如果是其他类型模型，参考 Savant 文档配置
```

**配置参考**：
- YOLOv8: `modules/yolov8/module.yml`
- PeopleNet: `modules/peoplenet/module.yml`
- Savant 官方示例: `Savant-releases-0.6.0/samples/`

### 步骤 3：更新 Router 配置

编辑 `config/router_config.json`，添加新的 egress：

```json
{
  "ingress": [{
    "name": "from_source",
    "socket": {
      "url": "sub+bind:ipc:///tmp/zmq-sockets/input-video.ipc"
    }
  }],
  "egress": [
    {
      "name": "to_yolov8",
      "socket": {
        "url": "dealer+bind:ipc:///tmp/zmq-sockets/yolov8.ipc"
      },
      "matcher": "[yolov8]"
    },
    {
      "name": "to_peoplenet",
      "socket": {
        "url": "dealer+bind:ipc:///tmp/zmq-sockets/peoplenet.ipc"
      },
      "matcher": "[peoplenet]"
    },
    {
      "name": "to_your_model",
      "socket": {
        "url": "dealer+bind:ipc:///tmp/zmq-sockets/your_model.ipc"
      },
      "matcher": "[your_model]"
    }
  ],
  "common": {
    "handler": {
      "module": "router_handler",
      "class_name": "SourceIdRouter"
    }
  }
}
```

编辑 `config/router_handler.py`，添加路由逻辑：

```python
class SourceIdRouter:
    def __call__(self, message_id: int, ingress_name: str, topic: str, message: Message):
        source_id = topic

        # 根据 source_id 设置路由标签
        if source_id in ['video1', 'video2']:
            message.labels = ['yolov8']
        elif source_id == 'video3':
            message.labels = ['peoplenet']
        elif source_id == 'video4':  # 新视频源
            message.labels = ['your_model']

        return message
```

### 步骤 4：更新 Docker Compose

编辑 `docker-compose.yml`，添加新模块服务：

```yaml
services:
  # ... 现有服务 ...

  # 新模型推理模块
  your-model-module:
    image: ghcr.io/insight-platform/savant-deepstream:0.6.0-7.1
    privileged: true
    restart: unless-stopped
    runtime: nvidia
    volumes:
      - zmq_sockets:/tmp/zmq-sockets
      - ./modules:/opt/savant/modules
      - ./models:/models
    command: modules/your_model_name/module.yml
    ports:
      - "8002:8080"  # Prometheus 指标端口
    environment:
      - ZMQ_SRC_ENDPOINT=router+connect:ipc:///tmp/zmq-sockets/your_model.ipc
      - ZMQ_SINK_ENDPOINT=pub+bind:ipc:///tmp/zmq-sockets/output-your-model.ipc
      - METRICS_FRAME_PERIOD=1000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/status"]
      interval: 5s
      timeout: 3s
      retries: 12
      start_period: 30s
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    depends_on:
      router:
        condition: service_started

  # JSON 结果输出
  json-sink-your-model:
    image: ghcr.io/insight-platform/savant-adapters-py:0.6.0
    restart: unless-stopped
    volumes:
      - zmq_sockets:/tmp/zmq-sockets
      - ./output:/output
    environment:
      - ZMQ_ENDPOINT=sub+connect:ipc:///tmp/zmq-sockets/output-your-model.ipc
      - FILENAME_PATTERN=/output/your_model_%source_id_%src_filename.json
    command: python -m adapters.python.sinks.metadata_json
    depends_on:
      - your-model-module
    deploy:
      resources:
        limits:
          memory: 256M
        reservations:
          memory: 64M
```

### 步骤 5：更新 Prometheus 配置

编辑 `monitoring/prometheus.yml`，添加新模块的采集目标：

```yaml
scrape_configs:
  # ... 现有配置 ...

  # 新模型指标
  - job_name: 'your-model-module'
    static_configs:
      - targets: ['your-model-module:8080']
        labels:
          module: 'your_model'
          model: 'your_model_name'
```

### 步骤 6：验证配置

运行配置验证工具：

```bash
# 在项目根目录
python scripts/validate_config.py
```

或者手动验证：

```bash
# 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('modules/your_model_name/module.yml'))"

# 验证 JSON 语法
python -c "import json; json.load(open('config/router_config.json'))"

# 验证 Docker Compose
docker-compose config
```

### 步骤 7：部署和测试

#### 本地测试（如果有 GPU）

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f your-model-module

# 检查健康状态
docker ps | grep your-model

# 检查指标
curl http://localhost:8002/metrics | head -20
```

#### 云端部署

```bash
# 1. 上传模型文件
scp -r models/your_model_name/ root@your-server:/root/ai_video_analysis/models/

# 2. 上传配置文件
scp modules/your_model_name/module.yml root@your-server:/root/ai_video_analysis/modules/your_model_name/
scp config/router_config.json root@your-server:/root/ai_video_analysis/config/
scp config/router_handler.py root@your-server:/root/ai_video_analysis/config/
scp docker-compose.yml root@your-server:/root/ai_video_analysis/
scp monitoring/prometheus.yml root@your-server:/root/ai_video_analysis/monitoring/

# 3. 重启服务
ssh root@your-server "cd /root/ai_video_analysis && docker-compose up -d"

# 4. 检查状态
ssh root@your-server "docker ps | grep your-model"
```

---

## 常见问题

### Q1: 模型加载失败

**错误信息**：
```
Model file "/models/your_model.onnx" not found
```

**解决方案**：
1. 检查模型文件路径是否正确
2. 确认 Docker volume 挂载正确
3. 检查文件权限

### Q2: 输入输出配置错误

**错误信息**：
```
Input shape mismatch
```

**解决方案**：
1. 使用 Netron 查看模型结构：https://netron.app/
2. 确认输入层名称、shape、数据类型
3. 确认输出层名称和格式

### Q3: TensorRT 引擎构建失败

**错误信息**：
```
Failed to build TensorRT engine
```

**解决方案**：
1. 检查 ONNX 模型是否有不支持的算子
2. 尝试使用 `precision: fp32` 而不是 `fp16`
3. 查看完整日志：`docker logs <container_name>`

### Q4: 检测结果为空

**可能原因**：
1. 置信度阈值过高
2. NMS 阈值不合适
3. 输入预处理不正确（scale_factor, color_format）

**解决方案**：
1. 降低 `confidence_threshold`
2. 调整 `nms_iou_threshold`
3. 检查 `scale_factor` 和 `color_format` 配置

---

## 模型配置模板

### YOLO 系列模型

```yaml
model:
  format: onnx
  model_file: /models/yolov8n.onnx
  batch_size: 4
  precision: fp16
  input:
    shape: [3, 640, 640]
    scale_factor: 0.003921568627451
    color_format: rgb
  output:
    num_detected_classes: 80
    layer_names: ['output0']
    converter:
      module: savant.converter.yolo
      class_name: TensorToBBoxConverter
      kwargs:
        confidence_threshold: 0.25
        nms_iou_threshold: 0.45
```

### NVIDIA TAO 模型（如 PeopleNet）

```yaml
model:
  format: onnx
  model_file: /models/peoplenet/resnet34_peoplenet.onnx
  batch_size: 4
  input:
    layer_name: input_1:0
    shape: [3, 544, 960]
    scale_factor: 0.0039215697906911373
  output:
    layer_names: [output_bbox/BiasAdd:0, output_cov/Sigmoid:0]
    num_detected_classes: 3
    objects:
      - class_id: 0
        label: person
      - class_id: 2
        label: face
```

---

## 检查清单

部署新模型前，确认以下事项：

- [ ] 模型文件已放置到 `models/` 目录
- [ ] Module 配置文件已创建并验证
- [ ] Router 配置已更新
- [ ] Docker Compose 已添加新服务
- [ ] Prometheus 配置已更新
- [ ] 配置验证工具通过
- [ ] 本地测试通过（如果有 GPU）
- [ ] 云端部署成功
- [ ] 健康检查通过
- [ ] 指标端点正常
- [ ] 输出结果正确

---

## 参考资料

- Savant 官方文档：https://docs.savant-ai.io/
- Savant 示例代码：`Savant-releases-0.6.0/samples/`
- ONNX 模型查看工具：https://netron.app/
- TensorRT 文档：https://docs.nvidia.com/deepstream/

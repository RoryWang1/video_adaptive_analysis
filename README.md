# AI 视频流分析系统 - MVP 版本

基于 Savant 框架的 AI 视频流分析系统，支持实时视频目标检测。

## 项目概述

**当前版本**: MVP (最小可运行系统)

**功能**:
- ✅ 视频文件输入
- ✅ YOLOv8 目标检测
- ✅ JSON 结果输出

**技术栈**:
- Savant Framework 0.6.0+
- YOLOv8n (ONNX)
- Docker + Docker Compose
- ZeroMQ (消息传输)

---

## 项目结构

```
ai_video_analysis/
├── modules/
│   └── yolov8/
│       └── module.yml          # YOLOv8 模块配置
├── models/
│   └── yolov8n.onnx           # ONNX 模型 (12 MB)
├── videos/
│   └── test.mp4               # 测试视频 (49 秒)
├── output/
│   └── results.json           # 输出结果（运行后生成）
├── scripts/
│   ├── verify_local.sh        # 本地验证脚本
│   └── convert_model.sh       # 模型转换脚本
├── docker-compose.mvp.yml     # MVP 版 Docker Compose
├── CLAUDE.md                  # Claude 工作规范
└── docs/
    ├── ARCHITECTURE_DESIGN.md
    ├── DEVELOPMENT_PLAN_V4.md
    └── DEVELOPMENT_PLAN_MVP.md
```

---

## 快速开始

### 本地验证（macOS）

```bash
# 1. 验证配置和文件
bash scripts/verify_local.sh

# 应该看到：
# ✅ 本地验证完成！
# 🚀 准备就绪，可以部署到云端 GPU 实例！
```

### 云端部署（GPU 实例）

详见: [DEPLOY.md](DEPLOY.md)

---

## 开发环境

### Python 虚拟环境

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

### 系统要求

**本地开发**:
- macOS (Apple Silicon 或 Intel)
- Anaconda/Miniconda
- Docker Desktop
- Python 3.10

**云端部署**:
- Ubuntu 22.04
- NVIDIA GPU (T4 / RTX 3060+)
- NVIDIA Driver >= 525
- Docker + nvidia-container-toolkit
- 显存 >= 8GB

---

## 架构说明

### MVP 简化架构

```
视频文件 → Source Adapter → ZeroMQ → YOLOv8 Module → JSON Sink
```

### 数据流

1. **Source Adapter** 读取 `videos/test.mp4`
2. 通过 **ZeroMQ IPC** 发送帧数据
3. **YOLOv8 Module** 进行 GPU 推理
4. 通过 **ZeroMQ IPC** 发送结果
5. **JSON Sink** 输出到 `output/results.json`

---

## 配置说明

### YOLOv8 模块配置

文件: `modules/yolov8/module.yml`

```yaml
name: yolov8_detector
parameters:
  batch_size: 1        # 批处理大小
  frame:
    width: 1280        # 帧宽度
    height: 720        # 帧高度

pipeline:
  elements:
    - element: nvinfer@detector
      name: yolov8
      model:
        format: onnx
        model_file: /models/yolov8n.onnx
        batch_size: 1
        precision: fp16  # FP16 精度加速
```

### Docker Compose 配置

文件: `docker-compose.mvp.yml`

**服务**:
- `source-adapter`: 读取视频文件
- `yolov8-module`: GPU 推理
- `json-sink`: 结果输出

---

## 开发文档

- [架构设计](docs/ARCHITECTURE_DESIGN.md) - 完整架构设计
- [开发计划 MVP](docs/DEVELOPMENT_PLAN_MVP.md) - MVP 开发计划
- [开发计划完整版](docs/DEVELOPMENT_PLAN_V4.md) - 生产级开发计划
- [Claude 工作规范](CLAUDE.md) - AI 助手工作规范
- [云端部署指南](DEPLOY.md) - 云端部署步骤

---

## 验证清单

### 本地验证
- [x] 项目目录结构
- [x] module.yml 语法正确
- [x] docker-compose.mvp.yml 语法正确
- [x] YOLOv8 ONNX 模型 (12 MB)
- [x] 测试视频 (49 秒)

### 云端验证（待完成）
- [ ] 服务成功启动
- [ ] GPU 推理正常
- [ ] 看到 JSON 输出结果
- [ ] 检测结果合理

---

## 预期结果

运行成功后，`output/results.json` 应包含类似内容：

```json
{
  "source_id": "test-video",
  "frame_num": 100,
  "timestamp": 1234567890,
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

## 下一步

1. **云端部署** - 在 GPU 实例上运行推理
2. **验证结果** - 检查检测效果
3. **扩展功能** - 添加多路视频、多模型（可选）
4. **生产化** - 添加监控、持久化等（可选）

---

## 常见问题

### Q: 为什么模型文件这么大？
A: ONNX 格式包含完整的模型结构和权重，比 PT 格式大。云端会转换为 TensorRT Engine 进一步优化。

### Q: 可以用自己的视频吗？
A: 可以，将视频文件放到 `videos/test.mp4` 即可。建议时长 10-60 秒。

### Q: 本地 macOS 可以运行吗？
A: 本地只能验证配置，无法运行 GPU 推理。需要云端 NVIDIA GPU。

### Q: 如何查看检测结果？
A: 运行完成后查看 `output/results.json` 文件。

---

## 许可证

本项目仅用于学习和研究目的。

---

## 联系方式

如有问题，请查看文档或提交 Issue。

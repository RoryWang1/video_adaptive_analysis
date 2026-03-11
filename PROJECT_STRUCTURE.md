# 项目结构说明

## 目录结构

```
ai_video_analysis/
├── CLAUDE.md                      # Claude 工作规范和项目说明
├── README.md                      # 项目简介
├── docker-compose.phase3.yml      # Phase 3 多路视频+多模型部署配置
├── .gitignore                     # Git 忽略文件配置
│
├── config/                        # 配置文件目录
│   ├── router_config.json         # Router 路由配置
│   └── router_handler.py          # Router 自定义处理逻辑
│
├── modules/                       # Savant 模块配置
│   ├── yolov8/
│   │   └── module.yml             # YOLOv8 检测模块配置
│   └── peoplenet/
│       └── module.yml             # PeopleNet 人脸检测模块配置
│
├── models/                        # AI 模型文件
│   ├── yolov8n.onnx               # YOLOv8 ONNX 模型
│   └── peoplenet/                 # PeopleNet 模型文件
│       ├── resnet34_peoplenet.onnx
│       ├── labels.txt
│       ├── nvinfer_config.txt
│       └── resnet34_peoplenet_int8.txt
│
├── videos/                        # 测试视频文件
│   ├── video1.mp4
│   ├── video2.mp4
│   └── video3.mp4
│
├── output/                        # 输出结果目录（服务器端生成）
│
├── scripts/                       # 工具脚本
│   ├── convert_model.sh           # 模型转换脚本
│   └── verify_local.sh            # 本地验证脚本
│
└── docs/                          # 文档目录
    ├── ARCHITECTURE_DESIGN.md     # 架构设计文档
    ├── DEVELOPMENT_PLAN_MVP.md    # MVP 开发计划
    └── Savant-code/               # Savant 官方示例代码（参考用）
```

## 核心文件说明

### 配置文件

- **docker-compose.phase3.yml**: Phase 3 部署配置
  - 3 个视频源适配器（video1, video2, video3）
  - 1 个 Router（流量分发）
  - 2 个推理模块（YOLOv8, PeopleNet）
  - 2 个 JSON Sink（结果输出）

- **config/router_config.json**: Router 配置
  - ingress: 接收视频流
  - egress: 分发到不同模块
  - common: 通用配置和 handler

- **config/router_handler.py**: Router 自定义逻辑
  - 根据 source_id 设置路由 labels
  - video1/video2 → yolov8
  - video3 → peoplenet

### 模块配置

- **modules/yolov8/module.yml**: YOLOv8 检测配置
  - 输入: 1280x720
  - 批处理: 8
  - 精度: FP16
  - 置信度阈值: 0.25

- **modules/peoplenet/module.yml**: PeopleNet 检测配置
  - 输入: 1280x720
  - 批处理: 4
  - 检测类别: person, face

## 部署说明

### 本地开发
- 配置编辑和测试
- PyFunc 逻辑开发
- 集成测试

### 云端部署
- GPU 推理验证
- 性能测试
- 生产运行

## 数据流

```
视频源 → Source Adapter → Router → Module (YOLOv8/PeopleNet) → JSON Sink → 输出文件
```

## 注意事项

1. **模型文件**: 不提交到 Git（已在 .gitignore 中配置）
2. **视频文件**: 不提交到 Git（已在 .gitignore 中配置）
3. **输出文件**: 仅在服务器端生成
4. **Savant-code**: 仅作为参考，不修改

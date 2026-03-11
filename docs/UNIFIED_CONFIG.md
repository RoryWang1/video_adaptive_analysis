# 统一配置管理指南

## 概述

从版本 1.1 开始，系统采用**统一配置文件**（`config.yml`）管理所有视频源、模型和路由规则。

**优势**：
- ✅ 单一配置文件，易于管理
- ✅ 自动生成 Docker Compose 和 Router 配置
- ✅ 避免配置不一致
- ✅ 添加视频源/模型更简单

---

## 快速开始

### 1. 编辑统一配置文件

编辑 `config.yml`：

```yaml
# 添加新视频源
video_sources:
  - id: video4  # 新增
    type: file
    location: /videos/video4.mp4
    loop: true
    sync_output: true
    route_to: yolov8
    memory_limit: 512M

# 添加新模型
models:
  - name: your_model  # 新增
    module_path: modules/your_model/module.yml
    batch_size: 4
    prometheus_port: 8002
    container_port: 8080
    zmq_socket: your_model.ipc
    healthcheck: true
    gpu_required: true
```

### 2. 生成配置文件

```bash
# 运行配置生成工具
python scripts/generate_config.py

# 或使用虚拟环境
conda run -n savant-video-analysis python scripts/generate_config.py
```

**生成的文件**：
- `docker-compose.phase3.yml`
- `config/router_config.json`
- `config/router_handler.py`
- `monitoring/prometheus.yml`

### 3. 验证配置

```bash
# 验证生成的配置
python scripts/validate_config.py
```

### 4. 部署

```bash
# 使用一键部署脚本
./scripts/deploy.sh

# 或手动部署
docker-compose -f docker-compose.phase3.yml up -d
```

---

## 配置文件详解

### 项目信息

```yaml
project:
  name: ai_video_analysis  # 项目名称
  version: "1.0.0"         # 版本号
```

### 视频源配置

```yaml
video_sources:
  - id: video1              # 唯一标识符
    type: file              # 类型：file, rtsp, usb, http
    location: /videos/video1.mp4  # 位置
    loop: true              # 是否循环播放
    sync_output: true       # 是否同步输出
    route_to: yolov8        # 路由到哪个模型
    memory_limit: 512M      # 内存限制
```

**支持的视频源类型**：

| 类型 | 说明 | location 示例 |
|------|------|--------------|
| file | 本地文件 | `/videos/video1.mp4` |
| rtsp | RTSP 流 | `rtsp://admin:pass@192.168.1.100:554/stream` |
| usb | USB 摄像头 | `/dev/video0` |
| http | HTTP 流 | `https://example.com/video.mp4` |

**RTSP 额外配置**：

```yaml
- id: camera1
  type: rtsp
  location: rtsp://admin:password@192.168.1.100:554/stream
  route_to: yolov8
  rtsp_transport: tcp  # 使用 TCP 传输（更稳定）
```

### 模型配置

```yaml
models:
  - name: yolov8                    # 模型名称
    module_path: modules/yolov8/module.yml  # Module 配置路径
    batch_size: 8                   # 批处理大小
    prometheus_port: 8000           # 主机端口
    container_port: 8080            # 容器内部端口
    zmq_socket: yolov8.ipc          # ZeroMQ socket 文件名
    healthcheck: true               # 是否启用健康检查
    gpu_required: true              # 是否需要 GPU
```

### 监控配置

```yaml
monitoring:
  prometheus:
    enabled: true      # 是否启用
    port: 9090         # 端口
    retention: 7d      # 数据保留时间
    memory_limit: 512M # 内存限制

  grafana:
    enabled: true
    port: 3000
    admin_password: admin
    memory_limit: 512M
```

### Docker 镜像版本

```yaml
docker_images:
  savant_deepstream: ghcr.io/insight-platform/savant-deepstream:0.6.0-7.1
  savant_adapters_gstreamer: ghcr.io/insight-platform/savant-adapters-gstreamer:0.6.0
  # ... 其他镜像
```

### 资源限制默认值

```yaml
resource_defaults:
  source_adapter:
    memory_limit: 512M
    memory_reservation: 128M
  router:
    memory_limit: 256M
    memory_reservation: 64M
  # ... 其他服务
```

---

## 常见操作

### 添加新视频源

1. 编辑 `config.yml`，在 `video_sources` 下添加：

```yaml
- id: video4
  type: file
  location: /videos/video4.mp4
  loop: true
  sync_output: true
  route_to: yolov8  # 选择使用的模型
  memory_limit: 512M
```

2. 重新生成配置：

```bash
python scripts/generate_config.py
```

3. 重新部署：

```bash
docker-compose -f docker-compose.phase3.yml up -d
```

### 添加新模型

1. 准备模型文件和 Module 配置（参考 `docs/ADD_NEW_MODEL.md`）

2. 编辑 `config.yml`，在 `models` 下添加：

```yaml
- name: your_model
  module_path: modules/your_model/module.yml
  batch_size: 4
  prometheus_port: 8002  # 使用未占用的端口
  container_port: 8080
  zmq_socket: your_model.ipc
  healthcheck: true
  gpu_required: true
```

3. 重新生成配置：

```bash
python scripts/generate_config.py
```

4. 重新部署：

```bash
docker-compose -f docker-compose.phase3.yml up -d
```

### 修改路由规则

直接在 `config.yml` 中修改 `route_to` 字段：

```yaml
video_sources:
  - id: video1
    route_to: yolov8  # 改为其他模型名称
```

然后重新生成配置并部署。

### 调整资源限制

修改 `config.yml` 中的 `memory_limit`：

```yaml
video_sources:
  - id: video1
    memory_limit: 1G  # 从 512M 增加到 1G
```

或修改默认值：

```yaml
resource_defaults:
  source_adapter:
    memory_limit: 1G  # 影响所有 source adapter
```

---

## 配置生成工具

### 基本用法

```bash
# 使用默认配置文件 config.yml
python scripts/generate_config.py

# 使用自定义配置文件
python scripts/generate_config.py --config my_config.yml
```

### 生成流程

```
config.yml
    ↓
generate_config.py
    ↓
├─ docker-compose.phase3.yml  (Docker Compose 配置)
├─ config/router_config.json  (Router 配置)
├─ config/router_handler.py   (Router Handler)
└─ monitoring/prometheus.yml  (Prometheus 配置)
```

### 注意事项

⚠️ **重要**：
- 生成的配置文件会**覆盖**现有文件
- 手动修改生成的文件会在下次生成时丢失
- 所有配置修改应该在 `config.yml` 中进行

---

## 与旧版本的区别

### 旧方式（手动配置）

需要手动编辑多个文件：
1. `docker-compose.phase3.yml` - 添加服务
2. `config/router_config.json` - 添加 egress
3. `config/router_handler.py` - 添加路由逻辑
4. `monitoring/prometheus.yml` - 添加采集目标

**问题**：
- ❌ 容易遗漏某个文件
- ❌ 配置不一致
- ❌ 维护困难

### 新方式（统一配置）

只需编辑一个文件：
1. `config.yml` - 定义所有配置
2. 运行 `generate_config.py` - 自动生成所有文件

**优势**：
- ✅ 单一配置源
- ✅ 自动保持一致性
- ✅ 易于维护

---

## 迁移指南

如果你有旧版本的手动配置，可以这样迁移：

### 步骤 1：备份现有配置

```bash
cp docker-compose.phase3.yml docker-compose.phase3.yml.backup
cp config/router_config.json config/router_config.json.backup
cp config/router_handler.py config/router_handler.py.backup
```

### 步骤 2：编辑 config.yml

根据现有配置填写 `config.yml`。

### 步骤 3：生成新配置

```bash
python scripts/generate_config.py
```

### 步骤 4：对比验证

```bash
# 对比 Docker Compose
diff docker-compose.phase3.yml.backup docker-compose.phase3.yml

# 对比 Router 配置
diff config/router_config.json.backup config/router_config.json
```

### 步骤 5：测试部署

```bash
# 验证配置
python scripts/validate_config.py

# 部署测试
docker-compose -f docker-compose.phase3.yml up -d
```

---

## 故障排查

### 问题 1：生成失败

**错误**：
```
❌ 配置文件不存在: config.yml
```

**解决**：
确保 `config.yml` 存在于项目根目录。

### 问题 2：YAML 语法错误

**错误**：
```
yaml.scanner.ScannerError: ...
```

**解决**：
检查 `config.yml` 的 YAML 语法，注意缩进和格式。

### 问题 3：端口冲突

**错误**：
配置验证工具报告端口冲突

**解决**：
确保每个模型的 `prometheus_port` 唯一。

---

## 最佳实践

1. **版本控制**：
   - 将 `config.yml` 提交到 Git
   - 不要提交生成的配置文件（已在 `.gitignore` 中）

2. **配置验证**：
   - 生成配置后立即运行验证工具
   - 部署前确保验证通过

3. **增量修改**：
   - 一次只修改一个配置项
   - 修改后立即测试

4. **文档更新**：
   - 重要配置修改记录在注释中
   - 保持 `config.yml` 注释清晰

---

## 参考资料

- 添加新模型：`docs/ADD_NEW_MODEL.md`
- 添加新视频源：`docs/ADD_NEW_VIDEO_SOURCE.md`
- 配置验证：`scripts/validate_config.py`
- 一键部署：`scripts/deploy.sh`

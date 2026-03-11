# 添加新视频源指南

本文档说明如何向 Savant 视频分析系统添加新的视频源。

## 支持的视频源类型

- 本地视频文件（MP4, AVI, MKV 等）
- RTSP 视频流
- USB 摄像头
- IP 摄像头
- HTTP 视频流

---

## 方案 A：添加本地视频文件

### 步骤 1：准备视频文件

将视频文件放置到 `videos/` 目录：

```bash
cp /path/to/your_video.mp4 videos/video4.mp4
```

### 步骤 2：更新 Docker Compose

编辑 `docker-compose.phase3.yml`，添加新的 source adapter：

```yaml
services:
  # ... 现有服务 ...

  # 视频源适配器 4
  source-adapter-4:
    image: ghcr.io/insight-platform/savant-adapters-gstreamer:0.6.0
    restart: unless-stopped
    volumes:
      - ./videos:/videos
      - zmq_sockets:/tmp/zmq-sockets
      - /tmp/video-downloads:/tmp/video-downloads
    environment:
      - LOCATION=/videos/video4.mp4
      - DOWNLOAD_PATH=/tmp/video-downloads
      - ZMQ_ENDPOINT=pub+connect:ipc:///tmp/zmq-sockets/input-video.ipc
      - SOURCE_ID=video4
      - SYNC_OUTPUT=True
    entrypoint: /opt/savant/adapters/gst/sources/video_loop.sh
    depends_on:
      router:
        condition: service_started
      yolov8-module:  # 或其他模块
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 128M
```

### 步骤 3：更新 Router 配置

编辑 `config/router_handler.py`，添加路由规则：

```python
class SourceIdRouter:
    def __call__(self, message_id: int, ingress_name: str, topic: str, message: Message):
        source_id = topic

        if source_id in ['video1', 'video2']:
            message.labels = ['yolov8']
        elif source_id == 'video3':
            message.labels = ['peoplenet']
        elif source_id == 'video4':  # 新视频源
            message.labels = ['yolov8']  # 选择使用的模型

        return message
```

### 步骤 4：部署

```bash
# 重启服务
docker-compose -f docker-compose.phase3.yml up -d

# 检查新视频源状态
docker logs ai_video_analysis_source-adapter-4_1 -f
```

---

## 方案 B：添加 RTSP 视频流

### 步骤 1：更新 Docker Compose

```yaml
services:
  # RTSP 视频源适配器
  source-adapter-rtsp-1:
    image: ghcr.io/insight-platform/savant-adapters-gstreamer:0.6.0
    restart: unless-stopped
    volumes:
      - zmq_sockets:/tmp/zmq-sockets
    environment:
      - LOCATION=rtsp://username:password@192.168.1.100:554/stream
      - ZMQ_ENDPOINT=pub+connect:ipc:///tmp/zmq-sockets/input-video.ipc
      - SOURCE_ID=camera1
      - SYNC_OUTPUT=False  # RTSP 流通常不需要同步
    entrypoint: /opt/savant/adapters/gst/sources/rtsp.sh
    depends_on:
      router:
        condition: service_started
      yolov8-module:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 128M
```

### 步骤 2：更新 Router 配置

```python
class SourceIdRouter:
    def __call__(self, message_id: int, ingress_name: str, topic: str, message: Message):
        source_id = topic

        if source_id in ['video1', 'video2']:
            message.labels = ['yolov8']
        elif source_id == 'video3':
            message.labels = ['peoplenet']
        elif source_id == 'camera1':  # RTSP 摄像头
            message.labels = ['yolov8']

        return message
```

### RTSP 连接参数说明

**基本格式**：
```
rtsp://[username:password@]host[:port]/path
```

**示例**：
```bash
# 无认证
LOCATION=rtsp://192.168.1.100:554/stream

# 有认证
LOCATION=rtsp://admin:password123@192.168.1.100:554/stream

# 海康威信
LOCATION=rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101

# 大华
LOCATION=rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0
```

---

## 方案 C：添加 USB 摄像头

### 步骤 1：查找摄像头设备

```bash
# 列出所有视频设备
ls -l /dev/video*

# 查看设备信息
v4l2-ctl --list-devices
```

### 步骤 2：更新 Docker Compose

```yaml
services:
  # USB 摄像头适配器
  source-adapter-usb-1:
    image: ghcr.io/insight-platform/savant-adapters-gstreamer:0.6.0
    restart: unless-stopped
    privileged: true  # 需要访问设备
    devices:
      - /dev/video0:/dev/video0  # 映射摄像头设备
    volumes:
      - zmq_sockets:/tmp/zmq-sockets
    environment:
      - LOCATION=/dev/video0
      - ZMQ_ENDPOINT=pub+connect:ipc:///tmp/zmq-sockets/input-video.ipc
      - SOURCE_ID=usb_camera1
      - SYNC_OUTPUT=False
    entrypoint: /opt/savant/adapters/gst/sources/usb_cam.sh
    depends_on:
      router:
        condition: service_started
      yolov8-module:
        condition: service_healthy
```

---

## 方案 D：添加 HTTP 视频流

### 步骤 1：更新 Docker Compose

```yaml
services:
  # HTTP 视频流适配器
  source-adapter-http-1:
    image: ghcr.io/insight-platform/savant-adapters-gstreamer:0.6.0
    restart: unless-stopped
    volumes:
      - zmq_sockets:/tmp/zmq-sockets
      - /tmp/video-downloads:/tmp/video-downloads
    environment:
      - LOCATION=https://example.com/video.mp4
      - DOWNLOAD_PATH=/tmp/video-downloads
      - ZMQ_ENDPOINT=pub+connect:ipc:///tmp/zmq-sockets/input-video.ipc
      - SOURCE_ID=http_stream1
      - SYNC_OUTPUT=False
    entrypoint: /opt/savant/adapters/gst/sources/video_loop.sh
    depends_on:
      router:
        condition: service_started
      yolov8-module:
        condition: service_healthy
```

---

## 高级配置

### 配置视频帧率

```yaml
environment:
  - LOCATION=/videos/video4.mp4
  - SOURCE_ID=video4
  - FRAMERATE=25/1  # 设置帧率为 25 FPS
```

### 配置视频分辨率

```yaml
environment:
  - LOCATION=/videos/video4.mp4
  - SOURCE_ID=video4
  - WIDTH=1920
  - HEIGHT=1080
```

### 配置重连策略（RTSP）

```yaml
environment:
  - LOCATION=rtsp://192.168.1.100:554/stream
  - SOURCE_ID=camera1
  - RTSP_TRANSPORT=tcp  # 使用 TCP 传输（更稳定）
  - RTSP_LATENCY=100    # 延迟（毫秒）
```

---

## 批量添加视频源

如果需要添加多个视频源，可以使用脚本生成配置：

### 生成脚本示例

```bash
#!/bin/bash
# generate_sources.sh

for i in {4..10}; do
  cat >> docker-compose.phase3.yml << EOF

  source-adapter-$i:
    image: ghcr.io/insight-platform/savant-adapters-gstreamer:0.6.0
    restart: unless-stopped
    volumes:
      - ./videos:/videos
      - zmq_sockets:/tmp/zmq-sockets
    environment:
      - LOCATION=/videos/video$i.mp4
      - ZMQ_ENDPOINT=pub+connect:ipc:///tmp/zmq-sockets/input-video.ipc
      - SOURCE_ID=video$i
      - SYNC_OUTPUT=True
    entrypoint: /opt/savant/adapters/gst/sources/video_loop.sh
    depends_on:
      router:
        condition: service_started
      yolov8-module:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 128M
EOF
done
```

---

## 监控视频源

### 查看视频源日志

```bash
# 查看特定视频源日志
docker logs ai_video_analysis_source-adapter-4_1 -f

# 查看所有视频源日志
docker-compose -f docker-compose.phase3.yml logs -f | grep source-adapter
```

### 检查视频源状态

```bash
# 查看容器状态
docker ps | grep source-adapter

# 查看资源使用
docker stats --no-stream | grep source-adapter
```

### Grafana 监控

在 Grafana 中可以查看：
- 每个视频源的 FPS
- 处理延迟
- 检测对象数量

---

## 常见问题

### Q1: RTSP 连接失败

**错误信息**：
```
Could not connect to RTSP server
```

**解决方案**：
1. 检查 RTSP URL 是否正确
2. 检查用户名密码
3. 检查网络连接
4. 尝试使用 TCP 传输：`RTSP_TRANSPORT=tcp`
5. 使用 VLC 测试 RTSP 流是否可用

### Q2: USB 摄像头无法访问

**错误信息**：
```
Cannot open device /dev/video0
```

**解决方案**：
1. 确认设备存在：`ls -l /dev/video*`
2. 检查设备权限：`sudo chmod 666 /dev/video0`
3. 确认 Docker Compose 中添加了 `privileged: true`
4. 确认 `devices` 映射正确

### Q3: 视频循环播放不工作

**问题**：视频播放一次后停止

**解决方案**：
确认使用了 `video_loop.sh` 而不是 `video_file.sh`：
```yaml
entrypoint: /opt/savant/adapters/gst/sources/video_loop.sh
```

### Q4: 多个视频源性能下降

**现象**：添加多个视频源后 FPS 下降

**解决方案**：
1. 检查 GPU 利用率：`nvidia-smi`
2. 增加模块的 `batch_size`
3. 降低视频分辨率
4. 添加更多 GPU 或模块实例

---

## 视频源类型对比

| 类型 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 本地文件 | 稳定、可重复测试 | 不是实时流 | 开发测试 |
| RTSP | 实时、广泛支持 | 网络依赖 | 生产环境 |
| USB 摄像头 | 低延迟 | 需要物理连接 | 边缘设备 |
| HTTP 流 | 简单 | 延迟较高 | 特定场景 |

---

## 检查清单

添加新视频源前，确认以下事项：

- [ ] 视频源可访问（文件存在/RTSP 可连接）
- [ ] Docker Compose 已添加新服务
- [ ] Router 配置已更新
- [ ] SOURCE_ID 唯一且有意义
- [ ] 依赖的模块已配置健康检查
- [ ] 资源限制已配置
- [ ] 配置验证工具通过
- [ ] 服务启动成功
- [ ] 日志无错误
- [ ] 输出结果正确

---

## 参考资料

- Savant Adapters 文档：https://docs.savant-ai.io/
- GStreamer 文档：https://gstreamer.freedesktop.org/
- RTSP 协议：https://en.wikipedia.org/wiki/Real_Time_Streaming_Protocol

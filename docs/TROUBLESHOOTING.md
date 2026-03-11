# 故障排查指南

本文档提供 Savant 视频分析系统常见问题的排查和解决方案。

## 目录

1. [服务启动问题](#服务启动问题)
2. [模型加载问题](#模型加载问题)
3. [视频源问题](#视频源问题)
4. [性能问题](#性能问题)
5. [网络和通信问题](#网络和通信问题)
6. [监控问题](#监控问题)
7. [输出问题](#输出问题)

---

## 服务启动问题

### 问题 1：容器无法启动

**症状**：
```bash
docker ps
# 某些容器不在列表中
```

**排查步骤**：

```bash
# 1. 查看所有容器（包括停止的）
docker ps -a

# 2. 查看容器日志
docker logs <container_name>

# 3. 检查容器退出代码
docker inspect <container_name> | grep ExitCode
```

**常见原因和解决方案**：

| 原因 | 解决方案 |
|------|---------|
| 配置文件错误 | 运行 `python scripts/validate_config.py` |
| 端口冲突 | 检查端口占用：`netstat -tlnp \| grep <port>` |
| 资源不足 | 检查内存和 GPU：`free -h` 和 `nvidia-smi` |
| 依赖服务未就绪 | 检查 `depends_on` 配置 |

### 问题 2：健康检查失败

**症状**：
```bash
docker ps
# 显示 (unhealthy)
```

**排查步骤**：

```bash
# 1. 查看健康检查日志
docker inspect <container_name> --format='{{json .State.Health}}' | python3 -m json.tool

# 2. 手动执行健康检查命令
docker exec <container_name> curl -f http://localhost:8080/status

# 3. 查看容器日志
docker logs <container_name> --tail 100
```

**解决方案**：

```bash
# 如果是端口问题，检查配置
# healthcheck 端口应该是容器内部端口 8080，不是映射后的端口

# 正确配置：
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/status"]

# 错误配置：
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/status"]  # 错误！
```

### 问题 3：GPU 不可用

**症状**：
```
CUDA error: no CUDA-capable device is detected
```

**排查步骤**：

```bash
# 1. 检查 NVIDIA 驱动
nvidia-smi

# 2. 检查 Docker NVIDIA Runtime
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# 3. 检查 Docker Compose 配置
grep -A 5 "runtime: nvidia" docker-compose.phase3.yml
```

**解决方案**：

```bash
# 安装 NVIDIA Docker Runtime
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

---

## 模型加载问题

### 问题 4：模型文件未找到

**症状**：
```
Model file "/models/yolov8n.onnx" not found
```

**排查步骤**：

```bash
# 1. 检查宿主机文件
ls -lh models/

# 2. 检查容器内文件
docker exec <module_container> ls -lh /models/

# 3. 检查 volume 挂载
docker inspect <module_container> | grep -A 10 Mounts
```

**解决方案**：

```bash
# 确保模型文件存在
ls -lh models/yolov8n.onnx

# 确保 Docker Compose 中 volume 挂载正确
volumes:
  - ./models:/models  # 正确
  # - ./model:/models  # 错误：目录名拼写错误
```

### 问题 5：TensorRT 引擎构建失败

**症状**：
```
Failed to build TensorRT engine
```

**排查步骤**：

```bash
# 1. 查看完整日志
docker logs <module_container> 2>&1 | grep -i "tensorrt\|engine\|error"

# 2. 检查 ONNX 模型
# 使用 Netron 查看：https://netron.app/

# 3. 检查 GPU 显存
nvidia-smi
```

**解决方案**：

```yaml
# 1. 尝试使用 FP32 而不是 FP16
model:
  precision: fp32  # 而不是 fp16

# 2. 减小 batch_size
parameters:
  batch_size: 1  # 从 8 减小到 1

# 3. 清理旧的引擎文件
# 删除 models/ 目录下的 .engine 文件
```

### 问题 6：检测结果为空

**症状**：
输出 JSON 中 `objects` 数组为空

**排查步骤**：

```bash
# 1. 检查模型是否正常加载
docker logs <module_container> | grep "Model.*loaded"

# 2. 检查输入视频
# 确认视频可以正常播放

# 3. 检查置信度阈值
grep "confidence_threshold" modules/*/module.yml
```

**解决方案**：

```yaml
# 降低置信度阈值
output:
  converter:
    kwargs:
      confidence_threshold: 0.1  # 从 0.25 降低到 0.1
      nms_iou_threshold: 0.45
```

---

## 视频源问题

### 问题 7：RTSP 连接失败

**症状**：
```
Could not connect to RTSP server
```

**排查步骤**：

```bash
# 1. 使用 VLC 测试 RTSP 流
vlc rtsp://username:password@192.168.1.100:554/stream

# 2. 使用 ffprobe 测试
ffprobe rtsp://username:password@192.168.1.100:554/stream

# 3. 检查网络连接
ping 192.168.1.100
telnet 192.168.1.100 554
```

**解决方案**：

```yaml
# 1. 使用 TCP 传输（更稳定）
environment:
  - RTSP_TRANSPORT=tcp

# 2. 增加超时时间
environment:
  - RTSP_LATENCY=2000  # 2 秒

# 3. 检查 URL 格式
# 正确：rtsp://admin:pass@192.168.1.100:554/stream
# 错误：rtsp://192.168.1.100:554/stream（缺少认证）
```

### 问题 8：视频循环播放停止

**症状**：
视频播放一次后容器退出

**解决方案**：

```yaml
# 使用 video_loop.sh 而不是 video_file.sh
entrypoint: /opt/savant/adapters/gst/sources/video_loop.sh  # 正确
# entrypoint: /opt/savant/adapters/gst/sources/video_file.sh  # 错误
```

---

## 性能问题

### 问题 9：FPS 过低

**症状**：
Grafana 显示 FPS < 10

**排查步骤**：

```bash
# 1. 检查 GPU 利用率
nvidia-smi -l 1

# 2. 检查 CPU 和内存
docker stats

# 3. 检查队列堆积
# 在 Grafana 中查看 stage_queue_length
```

**解决方案**：

| 瓶颈 | 解决方案 |
|------|---------|
| GPU 利用率低 | 增加 batch_size |
| GPU 显存不足 | 减小 batch_size 或使用 FP16 |
| CPU 瓶颈 | 减小视频分辨率 |
| 队列堆积 | 增加模块实例数 |

```yaml
# 增加 batch_size
parameters:
  batch_size: 16  # 从 8 增加到 16

# 使用 FP16 精度
model:
  precision: fp16
```

### 问题 10：内存不足

**症状**：
```
OOMKilled
```

**排查步骤**：

```bash
# 1. 检查容器内存限制
docker inspect <container_name> | grep Memory

# 2. 检查实际内存使用
docker stats --no-stream
```

**解决方案**：

```yaml
# 增加内存限制
deploy:
  resources:
    limits:
      memory: 1G  # 从 512M 增加到 1G
```

---

## 网络和通信问题

### 问题 11：ZeroMQ 连接失败

**症状**：
```
Failed to connect to ZeroMQ socket
```

**排查步骤**：

```bash
# 1. 检查 socket 文件
docker exec <container_name> ls -l /tmp/zmq-sockets/

# 2. 检查 ZeroMQ 配置
grep "ZMQ_.*_ENDPOINT" docker-compose.phase3.yml

# 3. 检查容器网络
docker network inspect ai_video_analysis_default
```

**解决方案**：

```yaml
# 确保 socket 类型匹配
# Router 端：dealer+bind
# Module 端：router+connect

# Router 配置
egress:
  - socket:
      url: "dealer+bind:ipc:///tmp/zmq-sockets/yolov8.ipc"

# Module 配置
environment:
  - ZMQ_SRC_ENDPOINT=router+connect:ipc:///tmp/zmq-sockets/yolov8.ipc
```

### 问题 12：Router 不分发消息

**症状**：
视频源有数据，但模块没有收到

**排查步骤**：

```bash
# 1. 检查 Router 日志
docker logs ai_video_analysis_router_1

# 2. 检查 Router 配置
cat config/router_config.json

# 3. 检查 Router Handler
cat config/router_handler.py
```

**解决方案**：

```python
# 确保 Router Handler 返回 message
def __call__(self, message_id, ingress_name, topic, message):
    source_id = topic
    if source_id == 'video1':
        message.labels = ['yolov8']
    return message  # 重要：必须返回 message
```

---

## 监控问题

### 问题 13：Prometheus 无法采集指标

**症状**：
Prometheus Targets 显示 "down"

**排查步骤**：

```bash
# 1. 检查指标端点
curl http://localhost:8000/metrics

# 2. 检查 Prometheus 配置
cat monitoring/prometheus.yml

# 3. 检查 Prometheus 日志
docker logs ai_video_analysis_prometheus_1
```

**解决方案**：

```yaml
# 确保采集目标使用容器内部端口
scrape_configs:
  - job_name: 'yolov8-module'
    static_configs:
      - targets: ['yolov8-module:8080']  # 容器内部端口
        # 不是 ['yolov8-module:8000']  # 错误
```

### 问题 14：Grafana 无法连接 Prometheus

**症状**：
Grafana 数据源测试失败

**解决方案**：

```yaml
# Grafana 数据源配置
URL: http://prometheus:9090  # 使用服务名，不是 localhost
```

---

## 输出问题

### 问题 15：没有输出文件

**症状**：
`output/` 目录为空

**排查步骤**：

```bash
# 1. 检查 JSON Sink 日志
docker logs ai_video_analysis_json-sink-yolov8_1

# 2. 检查 output 目录权限
ls -ld output/

# 3. 检查 ZeroMQ 连接
docker logs ai_video_analysis_json-sink-yolov8_1 | grep -i "connect\|error"
```

**解决方案**：

```bash
# 1. 确保 output 目录存在且可写
mkdir -p output
chmod 777 output

# 2. 检查 JSON Sink 配置
environment:
  - ZMQ_ENDPOINT=sub+connect:ipc:///tmp/zmq-sockets/output-yolov8.ipc
  - FILENAME_PATTERN=/output/yolov8_%source_id_%src_filename.json
```

---

## 调试技巧

### 技巧 1：查看实时日志

```bash
# 查看所有服务日志
docker-compose -f docker-compose.phase3.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.phase3.yml logs -f yolov8-module

# 过滤错误日志
docker-compose -f docker-compose.phase3.yml logs | grep -i error
```

### 技巧 2：进入容器调试

```bash
# 进入容器
docker exec -it ai_video_analysis_yolov8-module_1 bash

# 检查文件
ls -lh /models/
ls -lh /opt/savant/modules/

# 检查进程
ps aux

# 检查网络
netstat -tlnp
```

### 技巧 3：使用 Grafana 监控

在 Grafana 中查看：
- FPS 趋势
- 队列长度
- Pipeline 延迟
- 对象检测数量

### 技巧 4：配置验证

```bash
# 运行配置验证工具
python scripts/validate_config.py

# 验证 Docker Compose
docker-compose -f docker-compose.phase3.yml config

# 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('modules/yolov8/module.yml'))"
```

---

## 紧急恢复

### 完全重启系统

```bash
# 1. 停止所有服务
docker-compose -f docker-compose.phase3.yml down

# 2. 清理资源
docker system prune -f

# 3. 重新启动
docker-compose -f docker-compose.phase3.yml up -d

# 4. 检查状态
docker-compose -f docker-compose.phase3.yml ps
```

### 重置单个服务

```bash
# 重启单个服务
docker-compose -f docker-compose.phase3.yml restart yolov8-module

# 重建单个服务
docker-compose -f docker-compose.phase3.yml up -d --force-recreate yolov8-module
```

---

## 获取帮助

如果以上方法都无法解决问题：

1. **收集信息**：
   ```bash
   # 导出所有日志
   docker-compose -f docker-compose.phase3.yml logs > debug.log

   # 导出容器状态
   docker ps -a > containers.txt

   # 导出系统信息
   nvidia-smi > gpu_info.txt
   free -h > memory_info.txt
   ```

2. **查看文档**：
   - Savant 官方文档：https://docs.savant-ai.io/
   - 项目文档：`docs/` 目录

3. **提交 Issue**：
   - GitHub: https://github.com/RoryWang1/video_adaptive_analysis/issues
   - 附上收集的日志和配置文件

---

## 预防措施

1. **定期备份配置**
2. **使用配置验证工具**
3. **监控系统资源**
4. **定期查看日志**
5. **保持文档更新**

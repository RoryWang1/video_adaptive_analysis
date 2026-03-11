# 监控系统部署说明

## 概述

为 Savant 视频分析系统添加了 Prometheus + Grafana 监控体系，可以实时监控：
- 模块 FPS（帧率）
- Pipeline 延迟
- GPU 利用率
- 吞吐量
- 对象检测数量

## 架构

```
Savant 模块 (YOLOv8/PeopleNet)
    ↓ 暴露 Prometheus 指标
Prometheus (采集和存储)
    ↓ 提供数据源
Grafana (可视化面板)
```

## 配置文件

### 1. 模块配置更新

**modules/yolov8/module.yml**:
- 添加了 `metrics` 配置段
- Prometheus 端口: 8000
- 每 1000 帧或每 10 秒报告一次

**modules/peoplenet/module.yml**:
- 添加了 `metrics` 配置段
- Prometheus 端口: 8001
- 每 1000 帧或每 10 秒报告一次

### 2. Prometheus 配置

**monitoring/prometheus.yml**:
- 采集间隔: 10 秒
- 采集目标:
  - yolov8-module:8000
  - peoplenet-module:8001
  - prometheus:9090

### 3. Grafana 仪表板

**monitoring/grafana-dashboard.json**:
- 模块 FPS 趋势图
- Pipeline 延迟趋势图
- 自动刷新: 5 秒

### 4. Docker Compose 更新

**docker-compose.yml**:
- YOLOv8 模块暴露端口 8000
- PeopleNet 模块暴露端口 8001
- Prometheus 服务端口 9090
- Grafana 服务端口 3000

## 部署步骤

### 本地验证

```bash
# 1. 验证配置文件语法
docker-compose config

# 2. 检查 Prometheus 配置
docker run --rm -v $(pwd)/monitoring:/etc/prometheus \
  prom/prometheus:latest \
  promtool check config /etc/prometheus/prometheus.yml
```

### 云端部署

```bash
# 1. 上传配置文件
scp -r modules/ root@120.24.249.245:/root/ai_video_analysis/
scp -r monitoring/ root@120.24.249.245:/root/ai_video_analysis/
scp docker-compose.yml root@120.24.249.245:/root/ai_video_analysis/

# 2. 重启服务应用新配置
ssh root@120.24.249.245 "cd /root/ai_video_analysis && \
  docker-compose down && \
  docker-compose up -d"

# 3. 等待服务启动
sleep 30

# 4. 检查服务状态
ssh root@120.24.249.245 "docker-compose ps"
```

## 访问监控

### Prometheus

访问地址: http://120.24.249.245:9090

**常用查询**:
```promql
# 模块 FPS
rate(savant_frame_counter[1m])

# Pipeline 延迟
savant_pipeline_latency_ms

# 对象检测数量
rate(savant_object_counter[1m])
```

### Grafana

访问地址: http://120.24.249.245:3000

**默认登录**:
- 用户名: admin
- 密码: admin

**首次登录后**:
1. 添加 Prometheus 数据源
   - URL: http://prometheus:9090
2. 导入仪表板
   - 使用 `/etc/grafana/provisioning/dashboards/savant.json`

## 监控指标说明

### 核心指标

| 指标名称 | 说明 | 单位 |
|---------|------|------|
| savant_frame_counter | 处理的帧数 | 帧 |
| savant_object_counter | 检测的对象数 | 个 |
| savant_pipeline_latency_ms | Pipeline 延迟 | 毫秒 |
| savant_fps | 实时 FPS | 帧/秒 |
| savant_batch_size | 批处理大小 | 帧 |

### 性能目标

| 指标 | 目标值 | 当前值 |
|------|--------|--------|
| YOLOv8 FPS | > 40 | 50 |
| PeopleNet FPS | > 20 | 25 |
| 端到端延迟 | < 100ms | 待测 |
| GPU 利用率 | > 60% | 待测 |

## 故障排查

### Prometheus 无法采集指标

```bash
# 检查模块是否暴露指标端口
ssh root@120.24.249.245 "curl http://localhost:8000/metrics"
ssh root@120.24.249.245 "curl http://localhost:8001/metrics"

# 检查 Prometheus 日志
ssh root@120.24.249.245 "docker logs ai_video_analysis_prometheus_1"
```

### Grafana 无法连接 Prometheus

```bash
# 检查 Prometheus 是否运行
ssh root@120.24.249.245 "docker ps | grep prometheus"

# 检查网络连接
ssh root@120.24.249.245 "docker exec ai_video_analysis_grafana_1 \
  curl http://prometheus:9090/api/v1/status/config"
```

### 模块指标端口冲突

如果端口 8000/8001 已被占用：
1. 修改 `modules/*/module.yml` 中的 `prometheus.port`
2. 修改 `docker-compose.yml` 中的端口映射
3. 修改 `monitoring/prometheus.yml` 中的采集目标

## 下一步

监控系统部署完成后，可以进行：

1. **性能测试**
   - 测试不同 batch_size 的性能
   - 测试更多路视频的并发能力
   - 记录性能基线数据

2. **优化调整**
   - 根据监控数据调整参数
   - 优化 TensorRT 引擎配置
   - 提升 GPU 利用率

3. **稳定性测试**
   - 长时间运行测试（> 1 小时）
   - 监控内存泄漏
   - 验证错误恢复机制

# 稳定性提升文档

## 概述

本文档记录了为提升系统稳定性所做的优化措施。

## 优化内容

### 1. 资源限制配置

为所有容器添加了内存限制，防止资源耗尽导致系统崩溃：

| 服务 | 内存限制 | 内存预留 | 说明 |
|------|---------|---------|------|
| source-adapter (×3) | 512M | 128M | 视频源适配器 |
| router | 256M | 64M | 流量分发路由 |
| json-sink (×2) | 256M | 64M | JSON 输出 |
| prometheus | 512M | 128M | 监控服务 |
| grafana | 512M | 128M | 可视化服务 |
| yolov8-module | 无限制 | GPU | GPU 推理模块 |
| peoplenet-module | 无限制 | GPU | GPU 推理模块 |

**注意**：GPU 推理模块不设置内存限制，因为需要动态分配 GPU 显存。

### 2. 服务依赖优化

优化了容器启动顺序和依赖关系：

```
启动顺序：
1. Router（流量分发中心）
2. YOLOv8 Module + PeopleNet Module（等待健康检查通过）
3. Source Adapters（等待对应模块健康后启动）
4. JSON Sinks（等待模块启动后启动）
5. Prometheus + Grafana（独立启动）
```

**优点**：
- ✅ 避免视频源在模块未就绪时发送数据
- ✅ 减少启动时的错误日志
- ✅ 提升系统启动可靠性

### 3. 健康检查配置

所有关键服务都配置了健康检查：

**YOLOv8 Module**：
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/status"]
  interval: 5s
  timeout: 3s
  retries: 12
  start_period: 30s
```

**PeopleNet Module**：
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/status"]
  interval: 5s
  timeout: 3s
  retries: 12
  start_period: 30s
```

### 4. 重启策略

所有服务使用 `restart: unless-stopped`：
- 容器异常退出时自动重启
- 手动停止的容器不会自动重启
- 系统重启后自动恢复服务

### 5. Prometheus 数据保留策略

配置 Prometheus 数据保留时间为 7 天：
```yaml
command:
  - '--storage.tsdb.retention.time=7d'
```

**优点**：
- ✅ 避免监控数据无限增长
- ✅ 保留足够的历史数据用于分析
- ✅ 平衡存储空间和数据价值

## 稳定性测试建议

### 1. 短期测试（1-2 小时）

验证系统基本稳定性：

```bash
# 1. 启动系统
docker-compose up -d

# 2. 监控容器状态
watch -n 5 'docker ps --format "table {{.Names}}\t{{.Status}}"'

# 3. 监控资源使用
watch -n 10 'docker stats --no-stream'

# 4. 检查日志错误
docker-compose logs --tail=100 | grep -i error
```

### 2. 长期测试（24 小时+）

验证系统长期运行稳定性：

```bash
# 1. 记录启动时间
date > stability_test_start.txt

# 2. 定期检查（每小时）
# 创建监控脚本
cat > monitor.sh << 'EOF'
#!/bin/bash
echo "=== $(date) ===" >> stability_log.txt
docker ps --format "table {{.Names}}\t{{.Status}}" >> stability_log.txt
docker stats --no-stream >> stability_log.txt
echo "" >> stability_log.txt
EOF

chmod +x monitor.sh

# 3. 设置定时任务（每小时执行）
crontab -e
# 添加：0 * * * * /path/to/monitor.sh

# 4. 24 小时后检查结果
cat stability_log.txt | grep -i "unhealthy\|restart"
```

### 3. 压力测试

测试系统在高负载下的表现：

```bash
# 1. 增加视频源数量（修改 docker-compose.yml）
# 2. 降低 batch_size 增加处理频率
# 3. 监控 GPU 利用率和内存使用
# 4. 观察是否有容器重启或崩溃
```

## 故障恢复机制

### 自动恢复

系统已配置自动恢复机制：

1. **容器崩溃**：自动重启（restart: unless-stopped）
2. **健康检查失败**：Docker 标记为 unhealthy，依赖服务会等待恢复
3. **ZeroMQ 连接断开**：Savant 内置重连机制

### 手动恢复

如果自动恢复失败，手动恢复步骤：

```bash
# 1. 检查问题容器
docker ps -a | grep -v "Up"

# 2. 查看容器日志
docker logs <container_name> --tail 100

# 3. 重启单个服务
docker-compose restart <service_name>

# 4. 如果需要，重启整个系统
docker-compose down
docker-compose up -d
```

## 监控告警

### Grafana 告警配置（可选）

可以在 Grafana 中配置告警规则：

1. **FPS 下降告警**：
   - 条件：FPS < 20（YOLOv8）或 FPS < 10（PeopleNet）
   - 持续时间：5 分钟

2. **队列堆积告警**：
   - 条件：队列长度 > 10
   - 持续时间：2 分钟

3. **容器不健康告警**：
   - 条件：健康检查失败
   - 立即告警

### Prometheus 告警规则（可选）

创建 `monitoring/alert_rules.yml`：

```yaml
groups:
  - name: savant_alerts
    interval: 30s
    rules:
      - alert: LowFPS
        expr: rate(stage_frame_counter_total{stage_name="sink"}[1m]) < 20
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "模块 FPS 过低"
          description: "{{ $labels.module }} FPS 低于 20"

      - alert: HighQueueLength
        expr: sum(stage_queue_length) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "队列堆积"
          description: "{{ $labels.module }} 队列长度超过 10"
```

## 已知限制

1. **GPU 模块内存**：未设置限制，依赖 NVIDIA 驱动管理
2. **日志轮转**：Docker 默认日志策略，未自定义配置
3. **网络故障**：ZeroMQ IPC 通信，不受网络影响，但 RTSP 流需要网络稳定

## 下一步优化建议

1. **添加 Watchdog**：监控服务健康状态，自动重启异常服务
2. **日志聚合**：使用 Loki 或 ELK 收集和分析日志
3. **备份机制**：定期备份 Prometheus 数据和 Grafana 配置
4. **多副本部署**：关键服务部署多个副本提高可用性

## 总结

通过以上优化，系统稳定性得到显著提升：

- ✅ 资源使用可控，避免 OOM
- ✅ 服务启动顺序合理，减少错误
- ✅ 自动重启机制完善
- ✅ 健康检查覆盖关键服务
- ✅ 监控数据保留策略合理

系统现在可以稳定运行，适合长期部署使用。

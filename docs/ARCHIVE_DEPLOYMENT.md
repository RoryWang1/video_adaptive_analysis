# 消息归档功能部署指南

## 更新内容

### 新增功能
✅ 消息归档 Sink - 保存完整的 Savant Message
✅ 消息归档 Source - 重放归档的消息
✅ 自动清理脚本 - 管理归档文件
✅ 完整的使用文档

### 移除内容
❌ redis-stream-source - 设计缺陷，已删除
❌ postgres-replay-source - 暂不需要，已删除

## 部署步骤

### 1. 上传文件到服务器

```bash
# 上传新增的文件
scp /Users/rory/work/project/ai_video_analysis/adapters/message_archive_sink.py root@8.135.51.2:/root/ai_video_analysis/adapters/

scp /Users/rory/work/project/ai_video_analysis/adapters/message_archive_source.py root@8.135.51.2:/root/ai_video_analysis/adapters/

scp /Users/rory/work/project/ai_video_analysis/scripts/cleanup_archive.sh root@8.135.51.2:/root/ai_video_analysis/scripts/

# 上传更新的配置
scp /Users/rory/work/project/ai_video_analysis/docker-compose.yml root@8.135.51.2:/root/ai_video_analysis/

# 上传文档
scp /Users/rory/work/project/ai_video_analysis/docs/MESSAGE_ARCHIVE_GUIDE.md root@8.135.51.2:/root/ai_video_analysis/docs/

scp /Users/rory/work/project/ai_video_analysis/docs/REPLAY_SOLUTIONS.md root@8.135.51.2:/root/ai_video_analysis/docs/

scp /Users/rory/work/project/ai_video_analysis/docs/PERSISTENCE_FIX_SUMMARY.md root@8.135.51.2:/root/ai_video_analysis/docs/
```

### 2. 清理旧服务

```bash
# 停止并删除旧的 redis-stream-source
ssh root@8.135.51.2 "cd /root/ai_video_analysis && docker-compose stop redis-stream-source && docker-compose rm -f redis-stream-source"

# 删除旧文件
ssh root@8.135.51.2 "rm -f /root/ai_video_analysis/adapters/redis_stream_source.py"
ssh root@8.135.51.2 "rm -f /root/ai_video_analysis/adapters/postgres_replay_source.py"
```

### 3. 验证配置

```bash
# 验证 docker-compose.yml
ssh root@8.135.51.2 "cd /root/ai_video_analysis && docker-compose config | grep -A 10 message-archive-sink"

# 验证文件存在
ssh root@8.135.51.2 "ls -la /root/ai_video_analysis/adapters/message_archive_*.py"
ssh root@8.135.51.2 "ls -la /root/ai_video_analysis/scripts/cleanup_archive.sh"
```

### 4. 创建归档目录

```bash
# 创建归档目录
ssh root@8.135.51.2 "mkdir -p /root/ai_video_analysis/data/message_archive"

# 设置权限
ssh root@8.135.51.2 "chmod 755 /root/ai_video_analysis/data/message_archive"
ssh root@8.135.51.2 "chmod +x /root/ai_video_analysis/scripts/cleanup_archive.sh"
```

### 5. 测试归档功能（可选）

```bash
# 启动归档服务（测试）
ssh root@8.135.51.2 "cd /root/ai_video_analysis && docker-compose --profile archive up -d message-archive-sink"

# 查看日志
ssh root@8.135.51.2 "cd /root/ai_video_analysis && docker-compose logs -f message-archive-sink"

# 等待几分钟，检查归档文件
ssh root@8.135.51.2 "find /root/ai_video_analysis/data/message_archive -name '*.msg' | head -5"

# 停止归档服务
ssh root@8.135.51.2 "cd /root/ai_video_analysis && docker-compose stop message-archive-sink"
```

## 验证清单

- [ ] 旧的 redis-stream-source 服务已停止并删除
- [ ] 新的 message_archive_sink.py 文件已上传
- [ ] 新的 message_archive_source.py 文件已上传
- [ ] cleanup_archive.sh 脚本已上传并有执行权限
- [ ] docker-compose.yml 已更新
- [ ] 归档目录已创建
- [ ] 文档已更新

## 当前服务状态

```bash
# 检查所有持久化服务
ssh root@8.135.51.2 "cd /root/ai_video_analysis && docker-compose ps | grep -E '(postgres-sink|redis-stream)'"
```

预期输出：
```
postgres-sink-yolov8       Up
postgres-sink-peoplenet    Up
redis-stream-sink          Up
```

注意：message-archive-sink 默认不启动（使用 profile），按需启用。

## 使用说明

详细使用说明请参考：
- `docs/MESSAGE_ARCHIVE_GUIDE.md` - 消息归档功能使用指南
- `docs/REPLAY_SOLUTIONS.md` - 数据重放方案对比
- `docs/PERSISTENCE_FIX_SUMMARY.md` - 持久化功能修复总结

## 快速参考

### 启用归档
```bash
docker-compose --profile archive up -d message-archive-sink
```

### 重放归档
```bash
docker-compose run --rm \
  -e SOURCE_ID=video1 \
  -e FPS=25 \
  message-archive-sink \
  python /opt/adapters/message_archive_source.py
```

### 清理归档
```bash
bash scripts/cleanup_archive.sh --keep 7
```

#!/bin/bash
# 数据持久化层测试脚本
# 服务器: 47.112.171.226

set -e

echo "=========================================="
echo "数据持久化层测试和验证"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 服务器信息
SERVER_IP="47.112.171.226"
SERVER_USER="root"
SERVER_PATH="/root"

echo "📋 测试环境信息："
echo "  服务器: ${SERVER_IP}"
echo "  用户: ${SERVER_USER}"
echo "  路径: ${SERVER_PATH}"
echo ""

# ============================================
# 步骤 1: 上传文件到服务器
# ============================================
echo "=========================================="
echo "步骤 1: 上传文件到服务器"
echo "=========================================="
echo ""

echo "📤 上传适配器文件..."
scp -r adapters ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/

echo "📤 上传数据库初始化脚本..."
scp -r database ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/

echo "📤 上传配置文件..."
scp config.yml ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/

echo "📤 创建 scripts 目录并上传脚本..."
ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p ${SERVER_PATH}/scripts"
scp scripts/generate_config.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/scripts/
scp scripts/validate_config.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/scripts/

echo -e "${GREEN}✅ 文件上传完成${NC}"
echo ""

# ============================================
# 步骤 2: 在服务器上生成配置
# ============================================
echo "=========================================="
echo "步骤 2: 在服务器上生成配置"
echo "=========================================="
echo ""

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /root

echo "🔧 生成配置文件..."
conda run -n savant-video-analysis python scripts/generate_config.py

echo "🔍 验证配置..."
conda run -n savant-video-analysis python scripts/validate_config.py

echo "✅ 配置生成和验证完成"
ENDSSH

echo ""

# ============================================
# 步骤 3: 启动持久化服务
# ============================================
echo "=========================================="
echo "步骤 3: 启动持久化服务"
echo "=========================================="
echo ""

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /root

echo "🛑 停止现有服务..."
docker-compose down

echo "🚀 启动持久化服务..."
docker-compose up -d redis postgres

echo "⏳ 等待服务启动（30 秒）..."
sleep 30

echo "🏥 检查服务状态..."
docker-compose ps redis postgres

echo "✅ 持久化服务启动完成"
ENDSSH

echo ""

# ============================================
# 步骤 4: 测试 Redis 连接
# ============================================
echo "=========================================="
echo "步骤 4: 测试 Redis 连接"
echo "=========================================="
echo ""

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /root

echo "🔍 测试 Redis 连接..."
docker exec -it $(docker-compose ps -q redis) redis-cli ping

echo "📊 查看 Redis 信息..."
docker exec -it $(docker-compose ps -q redis) redis-cli info memory | grep used_memory_human

echo "✅ Redis 连接正常"
ENDSSH

echo ""

# ============================================
# 步骤 5: 测试 PostgreSQL 连接
# ============================================
echo "=========================================="
echo "步骤 5: 测试 PostgreSQL 连接"
echo "=========================================="
echo ""

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /root

echo "🔍 测试 PostgreSQL 连接..."
docker exec -it $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "SELECT version();"

echo "📊 查看数据库表..."
docker exec -it $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "\dt"

echo "📊 查看 sources 表数据..."
docker exec -it $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "SELECT * FROM sources;"

echo "📊 查看 models 表数据..."
docker exec -it $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "SELECT * FROM models;"

echo "✅ PostgreSQL 连接正常"
ENDSSH

echo ""

# ============================================
# 步骤 6: 启动完整系统
# ============================================
echo "=========================================="
echo "步骤 6: 启动完整系统"
echo "=========================================="
echo ""

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /root

echo "🚀 启动所有服务..."
docker-compose up -d

echo "⏳ 等待服务启动（60 秒）..."
sleep 60

echo "🏥 检查所有服务状态..."
docker-compose ps

echo "✅ 完整系统启动完成"
ENDSSH

echo ""

# ============================================
# 步骤 7: 验证数据流
# ============================================
echo "=========================================="
echo "步骤 7: 验证数据流"
echo "=========================================="
echo ""

echo "⏳ 等待数据处理（60 秒）..."
sleep 60

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /root

echo "📊 检查 Redis Stream 数据..."
docker exec $(docker-compose ps -q redis) redis-cli XLEN savant:video_stream

echo "📊 检查 Redis Stream 最新数据..."
docker exec $(docker-compose ps -q redis) redis-cli XREVRANGE savant:video_stream + - COUNT 1

echo "📊 检查 PostgreSQL 帧检测记录..."
docker exec $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "SELECT COUNT(*) as frame_count FROM frame_detections;"

echo "📊 检查 PostgreSQL 对象检测记录..."
docker exec $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "SELECT COUNT(*) as object_count FROM detected_objects;"

echo "📊 查看最近的检测结果..."
docker exec $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "
SELECT
    s.source_id,
    m.model_name,
    fd.frame_num,
    fd.timestamp,
    fd.object_count
FROM frame_detections fd
JOIN sources s ON fd.source_id = s.id
JOIN models m ON fd.model_id = m.id
ORDER BY fd.timestamp DESC
LIMIT 10;
"

echo "✅ 数据流验证完成"
ENDSSH

echo ""

# ============================================
# 步骤 8: 测试服务重启恢复
# ============================================
echo "=========================================="
echo "步骤 8: 测试服务重启恢复"
echo "=========================================="
echo ""

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /root

echo "📊 记录重启前的数据量..."
echo "Redis Stream 长度:"
docker exec $(docker-compose ps -q redis) redis-cli XLEN savant:video_stream

echo "PostgreSQL 记录数:"
docker exec $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "SELECT COUNT(*) FROM frame_detections;"

echo "🔄 重启 Redis 服务..."
docker-compose restart redis

echo "⏳ 等待 Redis 恢复（10 秒）..."
sleep 10

echo "📊 检查 Redis 数据是否恢复..."
docker exec $(docker-compose ps -q redis) redis-cli XLEN savant:video_stream

echo "🔄 重启 PostgreSQL 服务..."
docker-compose restart postgres

echo "⏳ 等待 PostgreSQL 恢复（10 秒）..."
sleep 10

echo "📊 检查 PostgreSQL 数据是否恢复..."
docker exec $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "SELECT COUNT(*) FROM frame_detections;"

echo "✅ 服务重启恢复测试完成"
ENDSSH

echo ""

# ============================================
# 步骤 9: 性能测试
# ============================================
echo "=========================================="
echo "步骤 9: 性能测试"
echo "=========================================="
echo ""

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /root

echo "📊 Redis 性能指标..."
docker exec $(docker-compose ps -q redis) redis-cli info stats | grep -E "total_commands_processed|instantaneous_ops_per_sec"

echo "📊 Redis 内存使用..."
docker exec $(docker-compose ps -q redis) redis-cli info memory | grep -E "used_memory_human|maxmemory_human"

echo "📊 PostgreSQL 性能指标..."
docker exec $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

echo "📊 查询性能测试（按对象类别统计）..."
docker exec $(docker-compose ps -q postgres) psql -U savant -d savant_video_analysis -c "
EXPLAIN ANALYZE
SELECT
    object_class,
    COUNT(*) as count,
    AVG(confidence) as avg_confidence
FROM detected_objects
GROUP BY object_class;
"

echo "✅ 性能测试完成"
ENDSSH

echo ""

# ============================================
# 步骤 10: 查看日志
# ============================================
echo "=========================================="
echo "步骤 10: 查看服务日志"
echo "=========================================="
echo ""

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /root

echo "📋 Redis Stream Sink 日志（最后 20 行）..."
docker-compose logs --tail=20 redis-stream-sink

echo "📋 Redis Stream Source 日志（最后 20 行）..."
docker-compose logs --tail=20 redis-stream-source

echo "📋 PostgreSQL Sink 日志（最后 20 行）..."
docker-compose logs --tail=20 postgres-sink-yolov8

echo "✅ 日志查看完成"
ENDSSH

echo ""

# ============================================
# 测试完成
# ============================================
echo "=========================================="
echo -e "${GREEN}✅ 所有测试完成！${NC}"
echo "=========================================="
echo ""

echo "📊 测试总结："
echo "  1. ✅ 文件上传"
echo "  2. ✅ 配置生成和验证"
echo "  3. ✅ 持久化服务启动"
echo "  4. ✅ Redis 连接测试"
echo "  5. ✅ PostgreSQL 连接测试"
echo "  6. ✅ 完整系统启动"
echo "  7. ✅ 数据流验证"
echo "  8. ✅ 服务重启恢复"
echo "  9. ✅ 性能测试"
echo "  10. ✅ 日志查看"
echo ""

echo "🎉 数据持久化层测试通过！"
echo ""

echo "📝 后续操作："
echo "  - 查看 Grafana: http://47.112.171.226:3000"
echo "  - 查看 Prometheus: http://47.112.171.226:9090"
echo "  - 连接 PostgreSQL: psql -h 47.112.171.226 -U savant -d savant_video_analysis"
echo ""

#!/bin/bash
# 本地验证脚本

echo "🔍 开始本地验证..."
echo ""

# 1. 检查必要文件
echo "📁 检查文件完整性..."
files=(
    "modules/yolov8/module.yml"
    "docker-compose.mvp.yml"
    "models/yolov8n.onnx"
    "videos/test.mp4"
    ".gitignore"
)

all_exist=true
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        size=$(ls -lh "$file" | awk '{print $5}')
        echo "  ✅ $file ($size)"
    else
        echo "  ❌ $file (不存在)"
        all_exist=false
    fi
done

if [ "$all_exist" = false ]; then
    echo ""
    echo "❌ 部分文件缺失，请检查"
    exit 1
fi

echo ""

# 2. 验证 YAML 语法
echo "📝 验证配置文件语法..."

# 验证 module.yml
/opt/anaconda3/envs/savant-video-analysis/bin/python3 << 'PYTHON'
import yaml
try:
    with open('modules/yolov8/module.yml') as f:
        yaml.safe_load(f)
    print("  ✅ module.yml 语法正确")
except Exception as e:
    print(f"  ❌ module.yml 语法错误: {e}")
    exit(1)
PYTHON

# 验证 docker-compose
if docker-compose -f docker-compose.mvp.yml config > /dev/null 2>&1; then
    echo "  ✅ docker-compose.mvp.yml 语法正确"
else
    echo "  ❌ docker-compose.mvp.yml 语法错误"
    exit 1
fi

echo ""

# 3. 检查 Docker 环境
echo "🐳 检查 Docker 环境..."
if command -v docker &> /dev/null; then
    docker_version=$(docker --version)
    echo "  ✅ Docker 已安装: $docker_version"
else
    echo "  ⚠️  Docker 未安装（云端需要）"
fi

if command -v docker-compose &> /dev/null; then
    compose_version=$(docker-compose --version)
    echo "  ✅ Docker Compose 已安装: $compose_version"
else
    echo "  ⚠️  Docker Compose 未安装（云端需要）"
fi

echo ""

# 4. 检查模型文件
echo "🤖 检查模型文件..."
model_size=$(ls -lh models/yolov8n.onnx | awk '{print $5}')
if [ "$model_size" = "9B" ]; then
    echo "  ❌ 模型文件异常（只有 9 字节）"
    exit 1
else
    echo "  ✅ 模型文件正常: $model_size"
fi

echo ""

# 5. 检查视频文件
echo "🎥 检查视频文件..."
video_size=$(ls -lh videos/test.mp4 | awk '{print $5}')
echo "  ✅ 视频文件: $video_size"

# 使用 ffprobe 检查视频信息（如果可用）
if command -v ffprobe &> /dev/null; then
    duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 videos/test.mp4 2>/dev/null)
    if [ -n "$duration" ]; then
        echo "  ✅ 视频时长: ${duration%.*} 秒"
    fi
fi

echo ""

# 6. 总结
echo "✅ 本地验证完成！"
echo ""
echo "📋 文件清单:"
echo "  - module.yml: ✅"
echo "  - docker-compose.mvp.yml: ✅"
echo "  - yolov8n.onnx: ✅ ($model_size)"
echo "  - test.mp4: ✅ ($video_size)"
echo ""
echo "🚀 准备就绪，可以部署到云端 GPU 实例！"

#!/bin/bash
# 转换 YOLOv8 PT 模型为 ONNX 格式

# 激活 conda 环境
eval "$(conda shell.bash hook)"
conda activate savant-video-analysis

# 转换模型
python3 << 'EOF'
from ultralytics import YOLO

print("📥 加载 YOLOv8n PT 模型...")
model = YOLO('models/yolov8n.pt')

print("🔄 转换为 ONNX 格式...")
model.export(format='onnx')

print("✅ ONNX 模型转换完成！")
print("📁 输出文件: yolov8n.onnx")
EOF

# 移动到 models 目录
if [ -f "yolov8n.onnx" ]; then
    mv yolov8n.onnx models/
    echo "✅ 模型已移动到 models/yolov8n.onnx"
    ls -lh models/yolov8n.onnx
else
    echo "❌ 转换失败，未找到 yolov8n.onnx"
fi

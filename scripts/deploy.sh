#!/bin/bash
#
# Savant 视频分析系统 - 一键部署脚本
#
# 功能：
# - 环境检查
# - 配置验证
# - 服务部署
# - 健康检查
#

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目配置
PROJECT_NAME="ai_video_analysis"
COMPOSE_FILE="docker-compose.phase3.yml"
PYTHON_ENV="savant-video-analysis"

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装"
        return 1
    fi
    print_success "$1 已安装"
    return 0
}

# 环境检查
check_environment() {
    print_header "1. 环境检查"

    local all_ok=true

    # 检查 Docker
    if check_command docker; then
        docker --version
    else
        all_ok=false
    fi

    # 检查 Docker Compose
    if check_command docker-compose; then
        docker-compose --version
    else
        all_ok=false
    fi

    # 检查 NVIDIA Docker Runtime（如果是 GPU 服务器）
    if command -v nvidia-smi &> /dev/null; then
        print_info "检测到 NVIDIA GPU"
        nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

        # 检查 nvidia-docker
        if docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
            print_success "NVIDIA Docker Runtime 正常"
        else
            print_warning "NVIDIA Docker Runtime 可能未正确配置"
        fi
    else
        print_warning "未检测到 NVIDIA GPU（本地开发环境正常）"
    fi

    # 检查 Python 环境
    if command -v conda &> /dev/null; then
        if conda env list | grep -q "$PYTHON_ENV"; then
            print_success "Python 环境 $PYTHON_ENV 存在"
        else
            print_warning "Python 环境 $PYTHON_ENV 不存在（配置验证需要）"
        fi
    fi

    if [ "$all_ok" = false ]; then
        print_error "环境检查失败，请安装缺失的依赖"
        exit 1
    fi

    print_success "环境检查通过"
}

# 配置验证
validate_config() {
    print_header "2. 配置验证"

    # 检查必需文件
    local required_files=(
        "$COMPOSE_FILE"
        "config/router_config.json"
        "config/router_handler.py"
        "modules/yolov8/module.yml"
        "modules/peoplenet/module.yml"
    )

    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            print_error "缺少必需文件: $file"
            exit 1
        fi
    done

    print_success "必需文件检查通过"

    # 运行配置验证工具（如果存在）
    if [ -f "scripts/validate_config.py" ]; then
        print_info "运行配置验证工具..."
        if command -v conda &> /dev/null && conda env list | grep -q "$PYTHON_ENV"; then
            conda run -n $PYTHON_ENV python scripts/validate_config.py || {
                print_error "配置验证失败"
                exit 1
            }
        else
            print_warning "跳过配置验证工具（Python 环境不可用）"
        fi
    fi

    print_success "配置验证通过"
}

# 部署服务
deploy_services() {
    print_header "3. 部署服务"

    print_info "停止现有服务..."
    docker-compose -f $COMPOSE_FILE down || true

    print_info "拉取最新镜像..."
    docker-compose -f $COMPOSE_FILE pull

    print_info "启动服务..."
    docker-compose -f $COMPOSE_FILE up -d

    print_success "服务启动完成"
}

# 健康检查
health_check() {
    print_header "4. 健康检查"

    print_info "等待服务启动（30 秒）..."
    sleep 30

    # 检查容器状态
    print_info "检查容器状态..."
    docker-compose -f $COMPOSE_FILE ps

    # 检查关键服务健康状态
    local services=("yolov8-module" "peoplenet-module")
    for service in "${services[@]}"; do
        local container_name="${PROJECT_NAME}_${service}_1"
        local health_status=$(docker inspect --format='{{.State.Health.Status}}' $container_name 2>/dev/null || echo "no-healthcheck")

        if [ "$health_status" = "healthy" ]; then
            print_success "$service 健康检查通过"
        elif [ "$health_status" = "no-healthcheck" ]; then
            print_warning "$service 未配置健康检查"
        else
            print_warning "$service 健康状态: $health_status"
        fi
    done

    # 检查 Prometheus 指标
    print_info "检查 Prometheus 指标..."
    if curl -s http://localhost:8000/metrics | head -5 > /dev/null 2>&1; then
        print_success "YOLOv8 指标端点正常"
    else
        print_warning "YOLOv8 指标端点不可访问"
    fi

    if curl -s http://localhost:8001/metrics | head -5 > /dev/null 2>&1; then
        print_success "PeopleNet 指标端点正常"
    else
        print_warning "PeopleNet 指标端点不可访问"
    fi

    # 检查 Grafana
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        print_success "Grafana 服务正常"
    else
        print_warning "Grafana 服务不可访问"
    fi

    print_success "健康检查完成"
}

# 显示访问信息
show_access_info() {
    print_header "5. 访问信息"

    echo "📊 监控服务："
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana:    http://localhost:3000 (admin/admin)"
    echo ""
    echo "📈 指标端点："
    echo "  - YOLOv8:     http://localhost:8000/metrics"
    echo "  - PeopleNet:  http://localhost:8001/metrics"
    echo ""
    echo "📝 查看日志："
    echo "  docker-compose -f $COMPOSE_FILE logs -f [service_name]"
    echo ""
    echo "🔍 查看状态："
    echo "  docker-compose -f $COMPOSE_FILE ps"
    echo ""
    echo "🛑 停止服务："
    echo "  docker-compose -f $COMPOSE_FILE down"
    echo ""
}

# 主函数
main() {
    print_header "Savant 视频分析系统 - 一键部署"

    # 检查是否在项目根目录
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "请在项目根目录运行此脚本"
        exit 1
    fi

    # 执行部署流程
    check_environment
    validate_config
    deploy_services
    health_check
    show_access_info

    print_success "🎉 部署完成！"
}

# 运行主函数
main

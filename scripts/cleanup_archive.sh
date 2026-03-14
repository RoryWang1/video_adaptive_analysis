#!/bin/bash
#
# 消息归档清理脚本
#
# 功能：
# - 清理指定天数之前的归档文件
# - 可以按 source_id 清理
# - 支持 dry-run 模式
#

set -e

# 默认配置
ARCHIVE_DIR="${ARCHIVE_DIR:-./data/message_archive}"
DAYS_TO_KEEP="${DAYS_TO_KEEP:-7}"
SOURCE_ID="${SOURCE_ID:-}"
DRY_RUN="${DRY_RUN:-false}"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 显示使用说明
show_usage() {
    cat << EOF
使用方法: $0 [选项]

选项:
  -d, --dir DIR           归档目录 (默认: ./data/message_archive)
  -k, --keep DAYS         保留最近 N 天的文件 (默认: 7)
  -s, --source SOURCE_ID  只清理指定 source_id 的文件
  -n, --dry-run           Dry-run 模式，只显示将要删除的文件
  -h, --help              显示此帮助信息

示例:
  # 清理 7 天前的所有归档
  $0

  # 清理 3 天前的归档
  $0 --keep 3

  # 只清理 video1 的归档
  $0 --source video1

  # Dry-run 模式
  $0 --dry-run

环境变量:
  ARCHIVE_DIR    归档目录
  DAYS_TO_KEEP   保留天数
  SOURCE_ID      源 ID
  DRY_RUN        Dry-run 模式 (true/false)
EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dir)
            ARCHIVE_DIR="$2"
            shift 2
            ;;
        -k|--keep)
            DAYS_TO_KEEP="$2"
            shift 2
            ;;
        -s|--source)
            SOURCE_ID="$2"
            shift 2
            ;;
        -n|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "未知选项: $1"
            show_usage
            exit 1
            ;;
    esac
done

# 检查归档目录
if [ ! -d "$ARCHIVE_DIR" ]; then
    print_error "归档目录不存在: $ARCHIVE_DIR"
    exit 1
fi

print_info "归档清理配置:"
echo "  - 归档目录: $ARCHIVE_DIR"
echo "  - 保留天数: $DAYS_TO_KEEP"
echo "  - Source ID: ${SOURCE_ID:-所有}"
echo "  - Dry-run: $DRY_RUN"
echo ""

# 构建查找路径
if [ -n "$SOURCE_ID" ]; then
    SEARCH_PATH="$ARCHIVE_DIR/$SOURCE_ID"
else
    SEARCH_PATH="$ARCHIVE_DIR"
fi

# 查找要删除的文件
print_info "查找 $DAYS_TO_KEEP 天前的文件..."

if [ "$DRY_RUN" = true ]; then
    print_warning "Dry-run 模式 - 不会实际删除文件"
    echo ""
fi

# 统计信息
total_files=0
total_size=0

# 查找并处理文件
while IFS= read -r -d '' file; do
    total_files=$((total_files + 1))
    file_size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo 0)
    total_size=$((total_size + file_size))

    if [ "$DRY_RUN" = true ]; then
        echo "  将删除: $file ($(numfmt --to=iec-i --suffix=B $file_size 2>/dev/null || echo "${file_size}B"))"
    else
        rm -f "$file"
    fi
done < <(find "$SEARCH_PATH" -name "*.msg" -type f -mtime +$DAYS_TO_KEEP -print0 2>/dev/null)

# 显示统计信息
echo ""
if [ $total_files -eq 0 ]; then
    print_success "没有需要清理的文件"
else
    total_size_human=$(numfmt --to=iec-i --suffix=B $total_size 2>/dev/null || echo "${total_size}B")

    if [ "$DRY_RUN" = true ]; then
        print_warning "将删除 $total_files 个文件，释放 $total_size_human 空间"
    else
        print_success "已删除 $total_files 个文件，释放 $total_size_human 空间"
    fi
fi

# 清理空目录
if [ "$DRY_RUN" = false ]; then
    find "$ARCHIVE_DIR" -type d -empty -delete 2>/dev/null || true
fi

print_success "清理完成"

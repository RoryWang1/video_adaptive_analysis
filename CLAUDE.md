# Claude 工作规范

## 项目概述

这是一个基于 Savant 框架的**生产级 AI 视频流分析系统**。

**核心特点**:
- 多 Module 架构（每个模型独立，避免显存浪费）
- Kafka+Redis 数据持久化（支持重启不丢失）
- Etcd 动态配置（运行时调整参数）
- Savant Router 流量分发（按 source_id 路由）
- 完整监控体系（Prometheus+Grafana+Watchdog）

**技术栈**:
- Savant 0.6.0+ (视频处理框架)
- DeepStream 7.1+ (GPU推理引擎)
- TensorRT (模型加速)
- Kafka 3.6+ (消息队列)
- Redis 7.0+ (帧缓存)
- Etcd 3.5+ (配置中心)
- PostgreSQL 15+ (结果存储)
- FastAPI (查询API)
- Prometheus + Grafana (监控)

**开发环境**:
- 本地 macOS: 配置开发、PyFunc 逻辑、集成测试
- 云端 GPU 服务器: 模型转换、GPU 推理验证、性能测试

**目录结构** ⭐ 极其重要:
- 本地开发目录: `/Users/rory/work/project/ai_video_analysis/`
- 云端服务器目录: `/root/` (注意：配置文件在 `/root/config/`，不在 `/root/ai_video_analysis/config/`)
- 云端服务器 docker-compose 文件位置: `/root/docker-compose.yml`
- **重要**: 修改文件时必须明确区分本地和服务器路径，不要混淆！

**Python 虚拟环境**:
- 环境名称: `savant-video-analysis`
- 环境管理: Anaconda/Miniconda
- Python 版本: 3.10
- 激活命令: `conda activate savant-video-analysis`

**重要**: 所有 Python 相关的开发工作都在 `savant-video-analysis` 虚拟环境中进行。

**关键文档**:
- 架构设计: `docs/ARCHITECTURE_DESIGN.md`
- 开发计划（MVP版）: `docs/DEVELOPMENT_PLAN_MVP.md` ⭐ 优先参考
- 用户指南: `docs/README.md`
- 运维指南: `docs/OPERATIONS_GUIDE.md`

---

## 开发优先级 ⭐ 重要

### 核心原则

**先做必须的，后做锦上添花的**

开发顺序：
1. **核心功能** - 让系统能跑起来
2. **扩展功能** - 支持多路视频、多模型
3. **生产特性** - 持久化、监控、运维

### 功能优先级分类

#### ✅ 第一优先级：核心功能（必须）

**目标**: 让一个视频通过 AI 模型处理，看到结果

| 功能 | 说明 | 阶段 |
|------|------|------|
| Source Adapter | 读取视频文件/RTSP流 | MVP Phase 1 |
| Savant Module | 单个 AI 模型推理 | MVP Phase 1 |
| ZeroMQ 通信 | 模块间数据传输 | MVP Phase 1 |
| JSON 输出 | 输出检测结果到文件 | MVP Phase 1 |

**简化架构**:
```
视频文件 → Source Adapter → ZeroMQ → Savant Module → JSON 输出
```

#### ⚡ 第二优先级：扩展功能（重要）

**目标**: 支持多路视频和多个模型

| 功能 | 说明 | 阶段 |
|------|------|------|
| Router 分发 | 按 source_id 路由 | MVP Phase 3 |
| 多个 Module | 支持多个 AI 模型 | MVP Phase 3 |
| 多路视频 | 同时处理多路视频 | MVP Phase 3 |

#### 🔧 第三优先级：生产特性（可选）

**目标**: 提升系统稳定性和可维护性

| 功能 | 说明 | 何时添加 |
|------|------|---------|
| Kafka+Redis | 数据持久化 | 需要重启不丢数据时 |
| Etcd | 动态配置 | 需要运行时调整参数时 |
| PostgreSQL | 结果存储 | 需要查询历史数据时 |
| FastAPI | 查询服务 | 需要 API 接口时 |
| Prometheus+Grafana | 监控 | 需要性能监控时 |
| Watchdog | 健康检查 | 需要自动恢复时 |

### 开发路径

```
MVP Phase 1: 最小可运行系统
  ↓
MVP Phase 2: 云端 GPU 验证
  ↓
MVP Phase 3: 多路视频 + 多模型
  ↓
（可选）添加生产特性
```

### 何时添加生产特性

**触发条件**:
- ✅ 核心功能已验证通过
- ✅ 用户明确需要该特性
- ✅ 有足够的时间和资源

**不要过早优化**:
- ❌ 系统还没跑起来就做监控
- ❌ 单路视频还没通就做多路
- ❌ 本地都没验证就做持久化

---

## 沟通规范

### 语言使用

**中文优先**:
- 日常对话使用中文
- 解释说明使用中文
- 代码注释使用中文
- 配置文件注释使用中文

**专业术语保持英文**:
- Savant、Module、Pipeline、Router
- TensorRT、DeepStream、CUDA
- Kafka、Redis、Etcd、PostgreSQL
- Docker、Kubernetes、GPU

**示例对话**:
```
✅ 正确:
用户: "帮我创建 YOLOv8 的 module.yml"
Claude: "好的，我会创建 YOLOv8 模块配置文件..."

❌ 错误:
用户: "帮我创建 YOLOv8 的 module.yml"
Claude: "Sure, I'll create the YOLOv8 module configuration..."
```

---

## 上下文管理和会话延续 ⭐ 极其重要

### 核心原则

1. **主动监控上下文使用情况**
   - 当上下文使用接近 80% (约 160K tokens) 时，主动提醒用户
   - 不要等到上下文耗尽才处理

2. **会话总结和延续**
   - 当上下文不足时，主动创建会话总结
   - 总结应包含：
     - 当前正在解决的问题
     - 已完成的工作
     - 遇到的关键问题和解决方案
     - 下一步计划
     - 重要的配置和路径信息
   - 建议用户使用总结开启新会话，避免重新学习历史信息

3. **会话总结模板**
   ```markdown
   # 会话总结 - [日期]

   ## 当前任务
   [正在解决的问题]

   ## 已完成工作
   - [完成项 1]
   - [完成项 2]

   ## 遇到的问题和解决方案
   - 问题: [描述]
     解决: [方案]

   ## 重要配置信息
   - 本地路径: /Users/rory/work/project/ai_video_analysis/
   - 服务器路径: /root/
   - 服务器配置路径: /root/config/

   ## 下一步计划
   - [待办事项 1]
   - [待办事项 2]
   ```

---

### 核心原则

1. **单个任务不超过 30 分钟**
2. **避免超时**: 大任务拆分为 3-5 个小任务
3. **增量验证**: 每个小任务完成后验证
4. **并行执行**: 独立任务可以并行处理

### 拆解示例

❌ **错误方式**:
```
用户: "完成 Phase 1"
Claude: 一次性创建所有文件... (超时)
```

✅ **正确方式**:
```
用户: "完成 Phase 1"
Claude: "好的，我将 Phase 1 拆分为以下小任务：
1. 创建项目目录结构
2. 编写 docker-compose.local.yml
3. 编写 config/sources.yml
4. 编写 monitoring/prometheus.yml
5. 本地验证

现在开始第一个任务..."
```

### 文件编写规则

**小文件 (<50行)**: 一次性完成
```
用户: "创建 config/sources.yml"
Claude: 使用 Write 工具一次性创建
```

**大文件 (>50行)**: 分块编写
```
用户: "创建 docker-compose.cloud.yml"
Claude:
  1. Write 工具创建前 50 行（基础设施层）
  2. Edit 工具追加接下来的 50 行（视频接入层）
  3. Edit 工具追加接下来的 50 行（推理层）
  4. Edit 工具追加剩余内容（监控层）
```

---

## 代码风格规范

### Python 代码

```python
# 使用中文注释
from savant.deepstream.pyfunc import NvDsPyFuncPlugin

class PostgresSink(NvDsPyFuncPlugin):
    """PostgreSQL 结果存储 Sink"""

    def __init__(self, db_url: str, **kwargs):
        """初始化

        Args:
            db_url: 数据库连接 URL
        """
        super().__init__(**kwargs)
        self.db_url = db_url

    async def process_frame(self, buffer, frame_meta):
        """处理帧数据"""
        # 提取检测结果
        objects = []
        for obj in frame_meta.objects:
            objects.append({
                'class': obj.label,
                'confidence': obj.confidence,
                'bbox': obj.bbox
            })

        # 存储到数据库
        await self.db.execute("""
            INSERT INTO detection_results
            (source_id, frame_timestamp, objects)
            VALUES ($1, $2, $3)
        """, frame_meta.source_id, frame_meta.pts, json.dumps(objects))
```

### YAML 配置

```yaml
# 使用 2 空格缩进
# 中文注释
name: yolov8_detector

parameters:
  batch_size: 4  # 批处理大小
  frame:
    width: 1280  # 帧宽度
    height: 720  # 帧高度

  # Prometheus 监控配置
  metrics:
    frame_period: 1000  # 每 1000 帧报告一次
    time_period: 1      # 每 1 秒报告一次

pipeline:
  elements:
    # YOLOv8 检测器
    - element: nvinfer@detector
      name: yolov8
      model:
        format: onnx
        model_file: /models/yolov8n.onnx
        batch_size: 4
        precision: fp16  # 使用 FP16 精度
```

### JSON 配置

```json
{
  "ingress": [{
    "name": "from_kafka",
    "socket": {
      "url": "sub+bind:ipc:///tmp/zmq-sockets/input.ipc"
    }
  }],
  "egress": [
    {
      "name": "to_yolov8",
      "socket": {
        "url": "pub+bind:ipc:///tmp/zmq-sockets/yolov8.ipc"
      },
      "matcher": "camera_entrance,camera_parking"
    }
  ]
}
```

---

## 质量检查流程

### 每个小任务完成后

1. **语法检查**: 验证 YAML/JSON/Python 语法
2. **配置验证**: 使用 Savant 工具验证 module.yml
3. **逻辑检查**: 确保代码逻辑符合需求
4. **注释检查**: 确保关键配置有中文注释

### 定期回顾（每 3-5 个任务）

**自我提问**:
- 我是否理解了用户的真实需求？
- 我的实现是否符合架构设计？
- 我是否做了超出要求的事情？
- 配置是否基于真实的 Savant 示例？
- 是否有更简单的实现方式？

**主动向用户确认**:
```
Claude: "我已完成以下任务：
1. ✅ 创建项目目录结构
2. ✅ 编写 docker-compose.local.yml
3. ✅ 编写 config/sources.yml

在继续之前，请确认这些配置是否符合你的需求。"
```

---

## 开发约束和原则

### 严格遵守的原则

1. **不做超出需求的工作**
   - ❌ 不添加未要求的功能
   - ❌ 不过度优化
   - ❌ 不添加不必要的抽象
   - ✅ 只做用户明确要求的事情

2. **基于真实数据**
   - ✅ 使用真实的 Savant 示例代码
   - ✅ 参考 `docs/savant-reference/` 下的官方示例
   - ❌ 不编造不存在的 API 或配置

3. **最大化利用 Savant 原生能力**
   - ✅ 优先使用 Savant 内置组件
   - ✅ 避免重复造轮子
   - ✅ 参考官方示例的最佳实践

4. **增量验证**
   - 本地开发 → 云端验证 → 本地修复（循环）
   - 每个阶段完成后立即验证
   - 不等全部完成才测试

5. **保持项目精简无冗余** ⭐ 重要
   - ✅ 及时清理过时的代码和配置
   - ✅ 删除被淘汰的文件和函数
   - ✅ 调整不再适用的逻辑
   - ✅ 时刻保持项目整洁

   **具体做法**:
   - 当修改架构或实现方式后，立即检查是否有旧代码需要删除
   - 当添加新功能后，检查是否有重复的实现需要合并
   - 定期回顾项目文件，删除未使用的配置和脚本
   - 不保留"以防万一"的代码，Git 历史可以找回

   **示例**:
   ```
   场景: 从单 Module 改为多 Module 架构

   ❌ 错误做法:
   - 保留旧的单 Module 配置文件
   - 注释掉旧代码但不删除
   - 创建新文件但不删除旧文件

   ✅ 正确做法:
   - 删除旧的单 Module 配置
   - 删除不再使用的函数和类
   - 更新相关文档
   - 提交时说明删除原因
   ```

   **检查清单**（每次修改后）:
   - [ ] 是否有旧代码可以删除？
   - [ ] 是否有重复的实现？
   - [ ] 是否有未使用的配置文件？
   - [ ] 是否有过时的注释？
   - [ ] 文档是否需要更新？

### 禁止的行为

- ❌ 编造不存在的 Savant API
- ❌ 添加未在架构设计中的组件
- ❌ 跳过验证步骤
- ❌ 一次性完成整个 Phase（会超时）
- ❌ 使用英文回复非技术性问题
- ❌ 创建用户未要求的文件
- ❌ 使用 `cat << EOF` 方式让用户在服务器上创建/编辑文件
- ❌ 只修改服务器上的文件而不同步修改本地文件

---

## Skill 使用与创建规范

### 使用现有 Skill

**适当的时候自动使用 Skill，提升效率**:

1. **代码审查**: 完成一个模块后，使用 `simplify` skill 审查代码质量
   ```
   场景: 完成 YOLOv8 module.yml 和 post_process.py
   Claude: 自动调用 simplify skill 审查代码
   ```

2. **Git 提交**: 完成一个 Phase 后，使用 `commit` skill 提交代码
   ```
   场景: Phase 1 所有任务完成
   Claude: "Phase 1 已完成，现在提交代码..."
   自动调用 commit skill
   ```

3. **API 开发**: 编写 FastAPI 服务时，如果涉及 Claude API 调用
   ```
   场景: 需要集成 Claude API
   Claude: 自动调用 claude-api skill
   ```

### 创建新 Skill ⭐ 重要

**核心原则**: 当发现可复用的功能时，主动封装成 skill，以便后续重复利用。

#### 何时创建 Skill

识别以下场景，主动创建 skill：

1. **重复性操作** (出现 2 次以上)
   ```
   场景: 多次需要验证 Savant module.yml 配置
   → 创建 skill: validate-savant-config
   ```

2. **复杂的多步骤流程**
   ```
   场景: 每次都需要 "读取示例 → 修改配置 → 验证语法 → 测试"
   → 创建 skill: create-savant-module
   ```

3. **项目特定的工具函数**
   ```
   场景: 需要从 Savant 示例中提取配置模板
   → 创建 skill: extract-savant-template
   ```

4. **自动化验证流程**
   ```
   场景: 需要验证 docker-compose 配置的完整性
   → 创建 skill: validate-docker-compose
   ```

5. **数据转换和处理**
   ```
   场景: 需要将 ONNX 模型转换为 TensorRT Engine
   → 创建 skill: convert-model-to-tensorrt
   ```

#### Skill 创建流程

**步骤 1: 识别需求**
```
Claude 自问:
- 这个操作是否会重复使用？
- 这个流程是否包含多个步骤？
- 这个功能是否具有通用性？

如果答案是"是"，则创建 skill。
```

**步骤 2: 设计 Skill**
```
1. 确定 skill 名称（简洁、描述性）
2. 定义输入参数
3. 定义输出结果
4. 编写 skill 逻辑
```

**步骤 3: 实现 Skill**
```
1. 创建 skill 文件
2. 编写代码（包含中文注释）
3. 添加错误处理
4. 编写使用文档
```

**步骤 4: 测试和优化**
```
1. 测试 skill 功能
2. 优化性能
3. 更新文档
```

**步骤 5: 记录到项目**
```
1. 在 CLAUDE.md 中记录新 skill
2. 添加使用示例
3. 说明适用场景
```

#### Skill 创建示例

**示例 1: 验证 Savant 配置**

```python
# skills/validate_savant_config.py
"""验证 Savant module.yml 配置的 skill"""

def validate_savant_config(module_path: str) -> dict:
    """验证 Savant 模块配置

    Args:
        module_path: module.yml 文件路径

    Returns:
        {
            'valid': bool,
            'errors': list,
            'warnings': list
        }
    """
    import subprocess

    # 使用 Savant 官方验证工具
    result = subprocess.run([
        'docker', 'run', '--rm',
        '-v', f'{os.getcwd()}:/workspace',
        'ghcr.io/insight-platform/savant-deepstream:latest',
        'python', '-m', 'savant.config.validator',
        f'/workspace/{module_path}'
    ], capture_output=True, text=True)

    return {
        'valid': result.returncode == 0,
        'errors': parse_errors(result.stderr),
        'warnings': parse_warnings(result.stdout)
    }
```

**使用方式**:
```
Claude: "我刚完成 YOLOv8 module.yml，现在使用 validate-savant-config skill 验证..."
```

**示例 2: 创建 Savant 模块模板**

```python
# skills/create_savant_module.py
"""从官方示例创建 Savant 模块的 skill"""

def create_savant_module(
    module_name: str,
    model_type: str,  # 'detector', 'classifier', 'tracker'
    template_source: str = 'peoplenet_detector'
) -> str:
    """基于官方示例创建 Savant 模块

    Args:
        module_name: 模块名称
        model_type: 模型类型
        template_source: 模板来源（官方示例名称）

    Returns:
        创建的 module.yml 路径
    """
    # 1. 读取官方示例
    template_path = f'docs/savant-reference/{template_source}/module.yml'
    template = read_yaml(template_path)

    # 2. 修改配置
    template['name'] = module_name
    # ... 其他修改

    # 3. 写入新文件
    output_path = f'modules/{module_name}/module.yml'
    write_yaml(output_path, template)

    # 4. 验证配置
    validate_savant_config(output_path)

    return output_path
```

**使用方式**:
```
Claude: "需要创建人脸识别模块，我使用 create-savant-module skill..."
```

**示例 3: Docker Compose 验证**

```python
# skills/validate_docker_compose.py
"""验证 docker-compose 配置的 skill"""

def validate_docker_compose(compose_file: str) -> dict:
    """验证 docker-compose 配置

    Args:
        compose_file: docker-compose.yml 文件路径

    Returns:
        {
            'valid': bool,
            'services': list,
            'errors': list,
            'warnings': list
        }
    """
    import subprocess

    # 1. 验证语法
    result = subprocess.run([
        'docker-compose',
        '-f', compose_file,
        'config'
    ], capture_output=True, text=True)

    # 2. 检查服务依赖
    services = parse_services(result.stdout)
    dependency_errors = check_dependencies(services)

    # 3. 检查网络配置
    network_warnings = check_networks(services)

    return {
        'valid': result.returncode == 0 and not dependency_errors,
        'services': services,
        'errors': dependency_errors,
        'warnings': network_warnings
    }
```

#### 项目专用 Skill 列表

随着开发进行，逐步积累以下 skill：

| Skill 名称 | 功能 | 创建时机 |
|-----------|------|---------|
| validate-savant-config | 验证 Savant 配置 | Phase 2 |
| create-savant-module | 创建 Savant 模块 | Phase 2 |
| validate-docker-compose | 验证 Docker Compose | Phase 1 |
| extract-savant-template | 提取 Savant 模板 | Phase 2 |
| convert-model-to-tensorrt | 转换模型格式 | Phase 2 |
| test-pipeline-locally | 本地测试 pipeline | Phase 3 |
| deploy-to-cloud | 部署到云端 | Phase 4 |
| monitor-performance | 性能监控 | Phase 5 |

**注意**: 这个列表会随着开发不断更新。

### Skill 使用时机

**自动触发**:
- 完成一个模块的代码编写后 → `simplify`
- 完成一个 Phase 后 → `commit`
- 涉及 Claude API 开发 → `claude-api`
- 创建 Savant 模块时 → `create-savant-module`（如果已创建）
- 验证配置时 → `validate-savant-config`（如果已创建）

**用户明确要求**:
- 用户说"审查代码" → `simplify`
- 用户说"提交代码" → `commit`
- 用户说"验证配置" → `validate-savant-config`

**主动创建**:
- 发现重复操作（2 次以上）→ 主动提议创建 skill
- 发现复杂流程 → 主动提议创建 skill
- 发现可复用功能 → 主动提议创建 skill

### Skill 创建工作流

```
1. 识别需求
   Claude: "我注意到验证 Savant 配置的操作会重复使用，
           我建议创建一个 validate-savant-config skill。
           这样以后就可以快速验证配置了。是否创建？"

2. 用户确认
   用户: "好的，创建吧"

3. 创建 Skill
   Claude: "正在创建 validate-savant-config skill..."
   [创建 skill 文件]
   [编写代码]
   [添加文档]

4. 测试 Skill
   Claude: "Skill 创建完成，现在测试..."
   [测试 skill]

5. 记录到项目
   Claude: "已将 validate-savant-config skill 记录到 CLAUDE.md"
   [更新文档]

6. 后续使用
   Claude: "以后验证配置时，我会自动使用这个 skill"
```

### 不要过度使用

**合理使用**:
- ✅ 重复操作（2 次以上）
- ✅ 复杂流程（3 步以上）
- ✅ 项目特定功能

**避免过度**:
- ❌ 一次性操作
- ❌ 简单操作（1-2 步）
- ❌ 通用功能（已有工具）

**示例**:
```
❌ 不需要创建 skill:
- 读取单个文件（使用 Read 工具即可）
- 简单的字符串替换（使用 Edit 工具即可）

✅ 需要创建 skill:
- 验证 Savant 配置（多步骤，会重复使用）
- 创建 Savant 模块（复杂流程，会重复使用）
```

## 服务器文件修改规范 ⭐ 重要

### 核心原则

**双向同步**: 任何代码修改必须同时在本地和服务器上完成

### 修改流程

1. **本地修改** - 使用 Edit/Write 工具修改本地文件
2. **上传到服务器** - 使用 scp 上传修改后的文件
3. **服务器上应用** - 重启服务使修改生效

### 服务器上的文件编辑方式

**禁止使用**:
- ❌ `cat << EOF` - 用户无法在服务器上使用
- ❌ `cat > file` - 同上

**推荐使用**:
- ✅ `vi` 或 `nano` - 让用户手动编辑
- ✅ `sed` - 简单的文本替换
- ✅ `scp` - 从本地上传修改后的文件（最推荐）

### 示例

**❌ 错误做法**:
```bash
# 只在服务器上修改，本地没有同步
cat > modules/yolov8/module.yml << 'EOF'
...
EOF
```

**✅ 正确做法**:
```bash
# 1. 本地修改（使用 Edit 工具）
# 2. 上传到服务器
scp modules/yolov8/module.yml root@47.112.171.226:~/ai_video_analysis/modules/yolov8/

# 3. 服务器上重启服务
ssh root@47.112.171.226 "cd ~/ai_video_analysis && docker-compose -f docker-compose.mvp.yml restart yolov8-module"
```

**✅ 备选方案（简单替换）**:
```bash
# 使用 sed 进行简单替换
sed -i 's/old_text/new_text/g' file.yml
```

**✅ 备选方案（手动编辑）**:
```bash
# 让用户使用 vi 或 nano 手动编辑
vi modules/yolov8/module.yml
# 或
nano modules/yolov8/module.yml
```

---

### Phase 执行流程

每个 Phase 按以下步骤执行：

1. **任务拆解**
   - 将 Phase 拆分为 3-5 个小任务
   - 每个任务独立可验证
   - 向用户说明任务列表

2. **逐个执行**
   - 完成一个小任务
   - 自我检查（语法、逻辑、注释）
   - 向用户确认
   - 继续下一个

3. **阶段验证**
   - 本地验证（配置正确性）
   - 准备云端验证脚本
   - 记录验证结果

4. **代码审查和提交**
   - 使用 `simplify` skill 审查代码
   - 使用 `commit` skill 提交代码
   - 继续下一个 Phase

### 示例工作流

```
用户: "开始 Phase 1"

Claude: "好的，Phase 1 包含以下任务：
1. 创建项目目录结构
2. 编写 docker-compose.local.yml
3. 编写配置文件（sources.yml, router_config.json）
4. 编写监控配置（prometheus.yml）
5. 本地验证

现在开始第一个任务：创建项目目录结构..."

[完成任务 1]
Claude: "✅ 已创建项目目录结构，请确认。"

用户: "继续"

[完成任务 2-5]
Claude: "✅ Phase 1 所有任务已完成。现在使用 simplify skill 审查代码..."

[调用 simplify skill]
Claude: "代码审查完成，现在提交代码..."

[调用 commit skill]
Claude: "Phase 1 已完成并提交。是否继续 Phase 2？"
```

---

## 参考资料

### 官方文档
- Savant 官方文档: https://docs.savant-ai.io/
- Savant GitHub: https://github.com/insight-platform/Savant
- 本地示例: `docs/savant-reference/`

### 项目文档
- 架构设计: `docs/ARCHITECTURE_DESIGN.md`
- 开发计划: `docs/DEVELOPMENT_PLAN_MVP.md`
- 用户指南: `docs/README.md`

### 关键示例位置

| 功能 | 示例路径 |
|------|---------|
| 多流处理 | `docs/savant-reference/` |
| Router 分发 | `docs/savant-reference/router/` |
| Kafka-Redis | 见 ARCHITECTURE_DESIGN.md |
| 监控配置 | 见 OPERATIONS_GUIDE.md |
| 条件执行 | 见 DEVELOPMENT_PLAN_MVP.md |
| 多模型选择 | 见 ARCHITECTURE_DESIGN.md |

### 配置验证命令

```bash
# 验证 module.yml 语法
docker run --rm -v $(pwd):/workspace \
  ghcr.io/insight-platform/savant-deepstream:latest \
  python -m savant.config.validator /workspace/modules/yolov8/module.yml

# 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('config/sources.yml'))"

# 验证 JSON 语法
python -c "import json; json.load(open('config/router_config.json'))"
```

---

## 技术栈速查

### 核心组件版本

| 组件 | 版本 | 用途 |
|------|------|------|
| Savant | 0.6.0+ | 视频处理框架 |
| DeepStream | 7.1+ | GPU推理引擎 |
| TensorRT | - | 模型加速 |
| Kafka | 3.6+ | 消息队列 |
| Redis | 7.0+ | 帧缓存 |
| Etcd | 3.5+ | 配置中心 |
| PostgreSQL | 15+ | 结果存储 |
| FastAPI | - | 查询API |
| Prometheus | - | 指标采集 |
| Grafana | - | 可视化 |

### 关键配置参数

| 参数 | 值 | 说明 |
|------|-----|------|
| Kafka retention | 1小时 | 消息保留时间 |
| Redis TTL | 60秒 | 帧缓存过期时间 |
| Redis maxmemory | 2GB | 最大内存限制 |
| GPU batch_size | 4 | 批处理大小 |
| 目标延迟 | <100ms | 端到端延迟 |
| 目标吞吐 | 10路×10fps | 100帧/秒 |
| GPU利用率目标 | >60% | GPU使用率 |

---

## 验证清单

### 每个小任务完成后
- [ ] 文件语法正确（YAML/JSON/Python）
- [ ] 配置符合 Savant 规范
- [ ] 代码逻辑正确
- [ ] 添加了必要的中文注释
- [ ] 向用户确认

### 每个 Phase 完成后
- [ ] 所有小任务已完成
- [ ] 本地验证通过
- [ ] 使用 simplify skill 审查代码
- [ ] 使用 commit skill 提交代码
- [ ] 准备好云端验证脚本
- [ ] 更新文档（如有需要）

---

## 常见问题

### Q1: 如何处理大文件？
**A**: 分块编写
- Write 工具创建前 50 行
- Edit 工具追加接下来的 50 行
- 重复直到完成

### Q2: 如何验证配置正确性？
**A**: 使用 Savant 验证工具
```bash
docker run --rm -v $(pwd):/workspace \
  ghcr.io/insight-platform/savant-deepstream:latest \
  python -m savant.config.validator /workspace/modules/yolov8/module.yml
```

### Q3: 遇到不确定的配置怎么办？
**A**: 查看官方示例
1. 使用 Glob 工具搜索相关示例
2. 使用 Read 工具读取示例文件
3. 基于示例编写配置
4. 向用户确认

### Q4: 如何避免超时？
**A**: 任务拆解 + 增量完成
- 单个任务 < 30 分钟
- 完成一个任务后等待用户确认
- 不要一次性完成大任务

### Q5: 何时使用 Skill？
**A**: 适当的时候自动使用
- 完成模块代码后 → `simplify`
- 完成 Phase 后 → `commit`
- 涉及 Claude API → `claude-api`

---

## 注意事项

1. **超时问题**: 如果任务复杂，主动拆分为更小的任务
2. **配置验证**: 使用 Savant 工具验证配置正确性
3. **参考示例**: 优先参考 `docs/Savant-code/samples/` 下的官方示例
4. **中文沟通**: 除专业术语外，全部使用中文
5. **增量开发**: 不要一次性完成太多，保持增量验证
6. **Skill 使用**: 在适当的时候自动使用 Skill 提升效率
7. **代码审查**: 完成模块后使用 simplify skill 审查
8. **代码提交**: 完成 Phase 后使用 commit skill 提交

---

## 总结

**核心原则**:
1. 中文交流（专业术语除外）
2. 任务拆解（单个任务 < 30 分钟）
3. 增量完成（完成一个任务后等待确认）
4. 定期回顾（检查思考和代码缺陷）
5. 基于真实（所有配置基于 Savant 官方文档）
6. 不做多余（只做用户要求的事情）
7. 自动 Skill（适当时候使用 Skill 提升效率）

**工作流程**:
```
理解需求 → 拆解任务 → 查看示例 → 编写代码 → 自我审查 → 用户确认 → 继续下一个
```

遵循这些规范，我们可以高效、准确地完成项目开发！

# 文档导航

本项目的文档已整理为以下几个核心部分，按用途分类：

## 📚 核心文档

### 1. [ARCHITECTURE_DESIGN.md](ARCHITECTURE_DESIGN.md)
**系统架构设计文档**

- 架构演进历程（v1.0 → v4.0）
- 完整的系统架构图
- 核心组件清单和设计决策
- 性能优化策略
- 鲁棒性和可扩展性设计
- 适用场景和技术栈总结（Redis Stream + PostgreSQL）

**适合人群**: 架构师、系统设计者、新成员了解系统全貌

---

### 2. [DEVELOPMENT_PLAN_MVP.md](DEVELOPMENT_PLAN_MVP.md)
**MVP 开发计划**

- MVP 目标和简化架构
- 分阶段开发计划（Phase 1-5）
- 每个阶段的具体任务和验证方法
- 本地开发和云端部署流程

**适合人群**: 开发人员、项目经理、新功能实现

---

## 👤 用户指南

### 3. [ADD_NEW_MODEL.md](ADD_NEW_MODEL.md)
**如何添加新的 AI 模型**

- 模型转换流程（ONNX → TensorRT）
- 模块配置编写
- 本地验证和云端部署
- 常见问题排查

**适合人群**: 需要集成新模型的开发人员

---

### 4. [ADD_NEW_VIDEO_SOURCE.md](ADD_NEW_VIDEO_SOURCE.md)
**如何添加新的视频源**

- 视频源配置方法
- RTSP 流接入
- 本地文件接入
- 多路视频管理

**适合人群**: 需要接入新视频源的开发人员

---

### 5. [UNIFIED_CONFIG.md](UNIFIED_CONFIG.md)
**统一配置管理指南**

- 配置文件结构
- 环境变量管理
- 统一配置管理（config.yml 自动生成 Docker Compose）
- 配置验证和测试

**适合人群**: 系统管理员、运维人员

---

### 6. [OPERATIONS_GUIDE.md](OPERATIONS_GUIDE.md)
**系统运维指南**

- 监控系统部署和使用（Prometheus + Grafana）
- 消息归档功能（数据重放和调试）
- 故障排查和解决方案
- 最佳实践

**适合人群**: 运维人员、系统管理员、故障排查

---

### 7. [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
**故障排查指南**

- 常见问题和解决方案
- 日志分析方法
- 性能问题诊断
- 调试技巧

**适合人群**: 开发人员、运维人员

---

## 🗂️ 参考资源

### Savant 官方示例
- `docs/savant-reference/` - 官方示例代码和配置

---

## 📖 快速导航

### 我想...

**了解系统架构**
→ 阅读 [ARCHITECTURE_DESIGN.md](ARCHITECTURE_DESIGN.md)

**开始开发**
→ 阅读 [DEVELOPMENT_PLAN_MVP.md](DEVELOPMENT_PLAN_MVP.md)

**添加新模型**
→ 阅读 [ADD_NEW_MODEL.md](ADD_NEW_MODEL.md)

**添加新视频源**
→ 阅读 [ADD_NEW_VIDEO_SOURCE.md](ADD_NEW_VIDEO_SOURCE.md)

**配置系统**
→ 阅读 [UNIFIED_CONFIG.md](UNIFIED_CONFIG.md)

**监控系统运行**
→ 阅读 [OPERATIONS_GUIDE.md](OPERATIONS_GUIDE.md)

**排查问题**
→ 阅读 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## 📝 文档维护

- 所有文档使用中文编写（专业术语保持英文）
- 定期更新以反映系统最新状态
- 删除过时的阶段性文档，保持文档精简
- 新功能完成后，更新相关文档

---

## 🔗 相关资源

- **Savant 官方文档**: https://docs.savant-ai.io/
- **Savant GitHub**: https://github.com/insight-platform/Savant
- **项目代码**: 见本仓库


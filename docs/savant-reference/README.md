# Savant 官方示例参考

本目录保留了关键的 Savant 官方示例，仅作为配置参考使用。

## 目录说明

### peoplenet_detector/
PeopleNet 人脸检测示例的配置文件
- `module.yml` - PeopleNet 模块配置（完整版，包含 remote 下载配置）
- `docker-compose.x86.yml` - x86 平台部署配置

### router/
Router 流量分发示例
- `src/router.py` - Router handler 实现示例
- `src/router_config.json` - Router 配置示例
- `docker-compose.yml` - Router 部署配置
- `README.md` - 使用说明

## 使用说明

这些文件仅供参考，不要直接修改。实际项目配置位于：
- 模块配置：`/modules/`
- Router 配置：`/config/`
- 部署配置：`/docker-compose.phase3.yml`

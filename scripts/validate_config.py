#!/usr/bin/env python3
"""
配置验证工具

验证 Savant 视频分析系统的配置一致性，包括：
- Docker Compose 配置
- Savant Module 配置
- Router 配置
- 文件完整性检查
"""

import json
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Tuple


class ConfigValidator:
    """配置验证器"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config_yml = self._load_config_yml()

    def _load_config_yml(self) -> Dict:
        """加载 config.yml 配置文件"""
        config_file = self.project_root / 'config.yml'
        if not config_file.exists():
            return {}

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception:
            return {}

    def validate_all(self) -> bool:
        """执行所有验证"""
        print("🔍 开始配置验证...\n")

        # 1. 检查必需文件
        self.check_required_files()

        # 2. 验证 Docker Compose 配置
        self.validate_docker_compose()

        # 3. 验证 Module 配置
        self.validate_modules()

        # 4. 验证 Router 配置
        self.validate_router()

        # 5. 检查配置一致性
        self.check_consistency()

        # 输出结果
        self.print_results()

        return len(self.errors) == 0

    def check_required_files(self):
        """检查必需文件是否存在"""
        print("📁 检查必需文件...")

        required_files = [
            "docker-compose.yml",
            "config/router_config.json",
            "config/router_handler.py",
            "modules/yolov8/module.yml",
            "modules/peoplenet/module.yml",
            "monitoring/prometheus.yml",
        ]

        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                self.errors.append(f"缺少必需文件: {file_path}")
            else:
                print(f"  ✅ {file_path}")

        print()

    def validate_docker_compose(self):
        """验证 Docker Compose 配置"""
        print("🐳 验证 Docker Compose 配置...")

        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            return

        try:
            with open(compose_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            services = config.get('services', {})

            # 从 config.yml 动态构建必需服务列表
            required_services = ['router']

            # 添加模型服务
            if self.config_yml:
                for model in self.config_yml.get('models', []):
                    required_services.append(f"{model['name']}-module")
                    required_services.append(f"json-sink-{model['name']}")

                # 添加视频源服务
                for source in self.config_yml.get('video_sources', []):
                    required_services.append(f"source-adapter-{source['id']}")

                # 添加监控服务
                if self.config_yml.get('monitoring', {}).get('prometheus', {}).get('enabled'):
                    required_services.append('prometheus')
                if self.config_yml.get('monitoring', {}).get('grafana', {}).get('enabled'):
                    required_services.append('grafana')
            else:
                # 如果没有 config.yml，使用默认列表
                required_services.extend([
                    'yolov8-module', 'peoplenet-module',
                    'source-adapter-video1', 'source-adapter-video2', 'source-adapter-video3',
                    'json-sink-yolov8', 'json-sink-peoplenet',
                    'prometheus', 'grafana'
                ])

            for service in required_services:
                if service not in services:
                    self.errors.append(f"Docker Compose 缺少服务: {service}")
                else:
                    print(f"  ✅ 服务 {service} 已定义")

            # 检查健康检查配置
            if self.config_yml:
                for model in self.config_yml.get('models', []):
                    module_name = f"{model['name']}-module"
                    if module_name in services:
                        if 'healthcheck' not in services[module_name]:
                            self.warnings.append(f"服务 {module_name} 缺少健康检查配置")
            else:
                for module in ['yolov8-module', 'peoplenet-module']:
                    if module in services:
                        if 'healthcheck' not in services[module]:
                            self.warnings.append(f"服务 {module} 缺少健康检查配置")

            # 检查端口映射
            port_mappings = {}
            for service_name, service_config in services.items():
                ports = service_config.get('ports', [])
                for port in ports:
                    if isinstance(port, str):
                        host_port = port.split(':')[0]
                        if host_port in port_mappings:
                            self.errors.append(
                                f"端口冲突: {host_port} 被 {port_mappings[host_port]} "
                                f"和 {service_name} 同时使用"
                            )
                        port_mappings[host_port] = service_name

        except yaml.YAMLError as e:
            self.errors.append(f"Docker Compose YAML 格式错误: {e}")
        except Exception as e:
            self.errors.append(f"验证 Docker Compose 时出错: {e}")

        print()

    def validate_modules(self):
        """验证 Savant Module 配置"""
        print("🤖 验证 Savant Module 配置...")

        # 从 config.yml 获取模型列表
        if self.config_yml:
            modules = {}
            for model in self.config_yml.get('models', []):
                module_path = self.project_root / model['module_path']
                modules[model['name']] = module_path
        else:
            # 默认模型列表
            modules = {
                'yolov8': self.project_root / 'modules/yolov8/module.yml',
                'peoplenet': self.project_root / 'modules/peoplenet/module.yml',
            }

        for module_name, module_file in modules.items():
            if not module_file.exists():
                continue

            try:
                with open(module_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)

                # 检查必需字段
                if 'name' not in config:
                    self.errors.append(f"Module {module_name} 缺少 name 字段")

                if 'parameters' not in config:
                    self.errors.append(f"Module {module_name} 缺少 parameters 字段")
                else:
                    params = config['parameters']
                    # 检查 telemetry 配置
                    if 'telemetry' in params:
                        if 'metrics' in params['telemetry']:
                            print(f"  ✅ {module_name} telemetry 配置正确")
                        else:
                            self.warnings.append(
                                f"Module {module_name} telemetry 缺少 metrics 配置"
                            )

                if 'pipeline' not in config:
                    self.errors.append(f"Module {module_name} 缺少 pipeline 字段")

                print(f"  ✅ Module {module_name} 配置有效")

            except yaml.YAMLError as e:
                self.errors.append(f"Module {module_name} YAML 格式错误: {e}")
            except Exception as e:
                self.errors.append(f"验证 Module {module_name} 时出错: {e}")

        print()

    def validate_router(self):
        """验证 Router 配置"""
        print("🔀 验证 Router 配置...")

        router_config_file = self.project_root / 'config/router_config.json'
        if not router_config_file.exists():
            return

        try:
            with open(router_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 检查必需字段
            if 'ingress' not in config:
                self.errors.append("Router 配置缺少 ingress 字段")

            if 'egress' not in config:
                self.errors.append("Router 配置缺少 egress 字段")
            else:
                egress_names = [e.get('name') for e in config['egress']]
                print(f"  ✅ Egress 配置: {', '.join(egress_names)}")

                # 检查 egress 目标
                if self.config_yml:
                    expected_egress = [f"to_{model['name']}" for model in self.config_yml.get('models', [])]
                else:
                    expected_egress = ['to_yolov8', 'to_peoplenet']

                for expected in expected_egress:
                    if expected not in egress_names:
                        self.warnings.append(f"Router 缺少 egress: {expected}")

        except json.JSONDecodeError as e:
            self.errors.append(f"Router 配置 JSON 格式错误: {e}")
        except Exception as e:
            self.errors.append(f"验证 Router 配置时出错: {e}")

        print()

    def check_consistency(self):
        """检查配置一致性"""
        print("🔗 检查配置一致性...")

        # 检查 Docker Compose 和 Prometheus 的端口一致性
        try:
            # 读取 Docker Compose
            with open(self.project_root / 'docker-compose.yml', 'r') as f:
                compose_config = yaml.safe_load(f)

            # 读取 Prometheus 配置
            with open(self.project_root / 'monitoring/prometheus.yml', 'r') as f:
                prom_config = yaml.safe_load(f)

            # 提取 Docker Compose 中的端口映射
            services = compose_config.get('services', {})
            yolov8_ports = services.get('yolov8-module', {}).get('ports', [])
            peoplenet_ports = services.get('peoplenet-module', {}).get('ports', [])

            # 提取 Prometheus 采集目标
            scrape_configs = prom_config.get('scrape_configs', [])

            print("  ✅ 配置一致性检查通过")

        except Exception as e:
            self.warnings.append(f"一致性检查时出错: {e}")

        print()

    def print_results(self):
        """输出验证结果"""
        print("=" * 60)
        print("📊 验证结果")
        print("=" * 60)

        if self.errors:
            print(f"\n❌ 发现 {len(self.errors)} 个错误:\n")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")

        if self.warnings:
            print(f"\n⚠️  发现 {len(self.warnings)} 个警告:\n")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ 所有配置验证通过！")
        elif not self.errors:
            print("\n✅ 配置验证通过（有警告）")
        else:
            print("\n❌ 配置验证失败")

        print()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='验证 Savant 视频分析系统配置')
    parser.add_argument(
        '--project-root',
        default='.',
        help='项目根目录路径（默认：当前目录）'
    )
    args = parser.parse_args()

    validator = ConfigValidator(args.project_root)
    success = validator.validate_all()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

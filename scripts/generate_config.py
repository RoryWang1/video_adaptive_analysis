#!/usr/bin/env python3
"""
配置生成工具

从统一配置文件 config.yml 自动生成：
- docker-compose.phase3.yml
- config/router_config.json
- config/router_handler.py
- monitoring/prometheus.yml
"""

import json
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Any


class ConfigGenerator:
    """配置生成器"""

    def __init__(self, config_file: str = "config.yml"):
        self.config_file = Path(config_file)
        self.config = self.load_config()
        self.project_root = Path(".")

    def load_config(self) -> Dict:
        """加载配置文件"""
        if not self.config_file.exists():
            print(f"❌ 配置文件不存在: {self.config_file}")
            sys.exit(1)

        with open(self.config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def generate_all(self):
        """生成所有配置文件"""
        print("🔧 开始生成配置文件...\n")

        self.generate_docker_compose()
        self.generate_router_config()
        self.generate_router_handler()
        self.generate_prometheus_config()

        print("\n✅ 所有配置文件生成完成！")
        print("\n📝 生成的文件：")
        print("  - docker-compose.yml")
        print("  - config/router_config.json")
        print("  - config/router_handler.py")
        print("  - monitoring/prometheus.yml")

        # 提示持久化配置
        if self.config.get('persistence', {}).get('redis', {}).get('enabled'):
            print("\n💾 数据持久化已启用：")
            print("  - Redis Stream（数据流持久化）")
        if self.config.get('persistence', {}).get('postgres', {}).get('enabled'):
            print("  - PostgreSQL（结果持久化）")

    def generate_docker_compose(self):
        """生成 Docker Compose 配置"""
        print("📦 生成 Docker Compose 配置...")

        compose = {
            'version': '3.8',
            'services': {},
            'volumes': {
                'zmq_sockets': None,
                'prometheus_data': None,
                'grafana_data': None,
            }
        }

        # 添加持久化卷
        if self.config.get('persistence', {}).get('redis', {}).get('enabled'):
            compose['volumes']['redis_data'] = None

        if self.config.get('persistence', {}).get('postgres', {}).get('enabled'):
            compose['volumes']['postgres_data'] = None

        # 添加持久化服务
        if self.config.get('persistence', {}).get('redis', {}).get('enabled'):
            compose['services']['redis'] = self._create_redis_service()

        if self.config.get('persistence', {}).get('postgres', {}).get('enabled'):
            compose['services']['postgres'] = self._create_postgres_service()

        # 添加 Router
        compose['services']['router'] = self._create_router_service()

        # 添加模型服务
        for model in self.config['models']:
            service_name = f"{model['name']}-module"
            compose['services'][service_name] = self._create_model_service(model)

        # 添加视频源
        for source in self.config['video_sources']:
            service_name = f"source-adapter-{source['id']}"
            compose['services'][service_name] = self._create_source_service(source)

        # 添加 JSON Sink
        for model in self.config['models']:
            service_name = f"json-sink-{model['name']}"
            compose['services'][service_name] = self._create_json_sink_service(model)

        # 添加 Redis Stream Sink（如果启用）
        if self.config.get('persistence', {}).get('redis', {}).get('enabled'):
            compose['services']['redis-stream-sink'] = self._create_redis_stream_sink_service()

        # 添加 Redis Stream Source（如果启用）
        if self.config.get('persistence', {}).get('redis', {}).get('enabled'):
            compose['services']['redis-stream-source'] = self._create_redis_stream_source_service()

        # 添加 PostgreSQL Sink（如果启用）
        if self.config.get('persistence', {}).get('postgres', {}).get('enabled'):
            for model in self.config['models']:
                service_name = f"postgres-sink-{model['name']}"
                compose['services'][service_name] = self._create_postgres_sink_service(model)

        # 添加监控服务
        if self.config['monitoring']['prometheus']['enabled']:
            compose['services']['prometheus'] = self._create_prometheus_service()

        if self.config['monitoring']['grafana']['enabled']:
            compose['services']['grafana'] = self._create_grafana_service()

        # 写入文件
        output_file = self.project_root / 'docker-compose.yml'
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(compose, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        print(f"  ✅ 已生成: {output_file}")

    def _create_router_service(self) -> Dict:
        """创建 Router 服务配置"""
        defaults = self.config['resource_defaults']['router']
        return {
            'image': self.config['docker_images']['savant_router'],
            'restart': 'unless-stopped',
            'volumes': [
                './config/router_config.json:/opt/etc/configuration.json:ro',
                './config:/opt/python:ro',
                'zmq_sockets:/tmp/zmq-sockets'
            ],
            'deploy': {
                'resources': {
                    'limits': {'memory': defaults['memory_limit']},
                    'reservations': {'memory': defaults['memory_reservation']}
                }
            }
        }

    def _create_model_service(self, model: Dict) -> Dict:
        """创建模型服务配置"""
        service = {
            'image': self.config['docker_images']['savant_deepstream'],
            'privileged': True,
            'restart': 'unless-stopped',
            'runtime': 'nvidia',
            'volumes': [
                'zmq_sockets:/tmp/zmq-sockets',
                './modules:/opt/savant/modules',
                './models:/models'
            ],
            'command': model['module_path'],
            'ports': [f"{model['prometheus_port']}:{model['container_port']}"],
            'environment': [
                f"ZMQ_SRC_ENDPOINT=router+connect:ipc:///tmp/zmq-sockets/{model['zmq_socket']}",
                f"ZMQ_SINK_ENDPOINT=pub+bind:ipc:///tmp/zmq-sockets/output-{model['name']}.ipc",
                "METRICS_FRAME_PERIOD=1000"
            ],
            'depends_on': {
                'router': {'condition': 'service_started'}
            }
        }

        if model.get('healthcheck'):
            service['healthcheck'] = {
                'test': ["CMD", "curl", "-f", f"http://localhost:{model['container_port']}/status"],
                'interval': '5s',
                'timeout': '3s',
                'retries': 12,
                'start_period': '30s'
            }

        if model.get('gpu_required'):
            service['deploy'] = {
                'resources': {
                    'reservations': {
                        'devices': [{
                            'driver': 'nvidia',
                            'count': 1,
                            'capabilities': ['gpu']
                        }]
                    }
                }
            }

        return service

    def _create_source_service(self, source: Dict) -> Dict:
        """创建视频源服务配置"""
        defaults = self.config['resource_defaults']['source_adapter']

        service = {
            'image': self.config['docker_images']['savant_adapters_gstreamer'],
            'restart': 'unless-stopped',
            'volumes': [
                'zmq_sockets:/tmp/zmq-sockets'
            ],
            'environment': [
                f"LOCATION={source['location']}",
                "ZMQ_ENDPOINT=pub+connect:ipc:///tmp/zmq-sockets/input-video.ipc",
                f"SOURCE_ID={source['id']}",
                f"SYNC_OUTPUT={'True' if source.get('sync_output', True) else 'False'}"
            ],
            'depends_on': {
                'router': {'condition': 'service_started'}
            },
            'deploy': {
                'resources': {
                    'limits': {'memory': source.get('memory_limit', defaults['memory_limit'])},
                    'reservations': {'memory': defaults['memory_reservation']}
                }
            }
        }

        # 根据类型设置 entrypoint 和 volumes
        if source['type'] == 'file':
            service['volumes'].insert(0, './videos:/videos')
            service['volumes'].append('/tmp/video-downloads:/tmp/video-downloads')
            service['environment'].append('DOWNLOAD_PATH=/tmp/video-downloads')
            service['entrypoint'] = '/opt/savant/adapters/gst/sources/video_loop.sh'

        elif source['type'] == 'rtsp':
            service['entrypoint'] = '/opt/savant/adapters/gst/sources/rtsp.sh'
            if source.get('rtsp_transport'):
                service['environment'].append(f"RTSP_TRANSPORT={source['rtsp_transport']}")

        # 添加模型健康检查依赖
        route_to = source.get('route_to')
        if route_to:
            model_service = f"{route_to}-module"
            service['depends_on'][model_service] = {'condition': 'service_healthy'}

        return service

    def _create_json_sink_service(self, model: Dict) -> Dict:
        """创建 JSON Sink 服务配置"""
        defaults = self.config['resource_defaults']['json_sink']

        return {
            'image': self.config['docker_images']['savant_adapters_py'],
            'restart': 'unless-stopped',
            'volumes': [
                'zmq_sockets:/tmp/zmq-sockets',
                './output:/output'
            ],
            'environment': [
                f"ZMQ_ENDPOINT=sub+connect:ipc:///tmp/zmq-sockets/output-{model['name']}.ipc",
                f"FILENAME_PATTERN=/output/{model['name']}_%source_id_%src_filename.json"
            ],
            'command': 'python -m adapters.python.sinks.metadata_json',
            'depends_on': [f"{model['name']}-module"],
            'deploy': {
                'resources': {
                    'limits': {'memory': defaults['memory_limit']},
                    'reservations': {'memory': defaults['memory_reservation']}
                }
            }
        }

    def _create_prometheus_service(self) -> Dict:
        """创建 Prometheus 服务配置"""
        prom_config = self.config['monitoring']['prometheus']
        defaults = self.config['resource_defaults']['prometheus']

        return {
            'image': self.config['docker_images']['prometheus'],
            'restart': 'unless-stopped',
            'ports': [f"{prom_config['port']}:9090"],
            'volumes': [
                './monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro',
                'prometheus_data:/prometheus'
            ],
            'command': [
                '--config.file=/etc/prometheus/prometheus.yml',
                '--storage.tsdb.path=/prometheus',
                f"--storage.tsdb.retention.time={prom_config['retention']}",
                '--web.console.libraries=/usr/share/prometheus/console_libraries',
                '--web.console.templates=/usr/share/prometheus/consoles'
            ],
            'deploy': {
                'resources': {
                    'limits': {'memory': prom_config.get('memory_limit', defaults['memory_limit'])},
                    'reservations': {'memory': defaults['memory_reservation']}
                }
            }
        }

    def _create_redis_service(self) -> Dict:
        """创建 Redis 服务配置"""
        redis_config = self.config['persistence']['redis']
        defaults = self.config['resource_defaults']['redis']

        command_parts = [
            'redis-server',
        ]

        if redis_config.get('appendonly'):
            command_parts.append('--appendonly yes')
            command_parts.append(f"--appendfsync {redis_config.get('appendfsync', 'everysec')}")

        command_parts.append(f"--maxmemory {redis_config.get('memory_limit', '2gb')}")
        command_parts.append('--maxmemory-policy allkeys-lru')
        command_parts.append('--save 60 1000')

        return {
            'image': self.config['docker_images']['redis'],
            'restart': 'unless-stopped',
            'command': ' '.join(command_parts),
            'ports': [f"{redis_config['port']}:6379"],
            'volumes': ['redis_data:/data'],
            'deploy': {
                'resources': {
                    'limits': {'memory': defaults['memory_limit']},
                    'reservations': {'memory': defaults['memory_reservation']}
                }
            }
        }

    def _create_postgres_service(self) -> Dict:
        """创建 PostgreSQL 服务配置"""
        pg_config = self.config['persistence']['postgres']
        defaults = self.config['resource_defaults']['postgres']

        return {
            'image': self.config['docker_images']['postgres'],
            'restart': 'unless-stopped',
            'environment': [
                f"POSTGRES_DB={pg_config['database']}",
                f"POSTGRES_USER={pg_config['user']}",
                f"POSTGRES_PASSWORD={pg_config['password']}"
            ],
            'ports': [f"{pg_config['port']}:5432"],
            'volumes': [
                'postgres_data:/var/lib/postgresql/data',
                './database/init:/docker-entrypoint-initdb.d'
            ],
            'command': [
                'postgres',
                f"-c shared_buffers={pg_config.get('shared_buffers', '256MB')}",
                f"-c max_connections={pg_config.get('max_connections', 100)}",
                '-c work_mem=4MB'
            ],
            'deploy': {
                'resources': {
                    'limits': {'memory': defaults['memory_limit']},
                    'reservations': {'memory': defaults['memory_reservation']}
                }
            }
        }

    def _create_redis_stream_sink_service(self) -> Dict:
        """创建 Redis Stream Sink 服务配置"""
        redis_config = self.config['persistence']['redis']
        defaults = self.config['resource_defaults']['redis_stream_sink']

        return {
            'image': self.config['docker_images']['savant_adapters_py'],
            'restart': 'unless-stopped',
            'volumes': [
                'zmq_sockets:/tmp/zmq-sockets',
                './adapters:/opt/adapters'
            ],
            'environment': [
                'ZMQ_ENDPOINT=sub+connect:ipc:///tmp/zmq-sockets/input-video.ipc',
                f"REDIS_HOST={redis_config['host']}",
                f"REDIS_PORT={redis_config['port']}",
                f"REDIS_STREAM_KEY={redis_config['stream_key']}",
                f"REDIS_STREAM_MAXLEN={redis_config['maxlen']}"
            ],
            'command': 'python /opt/adapters/redis_stream_sink.py',
            'depends_on': ['redis'],
            'deploy': {
                'resources': {
                    'limits': {'memory': defaults['memory_limit']},
                    'reservations': {'memory': defaults['memory_reservation']}
                }
            }
        }

    def _create_redis_stream_source_service(self) -> Dict:
        """创建 Redis Stream Source 服务配置"""
        redis_config = self.config['persistence']['redis']
        defaults = self.config['resource_defaults']['redis_stream_source']

        return {
            'image': self.config['docker_images']['savant_adapters_py'],
            'restart': 'unless-stopped',
            'volumes': [
                'zmq_sockets:/tmp/zmq-sockets',
                './adapters:/opt/adapters'
            ],
            'environment': [
                'ZMQ_ENDPOINT=pub+connect:ipc:///tmp/zmq-sockets/input-video.ipc',
                f"REDIS_HOST={redis_config['host']}",
                f"REDIS_PORT={redis_config['port']}",
                f"REDIS_STREAM_KEY={redis_config['stream_key']}",
                f"REDIS_CONSUMER_GROUP={redis_config['consumer_group']}",
                'REDIS_CONSUMER_NAME=consumer1'
            ],
            'command': 'python /opt/adapters/redis_stream_source.py',
            'depends_on': ['redis', 'redis-stream-sink'],
            'deploy': {
                'resources': {
                    'limits': {'memory': defaults['memory_limit']},
                    'reservations': {'memory': defaults['memory_reservation']}
                }
            }
        }

    def _create_postgres_sink_service(self, model: Dict) -> Dict:
        """创建 PostgreSQL Sink 服务配置"""
        pg_config = self.config['persistence']['postgres']
        defaults = self.config['resource_defaults']['postgres_sink']

        db_url = f"postgresql://{pg_config['user']}:{pg_config['password']}@{pg_config['host']}:{pg_config['port']}/{pg_config['database']}"

        return {
            'image': self.config['docker_images']['savant_adapters_py'],
            'restart': 'unless-stopped',
            'volumes': [
                'zmq_sockets:/tmp/zmq-sockets',
                './adapters:/opt/adapters'
            ],
            'environment': [
                f"ZMQ_ENDPOINT=sub+connect:ipc:///tmp/zmq-sockets/output-{model['name']}.ipc",
                f"POSTGRES_HOST={pg_config['host']}",
                f"POSTGRES_PORT={pg_config['port']}",
                f"POSTGRES_DB={pg_config['database']}",
                f"POSTGRES_USER={pg_config['user']}",
                f"POSTGRES_PASSWORD={pg_config['password']}",
                'BATCH_SIZE=10'
            ],
            'command': 'python /opt/adapters/postgres_sink.py',
            'depends_on': ['postgres', f"{model['name']}-module"],
            'deploy': {
                'resources': {
                    'limits': {'memory': defaults['memory_limit']},
                    'reservations': {'memory': defaults['memory_reservation']}
                }
            }
        }

    def _create_grafana_service(self) -> Dict:
        """创建 Grafana 服务配置"""
        grafana_config = self.config['monitoring']['grafana']
        defaults = self.config['resource_defaults']['grafana']

        return {
            'image': self.config['docker_images']['grafana'],
            'restart': 'unless-stopped',
            'ports': [f"{grafana_config['port']}:3000"],
            'volumes': [
                'grafana_data:/var/lib/grafana',
                './monitoring/grafana-dashboard.json:/etc/grafana/provisioning/dashboards/savant.json:ro'
            ],
            'environment': [
                f"GF_SECURITY_ADMIN_PASSWORD={grafana_config['admin_password']}",
                'GF_USERS_ALLOW_SIGN_UP=false'
            ],
            'depends_on': ['prometheus'],
            'deploy': {
                'resources': {
                    'limits': {'memory': grafana_config.get('memory_limit', defaults['memory_limit'])},
                    'reservations': {'memory': defaults['memory_reservation']}
                }
            }
        }

    def generate_router_config(self):
        """生成 Router 配置"""
        print("🔀 生成 Router 配置...")

        router_config = {
            'ingress': [{
                'name': 'from_source',
                'socket': {
                    'url': 'sub+bind:ipc:///tmp/zmq-sockets/input-video.ipc'
                }
            }],
            'egress': [],
            'common': {
                'handler': {
                    'module': 'router_handler',
                    'class_name': 'SourceIdRouter'
                }
            }
        }

        # 为每个模型创建 egress
        for model in self.config['models']:
            router_config['egress'].append({
                'name': f"to_{model['name']}",
                'socket': {
                    'url': f"dealer+bind:ipc:///tmp/zmq-sockets/{model['zmq_socket']}"
                },
                'matcher': f"[{model['name']}]"
            })

        # 写入文件
        output_file = self.project_root / 'config/router_config.json'
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(router_config, f, indent=2)

        print(f"  ✅ 已生成: {output_file}")

    def generate_router_handler(self):
        """生成 Router Handler"""
        print("🐍 生成 Router Handler...")

        # 构建路由规则
        routing_rules = []
        for source in self.config['video_sources']:
            route_to = source.get('route_to')
            if route_to:
                routing_rules.append({
                    'source_id': source['id'],
                    'model': route_to
                })

        # 生成 Python 代码
        handler_code = '''"""Router Handler - 自动生成

此文件由 scripts/generate_config.py 自动生成
请勿手动编辑，修改 config.yml 后重新生成
"""

from savant_rs.primitives import Message


class SourceIdRouter:
    """基于 source_id 的路由器"""

    def __call__(self, message_id: int, ingress_name: str, topic: str, message: Message):
        """路由消息到对应的模型

        Args:
            message_id: 消息 ID
            ingress_name: 入口名称
            topic: 主题（通常是 source_id）
            message: 消息对象

        Returns:
            Message: 带有路由标签的消息
        """
        source_id = topic

        # 路由规则（自动生成）
'''

        # 添加路由规则
        for i, rule in enumerate(routing_rules):
            if i == 0:
                handler_code += f"        if source_id == '{rule['source_id']}':\n"
            else:
                handler_code += f"        elif source_id == '{rule['source_id']}':\n"
            handler_code += f"            message.labels = ['{rule['model']}']\n"

        # 添加默认规则
        handler_code += '''        else:
            # 默认不路由
            message.labels = []

        return message
'''

        # 写入文件
        output_file = self.project_root / 'config/router_handler.py'
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(handler_code)

        print(f"  ✅ 已生成: {output_file}")

    def generate_prometheus_config(self):
        """生成 Prometheus 配置"""
        print("📊 生成 Prometheus 配置...")

        prom_config = {
            'global': {
                'scrape_interval': '10s',
                'evaluation_interval': '10s',
                'scrape_timeout': '5s'
            },
            'scrape_configs': []
        }

        # 为每个模型添加采集目标
        for model in self.config['models']:
            prom_config['scrape_configs'].append({
                'job_name': f"{model['name']}-module",
                'static_configs': [{
                    'targets': [f"{model['name']}-module:{model['container_port']}"],
                    'labels': {
                        'module': model['name'],
                        'model': model['name']
                    }
                }]
            })

        # 添加 Prometheus 自身
        prom_config['scrape_configs'].append({
            'job_name': 'prometheus',
            'static_configs': [{
                'targets': ['localhost:9090']
            }]
        })

        # 写入文件
        output_file = self.project_root / 'monitoring/prometheus.yml'
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(prom_config, f, default_flow_style=False)

        print(f"  ✅ 已生成: {output_file}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='从统一配置文件生成 Docker Compose 和 Router 配置'
    )
    parser.add_argument(
        '--config',
        default='config.yml',
        help='配置文件路径（默认：config.yml）'
    )
    args = parser.parse_args()

    generator = ConfigGenerator(args.config)
    generator.generate_all()


if __name__ == '__main__':
    main()

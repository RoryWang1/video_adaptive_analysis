#!/usr/bin/env python3
"""
Redis Stream Source Adapter

从 Redis Stream 读取视频帧，发送到 Savant Router。
"""

import os
import sys
import base64
import json
import logging
import time
from typing import Iterator

import redis
from savant.api.builder import build_zmq_sink
from savant.utils.logging import get_logger

logger = get_logger(__name__)


class RedisStreamSource:
    """Redis Stream Source Adapter"""

    def __init__(
        self,
        zmq_endpoint: str,
        redis_host: str,
        redis_port: int,
        stream_key: str,
        consumer_group: str,
        consumer_name: str,
        block_ms: int = 1000,
    ):
        """初始化

        Args:
            zmq_endpoint: ZeroMQ 目标端点
            redis_host: Redis 主机
            redis_port: Redis 端口
            stream_key: Stream 键名
            consumer_group: 消费者组名
            consumer_name: 消费者名称
            block_ms: 阻塞等待时间（毫秒）
        """
        self.zmq_endpoint = zmq_endpoint
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.stream_key = stream_key
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.block_ms = block_ms

        # 连接 Redis
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=False,
            socket_keepalive=True,
            socket_connect_timeout=5,
        )

        # 创建消费者组
        self._create_consumer_group()

        logger.info(
            f"Redis Stream Source 初始化完成: "
            f"redis={redis_host}:{redis_port}, "
            f"stream={stream_key}, "
            f"group={consumer_group}, "
            f"consumer={consumer_name}"
        )

    def _create_consumer_group(self):
        """创建消费者组"""
        try:
            self.redis_client.xgroup_create(
                self.stream_key,
                self.consumer_group,
                id='0',
                mkstream=True
            )
            logger.info(f"创建消费者组: {self.consumer_group}")
        except redis.ResponseError as e:
            if 'BUSYGROUP' in str(e):
                logger.info(f"消费者组已存在: {self.consumer_group}")
            else:
                raise

    def run(self):
        """运行 Source"""
        logger.info(f"开始从 Redis Stream 读取数据，发送到 {self.zmq_endpoint}...")

        # 创建 ZeroMQ Sink
        sink = build_zmq_sink(self.zmq_endpoint)

        frame_count = 0
        error_count = 0
        last_log_time = time.time()

        try:
            while True:
                try:
                    # 从 Stream 读取消息
                    messages = self.redis_client.xreadgroup(
                        self.consumer_group,
                        self.consumer_name,
                        {self.stream_key: '>'},
                        count=1,
                        block=self.block_ms
                    )

                    if not messages:
                        continue

                    for stream, msgs in messages:
                        for msg_id, data in msgs:
                            try:
                                # 解析消息数据
                                source_id = data[b'source_id'].decode('utf-8')
                                frame_num = int(data[b'frame_num'])
                                pts = int(data[b'pts'])
                                width = int(data[b'width'])
                                height = int(data[b'height'])
                                fps = float(data.get(b'fps', b'30.0'))

                                # 构建 Savant 消息（仅元数据）
                                # 注意：帧数据通过 ZeroMQ 直接传输，不在 Redis 中
                                message = {
                                    'source_id': source_id,
                                    'frame_idx': frame_num,
                                    'pts': pts,
                                    'width': width,
                                    'height': height,
                                    'fps': fps,
                                }

                                # 发送到 ZeroMQ
                                sink.send(json.dumps(message).encode('utf-8'))

                                frame_count += 1

                                # 确认消息
                                self.redis_client.xack(
                                    self.stream_key,
                                    self.consumer_group,
                                    msg_id
                                )

                                # 定期输出日志
                                now = time.time()
                                if now - last_log_time >= 10:
                                    logger.info(
                                        f"已处理 {frame_count} 帧 "
                                        f"(source_id={source_id}, frame={frame_num})"
                                    )
                                    last_log_time = now

                            except Exception as e:
                                error_count += 1
                                logger.error(f"处理消息失败: {e}", exc_info=True)

                                # 消息处理失败，不确认，稍后重试
                                if error_count > 100:
                                    logger.error("错误次数过多，退出")
                                    return

                except redis.ConnectionError as e:
                    logger.error(f"Redis 连接失败: {e}")
                    time.sleep(5)  # 等待重连
                except Exception as e:
                    logger.error(f"读取消息失败: {e}", exc_info=True)
                    time.sleep(1)

        except KeyboardInterrupt:
            logger.info("收到中断信号，正在退出...")
        except Exception as e:
            logger.error(f"运行失败: {e}", exc_info=True)
        finally:
            logger.info(f"总共处理 {frame_count} 帧，错误 {error_count} 次")


def main():
    """主函数"""
    # 从环境变量读取配置
    zmq_endpoint = os.getenv('ZMQ_ENDPOINT', 'pub+connect:ipc:///tmp/zmq-sockets/input-video.ipc')
    redis_host = os.getenv('REDIS_HOST', 'redis')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    stream_key = os.getenv('REDIS_STREAM_KEY', 'savant:video_stream')
    consumer_group = os.getenv('REDIS_CONSUMER_GROUP', 'savant_group')
    consumer_name = os.getenv('REDIS_CONSUMER_NAME', 'consumer1')
    block_ms = int(os.getenv('REDIS_BLOCK_MS', '1000'))

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建并运行 Source
    source = RedisStreamSource(
        zmq_endpoint=zmq_endpoint,
        redis_host=redis_host,
        redis_port=redis_port,
        stream_key=stream_key,
        consumer_group=consumer_group,
        consumer_name=consumer_name,
        block_ms=block_ms,
    )

    source.run()


if __name__ == '__main__':
    main()

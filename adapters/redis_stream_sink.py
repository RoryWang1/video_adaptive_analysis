#!/usr/bin/env python3
"""
Redis Stream Sink Adapter

将 Savant 视频帧写入 Redis Stream，实现数据流持久化。
"""

import os
import sys
import json
import logging

import redis
from savant_rs.zmq import BlockingReader, ReaderConfig
from savant_rs.utils.serialization import load_message_from_bytes

logger = logging.getLogger(__name__)


class RedisStreamSink:
    """Redis Stream Sink Adapter"""

    def __init__(
        self,
        zmq_endpoint: str,
        redis_host: str,
        redis_port: int,
        stream_key: str,
        maxlen: int = 1000,
    ):
        """初始化

        Args:
            zmq_endpoint: ZeroMQ 源端点
            redis_host: Redis 主机
            redis_port: Redis 端口
            stream_key: Stream 键名
            maxlen: 队列最大长度
        """
        self.zmq_endpoint = zmq_endpoint
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.stream_key = stream_key
        self.maxlen = maxlen

        # 连接 Redis
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=False,  # 保持二进制数据
            socket_keepalive=True,
            socket_connect_timeout=5,
        )

        logger.info(
            f"Redis Stream Sink 初始化完成: "
            f"redis={redis_host}:{redis_port}, "
            f"stream={stream_key}, "
            f"maxlen={maxlen}"
        )

    def run(self):
        """运行 Sink"""
        logger.info(f"开始从 {self.zmq_endpoint} 接收数据...")

        # 创建 ZeroMQ Reader（使用 Builder）
        from savant_rs.zmq import ReaderConfigBuilder

        config = ReaderConfigBuilder(self.zmq_endpoint).build()
        reader = BlockingReader(config)
        reader.start()  # 启动 reader
        logger.info(f"已连接到 ZeroMQ: {self.zmq_endpoint}")

        frame_count = 0
        error_count = 0

        try:
            while True:
                try:
                    # 接收消息
                    result = reader.receive()

                    # 提取 Message 对象
                    if hasattr(result, 'message'):
                        message = result.message
                    else:
                        # 可能是超时或其他结果
                        continue

                    # message 已经是 Message 对象，不需要再解析
                    if message is None or not message.is_video_frame():
                        continue

                    frame = message.as_video_frame()

                    # 提取帧信息
                    source_id = frame.source_id

                    # 提取帧编号 - 尝试多个可能的属性
                    frame_idx = 0
                    if hasattr(frame, 'keyframe_id'):
                        frame_idx = frame.keyframe_id
                    elif hasattr(frame, 'idx'):
                        frame_idx = frame.idx
                    elif hasattr(frame, 'frame_num'):
                        frame_idx = frame.frame_num

                    pts = frame.pts if hasattr(frame, 'pts') else 0
                    frame_width = frame.width
                    frame_height = frame.height

                    # 写入 Redis Stream（仅元数据，不包含帧数据）
                    message_data = {
                        'source_id': source_id,
                        'frame_num': str(frame_idx),
                        'pts': str(pts),
                        'timestamp': str(pts / 1000000.0) if pts > 0 else '0',  # 转换为秒
                        'width': str(frame_width),
                        'height': str(frame_height),
                    }

                    # XADD 写入
                    msg_id = self.redis_client.xadd(
                        self.stream_key,
                        message_data,
                        maxlen=self.maxlen,
                        approximate=True,  # 使用近似裁剪，性能更好
                    )

                    frame_count += 1

                    if frame_count % 100 == 0:
                        logger.info(
                            f"已处理 {frame_count} 帧 "
                            f"(source_id={source_id}, frame={frame_idx})"
                        )

                except Exception as e:
                    error_count += 1
                    logger.error(f"处理消息失败: {e}", exc_info=True)

                    if error_count > 100:
                        logger.error("错误次数过多，退出")
                        break

        except KeyboardInterrupt:
            logger.info("收到中断信号，正在退出...")
        except Exception as e:
            logger.error(f"运行失败: {e}", exc_info=True)
        finally:
            logger.info(f"总共处理 {frame_count} 帧，错误 {error_count} 次")


def main():
    """主函数"""
    # 从环境变量读取配置
    zmq_endpoint = os.getenv('ZMQ_ENDPOINT', 'sub+connect:ipc:///tmp/zmq-sockets/input-video.ipc')
    redis_host = os.getenv('REDIS_HOST', 'redis')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    stream_key = os.getenv('REDIS_STREAM_KEY', 'savant:video_stream')
    maxlen = int(os.getenv('REDIS_STREAM_MAXLEN', '1000'))

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建并运行 Sink
    sink = RedisStreamSink(
        zmq_endpoint=zmq_endpoint,
        redis_host=redis_host,
        redis_port=redis_port,
        stream_key=stream_key,
        maxlen=maxlen,
    )

    sink.run()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
消息归档重放 Source

从归档文件读取完整的 Savant Message 并重放。
"""

import os
import sys
import glob
import logging
import time
from savant_rs.zmq import BlockingWriter, WriterConfigBuilder
from savant_rs.utils.serialization import load_message_from_bytes

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MessageArchiveSource:
    """消息归档重放 Source"""

    def __init__(
        self,
        zmq_endpoint: str,
        archive_dir: str,
        source_id: str = None,
        fps: float = None,
        loop: bool = False
    ):
        """
        Args:
            zmq_endpoint: ZeroMQ 目标端点
            archive_dir: 归档目录
            source_id: 可选，只重放指定 source_id 的消息
            fps: 可选，重放帧率（None 表示尽快发送）
            loop: 是否循环重放
        """
        self.zmq_endpoint = zmq_endpoint
        self.archive_dir = archive_dir
        self.source_id = source_id
        self.fps = fps
        self.loop = loop

        logger.info(f"消息归档 Source 初始化完成: archive_dir={archive_dir}")

    def get_message_files(self):
        """获取所有消息文件"""
        if self.source_id:
            pattern = os.path.join(self.archive_dir, self.source_id, "*.msg")
        else:
            pattern = os.path.join(self.archive_dir, "*", "*.msg")

        files = sorted(glob.glob(pattern))
        return files

    def run(self):
        """运行 Source"""
        config = WriterConfigBuilder(self.zmq_endpoint).build()
        writer = BlockingWriter(config)
        writer.start()

        logger.info(f"开始从 {self.archive_dir} 重放消息")

        # 查找所有消息文件
        files = self.get_message_files()

        if not files:
            logger.warning(f"未找到消息文件")
            return

        logger.info(f"找到 {len(files)} 条消息")

        frame_delay = 1.0 / self.fps if self.fps else 0

        try:
            while True:
                frame_count = 0
                error_count = 0

                for filepath in files:
                    try:
                        # 读取消息
                        with open(filepath, 'rb') as f:
                            message_bytes = f.read()

                        # 反序列化
                        message = load_message_from_bytes(message_bytes)

                        # 发送到 ZeroMQ
                        writer.send_message(message, None)

                        frame_count += 1

                        if frame_count % 100 == 0:
                            logger.info(f"已重放 {frame_count}/{len(files)} 条消息")

                        # 控制帧率
                        if frame_delay > 0:
                            time.sleep(frame_delay)

                    except Exception as e:
                        error_count += 1
                        logger.error(f"重放消息失败 ({filepath}): {e}")

                        if error_count > 100:
                            logger.error("错误次数过多，退出")
                            return

                logger.info(f"重放完成，共 {frame_count} 条消息，错误 {error_count} 次")

                if not self.loop:
                    break

                logger.info("循环重放...")

        except KeyboardInterrupt:
            logger.info(f"停止重放")


def main():
    """主函数"""
    source = MessageArchiveSource(
        zmq_endpoint=os.getenv('ZMQ_ENDPOINT', 'pub+bind:ipc:///tmp/zmq-sockets/replay.ipc'),
        archive_dir=os.getenv('ARCHIVE_DIR', '/data/message_archive'),
        source_id=os.getenv('SOURCE_ID', None),
        fps=float(os.getenv('FPS', 0)) or None,
        loop=os.getenv('LOOP', 'false').lower() == 'true'
    )

    source.run()


if __name__ == '__main__':
    main()

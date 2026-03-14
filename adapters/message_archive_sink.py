#!/usr/bin/env python3
"""
完整消息持久化 Sink

将完整的 Savant Message 序列化后存储，支持完整重放。
"""

import os
import sys
import logging
import time
from datetime import datetime
from savant_rs.zmq import BlockingReader, ReaderConfigBuilder
from savant_rs.utils.serialization import save_message_to_bytes

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MessageArchiveSink:
    """完整消息归档 Sink"""

    def __init__(
        self,
        zmq_endpoint: str,
        archive_dir: str,
        max_files_per_source: int = 1000
    ):
        """
        Args:
            zmq_endpoint: ZeroMQ 源端点
            archive_dir: 归档目录
            max_files_per_source: 每个 source 最多保留的文件数（自动清理旧文件）
        """
        self.zmq_endpoint = zmq_endpoint
        self.archive_dir = archive_dir
        self.max_files_per_source = max_files_per_source
        os.makedirs(archive_dir, exist_ok=True)

        logger.info(f"消息归档 Sink 初始化完成: archive_dir={archive_dir}")

    def cleanup_old_files(self, source_dir: str):
        """清理旧文件，保持文件数量在限制内"""
        try:
            files = []
            for f in os.listdir(source_dir):
                if f.endswith('.msg'):
                    filepath = os.path.join(source_dir, f)
                    files.append((filepath, os.path.getmtime(filepath)))

            # 按修改时间排序
            files.sort(key=lambda x: x[1])

            # 删除最旧的文件
            while len(files) > self.max_files_per_source:
                oldest_file = files.pop(0)[0]
                os.remove(oldest_file)
                logger.debug(f"删除旧归档文件: {oldest_file}")

        except Exception as e:
            logger.warning(f"清理旧文件失败: {e}")

    def run(self):
        """运行 Sink"""
        config = ReaderConfigBuilder(self.zmq_endpoint).build()
        reader = BlockingReader(config)
        reader.start()

        logger.info(f"开始从 {self.zmq_endpoint} 接收数据...")
        logger.info(f"已连接到 ZeroMQ: {self.zmq_endpoint}")

        frame_count = 0
        error_count = 0
        last_log_time = time.time()

        try:
            while True:
                try:
                    result = reader.receive()

                    if hasattr(result, 'message'):
                        message = result.message

                        # 序列化完整消息
                        message_bytes = save_message_to_bytes(message)

                        # 获取帧信息
                        frame = message.as_video_frame()
                        source_id = frame.source_id

                        # 创建 source 目录
                        source_dir = os.path.join(self.archive_dir, source_id)
                        os.makedirs(source_dir, exist_ok=True)

                        # 文件名：YYYYMMDD_HHMMSS_framecount.msg
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"{timestamp}_{frame_count:08d}.msg"
                        filepath = os.path.join(source_dir, filename)

                        # 保存消息
                        with open(filepath, 'wb') as f:
                            f.write(message_bytes)

                        frame_count += 1

                        # 定期清理旧文件
                        if frame_count % 100 == 0:
                            self.cleanup_old_files(source_dir)

                        # 定期输出日志
                        now = time.time()
                        if now - last_log_time >= 10:
                            logger.info(
                                f"已归档 {frame_count} 条消息 "
                                f"(source_id={source_id})"
                            )
                            last_log_time = now

                except Exception as e:
                    error_count += 1
                    logger.error(f"处理消息失败: {e}", exc_info=True)

                    if error_count > 100:
                        logger.error("错误次数过多，退出")
                        break

        except KeyboardInterrupt:
            logger.info(f"停止归档，共处理 {frame_count} 条消息")

        logger.info(f"归档完成，共 {frame_count} 条消息，错误 {error_count} 次")


def main():
    """主函数"""
    sink = MessageArchiveSink(
        zmq_endpoint=os.getenv('ZMQ_ENDPOINT', 'sub+connect:ipc:///tmp/zmq-sockets/output-yolov8.ipc'),
        archive_dir=os.getenv('ARCHIVE_DIR', '/data/message_archive'),
        max_files_per_source=int(os.getenv('MAX_FILES_PER_SOURCE', 1000))
    )

    sink.run()


if __name__ == '__main__':
    main()

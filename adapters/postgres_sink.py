#!/usr/bin/env python3
"""
PostgreSQL Sink Adapter

将 Savant 检测结果写入 PostgreSQL 数据库。
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any

import asyncpg
from savant.api.builder import build_zmq_source
from savant.api.parser import parse_zmq_message
from savant.utils.logging import get_logger

logger = get_logger(__name__)


class PostgresSink:
    """PostgreSQL Sink Adapter"""

    def __init__(
        self,
        zmq_endpoint: str,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        batch_size: int = 10,
    ):
        """初始化

        Args:
            zmq_endpoint: ZeroMQ 源端点
            db_host: 数据库主机
            db_port: 数据库端口
            db_name: 数据库名称
            db_user: 数据库用户
            db_password: 数据库密码
            batch_size: 批量插入大小
        """
        self.zmq_endpoint = zmq_endpoint
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.batch_size = batch_size

        self.pool = None
        self.batch = []

        logger.info(
            f"PostgreSQL Sink 初始化: "
            f"db={db_host}:{db_port}/{db_name}, "
            f"batch_size={batch_size}"
        )

    async def init_pool(self):
        """初始化数据库连接池"""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            logger.info("数据库连接池创建成功")
        except Exception as e:
            logger.error(f"创建数据库连接池失败: {e}")
            raise

    async def close_pool(self):
        """关闭数据库连接池"""
        if self.pool:
            await self.pool.close()
            logger.info("数据库连接池已关闭")

    async def insert_result(self, result: Dict[str, Any]):
        """插入检测结果（帧级别 + 对象级别）

        Args:
            result: 检测结果字典
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # 1. 获取 source_id 和 model_id
                source_db_id = await conn.fetchval(
                    "SELECT id FROM sources WHERE source_id = $1",
                    result['source_id']
                )
                model_db_id = await conn.fetchval(
                    "SELECT id FROM models WHERE model_name = $1",
                    result['model_name']
                )

                if not source_db_id or not model_db_id:
                    logger.warning(
                        f"Source or model not found: "
                        f"source_id={result['source_id']}, "
                        f"model_name={result['model_name']}"
                    )
                    return

                # 2. 插入帧检测记录
                frame_detection_id = await conn.fetchval(
                    """
                    INSERT INTO frame_detections
                    (source_id, model_id, frame_num, timestamp, fps, object_count, processing_time_ms)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (source_id, model_id, frame_num, timestamp) DO NOTHING
                    RETURNING id
                    """,
                    source_db_id,
                    model_db_id,
                    result['frame_num'],
                    result['timestamp'],
                    result.get('fps'),
                    len(result['objects']),
                    result.get('processing_time_ms'),
                )

                if not frame_detection_id:
                    # 记录已存在，跳过
                    return

                # 3. 批量插入检测对象
                if result['objects']:
                    await conn.executemany(
                        """
                        INSERT INTO detected_objects
                        (frame_detection_id, object_class, confidence, bbox_x, bbox_y, bbox_width, bbox_height, track_id, attributes)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                        [
                            (
                                frame_detection_id,
                                obj['class'],
                                obj['confidence'],
                                obj['bbox']['x'],
                                obj['bbox']['y'],
                                obj['bbox']['width'],
                                obj['bbox']['height'],
                                obj.get('track_id'),
                                json.dumps(obj.get('attributes')) if obj.get('attributes') else None,
                            )
                            for obj in result['objects']
                        ],
                    )

    async def insert_batch(self, results: List[Dict[str, Any]]):
        """批量插入检测结果

        Args:
            results: 检测结果列表
        """
        if not results:
            return

        for result in results:
            await self.insert_result(result)

        logger.info(f"批量插入 {len(results)} 条检测结果")

    def parse_detection_result(self, message) -> Dict[str, Any]:
        """解析检测结果

        Args:
            message: Savant 消息

        Returns:
            检测结果字典
        """
        # 解析消息
        parsed = parse_zmq_message(message)

        if parsed is None:
            return None

        # 提取基本信息
        source_id = parsed.source_id
        frame_num = parsed.idx
        timestamp = datetime.fromtimestamp(parsed.pts / 1000000.0)

        # 提取检测对象
        objects = []
        if hasattr(parsed, 'objects'):
            for obj in parsed.objects:
                objects.append({
                    'class': obj.label,
                    'confidence': obj.confidence,
                    'bbox': {
                        'x': obj.bbox.xc,
                        'y': obj.bbox.yc,
                        'width': obj.bbox.width,
                        'height': obj.bbox.height,
                    },
                    'track_id': getattr(obj, 'track_id', None),
                })

        # 提取模型名称（从元数据中）
        model_name = 'unknown'
        if hasattr(parsed, 'json'):
            try:
                metadata = json.loads(parsed.json())
                model_name = metadata.get('model_name', 'unknown')
            except:
                pass

        # 构建结果
        result = {
            'source_id': source_id,
            'model_name': model_name,
            'frame_num': frame_num,
            'timestamp': timestamp,
            'fps': getattr(parsed, 'fps', None),
            'objects': objects,
            'processing_time_ms': getattr(parsed, 'processing_time_ms', None),
        }

        return result

    async def run(self):
        """运行 Sink"""
        logger.info(f"开始从 {self.zmq_endpoint} 接收检测结果...")

        # 初始化数据库连接池
        await self.init_pool()

        # 创建 ZeroMQ 源
        source = build_zmq_source(self.zmq_endpoint)

        frame_count = 0
        error_count = 0

        try:
            for message in source:
                try:
                    # 解析检测结果
                    result = self.parse_detection_result(message)

                    if result is None:
                        continue

                    # 添加到批次
                    self.batch.append(result)

                    # 批量插入
                    if len(self.batch) >= self.batch_size:
                        await self.insert_batch(self.batch)
                        frame_count += len(self.batch)
                        self.batch = []

                        if frame_count % 100 == 0:
                            logger.info(f"已处理 {frame_count} 帧检测结果")

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
            # 插入剩余的批次
            if self.batch:
                await self.insert_batch(self.batch)
                frame_count += len(self.batch)

            await self.close_pool()
            logger.info(f"总共处理 {frame_count} 帧，错误 {error_count} 次")


def main():
    """主函数"""
    # 从环境变量读取配置
    zmq_endpoint = os.getenv('ZMQ_ENDPOINT', 'sub+connect:ipc:///tmp/zmq-sockets/output-yolov8.ipc')
    db_host = os.getenv('POSTGRES_HOST', 'postgres')
    db_port = int(os.getenv('POSTGRES_PORT', '5432'))
    db_name = os.getenv('POSTGRES_DB', 'savant_video_analysis')
    db_user = os.getenv('POSTGRES_USER', 'savant')
    db_password = os.getenv('POSTGRES_PASSWORD', 'savant_password')
    batch_size = int(os.getenv('BATCH_SIZE', '10'))

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建并运行 Sink
    sink = PostgresSink(
        zmq_endpoint=zmq_endpoint,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        batch_size=batch_size,
    )

    # 运行异步任务
    asyncio.run(sink.run())


if __name__ == '__main__':
    main()

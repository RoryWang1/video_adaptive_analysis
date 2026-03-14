#!/usr/bin/env python3
"""
PostgreSQL Sink Adapter

将 Savant 检测结果写入 PostgreSQL 数据库。
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Any

import psycopg2
import psycopg2.pool
from savant_rs.zmq import BlockingReader, ReaderConfig
from savant_rs.utils.serialization import load_message_from_bytes

logger = logging.getLogger(__name__)


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

    def init_pool(self):
        """初始化数据库连接池"""
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
            )
            logger.info("数据库连接池创建成功")
        except Exception as e:
            logger.error(f"创建数据库连接池失败: {e}")
            raise

    def close_pool(self):
        """关闭数据库连接池"""
        if self.pool:
            self.pool.closeall()
            logger.info("数据库连接池已关闭")

    def insert_result(self, result: Dict[str, Any]):
        """插入检测结果（帧级别 + 对象级别）

        Args:
            result: 检测结果字典
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # 1. 获取 source_id 和 model_id
                cur.execute(
                    "SELECT id FROM sources WHERE source_id = %s",
                    (result['source_id'],)
                )
                row = cur.fetchone()
                source_db_id = row[0] if row else None

                cur.execute(
                    "SELECT id FROM models WHERE model_name = %s",
                    (result['model_name'],)
                )
                row = cur.fetchone()
                model_db_id = row[0] if row else None

                if not source_db_id or not model_db_id:
                    logger.warning(
                        f"Source or model not found: "
                        f"source_id={result['source_id']}, "
                        f"model_name={result['model_name']}"
                    )
                    return

                # 2. 插入帧检测记录
                cur.execute(
                    """
                    INSERT INTO frame_detections
                    (source_id, model_id, frame_num, timestamp, fps, object_count, processing_time_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_id, model_id, frame_num, timestamp) DO NOTHING
                    RETURNING id
                    """,
                    (
                        source_db_id,
                        model_db_id,
                        result['frame_num'],
                        result['timestamp'],
                        result.get('fps'),
                        len(result['objects']),
                        result.get('processing_time_ms'),
                    )
                )

                row = cur.fetchone()
                if not row:
                    # 记录已存在，跳过
                    return

                frame_detection_id = row[0]

                # 3. 批量插入检测对象
                if result['objects']:
                    cur.executemany(
                        """
                        INSERT INTO detected_objects
                        (frame_detection_id, object_class, confidence, bbox_x, bbox_y, bbox_width, bbox_height, track_id, attributes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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

                conn.commit()

        except Exception as e:
            conn.rollback()
            logger.error(f"插入数据失败: {e}", exc_info=True)
            raise
        finally:
            self.pool.putconn(conn)

    def insert_batch(self, results: List[Dict[str, Any]]):
        """批量插入检测结果

        Args:
            results: 检测结果列表
        """
        if not results:
            return

        for result in results:
            self.insert_result(result)

        logger.info(f"批量插入 {len(results)} 条检测结果")

    def parse_detection_result(self, message) -> Dict[str, Any]:
        """解析检测结果

        Args:
            message: Savant Message 对象（不是字节）

        Returns:
            检测结果字典
        """
        try:
            # message 已经是 Message 对象，不需要再解析
            if message is None or not message.is_video_frame():
                return None

            frame = message.as_video_frame()

            # 提取基本信息
            source_id = frame.source_id

            # 提取帧编号 - 尝试多个可能的属性
            frame_num = 0
            if hasattr(frame, 'keyframe_id'):
                frame_num = frame.keyframe_id
            elif hasattr(frame, 'idx'):
                frame_num = frame.idx
            elif hasattr(frame, 'frame_num'):
                frame_num = frame.frame_num

            timestamp = datetime.fromtimestamp(frame.pts / 1000000.0) if hasattr(frame, 'pts') else datetime.now()

            # 提取检测对象 - 使用 get_all_objects() 或直接访问
            objects = []
            try:
                # 尝试不同的方法获取对象
                if hasattr(frame, 'get_all_objects'):
                    frame_objects = frame.get_all_objects()
                elif hasattr(frame, 'access_objects'):
                    # access_objects 需要一个查询对象，传入 None 获取所有对象
                    from savant_rs.primitives import VideoObjectsQuery
                    query = VideoObjectsQuery.any()
                    frame_objects = frame.access_objects(query)
                else:
                    frame_objects = []

                for obj in frame_objects:
                    bbox = obj.detection_box
                    objects.append({
                        'class': obj.label,
                        'confidence': obj.confidence if hasattr(obj, 'confidence') and obj.confidence else 0.0,
                        'bbox': {
                            'x': bbox.xc,
                            'y': bbox.yc,
                            'width': bbox.width,
                            'height': bbox.height,
                        },
                        'track_id': obj.track_id if hasattr(obj, 'track_id') else None,
                    })
            except Exception as e:
                logger.warning(f"无法提取对象: {e}")
                objects = []

            # 从环境变量获取模型名称
            model_name = os.getenv('MODEL_NAME', 'unknown')

            # 构建结果
            result = {
                'source_id': source_id,
                'model_name': model_name,
                'frame_num': frame_num,
                'timestamp': timestamp,
                'fps': None,  # Savant 0.6.0 中可能没有直接的 fps 字段
                'objects': objects,
                'processing_time_ms': None,
            }

            return result

        except Exception as e:
            logger.error(f"解析消息失败: {e}", exc_info=True)
            return None

    def run(self):
        """运行 Sink"""
        logger.info(f"开始从 {self.zmq_endpoint} 接收检测结果...")

        # 初始化数据库连接池
        self.init_pool()

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

                    # 解析检测结果（message 已经是 Message 对象）
                    result = self.parse_detection_result(message)

                    if result is None:
                        continue

                    # 添加到批次
                    self.batch.append(result)

                    # 批量插入
                    if len(self.batch) >= self.batch_size:
                        self.insert_batch(self.batch)
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
                self.insert_batch(self.batch)
                frame_count += len(self.batch)

            self.close_pool()
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

    sink.run()


if __name__ == '__main__':
    main()

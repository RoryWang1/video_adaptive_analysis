"""Router handler - 根据 source_id 设置路由 labels"""

from typing import Any
from savant_rs import register_handler
from savant_rs.logging import LogLevel, log
from savant_rs.utils.serialization import Message


class SourceIdRouter:
    """根据 source_id 设置路由 labels"""

    def __call__(self, message_id: int, ingress_name: str, topic: str, message: Message):
        """处理每个消息，根据 source_id 设置 labels"""

        # 获取 source_id
        source_id = topic  # topic 就是 source_id

        log(
            LogLevel.Debug,
            'source_id_router',
            f'Received message from source_id: {source_id}',
        )

        # 根据 source_id 设置 labels
        if source_id in ['video1', 'video2']:
            message.labels = ['yolov8']
            log(
                LogLevel.Info,
                'source_id_router',
                f'Routing {source_id} to yolov8',
            )
        elif source_id == 'video3':
            message.labels = ['peoplenet']
            log(
                LogLevel.Info,
                'source_id_router',
                f'Routing {source_id} to peoplenet',
            )
        else:
            log(
                LogLevel.Warning,
                'source_id_router',
                f'Unknown source_id: {source_id}, not routing',
            )

        return message


def init(params: Any):
    """初始化 router handler"""
    log(
        LogLevel.Info,
        'router::init',
        'Initializing source_id router',
    )
    register_handler('ingress_handler', SourceIdRouter())
    log(
        LogLevel.Info,
        'router::init',
        'Source_id router initialized successfully',
    )
    return True

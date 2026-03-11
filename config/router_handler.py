"""Router Handler - 自动生成

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
        if source_id == 'video1':
            message.labels = ['yolov8']
        elif source_id == 'video2':
            message.labels = ['yolov8']
        elif source_id == 'video3':
            message.labels = ['peoplenet']
        else:
            # 默认不路由
            message.labels = []

        return message

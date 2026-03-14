"""Router Handler - 路由处理器

基于 source_id 为消息添加标签，实现流量分发
"""

from savant_rs.utils.serialization import Message


def init(params):
    """初始化函数

    Args:
        params: 初始化参数（从配置文件传入）

    Returns:
        bool: 初始化是否成功
    """
    from savant_rs import register_handler

    # 注册 ingress_handler
    register_handler('ingress_handler', ingress_handler)

    return True


def ingress_handler(message_id: int, ingress_name: str, topic: str, message: Message):
    """入口处理器 - 基于 source_id 添加标签

    Args:
        message_id: 消息ID
        ingress_name: 入口名称
        topic: 主题（即 source_id）
        message: 消息对象

    Returns:
        处理后的消息对象
    """
    source_id = topic

    # 路由规则：根据 source_id 分配到不同的模型
    if source_id == 'video1':
        message.labels = ['yolov8']
    elif source_id == 'video2':
        message.labels = ['yolov8']
    elif source_id == 'video3':
        message.labels = ['peoplenet']
    else:
        # 默认不分配标签（不会被路由）
        message.labels = []

    return message

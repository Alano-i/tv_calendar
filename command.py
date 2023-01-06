from mbot.core.plugins import plugin, PluginCommandContext, PluginCommandResponse
from mbot.openapi import mbot_api
import logging

from .event import save_json
from .event import push_message
server = mbot_api
_LOGGER = logging.getLogger(__name__)


@plugin.command(name='echo', title='更新追剧日历数据', desc='订阅剧集越多，执行时间越长，请耐心等待', icon='CalendarMonthOutlined', run_in_background=True)
def echo(ctx: PluginCommandContext):
    """
    异步执行,更新追剧日历数据
    """
    try:
        save_json()
    except Exception as e:
        _LOGGER.error(e)
        return PluginCommandResponse(True, f'创建追剧日历数据源失败')
    return PluginCommandResponse(True, f'创建追剧日历数据源成功')

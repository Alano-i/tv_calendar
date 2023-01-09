#!/usr/bin/env python3
import datetime
import typing
import random
import time
from typing import Dict, Any

from moviebotapi.common import MenuItem
from moviebotapi.core.models import MediaType
from moviebotapi.subscribe import SubStatus, Subscribe

import json
import shutil
from mbot.openapi import mbot_api
from mbot.core.plugins import *

import logging
# import yaml
# import re

server = mbot_api
api_url = "/3/tv/%(tv_id)s/season/%(season_number)s"
tv_api_url = "/3/tv/%(tv_id)s"
param = {'language': 'zh-CN'}
_LOGGER = logging.getLogger(__name__)
message_to_uid: typing.List[int] = []


@plugin.after_setup
def after_setup(plugin_meta: PluginMeta, config: Dict[str, Any]):
    global set_pic_url
    global message_to_uid
    set_pic_url = config.get('set_pic_url')
    message_to_uid = config.get('uid')
    shutil.copy('/data/plugins/tv_calendar_Alano/frontend/tv_calendar.html', '/app/frontend/static')
    shutil.copy('/data/plugins/tv_calendar_Alano/frontend/episode.html', '/app/frontend/static')
    shutil.copy('/data/plugins/tv_calendar_Alano/frontend/ALIBABA-Font-Bold.otf', '/app/frontend/static')
    shutil.copy('/data/plugins/tv_calendar_Alano/frontend/bg.png', '/app/frontend/static')
    shutil.copy('/data/plugins/tv_calendar_Alano/frontend/title.png', '/app/frontend/static')
    _LOGGER.info(f'追剧日历插件: WEB 页素材已复制并覆盖到「/app/frontend/static」')
    """授权并添加菜单"""
    href = '/common/view?hidePadding=true#/static/tv_calendar.html'
    # 授权管理员和普通用户可访问
    server.auth.add_permission([1, 2], href)
    # 获取菜单，把追剧日历添加到"我的"菜单分组
    menus = server.common.list_menus()
    for item in menus:
        if item.title == '我的':
            test = MenuItem()
            test.title = '追剧日历'
            test.href = href
            test.icon = 'Today'
            item.pages.append(test)
            break
    server.common.save_menus(menus)


@plugin.config_changed
def config_changed(config: Dict[str, Any]):
    global set_pic_url
    global message_to_uid
    set_pic_url = config.get('set_pic_url')
    message_to_uid = config.get('uid')

@plugin.task('save_json', '剧集更新', cron_expression='10 0 * * *')
def task():
    # 怕并发太高，衣总服务器撑不住
    time.sleep(random.randint(1, 3600))
    save_json()


def get_tmdb_info(tv_id, season_number):
    result = ''
    for i in range(5):
        try:
            result = server.tmdb.request_api(api_url % {'tv_id': tv_id, 'season_number': season_number}, param)
            break
        except Exception as e:
            _LOGGER.error(f'「get_tmdb_info」 请求异常，原因：{e}')
            time.sleep(5)
            continue
    if result:
        _LOGGER.info(f'「get_tmdb_info」请求成功')
        return result
    else:
        _LOGGER.error('「get_tmdb_info」请求获取失败，可能还没有这个剧集的信息')
    return False

def get_tv_info(tv_id):
    result = ''
    for i in range(5):
        try:
            result = server.tmdb.request_api(tv_api_url % {'tv_id': tv_id}, param)
            break
        except Exception as e:
            _LOGGER.error(f'「get_tv_info」请求异常，原因：{e}')
            time.sleep(5)
            continue
    if result:
        _LOGGER.info(f'「get_tv_info」请求成功')
        return result
    else:
        _LOGGER.error('「get_tv_info」请求获取失败，可能还没有这个剧集的信息')
        return False

def find_season_poster(seasons, season_number):
    for season in seasons:
        if season_number == season['season_number']:
            return season['poster_path']
    return ''


def save_json():
    _LOGGER.info('开始执行剧集数据更新')
    list_ = server.subscribe.list(MediaType.TV, SubStatus.Subscribing)
    custom_list = server.subscribe.list_custom_sub()
    custom_list_filter = list(filter(lambda x: x.media_type == MediaType.TV and x.tmdb_id and x.enable, custom_list))
    for item in custom_list_filter:
        list_.append(Subscribe({'tmdb_id': item.tmdb_id, 'season_index': item.season_number}, mbot_api.subscribe))
    episode_arr = []
    for row in list_:
        tv = get_tv_info(row.tmdb_id)
        if not tv:
            continue
        tv_poster = tv['poster_path']
        seasons = tv['seasons']
        tv_name = tv['name']
        _LOGGER.info(f'开始处理「{tv_name}」')
        tv_original_name = tv['original_name']
        backdrop_path = tv['backdrop_path']
        season_poster = find_season_poster(seasons, row.season_number)
        season = get_tmdb_info(row.tmdb_id, row.season_number)
        if not season:
            continue
        episodes = season['episodes']
        for episode in episodes:
            episode['tv_name'] = tv_name
            episode['tv_original_name'] = tv_original_name
            episode['tv_poster'] = tv_poster
            episode['season_poster'] = season_poster
            episode['backdrop_path'] = backdrop_path
            episode_arr.append(episode)
    try:
        with open('/app/frontend/static/original.json', 'w', encoding='utf-8') as fp:
            json.dump(episode_arr, fp, ensure_ascii=False)
        _LOGGER.info('开始写入新的追剧日历数据到「original.json」文件')
    except Exception as e:
            _LOGGER.error(f'写入新「original.json」文件出错，原因: {e}')
            pass
    _LOGGER.info('剧集数据更新结束')
    push_message()
    _LOGGER.info('追剧日历数据更新进程全部完成')

def get_after_day(day, n):
    offset = datetime.timedelta(days=n)
    # 获取想要的日期的时间
    after_day = day + offset
    return after_day

# def get_server_url():
#     try:
#         yml_file = "/data/conf/base_config.yml"
#         with open(yml_file, encoding='utf-8') as f:
#             yml_data = yaml.load(f, Loader=yaml.FullLoader)
#         mr_url = yml_data['web']['server_url']
#         if mr_url is None or mr_url == '':
#           return ''
#         if (re.match('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', mr_url) is not None):
#             _LOGGER.info(f'从配置文件中获取到的「mr_url」{mr_url}')
#             return mr_url
#     except Exception as e:
#         _LOGGER.error(f'获取「mr_url」异常，原因: {e}')
#         pass
#     return '' 

def push_message():
    _LOGGER.info('开始推送今日将要更新的剧集信息')
    msg_title = ''
    pic_url = ''
    # mr_url = get_server_url()
    # if mr_url:
    #     link_url = f'{mr_url}/static/tv_calendar.html'
    try:
        with open('/app/frontend/static/original.json', encoding='utf-8') as f:
            episode_arr = json.load(f)
        episode_filter = list(
            filter(lambda x: x['air_date'] == datetime.date.today().strftime('%Y-%m-%d'), episode_arr))
        name_dict = {}
        for item in episode_filter:
            if item['tv_name'] not in name_dict:
                name_dict[item['tv_name']] = [item]
            else:
                name_dict[item['tv_name']].append(item)
        img_api = 'https://api.r10086.com/img-api.php?type=%E5%8A%A8%E6%BC%AB%E7%BB%BC%E5%90%88' + str(
            random.randint(1, 18))
        
        if set_pic_url:
            pic_url = set_pic_url
            _LOGGER.info(f'已设置消息封面图片地址: {pic_url}')
        else:
            pic_url = img_api
            _LOGGER.info(f'未设置消息封面图片地址，封面图片将展示为随机二次元图片')
        if len(episode_arr) == 0:
            message = "今日没有剧集更新"
        else:
            message_arr = []
            tv_count = len(name_dict)
            if tv_count:
                msg_title = f'今天将更新 {int(tv_count):02d} 部剧集'
            else:
                msg_title = "今日没有剧集更新"
            for tv_name in name_dict:
                episodes = name_dict[tv_name]
                episode_number_arr = []
                for episode in episodes:
                    episode_number_arr.append(str(episode['episode_number']))
                episode_numbers = ','.join([f"{int(episode):02d}" for episode in episode_number_arr])
                message_arr.append(f"{tv_name} - 第 {episodes[0]['season_number']:02d} 季·第 {episode_numbers} 集")
            message = "\n".join(message_arr)
    except Exception as e:
        _LOGGER.error(f'处理异常，原因: {e}')
        pass

    server_url = mbot_api.config.web.server_url
    if server_url:
        link_url = f"{server_url.rstrip('/')}/static/tv_calendar.html"
    else:
        link_url = None

    try:
        if message_to_uid:
            for _ in message_to_uid:
                server.notify.send_message_by_tmpl('{{title}}', '{{a}}', {
                    'title': msg_title,
                    'a': message,
                    'pic_url': pic_url,
                    'link_url': link_url
                }, to_uid=_)
                _LOGGER.info(f'「今日剧集更新列表」已推送通知')
        else:
            server.notify.send_message_by_tmpl('{{title}}', '{{a}}', {
                'title': msg_title,
                'a': message,
                'pic_url': pic_url,
                'link_url': link_url
            })
            _LOGGER.info(f'「今日剧集更新列表」已推送通知')
    except Exception as e:
                    _LOGGER.error(f'消息推送异常1，原因: {e}')
                    pass

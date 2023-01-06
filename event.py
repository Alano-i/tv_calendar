import datetime
import typing
from typing import Dict, Any

from moviebotapi.core.models import MediaType
from moviebotapi.subscribe import SubStatus, Subscribe

import json
import shutil
from mbot.openapi import mbot_api
from mbot.core.plugins import *

import logging
import yaml
import re

import os

server = mbot_api
api_url = "/3/tv/%(tv_id)s/season/%(season_number)s"
tv_api_url = "/3/tv/%(tv_id)s"
param = {'language': 'zh-CN'}
_LOGGER = logging.getLogger(__name__)
message_to_uid: typing.List[int] = []


@plugin.after_setup
def after_setup(plugin_meta: PluginMeta, config: Dict[str, Any]):
    global message_to_uid
    message_to_uid = config.get('uid')

    if os.path.exists('/app/frontend/static/tv_calendar.html'):
        os.remove('/app/frontend/static/tv_calendar.html')
    if os.path.exists('/app/frontend/static/episode.html'):
        os.remove('/app/frontend/static/episode.html')
    if os.path.exists('/app/frontend/static/banner.jpg'):
        os.remove('/app/frontend/static/banner.jpg')
    shutil.copy('/data/plugins/tv_calendar/frontend/tv_calendar.html', '/app/frontend/static')
    shutil.copy('/data/plugins/tv_calendar/frontend/episode.html', '/app/frontend/static')
    shutil.copy('/data/plugins/tv_calendar/frontend/banner.jpg', '/app/frontend/static')


@plugin.config_changed
def config_changed(config: Dict[str, Any]):
    global message_to_uid
    message_to_uid = config.get('uid')


@plugin.task('save_json', '剧集更新', cron_expression='10 0 * * *')
def task():
    save_json()


def get_tmdb_info(tv_id, season_number):
    for i in range(5):
        try:
            res = server.tmdb.request_api(api_url % {'tv_id': tv_id, 'season_number': season_number}, param)
        except Exception as e:
            _LOGGER.error(e)
            continue
        return res
    return False


def get_tv_info(tv_id):
    for i in range(5):
        try:
            res = server.tmdb.request_api(tv_api_url % {'tv_id': tv_id}, param)
        except Exception as e:
            _LOGGER.error(e)
            continue
        return res
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
    custom_list_filter = list(filter(lambda x: x.media_type == MediaType.TV and x.tmdb_id is not None, custom_list))
    for item in custom_list_filter:
        list_.append(Subscribe({'tmdb_id': item.tmdb_id, 'season_index': item.season_number}, 'SubscribeApi'))
    episode_arr = []
    for row in list_:
        tv = get_tv_info(row.tmdb_id)
        if tv is False:
            continue
        tv_poster = tv['poster_path']
        seasons = tv['seasons']
        tv_name = tv['name']
        tv_original_name = tv['original_name']
        season_poster = find_season_poster(seasons, row.season_number)
        season = get_tmdb_info(row.tmdb_id, row.season_number)
        if season is False:
            continue
        episodes = season['episodes']
        for episode in episodes:
            episode['tv_name'] = tv_name
            episode['tv_original_name'] = tv_original_name
            episode['tv_poster'] = tv_poster
            episode['season_poster'] = season_poster
            episode_arr.append(episode)

    with open('/app/frontend/static/original.json', 'w', encoding='utf-8') as fp:
        json.dump(episode_arr, fp, ensure_ascii=False)

    _LOGGER.info('剧集数据更新结束')
    push_message()


def get_after_day(day, n):
    # 今天的时间

    # 计算偏移量
    offset = datetime.timedelta(days=n)
    # 获取想要的日期的时间
    after_day = day + offset
    return after_day


def get_server_url():
    yml_file = "/data/conf/base_config.yml"
    with open(yml_file, encoding='utf-8') as f:
        yml_data = yaml.load(f, Loader=yaml.FullLoader)
    mr_url = yml_data['web']['server_url']
    if (re.match('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', mr_url) != None):
        return mr_url
    return False


def push_message():
    _LOGGER.info('推送今日更新')
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
    img_api = 'https://cdn-us.imgs.moe/2023/01/06/63b7930dc9331.jpg'
    count = 0
    if len(episode_arr) == 0:
        message = "今日没有剧集更新"
    else:
        message_arr = []
        for tv_name in name_dict:
            count = count + 1
            episodes = name_dict[tv_name]
            episode_number_arr = []
            for episode in episodes:
                episode_number_arr.append(str(episode['episode_number']))
            episode_numbers = ','.join(episode_number_arr)
            message_arr.append(
                tv_name + 'S' + str(episodes[0]['season_number']) + 'E' + episode_numbers)
        message = "\n".join(message_arr)

    mr_url = get_server_url()
    link_url = ''
    if (mr_url != False):
        if (mr_url[-1] != '/'):
            mr_url += '/'
        link_url = mr_url + 'static/tv_calendar.html'
    if message_to_uid:
        for _ in message_to_uid:
            server.notify.send_message_by_tmpl('{{title}}', '{{a}}', {
                'title': '今日剧集更新 共' + str(count) + '部',
                'a': message,
                'link_url': link_url,
                'pic_url': img_api
            }, to_uid=_)
    else:
        server.notify.send_message_by_tmpl('{{title}}', '{{a}}', {
            'title': '今日剧集更新 共' + str(count) + '部',
            'a': message,
            'link_url': link_url,
            'pic_url': img_api

        })
    _LOGGER.info('完成推送')

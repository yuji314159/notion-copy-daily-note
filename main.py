import os
import sys
import typing
import logging
import json
import datetime
import requests
import http.client


NOTION_API_KEY = os.getenv('NOTION_API_KEY')
DAILY_DATABASE_ID = os.getenv('DAILY_DATABASE_ID')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

http.client.HTTPConnection.debuglevel = 1


class Notion:
    def __init__(self, api_key: str):
        self.API_KEY = api_key

    def query_database(self, database_id: str) -> dict[str, typing.Any]:
        res = requests.post(f'https://api.notion.com/v1/databases/{database_id}/query',
            json={
                'sorts': [
                    {
                        'property': '日付',
                        'direction': 'descending',
                    },
                ],
            },
            headers={
                'Authorization': f'Bearer {self.API_KEY}',
                'Notion-Version': '2022-06-28',
                'Content-Type': 'application/json',
            },
        )
        return res.json()

    def get_block_children(self, block_id: str) -> dict[str, typing.Any]:
        res = requests.get(f'https://api.notion.com/v1/blocks/{block_id}/children',
            headers={
                'Authorization': f'Bearer {self.API_KEY}',
                'Notion-Version': '2022-06-28',
            },
        )
        return res.json()

    def create_page(self, parent: dict, properties: dict, children: dict, *,
                    icon: str | None = None,
                    cover: str | None = None):
        res = requests.post(f'https://api.notion.com/v1/pages',
            json={
                'parent': parent,
                'icon': icon,
                'cover': cover,
                'properties': properties,
                'children': children,
            },
            headers={
                'Authorization': f'Bearer {self.API_KEY}',
                'Notion-Version': '2022-06-28',
                'Content-Type': 'application/json',
            },
        )
        return res.json()


class DiscordWebhook:
    def __init__(self, webhook_url: str):
        self.WEBHOOK_URL = webhook_url

    def send(self, content: str):
        requests.post(self.WEBHOOK_URL,
            json={'content': content},
            headers={'Content-Type': 'application/json'},
        )


def filter_output_children(children: dict) -> dict[str, typing.Any]:
    return [{
        'object': child['object'],
        'type': child['type'],
        child['type']: child[child['type']],
    } for child in children]


def main():
    notion = Notion(api_key=NOTION_API_KEY)

    pages = notion.query_database(DAILY_DATABASE_ID)
    latest_page = pages['results'][0]
    latest_page_id = latest_page['id']
    latest_date_iso = latest_page['properties']['日付']['date']['start']
    logger.info(f'latest_page_id: {latest_page_id}')
    logger.info(f'latest_date_iso: {latest_date_iso}')

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    today_str = now.strftime('%Y%m%d')
    today_iso = now.strftime('%Y-%m-%d')
    logger.info(f'today_str: {today_str}')
    logger.info(f'today_iso: {today_iso}')

    if latest_date_iso == today_iso:
        # すでにページが存在する
        logger.error(f'すでに同じ日付のページが存在します: date: {latest_date_iso}, page_id: {latest_page_id}')
        sys.exit(1)

    blocks = notion.get_block_children(latest_page_id)
    today_page = notion.create_page(
        parent={
            'type': 'database_id',
            'database_id': DAILY_DATABASE_ID,
        },
        properties={
            '名前': {
                'id': 'title',
                'type': 'title',
                'title': [
                    {
                        'type': 'text',
                        'text': {
                            'content': today_str,
                            'link': None,
                        },
                        'annotations': {
                            'bold': False,
                            'italic': False,
                            'strikethrough': False,
                            'underline': False,
                            'code': False,
                            'color': 'default',
                        },
                        'plain_text': today_str,
                        'href': None,
                    },
                ],
            },
            '日付': {
                'id': 'FS%3C%3C',
                'type': 'date',
                'date': {
                    'start': today_iso,
                    'end': None,
                    'time_zone': None,
                },
            },
        },
        children=filter_output_children(blocks['results']),
    )
    today_page_id = today_page['id']
    today_page_url = today_page['url']
    logger.info(f'今日のページを作成しました: date: {today_iso}, page_id: {today_page_id}')

    discord = DiscordWebhook(DISCORD_WEBHOOK_URL)
    discord.send(f'Daily Pageを作成しました:\n{today_page_url}')


if __name__ == '__main__':
    # ローカルテスト用のログ設定
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    root_logger.addHandler(ch)

    main()

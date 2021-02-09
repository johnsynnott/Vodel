import json
import os
import praw
import requests

from typing import Any, List


class Configurator:
    config_json = None

    def __init__(self, config_file):
        if os.path.exists(config_file):
            with open(config_file) as f:
                self.config_json = json.load(f)
        else:
            self.config_json = {}

    def __getitem__(self, item: str):
        return os.getenv(item.upper(), self.get_config_from_json(item))

    def get_config_from_json(self, path: str, default: Any = None):
        val = self.config_json
        for key in path.split('__'):
            val = val[key]
        return val


class LiveStream:
    url: str = None
    title: str = None

    def __init__(self, *args, **kwargs):
        # Setting it up this way in case I ever want to write tests. Positive thinking and all that.
        if 'blob' in kwargs:
            blob: dict = kwargs['blob']
            if 'videoId' in blob:
                self.url = f"https://www.youtube.com/watch?v={blob['videoId']}"
            if 'title' in blob and 'runs' in blob['title'] and len(blob['title']['runs']) and 'text' in blob['title']['runs'][0]:
                self.title = blob['title']['runs'][0]['text']


def get_channel_html(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def get_channel_data(channel_html: str) -> dict:
    # TODO clean up variable names and use the youtube api instead. This is so gross.
    left_trimmed = channel_html.split('var ytInitialData = ', 1)[1]
    left_right_trimmed = left_trimmed.split('</script>', 1)[0]
    trimmed = left_right_trimmed[:-1]
    return json.loads(trimmed)


def get_live_stream_blobs(channel_data: dict):
    for tab in channel_data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', []):
        for section_list in tab.get('tabRenderer', {}).get('content', {}).get('sectionListRenderer', {}).get('contents', []):
            for item_section in section_list.get('itemSectionRenderer', {}).get('contents', []):
                for featured_content_item in item_section.get('channelFeaturedContentRenderer', {}).get('items', []):
                    runs_data = featured_content_item.get('videoRenderer', {}).get('viewCountText', {}).get('runs', [])
                    if len(runs_data) >= 2 and runs_data[1].get('text', '') == ' watching':
                        yield LiveStream(blob=featured_content_item.get('videoRenderer', {}))


def get_live_streams(channel_url: str) -> List[LiveStream]:
    return list(get_live_stream_blobs(get_channel_data(get_channel_html(channel_url))))


def get_reddit_instance(config: Configurator) -> praw.Reddit:
    reddit = praw.Reddit(**{
        attribute: config[f'reddit__{attribute}']
        for attribute
        in (
            'client_id',
            'client_secret',
            'user_agent',
            'username',
            'password'
        )
    })
    reddit.validate_on_submit = True
    return reddit


if __name__ == '__main__':
    from sys import argv
    config = Configurator(argv[1] if len(argv) >= 2 else 'config.json')
    reddit = get_reddit_instance(config)
    for live_stream in get_live_streams(config['youtube__channel_url']):
        print(f'Posting: {live_stream.title} - {live_stream.url}')
        reddit.subreddit(config['reddit__subreddit']).submit(title=live_stream.title, url=live_stream.url)

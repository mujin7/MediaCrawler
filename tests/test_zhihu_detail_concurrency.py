import asyncio

import pytest

import config
from media_platform.zhihu.core import ZhihuCrawler


@pytest.mark.asyncio
async def test_detail_tasks_share_the_configured_concurrency_limit(monkeypatch):
    monkeypatch.setattr(config, 'MAX_CONCURRENCY_NUM', 1)
    monkeypatch.setattr(config, 'ZHIHU_SPECIFIED_ID_LIST', [
        f'https://www.zhihu.com/question/10/answer/{aid}' for aid in range(100, 110)
    ])
    crawler = ZhihuCrawler()
    active = peak = 0

    async def detail(full_note_url, semaphore):
        nonlocal active, peak
        async with semaphore:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1
            return None

    async def comments(contents):
        assert contents == []

    monkeypatch.setattr(crawler, 'get_note_detail', detail)
    monkeypatch.setattr(crawler, 'batch_get_content_comments', comments)
    await crawler.get_specified_notes()
    assert peak == 1

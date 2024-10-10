# test_tasks.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import pytest

from podcast_analyzer.tasks import async_refresh_feed, run_feed_analysis

pytestmark = pytest.mark.django_db(transaction=True)


def test_async_refresh(httpx_mock, empty_podcast, rss_feed_datastream):
    httpx_mock.add_response(
        url=empty_podcast.rss_feed,
        status_code=200,
        content=rss_feed_datastream,
    )
    async_refresh_feed(str(empty_podcast.id))
    assert empty_podcast.episodes.count() == 5


def test_run_feed_analysis(podcast_with_parsed_episodes):
    run_feed_analysis(podcast_with_parsed_episodes)
    assert podcast_with_parsed_episodes.release_frequency == "weekly"

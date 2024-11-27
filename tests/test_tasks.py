# test_tasks.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import pytest

from podcast_analyzer.tasks import (
    async_refresh_feed,
    fetch_avatar_for_person,
    fetch_podcast_cover_art,
    run_feed_analysis,
)

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


def test_fetch_avatar(httpx_mock, cover_art, podcast_with_parsed_episodes):
    person = (
        podcast_with_parsed_episodes.episodes.first()
        .hosts_detected_from_feed.filter(img_url__isnull=False)
        .first()
    )
    httpx_mock.add_response(
        url=person.img_url,
        headers={"Content-Type": "image/png"},
        status_code=200,
        content=cover_art,
    )
    assert not person.avatar
    fetch_avatar_for_person(person)
    assert person.avatar


def test_fetch_cover_art(httpx_mock, cover_art, podcast_with_parsed_episodes):
    podcast_with_parsed_episodes.podcast_art_cache_update_needed = True
    podcast_with_parsed_episodes.save()
    assert not podcast_with_parsed_episodes.podcast_cached_cover_art
    httpx_mock.add_response(
        url=podcast_with_parsed_episodes.podcast_cover_art_url,
        headers={"Content-Type": "image/png"},
        status_code=200,
        content=cover_art,
    )
    fetch_podcast_cover_art(podcast_with_parsed_episodes)
    assert podcast_with_parsed_episodes.podcast_cached_cover_art

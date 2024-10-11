# conftest.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Fixtures for testing."""

# type: ignore

from collections.abc import Generator
from datetime import timedelta
from io import BytesIO
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)
from django.utils import timezone
from podcastparser import parse

from podcast_analyzer.models import AnalysisGroup, Podcast, Season
from tests.factories.podcast import PodcastFactory, generate_episodes_for_podcast

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    u = User.objects.create_superuser(
        username="mcp", email="me@example.com", password="Some generic password"
    )
    yield u
    u.delete()


@pytest.fixture
def mute_signals(request):
    if "enable_signals" in request.keywords:
        return

    signals = [pre_save, post_save, pre_delete, post_delete, m2m_changed]
    restore = {}
    for signal in signals:
        restore[signal] = signal.receivers
        signal.receivers = []

    def restore_signals():
        for signal, receivers in restore.items():
            signal.receivers = receivers

    request.addfinalizer(restore_signals)


@pytest.fixture
def empty_podcast(mute_signals) -> Podcast:
    """
    Returns an podcast with no other metadata defined yet.
    """
    p = PodcastFactory()
    yield p
    p.delete()


@pytest.fixture
def valid_podcast(mute_signals) -> Generator[Podcast]:
    """
    Returns a properly structured podcast object with some initial metadata saved..
    """
    p = PodcastFactory(empty=False)
    yield p
    if p.podcast_cached_cover_art:
        p.podcast_cached_cover_art.delete()
    p.delete()


@pytest.fixture
def cover_art() -> Generator[bytes]:
    """
    Returns the bytes of a cover image.
    """
    with open("tests/data/example_cover_art.png", "rb") as f:
        img_bytes: bytes = f.read()
    yield img_bytes


@pytest.fixture
def dormant_podcast(valid_podcast) -> Podcast:
    """
    Episodes with episodes older than 65 days.
    """
    generate_episodes_for_podcast(
        podcast=valid_podcast, latest_datetime=timezone.now() - timedelta(days=90)
    )
    yield valid_podcast


@pytest.fixture
def active_podcast(valid_podcast) -> Podcast:
    """
    Episodes for podcast more recent than 65 days.
    """
    generate_episodes_for_podcast(
        podcast=valid_podcast, latest_datetime=timezone.now() - timedelta(days=6)
    )
    yield valid_podcast


@pytest.fixture
def active_tracking_podcast(valid_podcast) -> Generator[Podcast]:
    """
    Generates a current podcast where the media urls contain tracking data.
    """
    generate_episodes_for_podcast(
        podcast=valid_podcast,
        latest_datetime=timezone.now() - timedelta(days=6),
        tracking_data=True,
    )
    yield valid_podcast


@pytest.fixture
def rss_feed_datastream(empty_podcast) -> BytesIO:
    """
    Provides an RSS feed for a podcast from test directory.
    """
    with open("tests/data/podcast_rss_feed.xml", "rb") as f:
        rss_datastream = BytesIO(f.read())
    return rss_datastream


@pytest.fixture
def parsed_rss(empty_podcast, rss_feed_datastream) -> dict[str, Any]:
    """
    Provides an already parsed version of the rss feed.
    """
    url = empty_podcast.rss_feed
    return parse(url, rss_feed_datastream)


@pytest.fixture
def podcast_with_parsed_metadata(empty_podcast, parsed_rss):
    empty_podcast.update_podcast_metadata_from_feed_data(parsed_rss)
    yield empty_podcast


@pytest.fixture
def podcast_with_parsed_episodes(podcast_with_parsed_metadata, parsed_rss):
    podcast_with_parsed_metadata.update_episodes_from_feed_data(parsed_rss["episodes"])
    yield podcast_with_parsed_metadata


@pytest.fixture
def podcast_with_two_seasons(mute_signals):
    podcast = PodcastFactory(empty=False)
    s1 = Season.objects.create(podcast=podcast, season_number=1)
    s2 = Season.objects.create(podcast=podcast, season_number=2)
    generate_episodes_for_podcast(
        podcast=podcast, latest_datetime=timezone.now() - timedelta(days=80), season=s1
    )
    generate_episodes_for_podcast(
        podcast=podcast,
        latest_datetime=timezone.now() - timedelta(days=10),
        number_of_episodes=5,
        season=s2,
    )
    yield podcast
    podcast.delete()


@pytest.fixture
def analysis_group(podcast_with_parsed_episodes, active_podcast):
    agroup = AnalysisGroup.objects.create(name="Testing analysis group")
    yield agroup
    agroup.delete()

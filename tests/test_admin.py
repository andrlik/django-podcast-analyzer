# test_admin.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for the admin actions."""

from io import BytesIO

import pytest
from django.contrib import admin, messages

from podcast_analyzer.admin import PodcastAdmin
from podcast_analyzer.models import Podcast

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("expected_new", [0, 2, 4])
def test_get_new_episodes(
    rf,
    settings,
    user,
    httpx_mock,
    podcast_with_parsed_episodes,
    expected_new: int,
) -> None:
    with open("tests/data/podcast_rss_feed.xml", "rb") as f:
        datastream = BytesIO(f.read())
    settings.MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
    if expected_new > 0:
        episodes = podcast_with_parsed_episodes.episodes.all().order_by(
            "-release_datetime"
        )[:expected_new]
        for episode in episodes:
            episode.delete()
    ep_count = podcast_with_parsed_episodes.episodes.count()
    podcast_queryset = Podcast.objects.filter(id=podcast_with_parsed_episodes.id)
    httpx_mock.add_response(
        url=podcast_with_parsed_episodes.rss_feed, content=datastream
    )
    admin_obj = PodcastAdmin(Podcast, admin.site)
    request = rf.get("/admin/podcast_analyzer/")
    request.user = user
    request._messages = messages.storage.default_storage(request)
    admin_obj.check_for_new_episodes(request, podcast_queryset)
    podcast_with_parsed_episodes.refresh_from_db()
    assert podcast_with_parsed_episodes.episodes.count() - ep_count == expected_new


def test_get_all_episodes(
    rf, settings, httpx_mock, user, podcast_with_parsed_episodes
) -> None:
    settings.MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
    with open("tests/data/podcast_rss_feed.xml", "rb") as f:
        datastream = BytesIO(f.read())
    httpx_mock.add_response(
        url=podcast_with_parsed_episodes.rss_feed, content=datastream
    )
    latest_ep = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    original_duration = latest_ep.itunes_duration
    latest_ep.itunes_duration = 2460
    latest_ep.save()
    podcast_queryset = Podcast.objects.filter(id=podcast_with_parsed_episodes.id)
    request = rf.get("/admin/podcast_analyzer/")
    request.user = user
    request._messages = messages.storage.default_storage(request)
    admin_obj = PodcastAdmin(Podcast, admin.site)
    admin_obj.refresh_all_episodes(request, podcast_queryset)
    latest_ep.refresh_from_db()
    assert latest_ep.itunes_duration == original_duration


def test_feed_update(
    rf, settings, httpx_mock, user, podcast_with_parsed_episodes
) -> None:
    settings.MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
    with open("tests/data/podcast_rss_feed.xml", "rb") as f:
        datastream = BytesIO(f.read())
    httpx_mock.add_response(
        url=podcast_with_parsed_episodes.rss_feed, content=datastream
    )
    latest_ep = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    original_duration = latest_ep.itunes_duration
    latest_ep.itunes_duration = 2460
    latest_ep.save()
    podcast_queryset = Podcast.objects.filter(id=podcast_with_parsed_episodes.id)
    request = rf.get("/admin/podcast_analyzer/")
    request.user = user
    request._messages = messages.storage.default_storage(request)
    admin_obj = PodcastAdmin(Podcast, admin.site)
    eps, feeds = admin_obj.feed_update(
        request, podcast_queryset, update_existing_episodes=True
    )
    latest_ep.refresh_from_db()
    assert latest_ep.itunes_duration == original_duration
    assert eps == 5
    assert feeds == 1


def test_feed_unreachable(
    rf, settings, httpx_mock, user, podcast_with_parsed_episodes
) -> None:
    settings.MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
    httpx_mock.add_response(url=podcast_with_parsed_episodes.rss_feed, status_code=404)
    podcast_queryset = Podcast.objects.filter(id=podcast_with_parsed_episodes.id)
    request = rf.get("/admin/podcast_analyzer/")
    request.user = user
    request._messages = messages.storage.default_storage(request)
    admin_obj = PodcastAdmin(Podcast, admin.site)
    eps, feeds = admin_obj.feed_update(
        request, podcast_queryset, update_existing_episodes=True
    )
    assert eps == 0
    assert feeds == 1


def test_feed_invalid(
    rf, settings, httpx_mock, user, podcast_with_parsed_episodes
) -> None:
    settings.MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
    with open("tests/data/malformed_podcast_rss_feed.xml", "rb") as f:
        datastream = BytesIO(f.read())
    httpx_mock.add_response(
        url=podcast_with_parsed_episodes.rss_feed, content=datastream
    )
    podcast_queryset = Podcast.objects.filter(id=podcast_with_parsed_episodes.id)
    request = rf.get("/admin/podcast_analyzer/")
    request.user = user
    request._messages = messages.storage.default_storage(request)
    admin_obj = PodcastAdmin(Podcast, admin.site)
    eps, feeds = admin_obj.feed_update(
        request, podcast_queryset, update_existing_episodes=True
    )
    assert eps == 0
    assert feeds == 1

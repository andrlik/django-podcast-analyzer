# test_views.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for views."""

import pytest
from django.core.exceptions import ObjectDoesNotExist

from podcast_analyzer.models import Podcast
from tests.factories.podcast import PodcastFactory

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize(
    "view_name,is_detail",
    [
        ("podcast-list", False),
        ("podcast-detail", True),
        ("podcast-edit", True),
        ("podcast-delete", True),
        ("podcast-create", False),
    ],
)
def test_unauthenticated_get(
    client, tp, podcast_with_parsed_episodes, view_name, is_detail
) -> None:
    if not is_detail:
        url = tp.reverse(f"podcast_analyzer:{view_name}")
    else:
        url = tp.reverse(
            f"podcast_analyzer:{view_name}", id=podcast_with_parsed_episodes.id
        )
    response = client.get(url)
    assert response.status_code == 302
    assert "accounts/login/" in response["Location"]


@pytest.mark.parametrize(
    "view_name,is_detail",
    [
        ("podcast-create", False),
        ("podcast-edit", True),
        ("podcast-delete", True),
    ],
)
def test_unauthenticated_post(
    client, tp, podcast_with_parsed_episodes, view_name, is_detail
) -> None:
    data_kwargs = {
        "title": "Yet Another Tech Podcast",
        "rss_feed": "https://www.example.com/yatp/feeds/rss.xml",
    }
    if not is_detail:
        url = tp.reverse(f"podcast_analyzer:{view_name}")
    else:
        url = tp.reverse(
            f"podcast_analyzer:{view_name}", id=podcast_with_parsed_episodes.id
        )
    current_podcast_count = Podcast.objects.count()
    last_mod = podcast_with_parsed_episodes.modified
    response = client.post(url, data=data_kwargs)
    assert response.status_code == 302
    assert "accounts/login/" in response["Location"]
    assert Podcast.objects.count() == current_podcast_count
    podcast_with_parsed_episodes.refresh_from_db()
    assert last_mod == podcast_with_parsed_episodes.modified


@pytest.mark.parametrize(
    "view_name,is_detail",
    [
        ("podcast-list", False),
        ("podcast-detail", True),
        ("podcast-edit", True),
        ("podcast-delete", True),
        ("podcast-create", False),
    ],
)
def test_authenticated_get(
    client, tp, user, podcast_with_parsed_episodes, view_name, is_detail
) -> None:
    if not is_detail:
        url = tp.reverse(f"podcast_analyzer:{view_name}")
    else:
        url = tp.reverse(
            f"podcast_analyzer:{view_name}", id=podcast_with_parsed_episodes.id
        )
    client.force_login(user)
    response = client.get(url)
    assert response.status_code == 200


def test_authenticated_create(mute_signals, client, tp, user):
    client.force_login(user)
    data_kwargs = {
        "title": "Yet Another Tech Podcast",
        "rss_feed": "https://www.example.com/yatp/feeds/rss.xml",
    }
    current_podcast_count = Podcast.objects.count()
    response = client.post(
        tp.reverse("podcast_analyzer:podcast-create"), data=data_kwargs
    )
    assert response.status_code == 302
    assert current_podcast_count + 1 == Podcast.objects.count()
    new_pod = Podcast.objects.get(rss_feed="https://www.example.com/yatp/feeds/rss.xml")
    assert response["Location"] == new_pod.urls.view


def test_authenticated_edit(
    mute_signals, client, tp, user, podcast_with_parsed_episodes
):
    client.force_login(user)
    data_kwargs = {
        "title": "Yet Another Tech Podcast",
        "rss_feed": podcast_with_parsed_episodes.rss_feed,
        "site_url": podcast_with_parsed_episodes.site_url,
        "podcast_cover_art_url": podcast_with_parsed_episodes.podcast_cover_art_url,
        "release_frequency": podcast_with_parsed_episodes.release_frequency,
        "probable_feed_host": podcast_with_parsed_episodes.probable_feed_host
        if podcast_with_parsed_episodes.probable_feed_host
        else "",
        "analysis_group": [],
    }
    last_mod = podcast_with_parsed_episodes.modified
    response = client.post(
        tp.reverse("podcast_analyzer:podcast-edit", id=podcast_with_parsed_episodes.id),
        data=data_kwargs,
    )
    assert response.status_code == 302
    podcast_with_parsed_episodes.refresh_from_db()
    assert last_mod < podcast_with_parsed_episodes.modified
    assert podcast_with_parsed_episodes.title == "Yet Another Tech Podcast"


def test_authenticated_delete(
    mute_signals, client, tp, user, podcast_with_parsed_episodes
):
    client.force_login(user)
    podcast_count = Podcast.objects.count()
    response = client.post(
        tp.reverse(
            "podcast_analyzer:podcast-delete", id=podcast_with_parsed_episodes.id
        ),
        data={},
    )
    assert response.status_code == 302
    assert podcast_count - 1 == Podcast.objects.count()
    assert response["Location"] == tp.reverse("podcast_analyzer:podcast-list")
    with pytest.raises(ObjectDoesNotExist):
        Podcast.objects.get(id=podcast_with_parsed_episodes.id)


def test_podcast_detail_template_no_art(
    client, django_assert_max_num_queries, tp, user, podcast_with_parsed_episodes
):
    client.force_login(user)
    with django_assert_max_num_queries(25):
        response = client.get(
            tp.reverse(
                "podcast_analyzer:podcast-detail", id=podcast_with_parsed_episodes.id
            )
        )
    assert response.status_code == 200
    assert 'alt="Podcast logo art"' not in response.content.decode("utf-8")


def test_podcast_detail_template_with_art(
    mute_signals,
    django_assert_max_num_queries,
    httpx_mock,
    cover_art,
    client,
    user,
    tp,
    podcast_with_parsed_episodes,
):
    httpx_mock.add_response(
        url=podcast_with_parsed_episodes.podcast_cover_art_url,
        content=cover_art,
        headers=[("Content-Type", "image/jpeg")],
    )
    podcast_with_parsed_episodes.podcast_art_cache_update_needed = True
    podcast_with_parsed_episodes.save()
    podcast_with_parsed_episodes.fetch_podcast_cover_art()
    podcast_with_parsed_episodes.refresh_from_db()
    client.force_login(user)
    with django_assert_max_num_queries(25):
        response = client.get(
            tp.reverse(
                "podcast_analyzer:podcast-detail", id=podcast_with_parsed_episodes.id
            )
        )
    assert response.status_code == 200
    assert (
        f'<img src="{podcast_with_parsed_episodes.podcast_cached_cover_art.url}" alt="Podcast logo art"'
        in response.content.decode("utf-8")
    )


def test_podcast_detail_no_itunes_categories(
    mute_signals,
    django_assert_max_num_queries,
    client,
    user,
    tp,
    podcast_with_parsed_episodes,
):
    podcast_with_parsed_episodes.itunes_categories.clear()
    client.force_login(user)
    with django_assert_max_num_queries(25):
        response = client.get(
            tp.reverse(
                "podcast_analyzer:podcast-detail", id=podcast_with_parsed_episodes.id
            )
        )
    assert response.status_code == 200
    assert "No categories detected yet." in response.content.decode("utf-8")


def test_podcast_detail_with_analysis_group(
    mute_signals,
    django_assert_max_num_queries,
    client,
    tp,
    user,
    analysis_group,
    podcast_with_parsed_episodes,
):
    podcast_with_parsed_episodes.analysis_group.add(analysis_group)
    client.force_login(user)
    with django_assert_max_num_queries(25):
        response = client.get(
            tp.reverse(
                "podcast_analyzer:podcast-detail", id=podcast_with_parsed_episodes.id
            )
        )
    assert response.status_code == 200
    assert f"<li>{analysis_group.name}</li>" in response.content.decode("utf-8")


def test_pagination(mute_signals, django_assert_max_num_queries, client, tp, user):
    client.force_login(user)
    for _ in range(60):
        PodcastFactory()
    for x in [1, 2, 3]:
        with django_assert_max_num_queries(25):
            response = client.get(
                f"{tp.reverse('podcast_analyzer:podcast-list')}?page={x}"
            )
    assert response.status_code == 200
    response = client.get(f"{tp.reverse('podcast_analyzer:podcast-list')}?page=4")
    assert response.status_code == 404

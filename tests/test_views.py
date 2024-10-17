# test_views.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for views."""

import pytest
from django.core.exceptions import ObjectDoesNotExist

from podcast_analyzer.models import Person, Podcast
from tests.factories.person import PersonFactory
from tests.factories.podcast import PodcastFactory, generate_episodes_for_podcast

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


@pytest.mark.parametrize(
    "view_name,is_detail",
    [
        ("person-list", False),
        ("person-detail", True),
        ("person-edit", True),
        ("person-delete", True),
    ],
)
def test_unauthenticated_person_get_views(
    client, django_assert_max_num_queries, tp, view_name, is_detail
):
    people = [PersonFactory() for _ in range(4)]
    if is_detail:
        url = tp.reverse(f"podcast_analyzer:{view_name}", id=people[0].id)
    else:
        url = tp.reverse(f"podcast_analyzer:{view_name}")
    with django_assert_max_num_queries(25):
        response = client.get(url)
    assert response.status_code == 302
    assert "accounts/login" in response["Location"]


def test_unauthenticated_person_post_views(client, django_assert_max_num_queries, tp):
    person = PersonFactory(url="https://google.com")
    data = {
        "name": person.name,
        "url": "https://example.com",
        "img_url": "https://www.example.com/avatars/me.png",
    }
    with django_assert_max_num_queries(25):
        response = client.post(
            tp.reverse("podcast_analyzer:person-edit", id=person.id), data=data
        )
    assert response.status_code == 302
    assert "accounts/login" in response["Location"]
    person.refresh_from_db()
    assert person.url == "https://google.com"
    with django_assert_max_num_queries(25):
        response = client.post(
            tp.reverse("podcast_analyzer:person-delete", id=person.id), data={}
        )
    assert response.status_code == 302
    assert "accounts/login" in response["Location"]
    assert Person.objects.get(id=person.id)


@pytest.mark.parametrize(
    "view_name,is_detail",
    [
        ("person-list", False),
        ("person-detail", True),
        ("person-edit", True),
        ("person-delete", True),
    ],
)
def test_authenticated_person_get_views(
    client, django_assert_max_num_queries, tp, user, view_name, is_detail
):
    person = PersonFactory()
    if is_detail:
        url = tp.reverse(f"podcast_analyzer:{view_name}", id=person.id)
    else:
        url = tp.reverse(f"podcast_analyzer:{view_name}")
    client.force_login(user)
    with django_assert_max_num_queries(25):
        response = client.get(url)
    assert response.status_code == 200


def test_authenticated_person_edit(client, django_assert_max_num_queries, tp, user):
    person = PersonFactory(url="https://google.com")
    client.force_login(user)
    with django_assert_max_num_queries(25):
        response = client.post(
            tp.reverse("podcast_analyzer:person-edit", id=person.id),
            data={
                "name": person.name,
                "url": "https://example.com",
                "img_url": "https://www.example.com/avatars/me.png",
            },
        )
    assert response.status_code == 302
    assert response["Location"] == person.urls.view
    person.refresh_from_db()
    assert person.url == "https://example.com"


def test_authenticated_person_delete(client, django_assert_max_num_queries, tp, user):
    person = PersonFactory()
    client.force_login(user)
    with django_assert_max_num_queries(25):
        response = client.post(
            tp.reverse("podcast_analyzer:person-delete", id=person.id), data={}
        )
    assert response.status_code == 302
    assert response["Location"] == tp.reverse("podcast_analyzer:person-list")
    with pytest.raises(ObjectDoesNotExist):
        Person.objects.get(id=person.id)


@pytest.mark.parametrize("img_appears", [True, False])
def test_person_list_img_detection(client, tp, user, img_appears):
    if not img_appears:
        person = PersonFactory(img_url=None)
    else:
        person = PersonFactory()
    client.force_login(user)
    response = client.get(tp.reverse("podcast_analyzer:person-list"))
    assert response.status_code == 200
    if img_appears:
        assert (
            f'<a href="{person.urls.view}"><img src="{person.img_url}"'
            in response.content.decode("utf-8")
        )
    else:
        assert f'<a href="{person.urls.view}"><img src=' not in response.content.decode(
            "utf-8"
        )


def test_empty_person_list(client, django_assert_max_num_queries, tp, user):
    client.force_login(user)
    with django_assert_max_num_queries(25):
        response = client.get(tp.reverse("podcast_analyzer:person-list"))
    assert response.status_code == 200
    assert "There are no people yet." in response.content.decode("utf-8")


def test_person_detail_with_appearances(
    mute_signals, client, django_assert_max_num_queries, tp, user
):
    person = PersonFactory()
    podcast1 = PodcastFactory()
    podcast2 = PodcastFactory()
    generate_episodes_for_podcast(podcast1)
    generate_episodes_for_podcast(podcast2)
    for ep in podcast1.episodes.all()[:5]:
        ep.hosts_detected_from_feed.add(person)
    for ep in podcast2.episodes.all()[:3]:
        ep.guests_detected_from_feed.add(person)
    client.force_login(user)
    with django_assert_max_num_queries(
        50
    ):  # Allow more queries since we are doing complex pre-fetching.
        response = client.get(
            tp.reverse("podcast_analyzer:person-detail", id=person.id)
        )
    assert response.status_code == 200
    assert "No appearances yet." not in response.content.decode("utf-8")

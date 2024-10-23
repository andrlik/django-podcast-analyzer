# test_views.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for views."""

import re
import uuid

import pytest
from django.core.exceptions import ObjectDoesNotExist

from podcast_analyzer.models import AnalysisGroup, Episode, Person, Podcast
from tests.factories.person import PersonFactory
from tests.factories.podcast import PodcastFactory, generate_episodes_for_podcast

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize(
    "authenticated,expected_response_code", [(False, 302), (True, 200)]
)
def test_app_entry(
    client,
    django_assert_max_num_queries,
    tp,
    user,
    authenticated,
    expected_response_code,
):
    if authenticated:
        client.force_login(user)
    with django_assert_max_num_queries(25):
        response = client.get(tp.reverse("podcast_analyzer:entry"))
    assert response.status_code == expected_response_code
    if not authenticated:
        assert "accounts/login" in response["Location"]
    else:
        assert (
            f'<a href="{tp.reverse("podcast_analyzer:entry")}">Analyzer</a>'
            in response.content.decode("utf-8")
        )


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
    assert response["Location"] == new_pod.get_absolute_url()


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


@pytest.mark.parametrize("has_art", [True, False])
def test_podcast_list_conditional_art(
    mute_signals,
    client,
    django_assert_max_num_queries,
    httpx_mock,
    cover_art,
    tp,
    user,
    podcast_with_parsed_episodes,
    has_art,
):
    if has_art:
        podcast_with_parsed_episodes.podcast_art_cache_update_needed = True
        podcast_with_parsed_episodes.save()
        httpx_mock.add_response(
            url=podcast_with_parsed_episodes.podcast_cover_art_url,
            headers=[("Content-Type", "image/jpeg")],
            content=cover_art,
        )
        podcast_with_parsed_episodes.fetch_podcast_cover_art()
        podcast_with_parsed_episodes.refresh_from_db()
    client.force_login(user)
    with django_assert_max_num_queries(25):
        response = client.get(tp.reverse("podcast_analyzer:podcast-list"))
    assert response.status_code == 200
    if has_art:
        assert (
            f'<img src="{podcast_with_parsed_episodes.podcast_cached_cover_art.url}" alt="Podcast cover art for {podcast_with_parsed_episodes.title}"'
            in response.content.decode("utf-8")
        )
    else:
        assert (
            f'alt="Podcast cover art for {podcast_with_parsed_episodes.title}"'
            not in response.content.decode("utf-8")
        )


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
    assert (
        f'<li><a href="{analysis_group.get_absolute_url()}">{analysis_group.name}</a></li>'
        in response.content.decode("utf-8")
    )


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
    assert response["Location"] == person.get_absolute_url()
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
            f'<a href="{person.get_absolute_url()}"><img src="{person.img_url}"'
            in response.content.decode("utf-8")
        )
    else:
        assert (
            f'<a href="{person.get_absolute_url()}"><img src='
            not in response.content.decode("utf-8")
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


@pytest.mark.parametrize(
    "view_name,is_detail",
    [
        ("episode-list", False),
        ("episode-detail", True),
        ("episode-edit", True),
        ("episode-delete", True),
    ],
)
def test_unauthenticated_episode_get_views(
    client,
    django_assert_max_num_queries,
    tp,
    podcast_with_parsed_episodes,
    view_name,
    is_detail,
):
    pod_id = podcast_with_parsed_episodes.id
    if is_detail:
        ep = podcast_with_parsed_episodes.episodes.latest("release_datetime")
        url = tp.reverse(f"podcast_analyzer:{view_name}", podcast_id=pod_id, id=ep.id)
    else:
        url = tp.reverse(f"podcast_analyzer:{view_name}", podcast_id=pod_id)
    with django_assert_max_num_queries(40):
        response = client.get(url)
    assert response.status_code == 302
    assert "accounts/login" in response["Location"]


def test_unauthenticated_episode_post_views(
    client, django_assert_max_num_queries, tp, podcast_with_parsed_episodes
):
    pod_id = podcast_with_parsed_episodes.id
    ep = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    url = tp.reverse("podcast_analyzer:episode-edit", podcast_id=pod_id, id=ep.id)
    original_title = ep.title
    ep_id = ep.id
    data = {
        "title": f"{ep.title} with an edit",
        "ep_num": ep.ep_num,
        "ep_type": ep.ep_type,
        "analysis_group": [],
        "hosts_detected_from_feed": [],
        "guests_detected_from_feed": [],
    }
    with django_assert_max_num_queries(40):
        response = client.post(url, data=data)
    assert response.status_code == 302
    assert "accounts/login" in response["Location"]
    ep.refresh_from_db()
    assert ep.title == original_title
    with django_assert_max_num_queries(40):
        response = client.post(
            tp.reverse("podcast_analyzer:episode-delete", podcast_id=pod_id, id=ep.id),
            data={},
        )
    assert response.status_code == 302
    assert "accounts/login" in response["Location"]
    assert Episode.objects.get(pk=ep_id)


@pytest.mark.parametrize(
    "view_name,is_detail",
    [
        ("episode-list", False),
        ("episode-detail", True),
        ("episode-edit", True),
        ("episode-delete", True),
    ],
)
def test_authenticated_episode_get_views(
    client,
    django_assert_max_num_queries,
    tp,
    user,
    podcast_with_parsed_episodes,
    view_name,
    is_detail,
):
    pod_id = podcast_with_parsed_episodes.id
    if is_detail:
        ep = podcast_with_parsed_episodes.episodes.latest("release_datetime")
        url = tp.reverse(f"podcast_analyzer:{view_name}", podcast_id=pod_id, id=ep.id)
    else:
        url = tp.reverse(f"podcast_analyzer:{view_name}", podcast_id=pod_id)
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.get(url)
    assert response.status_code == 200


@pytest.mark.parametrize("has_group", [True, False])
def test_episode_detail_analysis_group(
    client,
    django_assert_max_num_queries,
    tp,
    user,
    podcast_with_parsed_episodes,
    analysis_group,
    has_group,
):
    ep = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    if has_group:
        ep.analysis_group.add(analysis_group)
    client.force_login(user)
    print(ep.get_absolute_url())
    with django_assert_max_num_queries(40):
        response = client.get(
            tp.reverse(
                "podcast_analyzer:episode-detail",
                podcast_id=podcast_with_parsed_episodes.id,
                id=ep.id,
            )
        )
    assert response.status_code == 200
    if has_group:
        assert (
            f'<li><a href="{analysis_group.get_absolute_url()}">{analysis_group.name}</a></li>'
            in response.content.decode("utf-8")
        )
    else:
        assert "No analysis groups." in response.content.decode("utf-8")


def test_authenticated_episode_post_views(
    client, django_assert_max_num_queries, tp, user, podcast_with_parsed_episodes
):
    pod_id = podcast_with_parsed_episodes.id
    ep = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    ep_id = ep.id
    data = {
        "title": f"{ep.title} with an edit",
        "ep_num": ep.ep_num,
        "ep_type": ep.ep_type,
        "analysis_group": [],
        "hosts_detected_from_feed": [],
        "guests_detected_from_feed": [],
    }
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.post(
            tp.reverse("podcast_analyzer:episode-edit", podcast_id=pod_id, id=ep_id),
            data=data,
        )
    assert response.status_code == 302
    assert ep.get_absolute_url() == response["Location"]
    ep.refresh_from_db()
    assert ep.title == data["title"]
    with django_assert_max_num_queries(40):
        response = client.post(
            tp.reverse("podcast_analyzer:episode-delete", podcast_id=pod_id, id=ep_id),
            data={},
        )
    assert response.status_code == 302
    assert (
        tp.reverse("podcast_analyzer:episode-list", podcast_id=pod_id)
        == response["Location"]
    )
    with pytest.raises(ObjectDoesNotExist):
        Episode.objects.get(pk=ep_id)


def test_authenticated_episode_detail_for_fake_podcast(
    client, django_assert_max_num_queries, user, podcast_with_parsed_episodes
):
    fake_pod_id = uuid.uuid4()
    while fake_pod_id in Podcast.objects.all().values_list("id", flat=True):
        fake_pod_id = uuid.uuid4()
    ep = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    client.force_login(user)

    with django_assert_max_num_queries(40):
        response = client.get(f"/podcasts/{fake_pod_id}/episodes/{ep.id}/")
    assert response.status_code == 404


def test_conditional_episode_person_views(
    mute_signals, client, django_assert_max_num_queries, tp, user
):
    podcast = PodcastFactory()
    generate_episodes_for_podcast(podcast)
    person1 = PersonFactory()
    person2 = PersonFactory()
    episodes_to_test = list(podcast.episodes.all()[:4])
    episodes_to_test[0].hosts_detected_from_feed.add(person1)
    episodes_to_test[1].hosts_detected_from_feed.add(person1)
    episodes_to_test[1].guests_detected_from_feed.add(person2)
    episodes_to_test[2].guests_detected_from_feed.add(person2)
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.get(
            tp.reverse(
                "podcast_analyzer:episode-detail",
                podcast_id=podcast.id,
                id=episodes_to_test[0].id,
            )
        )
    assert response.status_code == 200
    assert "No guests detected in feed." in response.content.decode("utf-8")
    assert "No hosts detected in feed." not in response.content.decode("utf-8")
    with django_assert_max_num_queries(40):
        response = client.get(
            tp.reverse(
                "podcast_analyzer:episode-detail",
                podcast_id=podcast.id,
                id=episodes_to_test[1].id,
            )
        )
    assert response.status_code == 200
    assert "No hosts detected in feed." not in response.content.decode("utf-8")
    assert "No guests detected in feed." not in response.content.decode("utf-8")
    with django_assert_max_num_queries(40):
        response = client.get(
            tp.reverse(
                "podcast_analyzer:episode-detail",
                podcast_id=podcast.id,
                id=episodes_to_test[2].id,
            )
        )
    assert response.status_code == 200
    assert "No hosts detected in feed." in response.content.decode("utf-8")
    assert "No guests detected in feed." not in response.content.decode("utf-8")
    with django_assert_max_num_queries(40):
        response = client.get(
            tp.reverse(
                "podcast_analyzer:episode-detail",
                podcast_id=podcast.id,
                id=episodes_to_test[3].id,
            )
        )
    assert response.status_code == 200
    assert "No hosts or guests detected in feed." in response.content.decode("utf-8")


def test_conditional_episode_list_view_season_detection(
    client, django_assert_max_num_queries, tp, user, podcast_with_parsed_episodes
):
    url = tp.reverse(
        "podcast_analyzer:episode-list", podcast_id=podcast_with_parsed_episodes.id
    )
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.get(url)
    assert response.status_code == 200
    assert "<td>Season</td>" in response.content.decode("utf-8")
    ep = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    content_with_ws_stripped = re.sub(r"\s", "", response.content.decode("utf-8"))
    assert (
        f'<tr><td>{ep.ep_num}</td><td>{ep.season.season_number}</td><td><ahref="{ep.get_absolute_url()}">{ep.title.replace(" ", "")}</a></td>'
        in content_with_ws_stripped
    )


def test_conditional_episode_list_view_no_episodes(
    client, django_assert_max_num_queries, tp, user, podcast_with_parsed_metadata
):
    url = tp.reverse(
        "podcast_analyzer:episode-list", podcast_id=podcast_with_parsed_metadata.id
    )
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.get(url)
    assert response.status_code == 200
    content_with_ws_stripped = re.sub(r"\s", "", response.content.decode("utf-8"))
    assert "<tbody></tbody>" in content_with_ws_stripped
    assert "No episodes found." in response.content.decode("utf-8")


@pytest.mark.parametrize("with_art", [True, False])
def test_episode_list_art_detection(
    mute_signals,
    httpx_mock,
    client,
    django_assert_max_num_queries,
    tp,
    cover_art,
    user,
    podcast_with_parsed_episodes,
    with_art,
):
    if with_art:
        podcast = podcast_with_parsed_episodes
        httpx_mock.add_response(
            url=podcast_with_parsed_episodes.podcast_cover_art_url,
            content=cover_art,
            headers=[("Content-Type", "image/jpeg")],
        )
        podcast_with_parsed_episodes.podcast_art_cache_update_needed = True
        podcast_with_parsed_episodes.save()
        podcast_with_parsed_episodes.fetch_podcast_cover_art()
        podcast_with_parsed_episodes.refresh_from_db()
    else:
        podcast = PodcastFactory()
        generate_episodes_for_podcast(podcast)
    url = tp.reverse("podcast_analyzer:episode-list", podcast_id=podcast.id)
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.get(url)
    assert response.status_code == 200
    print(response.content.decode("utf-8"))
    if with_art:
        assert (
            f'<img src="{podcast.podcast_cached_cover_art.url}" alt="Podcast logo art"'
            in response.content.decode("utf-8")
        )
    else:
        assert 'alt="Podcast logo art"' not in response.content.decode("utf-8")


@pytest.mark.parametrize(
    "view_name,is_detail",
    [
        ("ag-list", False),
        ("ag-create", False),
        ("ag-detail", True),
        ("ag-edit", True),
        ("ag-delete", True),
    ],
)
def test_unauthorized_analysis_group_get_views(
    client, django_assert_max_num_queries, tp, analysis_group, view_name, is_detail
):
    if is_detail:
        url = tp.reverse(f"podcast_analyzer:{view_name}", id=analysis_group.id)
    else:
        url = tp.reverse(f"podcast_analyzer:{view_name}")
    with django_assert_max_num_queries(40):
        response = client.get(url)
    assert response.status_code == 302
    assert "accounts/login" in response["Location"]


def test_unauthorized_analysis_group_post_views(
    mute_signals, client, django_assert_max_num_queries, tp, analysis_group
):
    podcast = PodcastFactory()
    generate_episodes_for_podcast(podcast)
    current_podcasts = analysis_group.num_podcasts
    ag_id = analysis_group.id
    data = {
        "name": "A better name",
        "podcasts": [podcast.id],
        "seasons": [],
        "episodes": [],
    }
    with django_assert_max_num_queries(40):
        response = client.post(
            tp.reverse("podcast_analyzer:ag-edit", id=analysis_group.id), data=data
        )
    assert response.status_code == 302
    assert "accounts/login" in response["Location"]
    analysis_group.refresh_from_db()
    assert analysis_group.name != "A better name"
    assert analysis_group.num_podcasts == current_podcasts
    with django_assert_max_num_queries(40):
        response = client.post(
            tp.reverse("podcast_analyzer:ag-delete", id=analysis_group.id), data={}
        )
    assert response.status_code == 302
    assert "accounts/login" in response["Location"]
    assert AnalysisGroup.objects.get(id=ag_id)


@pytest.mark.parametrize(
    "view_name,is_detail",
    [
        ("ag-list", False),
        ("ag-create", False),
        ("ag-detail", True),
        ("ag-edit", True),
        ("ag-delete", True),
    ],
)
def test_authorized_analysis_group_get_views(
    client,
    django_assert_max_num_queries,
    tp,
    user,
    analysis_group,
    view_name,
    is_detail,
):
    if is_detail:
        url = tp.reverse(f"podcast_analyzer:{view_name}", id=analysis_group.id)
    else:
        url = tp.reverse(f"podcast_analyzer:{view_name}")
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.get(url)
    assert response.status_code == 200


def test_authorized_analysis_group_detail_view_conditional_categories(
    client,
    django_assert_max_num_queries,
    tp,
    user,
    podcast_with_parsed_episodes,
    analysis_group,
):
    podcast_with_parsed_episodes.analysis_group.add(analysis_group)
    url = tp.reverse("podcast_analyzer:ag-detail", id=analysis_group.id)
    client.force_login(user)
    with django_assert_max_num_queries(50):
        response = client.get(url)
    assert response.status_code == 200
    assert "<li>Leisure - Games: 1</li>" in response.content.decode("utf-8")
    cat_to_change = podcast_with_parsed_episodes.itunes_categories.get(name="Games")
    podcast_with_parsed_episodes.itunes_categories.remove(cat_to_change)
    podcast_with_parsed_episodes.itunes_categories.add(cat_to_change.parent_category)
    analysis_group.refresh_from_db()
    with django_assert_max_num_queries(50):
        response = client.get(url)
    assert response.status_code == 200
    assert "<li>Leisure: 1</li>" in response.content.decode("utf-8")
    podcast_with_parsed_episodes.itunes_categories.clear()
    analysis_group.refresh_from_db()
    with django_assert_max_num_queries(50):
        response = client.get(url)
    assert response.status_code == 200
    assert (
        "<li>No categories found for this analysis group.</li>"
        in response.content.decode("utf-8")
    )


def test_authorized_analysis_group_create_view(
    client, django_assert_max_num_queries, tp, user, podcast_with_parsed_episodes
):
    url = tp.reverse("podcast_analyzer:ag-create")
    data = {
        "name": "The test generated analysis group",
        "podcasts": [podcast_with_parsed_episodes.id],
        "seasons": [],
        "episodes": [],
    }
    current_group_count = AnalysisGroup.objects.count()
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.post(url, data=data)
    print(response.content.decode("utf-8"))
    assert response.status_code == 302
    assert AnalysisGroup.objects.count() == current_group_count + 1
    group = AnalysisGroup.objects.latest("created")
    assert group.name == "The test generated analysis group"
    assert group.num_podcasts() == 1


def test_authorized_analysis_group_edit_delete_views(
    client,
    django_assert_max_num_queries,
    tp,
    user,
    podcast_with_parsed_episodes,
    analysis_group,
):
    ag_id = analysis_group.id
    data = {
        "name": "The test generated analysis group",
        "podcasts": [podcast_with_parsed_episodes.id],
        "seasons": [],
        "episodes": [],
    }
    current_group_count = AnalysisGroup.objects.count()
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.post(
            tp.reverse("podcast_analyzer:ag-edit", id=ag_id), data=data
        )
    assert response.status_code == 302
    assert analysis_group.get_absolute_url() == response["Location"]
    analysis_group.refresh_from_db()
    assert analysis_group.name == "The test generated analysis group"
    assert analysis_group.num_podcasts() == 1
    with django_assert_max_num_queries(40):
        response = client.post(
            tp.reverse("podcast_analyzer:ag-delete", id=analysis_group.id), data={}
        )
    assert response.status_code == 302
    assert tp.reverse("podcast_analyzer:ag-list") == response["Location"]
    assert AnalysisGroup.objects.count() == current_group_count - 1
    with pytest.raises(ObjectDoesNotExist):
        AnalysisGroup.objects.get(id=analysis_group.id)


def test_unauthorized_tag_podcast_list_view(
    client, django_assert_max_num_queries, tp, podcast_with_parsed_episodes
):
    new_tag = Podcast.tags.tag_model.objects.create(name="games")
    podcast_with_parsed_episodes.tags = "games"
    podcast_with_parsed_episodes.save()
    url = tp.reverse("podcast_analyzer:tag-podcast-list", tag_slug=new_tag.slug)
    with django_assert_max_num_queries(40):
        response = client.get(url)
    assert response.status_code == 302
    assert "accounts/login" in response["Location"]


def test_authorized_tag_podcast_list_view(
    client, django_assert_max_num_queries, user, podcast_with_parsed_episodes
):
    new_tag = Podcast.tags.tag_model.objects.create(name="games")
    podcast_with_parsed_episodes.tags = "games"
    podcast_with_parsed_episodes.save()
    url = new_tag.get_absolute_url()
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.get(url)
    assert response.status_code == 200
    assert f"Podcasts tagged with {new_tag.name}</a></li>" in response.content.decode(
        "utf-8"
    )


def test_non_existent_tag(
    client, django_assert_max_num_queries, user, podcast_with_parsed_episodes
):
    url = "/app/tags/some-random-tag/"
    client.force_login(user)
    with django_assert_max_num_queries(40):
        response = client.get(url)
    assert response.status_code == 404

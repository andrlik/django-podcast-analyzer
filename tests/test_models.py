# test_models.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import os
from datetime import datetime, timedelta
from io import BytesIO
from statistics import median_high

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone
from django_q.models import Schedule

from podcast_analyzer.exceptions import FeedFetchError, FeedParseError
from podcast_analyzer.models import (
    Episode,
    ItunesCategory,
    Person,
    Podcast,
    calculate_median_episode_duration,
)
from tests.factories.podcast import PodcastFactory, generate_episodes_for_podcast

pytestmark = pytest.mark.django_db(transaction=True)


def test_get_missing_feed(httpx_mock, empty_podcast):
    httpx_mock.add_response(url=empty_podcast.rss_feed, status_code=404)
    with pytest.raises(FeedFetchError):
        empty_podcast.get_feed_data()


def test_get_malformed_feed(httpx_mock, empty_podcast):
    with open(
        "tests/data/malformed_podcast_rss_feed.xml",
        "rb",
    ) as f:
        malformed_bytes = f.read()
    httpx_mock.add_response(url=empty_podcast.rss_feed, content=malformed_bytes)
    with pytest.raises(FeedParseError):
        empty_podcast.get_feed_data()


def test_get_feed_data(httpx_mock, empty_podcast, rss_feed_datastream):
    httpx_mock.add_response(url=empty_podcast.rss_feed, content=rss_feed_datastream)
    result = empty_podcast.get_feed_data()
    assert result["title"] == "Some Podcast"
    assert len(result["episodes"]) == 5


def test_update_metadata(httpx_mock, empty_podcast, rss_feed_datastream):
    httpx_mock.add_response(url=empty_podcast.rss_feed, content=rss_feed_datastream)
    result = empty_podcast.get_feed_data()
    empty_podcast.update_podcast_metadata_from_feed_data(result)
    assert empty_podcast.feed_contains_itunes_data
    assert empty_podcast.itunes_explicit
    assert empty_podcast.feed_contains_podcast_index_data
    assert empty_podcast.feed_contains_structured_donation_data
    assert empty_podcast.itunes_categories.count() == 2
    assert empty_podcast.podcast_cover_art_url is not None
    assert empty_podcast.podcast_art_cache_update_needed
    assert empty_podcast.author == "Some Podcast Company"
    assert empty_podcast.email == "contact@somepodcast.com"
    assert empty_podcast.last_checked is not None


def test_update_metadata_no_itunes_owner(empty_podcast):
    feed_dict = {
        "title": "Some Podcast",
        "episodes": [],
        "link": "https://www.somepodcast.com",
        "generator": "https://podbean.com/?v=5.5",
        "language": "en",
        "type": "serial",
        "itunes_author": "Some Podcast Company",
        "cover_url": "https://media.somepodcast.com/cover.jpg",
        "explicit": True,
        "itunes_keywords": ["games", "fiction", "unbearable opinions"],
        "import_prohibited": True,
        "funding_url": "https://www.patreonclone.com/somepodcast",
        "itunes_categories": [["Leisure", "Games"], ["Fiction", "Comedy Fiction"]],
    }
    empty_podcast.update_podcast_metadata_from_feed_data(feed_dict)
    assert empty_podcast.email is None


def test_update_metadata_category_no_children(empty_podcast):
    feed_dict = {
        "title": "Some Podcast",
        "episodes": [],
        "link": "https://www.somepodcast.com",
        "generator": "https://podbean.com/?v=5.5",
        "language": "en",
        "type": "serial",
        "itunes_author": "Some Podcast Company",
        "cover_url": "https://media.somepodcast.com/cover.jpg",
        "explicit": True,
        "itunes_keywords": ["games", "fiction", "unbearable opinions"],
        "import_prohibited": True,
        "funding_url": "https://www.patreonclone.com/somepodcast",
        "itunes_categories": [["Leisure", "Games"], ["Fiction"]],
    }
    empty_podcast.update_podcast_metadata_from_feed_data(feed_dict)
    fic_cat = ItunesCategory.objects.get(name="Fiction")
    assert fic_cat in empty_podcast.itunes_categories.all()


def test_update_metadata_no_podcast_index(empty_podcast):
    feed_dict = {
        "title": "Some Podcast",
        "episodes": [],
        "link": "https://www.somepodcast.com",
        "generator": "https://podbean.com/?v=5.5",
        "language": "en",
        "type": "serial",
        "itunes_author": "Some Podcast Company",
        "cover_url": "https://media.somepodcast.com/cover.jpg",
        "explicit": True,
        "itunes_keywords": ["games", "fiction", "unbearable opinions"],
        "itunes_owner": {
            "name": "Some Podcast Company",
            "email": "contact@somepodcast.com",
        },
        "itunes_categories": [["Leisure", "Games"], ["Fiction", "Comedy Fiction"]],
    }
    empty_podcast.update_podcast_metadata_from_feed_data(feed_dict)
    assert not empty_podcast.feed_contains_podcast_index_data


def test_update_metadata_no_itunes(empty_podcast):
    feed_dict = {
        "title": "Some Podcast",
        "episodes": [],
        "link": "https://www.somepodcast.com",
        "generator": "https://podbean.com/?v=5.5",
        "language": "en",
        "type": "serial",
        "cover_url": "https://media.somepodcast.com/cover.jpg",
        "explicit": True,
        "import_prohibited": True,
        "funding_url": "https://www.patreonclone.com/somepodcast",
    }
    empty_podcast.update_podcast_metadata_from_feed_data(feed_dict)
    assert not empty_podcast.feed_contains_itunes_data


def test_update_metadata_no_donation(empty_podcast):
    feed_dict = {
        "title": "Some Podcast",
        "episodes": [],
        "link": "https://www.somepodcast.com",
        "generator": "https://podbean.com/?v=5.5",
        "language": "en",
        "type": "serial",
        "itunes_author": "Some Podcast Company",
        "cover_url": "https://media.somepodcast.com/cover.jpg",
        "explicit": True,
        "itunes_keywords": ["games", "fiction", "unbearable opinions"],
        "itunes_owner": {
            "name": "Some Podcast Company",
            "email": "contact@somepodcast.com",
        },
        "import_prohibited": True,
        "itunes_categories": [["Leisure", "Games"], ["Fiction", "Comedy Fiction"]],
    }
    empty_podcast.update_podcast_metadata_from_feed_data(feed_dict)
    assert not empty_podcast.feed_contains_structured_donation_data


def test_update_metadata_no_cover_art(empty_podcast):
    feed_dict = {
        "title": "Some Podcast",
        "episodes": [],
        "link": "https://www.somepodcast.com",
        "generator": "https://podbean.com/?v=5.5",
        "language": "en",
        "type": "serial",
        "itunes_author": "Some Podcast Company",
        "explicit": True,
        "itunes_keywords": ["games", "fiction", "unbearable opinions"],
        "itunes_owner": {
            "name": "Some Podcast Company",
            "email": "contact@somepodcast.com",
        },
        "import_prohibited": True,
        "funding_url": "https://www.patreonclone.com/somepodcast",
        "itunes_categories": [["Leisure", "Games"], ["Fiction", "Comedy Fiction"]],
    }
    empty_podcast.update_podcast_metadata_from_feed_data(feed_dict)
    assert empty_podcast.podcast_cover_art_url is None


@pytest.mark.parametrize(
    "cover_url,response_status,response_headers,expect_success",
    [
        (None, None, None, False),
        ("https://media.somepodcast.com/cover.jpg", 404, None, False),
        ("https://media.somepodcast.com/cover.jpg", 200, None, False),
        (
            "https://media.somepodcast.com/cover.jpg",
            200,
            [("Content-Type", "image/jpeg")],
            True,
        ),
    ],
)
def test_fetch_cover_art(
    httpx_mock,
    valid_podcast,
    cover_url,
    response_status,
    response_headers,
    cover_art,
    expect_success,
):
    if cover_url is not None:
        valid_podcast.podcast_cover_art_url = cover_url
        valid_podcast.podcast_art_cache_update_needed = True
        valid_podcast.save()
        if response_status == 200 and response_headers is not None:
            httpx_mock.add_response(
                url=cover_url, headers=response_headers, content=cover_art
            )
        else:
            httpx_mock.add_response(url=cover_url, status_code=response_status)
        valid_podcast.fetch_podcast_cover_art()
        if expect_success:
            assert not valid_podcast.podcast_art_cache_update_needed
            assert valid_podcast.podcast_cached_cover_art
        else:
            assert valid_podcast.podcast_art_cache_update_needed
            assert not valid_podcast.podcast_cached_cover_art
    else:
        assert valid_podcast.podcast_cover_art_url is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cover_url,response_status,response_headers,expect_success",
    [
        (None, None, None, False),
        ("https://media.somepodcast.com/cover.jpg", 404, None, False),
        ("https://media.somepodcast.com/cover.jpg", 200, None, False),
        (
            "https://media.somepodcast.com/cover.jpg",
            200,
            [("Content-Type", "image/jpeg")],
            True,
        ),
        (
            "https://media.somepodcast.com/cover.jpg?from=rss",
            200,
            [("Content-Type", "image/jpeg")],
            True,
        ),
    ],
)
async def test_async_fetch_cover_art(
    httpx_mock,
    valid_podcast,
    cover_url,
    response_status,
    response_headers,
    cover_art,
    expect_success,
):
    if cover_url is not None:
        valid_podcast.podcast_cover_art_url = cover_url
        valid_podcast.podcast_art_cache_update_needed = True
        await valid_podcast.asave()
        if response_status == 200 and response_headers is not None:
            httpx_mock.add_response(
                url=cover_url, headers=response_headers, content=cover_art
            )
        else:
            httpx_mock.add_response(url=cover_url, status_code=response_status)
        await valid_podcast.afetch_podcast_cover_art()
        if expect_success:
            assert not valid_podcast.podcast_art_cache_update_needed
            assert valid_podcast.podcast_cached_cover_art
            assert valid_podcast.podcast_cached_cover_art.name[-3:] == "png"
        else:
            assert valid_podcast.podcast_art_cache_update_needed
            assert not valid_podcast.podcast_cached_cover_art
    else:
        assert valid_podcast.podcast_cover_art_url is None


def test_sync_fetch_cover_art_invalid_file(httpx_mock, valid_podcast):
    file_size = 9067
    random_file = BytesIO(initial_bytes=os.urandom(file_size))
    cover_url = "https://media.somepodcast.com/cover.jpg?from=rss"
    httpx_mock.add_response(
        url=cover_url,
        headers=[("Content-Type", "image/jpeg")],
        content=random_file.read(),
    )
    valid_podcast.podcast_cover_art_url = cover_url
    valid_podcast.podcast_art_cache_update_needed = True
    valid_podcast.save()
    valid_podcast.fetch_podcast_cover_art()
    art_update = valid_podcast.art_updates.latest("timestamp")
    assert not art_update.valid_file


@pytest.mark.parametrize(
    "update_all_eps,expected_first_touch_count,expected_second_touch_count",
    [
        (False, 5, 0),
        (True, 5, 5),
    ],
)
def test_new_episodes_in_feed(
    empty_podcast,
    parsed_rss,
    update_all_eps,
    expected_first_touch_count,
    expected_second_touch_count,
):
    empty_podcast.update_podcast_metadata_from_feed_data(parsed_rss)
    first_touch = empty_podcast.update_episodes_from_feed_data(
        parsed_rss["episodes"], update_existing_episodes=update_all_eps
    )
    assert first_touch == expected_first_touch_count
    second_touch = empty_podcast.update_episodes_from_feed_data(
        parsed_rss["episodes"], update_existing_episodes=update_all_eps
    )
    assert second_touch == expected_second_touch_count


def test_episodes_contain_funding_data(empty_podcast, parsed_rss):
    assert not empty_podcast.feed_contains_structured_donation_data
    parsed_rss["episodes"][0]["payment_url"] = "https://ko-fi.com/somepodcast"
    empty_podcast.update_episodes_from_feed_data(
        episode_list=parsed_rss["episodes"], update_existing_episodes=True
    )
    empty_podcast.refresh_from_db()
    assert empty_podcast.feed_contains_structured_donation_data


@pytest.mark.asyncio
async def test_analyze_host(podcast_with_parsed_metadata):
    await podcast_with_parsed_metadata.analyze_host()
    assert podcast_with_parsed_metadata.probable_feed_host == "Podbean"


@pytest.mark.asyncio
async def test_analyze_host_known_generator(mute_signals):
    new_podcast = await Podcast.objects.acreate(
        title="Tech Bros BSing",
        rss_feed="https://example.com",
        generator="Fireside (https://fireside.fm)",
    )
    await new_podcast.analyze_host()
    assert new_podcast.probable_feed_host == "Fireside.fm"
    await new_podcast.adelete()


@pytest.mark.asyncio
async def test_analyze_empty_host(mute_signals):
    new_podcast = await Podcast.objects.acreate(
        title="Tech Bros BSing", rss_feed="https://example.com", generator="monkey"
    )
    await new_podcast.analyze_host()
    assert new_podcast.probable_feed_host is None
    await new_podcast.adelete()


@pytest.mark.asyncio
async def test_analyze_host_from_episodes(mute_signals):
    new_podcast = await Podcast.objects.acreate(
        title="Tech Bros BSing", rss_feed="https://example.com", generator="monkey"
    )
    for i in range(5):
        await Episode.objects.acreate(
            podcast=new_podcast,
            guid=new_podcast.title.replace(" ", "-") + f"--{i}",
            download_url=f"http://media.blubrry.com/somepodcast/{i}",
        )
    await new_podcast.analyze_host()
    assert new_podcast.probable_feed_host == "Blubrry"
    await new_podcast.adelete()


@pytest.mark.asyncio
async def test_find_tracking(active_tracking_podcast):
    await active_tracking_podcast.analyze_feed_for_third_party_analytics()
    assert active_tracking_podcast.feed_contains_tracking_data


@pytest.mark.asyncio
async def test_find_tracking_false(active_podcast):
    await active_podcast.analyze_feed_for_third_party_analytics()
    assert not active_podcast.feed_contains_tracking_data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "days_between,expected_result",
    [
        (1, "daily"),
        (3, "often"),
        (7, "weekly"),
        (14, "biweekly"),
        (30, "monthly"),
        (45, "adhoc"),
    ],
)
async def test_calculate_release_frequency(
    podcast_with_parsed_metadata, days_between, expected_result
):
    await sync_to_async(generate_episodes_for_podcast)(
        podcast=podcast_with_parsed_metadata,
        latest_datetime=timezone.now() - timedelta(days=6),
        days_between=days_between,
    )

    await podcast_with_parsed_metadata.set_release_frequency(
        podcast_with_parsed_metadata.episodes.all()
    )
    assert podcast_with_parsed_metadata.release_frequency == expected_result


def test_duration_calculations(podcast_with_parsed_episodes):
    assert podcast_with_parsed_episodes.total_duration_seconds == 15702
    assert podcast_with_parsed_episodes.total_duration_timedelta == timedelta(
        seconds=15702
    )


def test_duration_empty_podcast(empty_podcast):
    assert empty_podcast.total_duration_seconds == 0
    assert empty_podcast.total_duration_timedelta is None


def test_ep_count_active(active_podcast):
    assert active_podcast.total_episodes == 10


def test_median_duration_active(podcast_with_parsed_episodes):
    ep_durations = [
        e.itunes_duration for e in podcast_with_parsed_episodes.episodes.all()
    ]
    assert (
        median_high(ep_durations)
        == podcast_with_parsed_episodes.median_episode_duration
    )
    assert podcast_with_parsed_episodes.median_episode_duration_timedelta == timedelta(
        seconds=podcast_with_parsed_episodes.median_episode_duration
    )


def test_median_duration_empty(empty_podcast):
    assert empty_podcast.median_episode_duration == 0
    assert empty_podcast.median_episode_duration_timedelta == timedelta(seconds=0)


def test_sync_last_release(podcast_with_parsed_episodes):
    expected_release_datetime = datetime.strptime(
        "Fri, 29 Apr 2023 06:00:00 -0400", "%a, %d %b %Y %H:%M:%S %z"
    )
    assert podcast_with_parsed_episodes.last_release_date == expected_release_datetime


def test_last_release_empty(empty_podcast):
    assert empty_podcast.last_release_date is None


@pytest.mark.asyncio
async def test_async_last_release(podcast_with_parsed_episodes):
    expected_release_datetime = datetime.strptime(
        "Fri, 29 Apr 2023 06:00:00 -0400", "%a, %d %b %Y %H:%M:%S %z"
    )
    rel_date = await podcast_with_parsed_episodes.alast_release_date()
    assert rel_date == expected_release_datetime


@pytest.mark.asyncio
async def test_async_last_release_empty(empty_podcast):
    assert await empty_podcast.alast_release_date() is None


def test_schedule_next_refresh_empty(empty_podcast):
    current_schedule_count = Schedule.objects.count()
    empty_podcast.schedule_next_refresh(last_release_date=None)
    assert current_schedule_count == Schedule.objects.count()


@pytest.mark.asyncio
async def test_detect_dormant(dormant_podcast):
    await dormant_podcast.set_dormant()
    assert dormant_podcast.dormant


@pytest.mark.asyncio
async def test_detect_dormant_empty(empty_podcast):
    last_mod = empty_podcast.modified
    await empty_podcast.set_dormant()
    await empty_podcast.arefresh_from_db()
    assert last_mod == empty_podcast.modified


@pytest.mark.asyncio
async def test_detect_active(active_podcast):
    await active_podcast.set_dormant()
    assert not active_podcast.dormant


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "full_episodes_only,latest_release,use_tracking,days_between,episode_limit,"
    "expected_freq,expected_dormant,expected_tracking",
    [
        (True, timezone.now() - timedelta(days=70), False, 1, 0, "daily", True, False),
        (True, timezone.now() - timedelta(days=70), True, 1, 0, "daily", True, True),
        (True, timezone.now() - timedelta(days=2), False, 1, 0, "daily", False, False),
        (False, timezone.now() - timedelta(days=2), False, 1, 0, "daily", False, False),
        (True, timezone.now() - timedelta(days=2), False, 3, 0, "often", False, False),
        (True, timezone.now() - timedelta(days=2), False, 7, 0, "weekly", False, False),
        (
            True,
            timezone.now() - timedelta(days=2),
            False,
            7,
            2,
            "pending",
            False,
            False,
        ),
        (
            True,
            timezone.now() - timedelta(days=2),
            False,
            14,
            0,
            "biweekly",
            False,
            False,
        ),
        (
            True,
            timezone.now() - timedelta(days=2),
            False,
            30,
            0,
            "monthly",
            False,
            False,
        ),
        (
            True,
            timezone.now() - timedelta(days=2),
            False,
            45,
            0,
            "adhoc",
            False,
            False,
        ),
    ],
)
async def test_analyze_podcast(
    podcast_with_parsed_metadata,
    episode_limit,
    full_episodes_only,
    latest_release,
    use_tracking,
    days_between,
    expected_freq,
    expected_dormant,
    expected_tracking,
):
    await sync_to_async(generate_episodes_for_podcast)(
        podcast=podcast_with_parsed_metadata,
        latest_datetime=latest_release,
        days_between=days_between,
        tracking_data=use_tracking,
        add_bonus_episode=True,
    )
    await podcast_with_parsed_metadata.analyze_feed(
        episode_limit=episode_limit, full_episodes_only=full_episodes_only
    )
    assert podcast_with_parsed_metadata.release_frequency == expected_freq
    assert podcast_with_parsed_metadata.dormant == expected_dormant
    assert podcast_with_parsed_metadata.feed_contains_tracking_data == expected_tracking


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "active,days_between,expected_delta",
    [
        (True, 1, timedelta(days=1)),
        (True, 4, timedelta(days=3)),
        (True, 7, timedelta(days=7)),
        (True, 14, timedelta(days=14)),
        (True, 29, timedelta(days=30)),
        (True, 45, timedelta(days=60)),
        (False, 7, timedelta(days=60)),
    ],
)
async def test_calculate_next_refresh(
    podcast_with_parsed_metadata, active, days_between, expected_delta
):
    if active:
        last_release = timezone.now()
    else:
        last_release = timezone.now() - timedelta(days=70)
    await sync_to_async(generate_episodes_for_podcast)(
        podcast=podcast_with_parsed_metadata,
        latest_datetime=last_release,
        days_between=days_between,
    )
    await podcast_with_parsed_metadata.analyze_feed()
    calculated_refresh = podcast_with_parsed_metadata.calculate_next_refresh_time(
        last_release_date=last_release
    )
    calculated_diff = calculated_refresh - last_release
    if active:
        assert calculated_diff == expected_delta
    else:
        assert calculated_diff >= expected_delta


def test_episode_persons_detection(podcast_with_parsed_episodes):
    """
    Checks that hosts and guests are correctly parsed from feed and that existing
    records are not duplicated.
    """
    episode = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    assert episode.hosts_detected_from_feed.count() == 1
    assert episode.guests_detected_from_feed.count() == 1
    assert Person.objects.count() == 2


def test_episode_no_person_records(active_podcast):
    """
    Checks that we don't create erroneous records when no
    person elements appear in the episode feed.
    """
    episode = active_podcast.episodes.latest("release_datetime")
    assert episode.hosts_detected_from_feed.count() == 0
    assert episode.guests_detected_from_feed.count() == 0
    assert Person.objects.count() == 0


def test_detect_person_img(podcast_with_parsed_episodes):
    """
    Checks if the system has correctly set the img element when supplied
    and left null if not.
    """
    episode = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    host = episode.hosts_detected_from_feed.all()[0]
    guest = episode.guests_detected_from_feed.all()[0]
    assert guest.img_url is None
    assert host.img_url is not None


@pytest.mark.parametrize(
    "podcast_count,skip_podcasts,hosted_eps,guested_eps,expected_result",
    [
        (2, 0, 4, 3, 2),
        (2, 1, 4, 0, 1),
        (2, 1, 3, 0, 1),
        (3, 1, 5, 2, 2),
        (3, 2, 0, 1, 1),
        (3, 3, 0, 0, 0),
    ],
)
def test_person_distinct_podcasts(
    mute_signals, podcast_count, skip_podcasts, hosted_eps, guested_eps, expected_result
):
    podcasts = [PodcastFactory() for _ in range(podcast_count)]
    for podcast in podcasts:
        generate_episodes_for_podcast(podcast)
    person = Person.objects.create(name="John Smith")
    if skip_podcasts < podcast_count:
        hosting_done = False
        for podcast in podcasts[skip_podcasts:]:
            if guested_eps > 0 and hosting_done or hosted_eps == 0:
                eps_to_edit = podcast.episodes.all()[:guested_eps]
                for ep in eps_to_edit:
                    ep.guests_detected_from_feed.add(person)
            elif hosted_eps > 0 and not hosting_done:
                eps_to_edit = podcast.episodes.all()[:hosted_eps]
                for ep in eps_to_edit:
                    ep.hosts_detected_from_feed.add(person)
                hosting_done = True
            else:
                pass  # No person entries to add.
    assert person.has_guested == guested_eps
    assert person.has_hosted == hosted_eps
    assert person.distinct_podcasts == expected_result


@pytest.mark.parametrize(
    "podcast_count,hosted_eps,guested_eps", [(0, 0, 0), (2, 4, 0), (2, 5, 5), (1, 0, 5)]
)
def test_person_total_episodes(mute_signals, podcast_count, hosted_eps, guested_eps):
    podcasts = [PodcastFactory() for _ in range(podcast_count)]
    for podcast in podcasts:
        generate_episodes_for_podcast(podcast)
    person = Person.objects.create(name="John Smith", url="https://www.example.com")
    hosting_done = False
    for podcast in podcasts:
        if guested_eps > 0 and hosting_done or hosted_eps == 0:
            eps_to_edit = podcast.episodes.all()[:guested_eps]
            for ep in eps_to_edit:
                ep.guests_detected_from_feed.add(person)
        elif hosted_eps > 0 and not hosting_done:
            eps_to_edit = podcast.episodes.all()[:hosted_eps]
            for ep in eps_to_edit:
                ep.hosts_detected_from_feed.add(person)
            hosting_done = True
        else:
            pass  # No entries to add
    assert person.get_total_episodes() == guested_eps + hosted_eps


def test_person_podcast_appearance_data(mute_signals):
    generated_podcasts = [PodcastFactory().id for _ in range(3)]
    person = Person.objects.create(name="John Smith", url="https://www.example.com")
    podcasts = Podcast.objects.filter(pk__in=generated_podcasts).order_by("title")
    for podcast in podcasts:
        generate_episodes_for_podcast(podcast)
    for ep in podcasts[0].episodes.all():
        ep.hosts_detected_from_feed.add(person)
    for ep in podcasts[1].episodes.all()[:5]:
        ep.guests_detected_from_feed.add(person)
    pod3_eps = podcasts[2].episodes.all()
    for ep in pod3_eps[:2]:
        ep.hosts_detected_from_feed.add(person)
    for ep in pod3_eps[4:6]:
        ep.guests_detected_from_feed.add(person)
    pod_data = person.get_podcasts_with_appearance_counts()
    assert len(pod_data) == 3
    assert pod_data[0].hosted_episodes.count() == 10
    assert pod_data[0].guested_episodes.count() == 0
    assert pod_data[1].hosted_episodes.count() == 0
    assert pod_data[1].guested_episodes.count() == 5
    assert pod_data[2].hosted_episodes.count() == 2
    assert pod_data[2].guested_episodes.count() == 2


def test_season_detection(podcast_with_parsed_metadata, parsed_rss):
    """
    Checks that seasons don't exist for the podcast in initial state
    and that a season is created after episodes are incorporated.
    """
    assert podcast_with_parsed_metadata.seasons.count() == 0
    podcast_with_parsed_metadata.update_episodes_from_feed_data(parsed_rss["episodes"])
    assert podcast_with_parsed_metadata.seasons.count() == 1


def test_no_season_detection(active_podcast):
    assert active_podcast.seasons.count() == 0


def test_transcript_detection(podcast_with_parsed_episodes):
    episode = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    assert episode.transcript_detected
    episode = podcast_with_parsed_episodes.episodes.get(ep_num=1)
    assert episode.transcript_detected


def test_no_transcript(active_podcast):
    episode = active_podcast.episodes.latest("release_datetime")
    assert not episode.transcript_detected


def test_cw_detection(podcast_with_parsed_episodes):
    cw_episodes = podcast_with_parsed_episodes.episodes.filter(cw_present=True)
    assert cw_episodes.count() == 2


def test_skip_items_without_enclosures(podcast_with_parsed_metadata, parsed_rss):
    """
    Under normal circumstances, an episode record should result in an insert, but
    if there are no enclosures it should be skipped. This tests both the atomic
    classmethod and the overall feed generation.
    """
    parsed_rss["episodes"][0]["enclosures"] = []
    assert not Episode.create_or_update_episode_from_feed(
        podcast_with_parsed_metadata, parsed_rss["episodes"][0]
    )
    podcast_with_parsed_metadata.update_episodes_from_feed_data(parsed_rss["episodes"])
    assert podcast_with_parsed_metadata.episodes.count() == 4


def test_episode_duration_property(podcast_with_parsed_episodes):
    expected_duration = timedelta(seconds=147)
    episode = podcast_with_parsed_episodes.episodes.latest("release_datetime")
    assert episode.duration == expected_duration


def test_no_duration_known(active_podcast):
    episode = active_podcast.episodes.latest("release_datetime")
    assert episode.duration is None


@pytest.mark.parametrize(
    "response_code,use_valid_rss,expected_count",
    [(401, True, 0), (404, True, 0), (500, True, 0), (200, False, 0), (200, True, 5)],
)
def test_full_feed_refresh(
    httpx_mock,
    empty_podcast,
    rss_feed_datastream,
    response_code,
    use_valid_rss,
    expected_count,
):
    """
    Tests the `refresh_feed` method.
    """
    if use_valid_rss:
        datastream = rss_feed_datastream
    else:
        with open(
            "tests/data/malformed_podcast_rss_feed.xml",
            "rb",
        ) as f:
            datastream = BytesIO(f.read())
    if response_code != 200:
        httpx_mock.add_response(url=empty_podcast.rss_feed, status_code=response_code)
    else:
        httpx_mock.add_response(
            url=empty_podcast.rss_feed, status_code=200, content=datastream
        )
    assert empty_podcast.refresh_feed() == expected_count


@pytest.mark.parametrize(
    "response_code,url_change_expected", [(301, True), (302, False)]
)
def test_redirected_feed(
    httpx_mock,
    empty_podcast,
    rss_feed_datastream,
    response_code,
    url_change_expected,
):
    """Test that feed data updates to new url when given a permanent redirect."""
    new_url_header = {"Location": "https://example.com/feed.xml"}
    original_url = empty_podcast.rss_feed
    httpx_mock.add_response(
        url=empty_podcast.rss_feed, status_code=response_code, headers=new_url_header
    )
    httpx_mock.add_response(
        url="https://example.com/feed.xml", status_code=200, content=rss_feed_datastream
    )
    empty_podcast.refresh_feed()
    empty_podcast.refresh_from_db()
    if url_change_expected:
        assert empty_podcast.rss_feed == "https://example.com/feed.xml"
    else:
        assert empty_podcast.rss_feed == original_url


def test_analysis_group_feed_count(
    analysis_group,
    podcast_with_parsed_episodes,
    active_podcast,
    podcast_with_two_seasons,
):
    podcast_with_parsed_episodes.analysis_group.add(analysis_group)
    for ep in active_podcast.episodes.all()[:3]:
        ep.analysis_group.add(analysis_group)
    season = podcast_with_two_seasons.seasons.get(season_number=1)
    season.analysis_group.add(analysis_group)
    analysis_group.refresh_from_db()
    assert analysis_group.num_podcasts() == 3
    assert analysis_group.num_seasons() == 2
    assert analysis_group.num_episodes() == 18
    assert analysis_group.num_people() == 2
    season.analysis_group.clear()
    analysis_group.refresh_from_db()
    assert analysis_group.num_podcasts() == 2
    assert analysis_group.num_seasons() == 1
    assert analysis_group.num_episodes() == 8
    assert analysis_group.num_people() == 2
    podcast_with_parsed_episodes.analysis_group.clear()
    analysis_group.refresh_from_db()
    assert analysis_group.num_podcasts() == 1
    assert analysis_group.num_episodes() == 3
    assert analysis_group.num_seasons() == 0
    assert analysis_group.num_people() == 0


def test_analysis_group_categories(
    mute_signals, podcast_with_parsed_episodes, analysis_group
):
    new_podcast = PodcastFactory()
    new_podcast.analysis_group.add(analysis_group)
    podcast_with_parsed_episodes.analysis_group.add(analysis_group)
    categories = analysis_group.get_itunes_categories_with_count()
    assert categories.exists()
    assert categories.count() == 2
    for category in categories:
        assert category.ag_pods == 1
    new_podcast.itunes_categories.set(
        podcast_with_parsed_episodes.itunes_categories.all()
    )
    analysis_group.refresh_from_db()
    categories = analysis_group.get_itunes_categories_with_count()
    assert categories.count() == 2
    for category in categories:
        assert category.ag_pods == 2


def test_analysis_group_calculate_duration_episodes(
    podcast_with_parsed_episodes, analysis_group
):
    podcast_with_parsed_episodes.analysis_group.add(analysis_group)
    assert (
        podcast_with_parsed_episodes.median_episode_duration
        == analysis_group.median_episode_duration
    )
    assert (
        podcast_with_parsed_episodes.total_duration_seconds
        == analysis_group.get_total_duration_seconds()
    )
    assert (
        analysis_group.get_median_duration_timedelta()
        == podcast_with_parsed_episodes.median_episode_duration_timedelta
    )
    assert (
        podcast_with_parsed_episodes.total_duration_timedelta
        == analysis_group.get_total_duration_timedelta()
    )


def test_calculate_median_duration_as_list(podcast_with_parsed_episodes):
    episode_list = list(podcast_with_parsed_episodes.episodes.all())
    assert (
        calculate_median_episode_duration(episode_list)
        == podcast_with_parsed_episodes.median_episode_duration
    )
    assert calculate_median_episode_duration([]) == 0

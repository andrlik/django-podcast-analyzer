# test_models.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from datetime import datetime, timedelta
from io import BytesIO

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from podcast_analyzer.exceptions import FeedFetchError, FeedParseError
from podcast_analyzer.models import Episode, Person
from tests.factories.podcast import generate_episodes_for_podcast

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
            assert valid_podcast.podcast_cached_cover_art.name[-3:] == "jpg"
        else:
            assert valid_podcast.podcast_art_cache_update_needed
            assert not valid_podcast.podcast_cached_cover_art
    else:
        assert valid_podcast.podcast_cover_art_url is None


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


@pytest.mark.asyncio
async def test_analyze_host(podcast_with_parsed_metadata):
    await podcast_with_parsed_metadata.analyze_host()
    assert podcast_with_parsed_metadata.probable_feed_host == "Podbean"


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


def test_sync_last_release(podcast_with_parsed_episodes):
    expected_release_datetime = datetime.strptime(
        "Fri, 29 Apr 2023 06:00:00 -0400", "%a, %d %b %Y %H:%M:%S %z"
    )
    assert podcast_with_parsed_episodes.last_release_date == expected_release_datetime


@pytest.mark.asyncio
async def test_async_last_release(podcast_with_parsed_episodes):
    expected_release_datetime = datetime.strptime(
        "Fri, 29 Apr 2023 06:00:00 -0400", "%a, %d %b %Y %H:%M:%S %z"
    )
    rel_date = await podcast_with_parsed_episodes.alast_release_date()
    assert rel_date == expected_release_datetime


@pytest.mark.asyncio
async def test_detect_dormant(dormant_podcast):
    await dormant_podcast.set_dormant()
    assert dormant_podcast.dormant


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
    assert analysis_group.num_feeds == 1
    assert analysis_group.num_seasons == 2
    assert analysis_group.num_episodes == 18
    season.analysis_group.clear()
    assert analysis_group.num_seasons == 2
    assert analysis_group.num_episodes == 18
    analysis_group.refresh_from_db()
    assert analysis_group.num_seasons == 1
    assert analysis_group.num_episodes == 8

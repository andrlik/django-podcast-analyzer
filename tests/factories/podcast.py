# podcast.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from datetime import datetime, timedelta

import factory
import pytest
from django.utils import timezone
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from podcast_analyzer.models import (
    KNOWN_GENERATOR_HOST_MAPPING,
    Episode,
    Podcast,
    Season,
)

pytestmark = pytest.mark.django_db(transaction=True)


class PodcastFactory(DjangoModelFactory):
    """
    Generates a podcast object.
    """

    title = factory.Faker("text", max_nb_chars=50)
    rss_feed = factory.Faker("uri")
    podcast_cover_art_url = factory.LazyAttribute(
        lambda o: factory.Faker("uri") if o.cover_art else None
    )
    podcast_art_cache_update_needed = factory.LazyAttribute(
        lambda o: True if o.cover_art else False
    )
    author = factory.Faker("name")
    generator = factory.LazyAttribute(
        lambda o: None if o.empty else FuzzyChoice(KNOWN_GENERATOR_HOST_MAPPING.keys())
    )
    email = factory.LazyAttribute(lambda o: None if o.empty else factory.Faker("email"))
    site_url = factory.LazyAttribute(
        lambda o: None if o.empty else factory.Faker("url")
    )

    class Meta:
        model = Podcast

    class Params:
        empty = True
        cover_art = False


class EpisodeFactory(DjangoModelFactory):
    """
    Generates an episode.
    """

    podcast = factory.SubFactory(PodcastFactory)
    guid = factory.Faker("uri")
    title = factory.Faker("text", max_nb_chars=50)
    episode_url = factory.Faker("uri")
    download_url = factory.Faker("uri")
    release_datetime = timezone.now() - timedelta(days=365)
    ep_num = 1
    ep_type = "full"
    season = None

    class Meta:
        model = Episode


@pytest.mark.django_db
def generate_episodes_for_podcast(
    podcast: Podcast,
    number_of_episodes: int = 10,
    latest_datetime: datetime | None = None,
    tracking_data: bool = False,
    days_between: int = 7,
    add_bonus_episode: bool = False,
    season: Season | None = None,
) -> None:
    """
    Given a podcast object, generate episodes for it.

    Args:
        podcast (Podcast): The Podcast instance to create for.
        number_of_episodes (int): Number of episodes to create, defaults to 10.
        latest_datetime (datetime | None): Most recent datetime of last episode.
        tracking_data (bool): Whether there should be tracking data in the urls.
        days_between (int): How many days between episodes.
        add_bonus_episode (bool): Add an episode with type of bonus
        season (Season):The season to add the episodes to
    """
    if number_of_episodes <= 0:
        msg = "Episodes to create must be greater than 0!"
        raise ValueError(msg)
    if not latest_datetime:
        latest_datetime = timezone.now()
    base_url: str = str(factory.Faker("url", schemes=["https"]))
    if tracking_data:
        base_url = f"https://media.blubrry.com/accountname/{base_url[8:]}"
    current_datetime = (
        latest_datetime
        - timedelta(days=1)
        - timedelta(days=days_between * number_of_episodes)
    )
    for x in range(number_of_episodes):
        EpisodeFactory(
            podcast=podcast,
            episode_url=f"{base_url}/episodes/{x + 1}",
            download_url=f"{base_url}/media/{x + 1}.mp3",
            ep_num=x + 1,
            release_datetime=current_datetime,
            season=season,
        )
        current_datetime = current_datetime + timedelta(days=days_between)
    if add_bonus_episode:
        EpisodeFactory(
            podcast=podcast,
            episode_url=f"{base_url}/episodes/{number_of_episodes + 1}",
            download_url=f"{base_url}/media/{number_of_episodes +1 }.mp3",
            ep_num=number_of_episodes + 1,
            release_datetime=current_datetime + timedelta(days=1),
            season=season,
        )

# tasks.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import logging

from podcast_analyzer.models import Person, Podcast

logger = logging.getLogger(__name__)


def async_refresh_feed(podcast_id: str) -> None:
    """
    Given a podcast object, call it's refresh feed function.

    Args:
        podcast_id (str): The podcast ID.
    """
    podcast = Podcast.objects.get(id=podcast_id)
    podcast.refresh_feed()


def run_feed_analysis(podcast: Podcast) -> None:
    """
    Wraps around the instance's feed analysis function.

    Args:
        podcast (Podcast): Podcast object to analyze.
    """
    logger.debug("Task 'run_feed_analysis' called!")
    asyncio.run(podcast.analyze_feed())
    podcast.schedule_next_refresh()


def fetch_podcast_cover_art(podcast: Podcast) -> None:
    """
    Wraps around the remote fetch functions for cover art.

    Args:
        podcast (Podcast): Podcast object to get cover art for.
    """
    logger.debug(f"Task 'fetch_podcast_cover_art' called for {podcast.title}!")
    asyncio.run(podcast.afetch_podcast_cover_art())


def fetch_avatar_for_person(person: Person) -> None:
    """
    Triggers the remote fetch of the person's avatar.

    Args:
        person (Person): The person record to populate with the avatar.
    """
    logger.debug(
        f"Task 'fetch_avatar_for_person' called for {person.name} ({person.id})"
    )
    asyncio.run(person.afetch_avatar())

# tasks.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import logging

from podcast_analyzer.models import Podcast

logger = logging.getLogger("podcast_analyzer")


def async_refresh_feed(podcast_id: str) -> None:
    """
    Given a podcast object, call it's refresh feed function.
    """
    podcast = Podcast.objects.get(id=podcast_id)
    podcast.refresh_feed()


def run_feed_analysis(podcast: Podcast) -> None:
    """
    Wraps around the instance's feed analysis function.
    """
    logger.debug("Task 'run_feed_analysis' called!")
    asyncio.run(podcast.analyze_feed())
    podcast.schedule_next_refresh()

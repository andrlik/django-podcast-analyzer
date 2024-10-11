# receivers.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django_q.tasks import async_task

from podcast_analyzer.models import Podcast
from podcast_analyzer.tasks import async_refresh_feed

logger = logging.getLogger("podcast_analyzer")


@receiver(post_save, sender=Podcast)
def import_podcast_on_create(sender, instance, created, *args, **kwargs):  # noqa: ARG001
    """
    When a podcast is created, schedule it for importing of feed data.
    """
    logger.debug("Checking to see if this is a new podcast...")
    if created:
        logger.debug(
            f"New podcast created! Adding a task to fetch "
            f"feed data from {instance.rss_feed}"
        )
        async_task(async_refresh_feed, podcast_id=instance.id)

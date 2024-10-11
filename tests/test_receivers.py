# test_receivers.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Placeholder for receiver related tests."""

import pytest

from podcast_analyzer import receivers
from podcast_analyzer.models import Podcast

pytestmark = pytest.mark.django_db(transaction=True)


def test_podcast_create_receiver(mocker):
    mocker.patch("podcast_analyzer.receivers.async_task")
    Podcast.objects.create(
        title="Some Techbros Chatting", rss_feed="https://example.com/podcast.rss"
    )
    receivers.async_task.assert_called_once()

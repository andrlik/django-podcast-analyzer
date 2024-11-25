# test_forms.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import pytest
from django.core.exceptions import ValidationError

from podcast_analyzer.forms import PersonMergeForm

pytestmark = pytest.mark.django_db


def test_disallow_merge_self(podcast_with_parsed_episodes):
    source_person = (
        podcast_with_parsed_episodes.episodes.first().hosts_detected_from_feed.first()
    )
    form = PersonMergeForm(
        initial={
            "source_person": source_person.id,
            "destination_person": source_person.id,
        }
    )
    with pytest.raises(ValidationError):
        form.clean()

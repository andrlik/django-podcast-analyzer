# test_management.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import pytest
from django.core import management
from django.core.management.base import CommandError

from podcast_analyzer.management.commands import seed_database_itunes
from podcast_analyzer.models import ItunesCategory

pytestmark = pytest.mark.django_db(transaction=True)


def test_seed_empty_database() -> None:
    """
    Tries to seed the database and checks for correct results.
    """
    management.call_command(seed_database_itunes.Command())
    assert ItunesCategory.objects.count() == 109


def test_seeding_nonempty_database() -> None:
    """
    Should raise a CommandError due to existing ItunesCategory
    records.
    """
    ItunesCategory.objects.create(name="Dummy Category")
    with pytest.raises(CommandError):
        management.call_command(seed_database_itunes.Command())

# person.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import factory
import pytest
from factory.django import DjangoModelFactory

from podcast_analyzer.models import Person

pytestmark = pytest.mark.django_db(transaction=True)


class PersonFactory(DjangoModelFactory):
    """
    Generate a new Person instance.
    """

    name = factory.Faker("name")
    url = factory.Faker("url")
    img_url = factory.Faker("uri")

    class Meta:
        model = Person

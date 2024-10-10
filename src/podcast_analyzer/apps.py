# apps.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PodcastAnalyzerConfig(AppConfig):
    name = "podcast_analyzer"
    verbose_name = _("Podcast Analyzer")
    default_auto_field = "django.db.models.AutoField"

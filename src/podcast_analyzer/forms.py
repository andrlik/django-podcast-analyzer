# forms.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from django import forms

from podcast_analyzer.models import AnalysisGroup, Episode, Podcast, Season


class AnalysisGroupForm(forms.ModelForm):
    """
    Form class that enables setting the reverse relationships
    to Podcast, Season, and Episode.

    Attributes:
        name (forms.CharField): Name of the group
        description (forms.TextField): Description of the group
        podcasts (form.ModelMultipleChoiceField): List of podcasts
        seasons (form.ModelMultipleChoiceField): List of seasons
        episodes (form.ModelMultipleChoiceField): List of episodes
    """

    class Meta:
        model = AnalysisGroup
        fields = ["name", "description"]

    podcasts = forms.ModelMultipleChoiceField(
        queryset=Podcast.objects.all(), required=False
    )
    seasons = forms.ModelMultipleChoiceField(
        queryset=Season.objects.all(), required=False
    )
    episodes = forms.ModelMultipleChoiceField(
        queryset=Episode.objects.all(), required=False
    )

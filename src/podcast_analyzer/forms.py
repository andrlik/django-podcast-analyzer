# forms.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from django import forms

from podcast_analyzer.models import AnalysisGroup, Episode, Podcast, Season


class AnalysisGroupForm(forms.ModelForm):
    class Meta:
        model = AnalysisGroup
        fields = ["name"]

    podcasts = forms.ModelMultipleChoiceField(
        queryset=Podcast.objects.all(), required=False
    )
    seasons = forms.ModelMultipleChoiceField(
        queryset=Season.objects.all(), required=False
    )
    episodes = forms.ModelMultipleChoiceField(
        queryset=Episode.objects.all(), required=False
    )

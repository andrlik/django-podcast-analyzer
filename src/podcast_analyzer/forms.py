# forms.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from django import forms
from django.core.exceptions import ValidationError

from podcast_analyzer.models import AnalysisGroup, Episode, Person, Podcast, Season


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


class PersonMergeForm(forms.Form):
    """
    Form class for validating person merge operations.

    Attributes:
        source_person (forms.ModelChoiceField): Source person
        destination_person (forms.ModelChoiceField): Destination person
    """

    cleaned_data = {}
    source_person = forms.ModelChoiceField(
        queryset=Person.objects.filter(merged_into__isnull=True),
        required=True,
        widget=forms.widgets.HiddenInput,
    )
    destination_person = forms.ModelChoiceField(
        queryset=Person.objects.filter(merged_into__isnull=True),
        required=True,
        widget=forms.widgets.HiddenInput,
    )

    def clean(self):
        """
        Run standard clean and then validate that user is not trying
        to merge a record into itself.
        """
        self.cleaned_data = super().clean()
        dest = self.cleaned_data.get("destination_person")
        source = self.cleaned_data.get("source_person")
        if dest == source:
            msg = "A record cannot be merged into itself!"
            raise ValidationError(msg)
        return self.cleaned_data

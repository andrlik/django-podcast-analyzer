# views.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import ClassVar

# from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from podcast_analyzer.models import Person, Podcast

# Create your views here.


class PodcastListView(LoginRequiredMixin, ListView):
    """
    View all podcasts in a list.
    """

    model = Podcast
    ordering = ["title"]
    paginate_by = 25

    def get_queryset(self):
        """
        Adds prefetching for related objects.
        """
        return Podcast.objects.all().prefetch_related(  # no cov
            "episodes", "seasons", "analysis_group"
        )


class PodcastDetailView(LoginRequiredMixin, DetailView):
    """
    A view to see a given podcasts data.
    """

    model = Podcast
    pk_url_kwarg = "id"
    context_object_name = "podcast"

    def get_queryset(self):
        """
        Adds prefetching for related objects.
        """
        return Podcast.objects.all().prefetch_related(  # no cov
            "episodes", "seasons", "analysis_group"
        )


class PodcastCreateView(LoginRequiredMixin, CreateView):
    """
    Provides a form to create a podcast.
    """

    model = Podcast
    fields: ClassVar[list[str]] = ["title", "rss_feed"]  # type: ignore


class PodcastUpdateView(LoginRequiredMixin, UpdateView):
    """
    View for updating a podcast record.
    """

    model = Podcast
    pk_url_kwarg = "id"
    fields: ClassVar[list[str]] = [  # type: ignore
        "title",
        "rss_feed",
        "site_url",
        "podcast_cover_art_url",
        "release_frequency",
        "probable_feed_host",
        "analysis_group",
    ]
    context_object_name = "podcast"


class PodcastDeleteView(LoginRequiredMixin, DeleteView):
    """
    For deleting a podcast record.
    """

    model = Podcast
    context_object_name = "podcast"
    pk_url_kwarg = "id"
    object: Podcast

    def get_queryset(self):
        """
        Adds prefetching for related objects.
        """
        return self.model.objects.all().prefetch_related(
            "episodes", "seasons", "analysis_group"
        )

    def get_success_url(self):
        return reverse_lazy("podcast_analyzer:podcast-list")


class PersonListView(LoginRequiredMixin, ListView):
    """View all people in a list"""

    model = Person
    pk_url_kwarg = "id"
    context_object_name = "people"
    paginate_by = 25
    prefetch_related = ["hosted_episodes", "guest_appearances"]
    ordering = ["name"]


class PersonDetailView(LoginRequiredMixin, DetailView):
    """View a specific person's details."""

    model = Person
    pk_url_kwarg = "id"
    context_object_name = "person"
    prefetch_related = ["hosted_episodes", "guest_appearances"]


class PersonUpdateView(LoginRequiredMixin, UpdateView):
    """Edit a given person's details."""

    model = Person
    fields: ClassVar[list[str]] = ["name", "url", "img_url"]
    context_object_name = "person"
    pk_url_kwarg = "id"


class PersonDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a person from the database."""

    model = Person
    pk_url_kwarg = "id"
    context_object_name = "person"
    prefetch_related = ["hosted_episodes", "guest_appearances"]
    object: Person

    def get_success_url(self):
        return reverse_lazy("podcast_analyzer:person-list")

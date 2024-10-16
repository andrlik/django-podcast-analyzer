# views.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import TYPE_CHECKING, ClassVar

# from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet

from podcast_analyzer.forms import AnalysisGroupForm
from podcast_analyzer.models import AnalysisGroup, Episode, Person, Podcast

# Create your views here.


class SelectPrefetchRelatedMixin:
    """
    Adds two class variables:
        prefetch_related: list[str]
        select_related: list[str]
    If they are populated, it will use them in the queryset.
    """

    model = None
    queryset = None
    ordering = None
    prefetch_related: ClassVar[list[str] | None] = None
    select_related: ClassVar[list[str] | None] = None

    def get_queryset(self):
        if not self.queryset:
            if self.model:
                qs = self.model._default_manager.all()
            else:  # no cov
                msg = "View does not have a queryset or model defined!"
                raise ImproperlyConfigured(msg)
        else:
            qs = self.queryset
        if self.select_related:
            qs = qs.select_related(*self.select_related)
        if self.prefetch_related:
            qs = qs.prefetch_related(*self.prefetch_related)
        if self.ordering:
            if isinstance(self.ordering, str):
                qs = qs.order_by(self.ordering)  # no cov, we're just mimicking Django
            else:
                qs = qs.order_by(*self.ordering)
        return qs


class PodcastListView(LoginRequiredMixin, SelectPrefetchRelatedMixin, ListView):
    """
    View all podcasts in a list.
    """

    model = Podcast
    ordering = ["title"]
    paginate_by = 25
    prefetch_related = ["episodes", "seasons", "analysis_group"]


class PodcastDetailView(LoginRequiredMixin, SelectPrefetchRelatedMixin, DetailView):
    """
    A view to see a given podcasts data.
    """

    model = Podcast
    pk_url_kwarg = "id"
    context_object_name = "podcast"
    prefetch_related = ["episodes", "seasons", "analysis_group"]


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


class PodcastDeleteView(LoginRequiredMixin, SelectPrefetchRelatedMixin, DeleteView):
    """
    For deleting a podcast record.
    """

    model = Podcast
    context_object_name = "podcast"
    pk_url_kwarg = "id"
    object: Podcast
    prefetch_related = ["episodes", "seasons", "analysis_group"]

    def get_success_url(self):
        return reverse_lazy("podcast_analyzer:podcast-list")


class PersonListView(LoginRequiredMixin, SelectPrefetchRelatedMixin, ListView):
    """View all people in a list"""

    model = Person
    pk_url_kwarg = "id"
    context_object_name = "people"
    paginate_by = 25
    ordering = ["name"]
    prefetch_related = ["hosted_episodes", "guest_appearances"]


class PersonDetailView(LoginRequiredMixin, SelectPrefetchRelatedMixin, DetailView):
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


class PersonDeleteView(LoginRequiredMixin, SelectPrefetchRelatedMixin, DeleteView):
    """Delete a person from the database."""

    model = Person
    pk_url_kwarg = "id"
    context_object_name = "person"
    prefetch_related = ["hosted_episodes", "guest_appearances"]
    object: Person

    def get_success_url(self):
        return reverse_lazy("podcast_analyzer:person-list")


class PodcastEpisodeDescendantMixin(SelectPrefetchRelatedMixin):
    """
    Allows the episode queryset to be filtered by the podcast it comes from.
    """

    podcast: Podcast | None = None
    if TYPE_CHECKING:
        queryset: QuerySet[Episode] | None

    def get_queryset(self):
        podcast_id = self.kwargs.get("podcast_id", None)  # type: ignore
        if not podcast_id:  # no cov
            raise Http404
        try:
            self.podcast = Podcast.objects.get(pk=podcast_id)
        except ObjectDoesNotExist as ode:  # no cov
            raise Http404 from ode
        self.queryset = Episode.objects.filter(podcast=self.podcast)
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # type: ignore
        context["podcast"] = self.podcast
        return context


class EpisodeListView(LoginRequiredMixin, PodcastEpisodeDescendantMixin, ListView):
    """View all episodes for given podcast"""

    model = Episode
    pk_url_kwarg = "id"
    context_object_name = "episodes"
    paginate_by = 50
    ordering = ["-ep_num"]
    select_related = ["podcast", "season"]


class EpisodeDetailView(LoginRequiredMixin, PodcastEpisodeDescendantMixin, DetailView):
    """View a given episode's details."""

    model = Episode
    pk_url_kwarg = "id"
    context_object_name = "episode"
    select_related = ["podcast", "season"]
    prefetch_related = [
        "analysis_group",
        "hosts_detected_from_feed",
        "guests_detected_from_feed",
    ]


class EpisodeUpdateView(LoginRequiredMixin, PodcastEpisodeDescendantMixin, UpdateView):
    """Edit a given episode's details."""

    model = Episode
    pk_url_kwarg = "id"
    context_object_name = "episode"
    fields = [
        "title",
        "ep_num",
        "ep_type",
        "analysis_group",
        "hosts_detected_from_feed",
        "guests_detected_from_feed",
    ]


class EpisodeDeleteView(LoginRequiredMixin, PodcastEpisodeDescendantMixin, DeleteView):
    """Delete a given episode."""

    model = Episode
    pk_url_kwarg = "id"
    context_object_name = "episode"
    object: Episode
    select_related = ["podcast", "season"]
    prefetch_related = [
        "analysis_group",
        "hosts_detected_from_feed",
        "guests_detected_from_feed",
    ]
    podcast: Podcast

    def get_success_url(self):
        return reverse_lazy(
            "podcast_analyzer:episode-list", kwargs={"podcast_id": self.podcast.pk}
        )


class AnalysisGroupListView(LoginRequiredMixin, SelectPrefetchRelatedMixin, ListView):
    """List of all analysis groups."""

    model = AnalysisGroup
    context_object_name = "groups"
    paginate_by = 25
    prefetch_related = ["podcasts", "seasons", "episodes"]
    ordering = ["name", "-created"]


class AnalysisGroupDetailView(
    LoginRequiredMixin, SelectPrefetchRelatedMixin, DetailView
):
    """Details for a given analysis group."""

    model = AnalysisGroup
    pk_url_kwarg = "id"
    context_object_name = "group"
    prefetch_related = ["podcasts", "seasons", "episodes"]


class AnalysisGroupUpdateView(
    LoginRequiredMixin, SelectPrefetchRelatedMixin, UpdateView
):
    """Update a given analysis group."""

    model = AnalysisGroup
    pk_url_kwarg = "id"
    context_object_name = "group"
    form_class = AnalysisGroupForm
    prefetch_related = ["podcasts", "seasons", "episodes"]
    object: AnalysisGroup

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["initial"]["podcasts"] = self.object.podcasts.all()
        kwargs["initial"]["seasons"] = self.object.seasons.all()
        kwargs["initial"]["episodes"] = self.object.episodes.all()
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.podcasts.set(form.cleaned_data["podcasts"])
        self.object.seasons.set(form.cleaned_data["seasons"])
        self.object.episodes.set(form.cleaned_data["episodes"])
        return super().form_valid(form)


class AnalysisGroupCreateView(LoginRequiredMixin, CreateView):
    """Create a new analysis group."""

    model = AnalysisGroup
    form_class = AnalysisGroupForm
    object: AnalysisGroup

    def form_valid(self, form):
        self.object = AnalysisGroup.objects.create(name=form.cleaned_data["name"])
        self.object.podcasts.set(form.cleaned_data["podcasts"])
        self.object.seasons.set(form.cleaned_data["seasons"])
        self.object.episodes.set(form.cleaned_data["episodes"])
        return HttpResponseRedirect(self.object.get_absolute_url())


class AnalysisGroupDeleteView(
    LoginRequiredMixin, SelectPrefetchRelatedMixin, DeleteView
):
    """Delete a given analysis group."""

    model = AnalysisGroup
    pk_url_kwarg = "id"
    context_object_name = "group"
    object: AnalysisGroup
    prefetch_related = ["podcasts", "seasons", "episodes"]

    def get_success_url(self):
        return reverse_lazy("podcast_analyzer:ag-list")

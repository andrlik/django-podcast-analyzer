# urls.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from django.urls import path

from podcast_analyzer import views

app_name = "podcast_analyzer"

urlpatterns = [
    path("", view=views.AppEntryView.as_view(), name="entry"),
    path(
        "analysis-groups/", view=views.AnalysisGroupListView.as_view(), name="ag-list"
    ),
    path(
        "analysis-groups/create/",
        view=views.AnalysisGroupCreateView.as_view(),
        name="ag-create",
    ),
    path(
        "analysis-groups/<uuid:id>/",
        view=views.AnalysisGroupDetailView.as_view(),
        name="ag-detail",
    ),
    path(
        "analysis-groups/<uuid:id>/edit/",
        view=views.AnalysisGroupUpdateView.as_view(),
        name="ag-edit",
    ),
    path(
        "analysis-groups/<uuid:id>/delete/",
        view=views.AnalysisGroupDeleteView.as_view(),
        name="ag-delete",
    ),
    path("people/", view=views.PersonListView.as_view(), name="person-list"),
    path(
        "people/<uuid:id>/", view=views.PersonDetailView.as_view(), name="person-detail"
    ),
    path(
        "people/<uuid:id>/edit/",
        view=views.PersonUpdateView.as_view(),
        name="person-edit",
    ),
    path(
        "people/<uuid:id>/delete/",
        view=views.PersonDeleteView.as_view(),
        name="person-delete",
    ),
    path("podcasts/", view=views.PodcastListView.as_view(), name="podcast-list"),
    path(
        "podcasts/add/", view=views.PodcastCreateView.as_view(), name="podcast-create"
    ),
    path(
        "podcasts/<uuid:id>/",
        view=views.PodcastDetailView.as_view(),
        name="podcast-detail",
    ),
    path(
        "podcasts/<uuid:podcast_id>/episodes/",
        view=views.EpisodeListView.as_view(),
        name="episode-list",
    ),
    path(
        "podcasts/<uuid:podcast_id>/episodes/<uuid:id>/",
        view=views.EpisodeDetailView.as_view(),
        name="episode-detail",
    ),
    path(
        "podcasts/<uuid:podcast_id>/episodes/<uuid:id>/edit/",
        view=views.EpisodeUpdateView.as_view(),
        name="episode-edit",
    ),
    path(
        "podcasts/<uuid:podcast_id>/episodes/<uuid:id>/delete/",
        view=views.EpisodeDeleteView.as_view(),
        name="episode-delete",
    ),
    path(
        "podcasts/<uuid:id>/edit/",
        view=views.PodcastUpdateView.as_view(),
        name="podcast-edit",
    ),
    path(
        "podcasts/<uuid:id>/delete/",
        view=views.PodcastDeleteView.as_view(),
        name="podcast-delete",
    ),
    path(
        "tags/<slug:tag_slug>/",
        view=views.TagPodcastListView.as_view(),
        name="tag-podcast-list",
    ),
]

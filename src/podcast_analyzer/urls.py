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
    path("", view=views.PodcastListView.as_view(), name="podcast-list"),
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
    path("add/", view=views.PodcastCreateView.as_view(), name="podcast-create"),
    path(
        "<uuid:id>/",
        view=views.PodcastDetailView.as_view(),
        name="podcast-detail",
    ),
    path(
        "<uuid:id>/edit/",
        view=views.PodcastUpdateView.as_view(),
        name="podcast-edit",
    ),
    path(
        "<uuid:id>/delete/",
        view=views.PodcastDeleteView.as_view(),
        name="podcast-delete",
    ),
]

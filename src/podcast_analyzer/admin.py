# admin.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import ngettext

from podcast_analyzer import FeedFetchError, FeedParseError
from podcast_analyzer.models import (
    AnalysisGroup,
    ArtUpdate,
    Episode,
    ItunesCategory,
    Person,
    Podcast,
    Season,
)

# Register your models here.


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    """
    Admin for detected persons.
    """

    list_display = [
        "name",
        "url",
        "has_hosted",
        "has_guested",
    ]


@admin.register(ItunesCategory)
class ItunesCategoryAdmin(admin.ModelAdmin):
    """
    Admin for iTunes Categories
    """

    list_display = ["parent_category", "name"]
    list_filter = ["parent_category"]


@admin.register(Podcast)
class PodcastAdmin(admin.ModelAdmin):
    """
    Admin for podcast records.
    """

    list_display = [
        "title",
        "site_url",
        "last_checked",
        "last_release_date",
        "itunes_explicit",
        "total_episodes",
        "total_duration_timedelta",
        "median_episode_duration_timedelta",
    ]
    list_filter = ["generator"]

    actions = ["check_for_new_episodes", "refresh_all_episodes"]

    def feed_update(
        self,
        request: HttpRequest,
        queryset: QuerySet[Podcast],
        *,
        update_existing_episodes: bool = False,
    ) -> tuple[int, int]:
        """
        Does a refresh of a list of feeds, ignoring any episodes already
        imported.
        """
        episodes_touched: int = 0
        feeds_refreshed: int = 0
        for instance in queryset:
            try:
                eps_updated: int = instance.refresh_feed(
                    update_existing_episodes=update_existing_episodes
                )
                episodes_touched += eps_updated
                feeds_refreshed += 1
            except FeedFetchError:
                self.message_user(
                    request,
                    f"Feed for {instance.title} is unreachable.",
                    messages.ERROR,
                )
            except FeedParseError as fpe:
                self.message_user(
                    request,
                    f"Parsing feed for {instance.title} resulted in error: {fpe}",
                    messages.ERROR,
                )
        return episodes_touched, feeds_refreshed

    @admin.action(description="Get new episodes")
    def check_for_new_episodes(self, request, queryset):
        """
        Refreshes the feed metadata and checks for any new episodes.
        """
        new_episodes, feeds_refreshed = self.feed_update(
            request, queryset, update_existing_episodes=False
        )
        self.message_user(
            request,
            ngettext("%d feed refreshed.", "%d feeds refreshed.", feeds_refreshed)
            % feeds_refreshed,
            messages.SUCCESS,
        )
        self.message_user(
            request,
            ngettext("%d episode added.", "%d episodes added.", new_episodes)
            % new_episodes,
            messages.SUCCESS,
        )

    @admin.action(description="Update feed and all episodes.")
    def refresh_all_episodes(self, request, queryset):
        """
        Refreshes the feed metadata, checks for new episodes, and updates
        EVERY existing episode with new data.
        """
        episodes_touched, feeds_refreshed = self.feed_update(
            request, queryset, update_existing_episodes=True
        )
        self.message_user(
            request,
            ngettext("%d feed refreshed.", "%d feeds refreshed.", feeds_refreshed)
            % feeds_refreshed,
            messages.SUCCESS,
        )
        self.message_user(
            request,
            ngettext(
                "%d episode added/refreshed.",
                "%d episodes added/refreshed.",
                episodes_touched,
            )
            % episodes_touched,
            messages.SUCCESS,
        )


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    """
    Admin for podcast seasons.
    """

    list_display = ["podcast", "season_number"]
    list_filter = ["podcast"]
    ordering = ["podcast__title", "season_number"]


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    """
    Admin for podcast episodes.
    """

    date_hierarchy = "release_datetime"
    list_display = [
        "podcast",
        "ep_num",
        "title",
        "release_datetime",
        "itunes_explicit",
        "duration",
        "mime_type",
    ]
    list_filter = ["podcast__title", "mime_type"]


@admin.register(AnalysisGroup)
class AnalysisGroupAdmin(admin.ModelAdmin):
    """
    Admin for analysis group objects.
    """

    list_display = ["name", "num_feeds", "num_seasons", "num_episodes"]


@admin.register(ArtUpdate)
class ArtUpdateAdmin(admin.ModelAdmin):
    """Admin for art update log"""

    list_display = [
        "timestamp",
        "podcast",
        "reported_mime_type",
        "actual_mime_type",
        "valid_file",
    ]
    list_filter = ["podcast", "reported_mime_type", "actual_mime_type", "valid_file"]

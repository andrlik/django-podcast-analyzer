# models.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import dataclasses
import datetime
import logging
import uuid
from collections.abc import Iterable, Sized
from io import BytesIO
from statistics import median_high
from typing import TYPE_CHECKING, Any, ClassVar

import httpx
import magic
import podcastparser
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.db import models
from django.db.models import Q, QuerySet

if TYPE_CHECKING:
    from django.db.models.manager import (
        Manager,
        ManyToManyRelatedManager,
        RelatedManager,
    )
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_q.models import Schedule
from django_q.tasks import async_task
from magic import MagicException
from tagulous.models import TagField

from podcast_analyzer import FeedFetchError, FeedParseError
from podcast_analyzer.utils import (
    split_keywords,
    update_file_extension_from_mime_type,
)

logger = logging.getLogger("podcast_analyzer")


KNOWN_GENERATOR_HOST_MAPPING: dict[str, str] = {
    "Fireside (https://fireside.fm)": "Fireside.fm",
    "https://podbean.com/": "Podbean",
    "https://simplecast.com": "Simplecast",
    "Transistor (https://transistor.fm)": "Transistor.fm",
    "acast.com": "Acast",
    "Anchor Podcasts": "Anchor/Spotify",
    "Pinecast (https://pinecast.com)": "Pinecast",
}

KNOWN_PARTIAL_GENERATOR_HOST_MAPPING: dict[str, str] = {
    "RedCircle": "RedCircle",
    "Libsyn": "Libsyn",
    "Squarespace": "Squarespace",
    "podbean.com": "Podbean",
}

KNOWN_DOMAINS_HOST_MAPPING: dict[str, str] = {
    "buzzsprout.com": "Buzzsprout",
    "fireside.fm": "Fireside.fm",
    "podbean.com": "Podbean",
    "simplecast.com": "Simplecast",
    "transistor.fm": "Transistor.fm",
    "redcircle.com": "RedCircle",
    "acast.com": "Acast",
    "pinecast.com": "Pinecast",
    "libsyn.com": "Libsyn",
    "spreaker.com": "Spreaker",
    "soundcloud.com": "Soundcloud",
    "anchor.fm": "Anchor/Spotify",
    "squarespace.com": "Squarespace",
    "blubrry.com": "Blubrry",
}

KNOWN_TRACKING_DOMAINS: dict[str, str] = {
    "podtrac": "Podtrac",
    "blubrry": "Blubrry",
}

ART_TITLE_LENGTH_LIMIT: int = 25


def podcast_art_directory_path(instance, filename):
    """
    Used for caching the podcast channel cover art.
    """
    title = instance.title
    if len(title) > ART_TITLE_LENGTH_LIMIT:
        title = title[:ART_TITLE_LENGTH_LIMIT]
    return f"{title.replace(" ", "_")}_{instance.id}/{filename}"


class TimeStampedModel(models.Model):
    """
    An abstract model with created and modified timestamp fields.
    """

    created = models.DateTimeField(
        auto_now_add=True, help_text=_("Time this object was created.")
    )
    modified = models.DateTimeField(
        auto_now=True, help_text=_("Time of last modification")
    )

    class Meta:
        abstract = True


class UUIDTimeStampedModel(TimeStampedModel):
    """
    Base model for all our objects records.

    Attributes:
        id (models.UUIDField): Unique ID.
        created (models.DateTimeField): Creation time.
        modified (models.DateTimeField): Modification time.
        cached_properties (list[str]): Names of cached properties that should be
            dropped on refresh_from_db
    """

    cached_properties: ClassVar[list[str]] = []

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True

    def refresh_from_db(self, using=None, fields=None, **kwargs: Any):
        """
        Also clear out cached_properties.
        """
        super().refresh_from_db(using, fields, **kwargs)
        for prop in self.cached_properties:
            try:
                del self.__dict__[prop]
            except KeyError:  # no cov
                pass


class ItunesCategory(TimeStampedModel):
    """
    Itunes categories.

    Attributes:
        name (str): Name of the category
        parent_category (ItunesCategory | None): Relation to another category as parent.
    """

    name = models.CharField(max_length=250)
    parent_category = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        verbose_name = "iTunes Category"
        verbose_name_plural = "iTunes Categories"
        ordering: ClassVar[list[str]] = ["parent_category__name", "name"]

    def __str__(self):  # no cov
        if self.parent_category is not None:
            return f"{self.parent_category.name}: {self.name}"
        return self.name


class AnalysisGroup(UUIDTimeStampedModel):
    """
    Abstract group to assign a record to for purposes of analysis.

    Attributes:
        name (str): Name of the group.
        podcasts (QuerySet[Podcast]): Podcasts explicitly linked to group.
        seasons (QuerySet[Season]): Seasons explicitly linked to group.
        episodes (QuerySet[Episode]): Episodes explicitly linked to group.
    """

    cached_properties: ClassVar[list[str]] = [
        "all_podcasts",
        "all_people",
        "all_episodes",
        "all_seasons",
        "median_episode_duration",
        "total_duration_seconds",
        "release_frequencies",
    ]
    if TYPE_CHECKING:
        podcasts: ManyToManyRelatedManager["Podcast", "Podcast"]
        seasons: ManyToManyRelatedManager["Season", "Season"]
        episodes: ManyToManyRelatedManager["Episode", "Episode"]
    name = models.CharField(max_length=250, help_text=_("Identifier for group."))
    description = models.TextField(
        blank=True,
        default="",
        help_text=_("Description of group for your future reference."),
    )

    class Meta:
        ordering: ClassVar[list[str]] = ["name", "created"]

    def __str__(self):  # no cov
        return self.name

    def get_absolute_url(self):
        return reverse_lazy("podcast_analyzer:ag-detail", kwargs={"id": self.pk})

    def num_podcasts(self) -> int:
        """
        Returns the total number of podcasts in this group, both explicitly
        and implied.
        """
        podcasts = self.all_podcasts
        return podcasts.count()

    def get_num_dormant_podcasts(self) -> int:
        """Get the podcasts connected, explict or implicit, that are dormant."""
        dormant_podcasts = self.all_podcasts.filter(dormant=True)
        return dormant_podcasts.count()

    def get_num_podcasts_with_itunes_data(self) -> int:
        """Include itunes specific elements in feed."""
        return self.all_podcasts.filter(feed_contains_itunes_data=True).count()

    def get_num_podcasts_with_podcast_index_data(self) -> int:
        """Includes Podcast index elements in feed."""
        return self.all_podcasts.filter(feed_contains_podcast_index_data=True).count()

    def get_num_podcasts_with_donation_data(self) -> int:
        """Feed contains structure donation/funding data."""
        return self.all_podcasts.filter(
            feed_contains_structured_donation_data=True
        ).count()

    def get_num_podcasts_using_trackers(self) -> int:
        """Feeds that contain what appears to be third-party tracking data."""
        return self.all_podcasts.filter(feed_contains_tracking_data=True).count()

    def get_counts_by_release_frequency(self) -> dict[str, int]:
        """
        Get counts of podcasts by release frequency.

        NOTE: This is based on podcasts' current release frequency. We can't reliably
        calculate this based on isolated seasons and episodes.
        """
        podcasts = self.get_all_podcasts()
        frequency_dict = {
            "daily": podcasts.filter(
                release_frequency=Podcast.ReleaseFrequency.DAILY
            ).count(),
            "often": podcasts.filter(
                release_frequency=Podcast.ReleaseFrequency.OFTEN
            ).count(),
            "weekly": podcasts.filter(
                release_frequency=Podcast.ReleaseFrequency.WEEKLY
            ).count(),
            "biweekly": podcasts.filter(
                release_frequency=Podcast.ReleaseFrequency.BIWEEKLY
            ).count(),
            "monthly": podcasts.filter(
                release_frequency=Podcast.ReleaseFrequency.MONTHLY
            ).count(),
            "adhoc": podcasts.filter(
                release_frequency=Podcast.ReleaseFrequency.ADHOC
            ).count(),
            "unknown": podcasts.filter(
                release_frequency=Podcast.ReleaseFrequency.UNKNOWN
            ).count(),
        }
        return frequency_dict

    @cached_property
    def release_frequencies(self) -> dict[str, int]:
        return self.get_counts_by_release_frequency()

    def num_seasons(self) -> int:
        """
        Returns the number of seasons associated with this group, both
        direct associations and implicit associations due to an assigned feed.
        """
        seasons = self.all_seasons
        return seasons.count()

    def num_episodes(self) -> int:
        """
        Returns the number of episodes associated with this group, whether directly
        or via an assigned season or podcast.
        """
        episodes = self.all_episodes
        return episodes.count()

    def num_people(self) -> int:
        """
        Returns the total number of people detected from episodes associated with
        this group.
        """
        return self.all_people.count()

    @cached_property
    def median_episode_duration(self) -> int:
        """The media duration of episodes in seconds."""
        return calculate_median_episode_duration(self.all_episodes)

    def get_median_duration_timedelta(self) -> datetime.timedelta | None:
        """Return the median duration of episodes as a timedelta."""
        median_duration = self.median_episode_duration
        if median_duration == 0:
            return None
        return datetime.timedelta(seconds=median_duration)

    def get_total_duration_seconds(self) -> int:
        """
        Calculate the total duration of all episodes, explicit and implied
        for this group.
        """
        episodes = self.all_episodes
        if not episodes.exists():
            return 0
        return episodes.aggregate(models.Sum("itunes_duration"))["itunes_duration__sum"]

    @cached_property
    def total_duration_seconds(self) -> int:
        return self.get_total_duration_seconds()

    def get_total_duration_timedelta(self) -> datetime.timedelta | None:
        duration = self.total_duration_seconds
        if duration == 0:
            return None
        return datetime.timedelta(seconds=self.get_total_duration_seconds())

    def get_itunes_categories_with_count(self) -> QuerySet[ItunesCategory]:
        """
        For all associated podcasts, explicit or implicit, return their
        associated distinct categories with counts.
        """
        ag_pods = models.Count("podcasts", filter=Q(podcasts__in=self.all_podcasts))
        return (
            ItunesCategory.objects.filter(podcasts__in=self.all_podcasts)
            .annotate(ag_pods=ag_pods)
            .select_related("parent_category")
            .order_by("parent_category__name", "name")
        )

    def get_all_episodes(self) -> QuerySet["Episode"]:
        """
        Get all episodes, explict and implied, for this Analysis Group.
        """
        podcasts = self.podcasts.all()
        seasons = self.seasons.exclude(podcast__in=podcasts)
        episode_ids = list(
            self.episodes.exclude(podcast__in=podcasts)
            .exclude(season__in=seasons)
            .values_list("id", flat=True)
        )
        for podcast in podcasts:
            if podcast.episodes.exists():
                episode_ids += list(podcast.episodes.all().values_list("id", flat=True))
        for season in seasons:
            episode_ids += list(season.episodes.all().values_list("id", flat=True))
        return Episode.objects.filter(id__in=episode_ids)

    def get_all_seasons(self) -> QuerySet["Season"]:
        """
        Returns a QuerySet of all Season objects for this group, both explicit
        and implied.
        """
        podcasts = self.podcasts.all()
        season_ids = list(
            self.seasons.exclude(podcast__id__in=podcasts).values_list("id", flat=True)
        )
        for podcast in podcasts:
            if podcast.seasons.exists():
                season_ids += list(podcast.seasons.all().values_list("id", flat=True))
        return Season.objects.filter(id__in=season_ids)

    def get_all_podcasts(self) -> QuerySet["Podcast"]:
        """
        Returns a QuerySet of all Podcast objects for this group, both explicitly
        assigned and implied by Season and Episode objects.
        """
        podcast_ids = list(self.podcasts.all().values_list("id", flat=True))
        podcast_ids_from_seasons = list(
            self.seasons.exclude(podcast__id__in=podcast_ids)
            .values_list("podcast__id", flat=True)
            .distinct()
        )
        podcast_ids_from_episodes = list(
            self.episodes.exclude(podcast__id__in=podcast_ids)
            .values_list("podcast__id", flat=True)
            .distinct()
        )
        podcast_ids = podcast_ids + podcast_ids_from_seasons + podcast_ids_from_episodes
        logger.debug(f"Found {len(podcast_ids)} podcast ids to fetch.")
        podcasts = Podcast.objects.filter(id__in=podcast_ids).prefetch_related(
            "itunes_categories"
        )
        return podcasts

    def get_all_people(self) -> QuerySet["Person"]:
        """Returns a QuerySet of all People that are associated with this group."""
        episodes_with_people = self.all_episodes.filter(
            Q(hosts_detected_from_feed__isnull=False)
            | Q(guests_detected_from_feed__isnull=False)
        )
        people = Person.objects.filter(
            Q(hosted_episodes__in=episodes_with_people)
            | Q(guest_appearances__in=episodes_with_people)
        ).distinct()
        return people

    @cached_property
    def all_people(self) -> QuerySet["Person"]:
        return self.get_all_people()

    @cached_property
    def all_podcasts(self) -> QuerySet["Podcast"]:
        return self.get_all_podcasts()

    @cached_property
    def all_episodes(self) -> QuerySet["Episode"]:
        return self.get_all_episodes()

    @cached_property
    def all_seasons(self) -> QuerySet["Season"]:
        return self.get_all_seasons()


class ArtUpdate(models.Model):
    """
    Model for capturing art update events. Useful for debugging.

    Attributes:
        podcast (Podcast): Podcast that this update relates to.
        timestamp (datetime): Timestamp when the update was requested.
        reported_mime_type (str): The mime_type returned by the remote server.
        actual_mime_type (str): The actual mime_type of the file.
        valid_file (bool): Whether the file was valid and of the allowed mime types.
    """

    podcast = models.ForeignKey(
        "Podcast", on_delete=models.CASCADE, related_name="art_updates"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    reported_mime_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text=_("What the server said the mime type was."),
    )
    actual_mime_type = models.CharField(
        max_length=50, null=True, blank=True, help_text=_("The actual mime type")
    )
    valid_file = models.BooleanField(
        default=False, help_text=_("Was this a valid art file or corrupt/unsupported?")
    )

    def __str__(self):  # no cov
        return f"Art Update: {self.podcast.title} at {self.timestamp}"


class Podcast(UUIDTimeStampedModel):
    """
    Model for a given podcast feed.

    Attributes:
        title (str): The title of the podcast.
        rss_feed (str): The URL of the RSS feed of the podcast.
        podcast_cover_art_url (str | None): The remove URL of the podcast cover art.
        podcast_cached_cover_art (File | None): The cached cover art.
        last_feed_update (datetime | None): When the podcast feed was last updated.
        dormant (bool): Whether the podcast is dormant or not.
        last_checked (datetime): When the podcast feed was last checked.
        author (str | None): The author of the podcast.
        language (str | None): The language of the podcast.
        generator (str | None): The reported generator of the feed.
        email (str | None): The email listed in the feed.
        site_url (str | None): The URL of the podcast site.
        itunes_explicit (bool | None): Whether the podcast has an explict tag on iTunes.
        itunes_feed_type (str | None): The feed type of the podcast feed.
        description (str | None): The provided description of the podcast.
        release_frequency (str): The detected release frequency.
            One of: daily, often, weekly, biweekly, monthly, adhoc, unknown.
        feed_contains_itunes_data (bool): Whether the podcast feed contains itunes data.
        feed_contains_podcast_index_data (bool): Whether the podcast feed contains
            podcast index elements.
        feed_contains_tracking_data (bool): Whether the podcast feed contains
            third-party tracking data.
        feed_contains_structured_donation_data (bool): Whether the feed contains
            donation links.
        funding_url (str | None): Provided URL for donations/support.
        probable_feed_host (str | None): Current assessment of the feed hosting company.
        itunes_categories (QuerySet[ItunesCategory]): The listed iTunes categories.
        tags (list[str]): The list of keywords/tags declared in the feed.
        analysis_group (QuerySet[AnalysisGroup]): The associated analysis groups.
    """

    cached_properties: ClassVar[list[str]] = [
        "total_duration_seconds",
        "last_release_date",
        "median_episode_duration",
    ]

    class ReleaseFrequency(models.TextChoices):
        """
        Choices for release frequency.
        """

        DAILY = "daily", _("Daily")
        OFTEN = "often", _("Mulitple times per week.")
        WEEKLY = "weekly", _("Weekly")
        BIWEEKLY = "biweekly", _("Biweekly")
        MONTHLY = "monthly", _("Monthly")
        ADHOC = "adhoc", _("Occasionally")
        UNKNOWN = "pending", _("Not Known Yet")

    if TYPE_CHECKING:
        episodes: RelatedManager["Episode"]
        seasons: RelatedManager["Season"]
        objects: Manager["Podcast"]

    title = models.CharField(
        max_length=250, db_index=True, help_text=_("Title of podcast")
    )
    rss_feed = models.URLField(
        help_text=_("URL of podcast feed."), db_index=True, unique=True
    )
    podcast_cover_art_url = models.URLField(
        max_length=500,
        help_text=_("Link to cover art for podcast."),
        null=True,
        blank=True,
    )
    podcast_cached_cover_art = models.ImageField(
        upload_to=podcast_art_directory_path, null=True, blank=True
    )
    podcast_art_cache_update_needed = models.BooleanField(default=False)
    last_feed_update = models.DateTimeField(
        null=True, blank=True, help_text=_("Last publish date per feed.")
    )
    dormant = models.BooleanField(
        default=False, help_text=_("Is this podcast dormant?")
    )
    last_checked = models.DateTimeField(
        null=True, blank=True, help_text=_("Last scan of feed completed at.")
    )
    author = models.CharField(
        max_length=250, help_text=_("Identfied feed author"), null=True, blank=True
    )
    language = models.CharField(
        max_length=10, help_text=_("Language of podcast"), null=True, blank=True
    )
    generator = models.CharField(
        max_length=250,
        help_text=_("Identified generator for feed."),
        null=True,
        blank=True,
    )
    email = models.EmailField(null=True, blank=True)
    site_url = models.URLField(null=True, blank=True)
    itunes_explicit = models.BooleanField(default=False)
    itunes_feed_type = models.CharField(max_length=25, null=True, blank=True)
    description = models.TextField(
        null=True, blank=True, help_text=_("Description of podcast")
    )
    release_frequency = models.CharField(  # type: ignore
        max_length=20,
        choices=ReleaseFrequency.choices,
        default=ReleaseFrequency.UNKNOWN,
        db_index=True,
        help_text=_(
            "How often this podcast releases, on average,"
            "not including trailers and bonus episodes."
        ),
    )
    feed_contains_itunes_data = models.BooleanField(default=False)
    feed_contains_podcast_index_data = models.BooleanField(default=False)
    feed_contains_tracking_data = models.BooleanField(default=False)
    feed_contains_structured_donation_data = models.BooleanField(default=False)
    funding_url = models.URLField(null=True, blank=True)
    probable_feed_host = models.CharField(max_length=250, null=True, blank=True)
    itunes_categories = models.ManyToManyField(
        ItunesCategory, blank=True, related_name="podcasts"
    )
    tags = TagField(  # type: ignore
        blank=True,
        get_absolute_url=lambda tag: reverse_lazy(  # type: ignore
            "podcast_analyzer:tag-podcast-list", kwargs={"tag_slug": tag.slug}
        ),
    )
    analysis_group = models.ManyToManyField(
        AnalysisGroup, related_name="podcasts", blank=True
    )

    class Meta:
        ordering: ClassVar[Iterable[str]] = ["title"]

    def __str__(self):  # no cov
        return self.title

    def get_absolute_url(self):  # no cov
        return reverse_lazy("podcast_analyzer:podcast-detail", kwargs={"id": self.id})

    @cached_property
    def total_duration_seconds(self) -> int:
        """
        Returns the total duration of all episodes in seconds.
        """
        if self.episodes.exists():
            return self.episodes.aggregate(models.Sum("itunes_duration"))[
                "itunes_duration__sum"
            ]
        return 0

    @property
    def total_duration_timedelta(self) -> datetime.timedelta | None:
        """
        Returns the total duration of the podcast as a timedelta object.
        """
        if not self.total_duration_seconds:
            return None
        return datetime.timedelta(seconds=self.total_duration_seconds)

    @cached_property
    def total_episodes(self) -> int:
        """
        Returns the total number of episodes of the podcast.
        """
        return self.episodes.count()

    @cached_property
    def median_episode_duration(self) -> int:
        """
        Returns the media duration across all episodes.
        """
        return calculate_median_episode_duration(self.episodes.all())

    @property
    def median_episode_duration_timedelta(self) -> datetime.timedelta:
        """
        Returns the median duration as a timedelta.
        """
        return datetime.timedelta(seconds=self.median_episode_duration)

    @cached_property
    def last_release_date(self) -> datetime.datetime | None:
        """
        Return the most recent episode's release datetime.
        """
        if self.episodes.exists():
            return self.episodes.latest("release_datetime").release_datetime
        return None

    async def alast_release_date(self) -> datetime.datetime | None:
        """
        Do an async fetch of the last release date.
        """
        if await self.episodes.aexists():
            last_ep = await self.episodes.alatest("release_datetime")
            return last_ep.release_datetime
        return None

    def refresh_feed(self, *, update_existing_episodes: bool = False) -> int:
        """
        Fetches the source feed and updates the record. This is best handled as
        a scheduled task in a worker process.

        Args:
            update_existing_episodes (bool): Update existing episodes with new data?

        Returns:
            An int representing the number of added episodes.
        """
        try:
            podcast_dict = self.get_feed_data()
        except FeedFetchError as fe:
            logger.error(f"Attempt to fetch feed {self.rss_feed} failed: {fe}")
            return 0
        except FeedParseError as fpe:
            logger.error(str(fpe))
            return 0
        self.update_podcast_metadata_from_feed_data(podcast_dict)
        try:
            episode_list = podcast_dict.get("episodes", [])
        except KeyError:  # no cov
            logger.info(f"Feed {self.rss_feed} contains no episodes.")
            return 0
        episodes_touched = self.update_episodes_from_feed_data(
            episode_list, update_existing_episodes=update_existing_episodes
        )
        logger.debug(
            f"Refreshed feed for {self.title} and "
            f"found updated {episodes_touched} episodes."
        )
        if self.podcast_art_cache_update_needed:
            async_task(self.fetch_podcast_cover_art)
        async_task("podcast_analyzer.tasks.run_feed_analysis", self)
        return episodes_touched

    def get_feed_data(self) -> dict[str, Any]:
        """
        Fetch a remote feed and return the rendered dict.

        Returns:
            A dict from the `podcastparser` library representing all the feed data.
        """
        true_url: str = self.rss_feed
        with httpx.Client(timeout=5) as client:
            try:
                r = client.get(
                    self.rss_feed,
                    follow_redirects=True,
                    headers={"user-agent": "gPodder/3.1.4 (http://gpodder.org/) Linux"},
                )
            except httpx.RequestError as reqerr:  # no cov
                msg = "Retrieving feed resulted in a request error!"
                raise FeedFetchError(msg) from reqerr
            if r.status_code != httpx.codes.OK:
                msg = f"Got status {r.status_code} when fetching {self.rss_feed}"
                raise FeedFetchError(msg)
            if r.url != true_url:
                true_url = str(r.url)
                prev_resp = r.history[-1]
                if prev_resp.status_code == httpx.codes.MOVED_PERMANENTLY:
                    self.rss_feed = true_url
                    self.save(update_fields=["rss_feed"])
            data_stream = BytesIO(r.content)
        try:
            result_set: dict[str, Any] = podcastparser.parse(true_url, data_stream)
        except podcastparser.FeedParseError as fpe:
            err_msg = f"Error parsing feed data for {true_url}: {fpe}"
            logger.error(err_msg)
            raise FeedParseError(err_msg) from fpe
        return result_set

    def update_podcast_metadata_from_feed_data(self, feed_dict: dict[str, Any]) -> None:
        """
        Given the parsed feed data, update the podcast channel level metadata
        in this record.
        """
        feed_field_mapping = {
            "title": "title",
            "description": "description",
            "link": "site_url",
            "generator": "generator",
            "language": "language",
            "funding_url": "funding_url",
            "type": "itunes_feed_type",
        }
        feed_cover_art_url = feed_dict.get("cover_url", None)
        if (
            feed_cover_art_url is not None
            and self.podcast_cover_art_url != feed_cover_art_url
        ):
            logger.debug(
                f"Adding podcast {self.title} to list of podcasts "
                "that must have cached cover art updated."
            )
            self.podcast_art_cache_update_needed = True
            self.podcast_cover_art_url = feed_cover_art_url
        for key in feed_dict.keys():
            if "itunes" in key:
                self.feed_contains_itunes_data = True
            if key in ("funding_url", "locked"):
                self.feed_contains_podcast_index_data = True
        for key, value in feed_field_mapping.items():
            setattr(self, value, feed_dict.get(key, None))
        if self.feed_contains_itunes_data:
            self.itunes_explicit = feed_dict.get("explicit", False)
            author_dict: dict[str, str] | None = feed_dict.get("itunes_owner", None)
            if author_dict is not None:
                self.author = author_dict["name"]
                self.email = author_dict.get("email")
            feed_categories = feed_dict.get("itunes_categories", [])
            category_data = []
            for category in feed_categories:
                parent, created = ItunesCategory.objects.get_or_create(
                    name=category[0], parent_category=None
                )

                if len(category) > 1:
                    cat, created = ItunesCategory.objects.get_or_create(
                        name=category[1], parent_category=parent
                    )

                    category_data.append(cat)
                else:
                    category_data.append(parent)
            self.itunes_categories.clear()
            self.itunes_categories.add(*category_data)
            logger.debug(
                f"Adding feed keywords of {feed_dict.get('itunes_keywords', [])}"
            )
            self.tags = split_keywords(feed_dict.get("itunes_keywords", []))
        if self.funding_url is not None:
            self.feed_contains_structured_donation_data = True
        self.last_checked = timezone.now()
        self.save()

    def fetch_podcast_cover_art(self) -> None:
        """
        Does a synchronous request to fetch the cover art of the podcast.
        """
        if (
            not self.podcast_art_cache_update_needed
            or self.podcast_cover_art_url is None
        ):  # no cov
            return
        try:
            r = httpx.get(self.podcast_cover_art_url, timeout=5)
            logger.debug(
                f"Fetched document with content type: {r.headers.get('Content-Type')}"
            )
        except httpx.RequestError:  # no cov
            return  # URL is not retrievable

        if r.status_code == httpx.codes.OK:
            reported_type = r.headers.get("Content-Type", default=None)
            logger.debug(
                "Retrieved a file with reported mimetype of "
                f"{r.headers.get('Content-Type')}!"
            )
            file_bytes = BytesIO(r.content)
            self.process_cover_art_data(
                file_bytes,
                cover_art_url=self.podcast_cover_art_url,
                reported_mime_type=reported_type,
            )

    async def afetch_podcast_cover_art(self) -> None:
        """
        Does an async request to fetch the cover art of the podcast.
        """
        if (
            not self.podcast_art_cache_update_needed
            or self.podcast_cover_art_url is None
        ):  # no cov
            return
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                r = await client.get(self.podcast_cover_art_url)
            except httpx.RequestError:  # no cov
                return  # URL is not retrievable.
        if r.status_code == httpx.codes.OK:
            reported_mime_type = r.headers.get("Content-Type", default=None)
            file_bytes = BytesIO(r.content)
            await sync_to_async(self.process_cover_art_data)(
                cover_art_data=file_bytes,
                cover_art_url=self.podcast_cover_art_url,
                reported_mime_type=reported_mime_type,
            )

    def process_cover_art_data(
        self,
        cover_art_data: BytesIO,
        cover_art_url: str,
        reported_mime_type: str | None,
    ) -> None:
        """
        Takes the received art from a given art update and then attempts to process it.

        Args:
            cover_art_data (BytesIO): the received art data.
            cover_art_url (str): the file name of the art data.
            reported_mime_type (str): Mime type reported by the server to be validated.
        """
        filename = cover_art_url.split("/")[-1]
        if "?" in filename:
            filename = filename.split("?")[0]
        art_file = File(cover_art_data, name=filename)
        update_record = ArtUpdate(podcast=self, reported_mime_type=reported_mime_type)
        try:
            actual_type = magic.from_buffer(cover_art_data.read(2048), mime=True)
            logger.debug(f"Actual mime type is {actual_type}")
            update_record.actual_mime_type = actual_type
            update_record.valid_file = True
        except MagicException as m:  # no cov
            logger.error(f"Error parsing actual mime type: {m}")
            update_record.valid_file = False
        if update_record.valid_file and update_record.actual_mime_type in [
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
        ]:
            filename = update_file_extension_from_mime_type(
                mime_type=update_record.actual_mime_type, filename=filename
            )
            logger.debug(
                "Updating cached cover art using new file "
                f"with mime type of {update_record.actual_mime_type}"
            )
            self.podcast_cached_cover_art.save(
                name=filename,
                content=art_file,
                save=False,
            )
            self.podcast_art_cache_update_needed = False
            self.save()
        else:
            logger.error(
                f"File mime type of {update_record.actual_mime_type} is "
                "not in allowed set!"
            )
            update_record.valid_file = False
            update_record.save()

    def update_episodes_from_feed_data(
        self,
        episode_list: list[dict[str, Any]],
        *,
        update_existing_episodes: bool = False,
    ) -> int:
        """
        Given a list of feed items representing episodes, process them into
        records.

        Args:
            episode_list (list[dict[str, Any]): The `episodes` from a parsed feed.
            update_existing_episodes (bool): Update existing episodes?

        Returns:
            The number of episodes created or updated.
        """
        num_eps_touched = 0
        for episode in episode_list:
            if (
                episode.get("payment_url", None) is not None
                and not self.feed_contains_structured_donation_data
            ):
                self.feed_contains_structured_donation_data = True
                self.save()
            edits_made = Episode.create_or_update_episode_from_feed(
                podcast=self,
                episode_dict=episode,
                update_existing_episodes=update_existing_episodes,
            )

            if edits_made:
                num_eps_touched += 1
        return num_eps_touched

    async def analyze_feed(
        self, episode_limit: int = 0, *, full_episodes_only: bool = True
    ) -> None:
        """
        Does additional analysis on release schedule, probable host,
        and if 3rd party tracking prefixes appear to be present.

        Args:
            episode_limit (int): Limit the result to the last n episodes. Zero for no limit. Default 0.
            full_episodes_only (bool): Exclude bonus episodes and trailers from analysis. Default True.
        """  # noqa: E501
        logger.info(f"Starting feed analysis for {self.title}")
        await self.analyze_host()
        await self.analyze_feed_for_third_party_analytics()
        episodes = self.episodes.all()
        if full_episodes_only:
            episodes = episodes.filter(ep_type="full")
        if episode_limit > 0:
            episodes = episodes.order_by("-release_datetime")[:episode_limit]
        await self.set_release_frequency(episodes)
        await self.set_dormant()

    def calculate_next_refresh_time(
        self, last_release_date: datetime.datetime
    ) -> datetime.datetime:
        """
        Given a podcast object, calculate the ideal next refresh time.

        Args:
            last_release_date (datetime): Provide the last release date of an episode.
        Returns:
            Datetime for next refresh.
        """
        frequency_day_mapping = {
            "daily": 1,
            "often": 3,
            "weekly": 7,
            "biweekly": 14,
            "monthly": 30,
            "adhoc": 60,
        }
        refresh_interval: datetime.timedelta = datetime.timedelta(
            days=frequency_day_mapping[self.release_frequency]
        )
        if self.dormant:
            refresh_interval = datetime.timedelta(days=60)
        next_run: datetime.datetime = last_release_date + refresh_interval
        while next_run < timezone.now():
            next_run = next_run + refresh_interval
        return next_run

    def schedule_next_refresh(
        self, last_release_date: datetime.datetime | None = None
    ) -> None:
        """
        Given a podcast object, schedule it's next refresh
        in the worker queue.

        """
        frequency_schedule_matching = {
            "daily": Schedule.DAILY,
            "often": Schedule.ONCE,
            "weekly": Schedule.WEEKLY,
            "biweekly": Schedule.BIWEEKLY,
            "monthly": Schedule.MONTHLY,
            "adhoc": Schedule.ONCE,
        }
        if last_release_date is None and self.last_release_date is not None:
            last_release_date = self.last_release_date
        if last_release_date is None:
            logger.error(
                f"Cannot schedule next refresh for {self} because there is no "
                "value for last_release_date"
            )
            return
        logger.debug("Received request to schedule next run...")
        if self.release_frequency != "pending":
            next_run: datetime.datetime = self.calculate_next_refresh_time(
                last_release_date
            )
            logger.debug(
                f"Scheduling next feed refresh for {self.title} for {next_run}"
            )
            refresh_schedule, created = Schedule.objects.get_or_create(
                func="django_podcast_analyzer.podcast_data.tasks.async_refresh_feed",
                kwargs=f"podcast_id='{self.id}'",
                name=f"{self.title} Refresh",
                defaults={
                    "repeats": -1,
                    "schedule_type": frequency_schedule_matching[
                        self.release_frequency
                    ],
                    "next_run": next_run,
                },
            )
            if not created:  # no cov, this is the same as above
                refresh_schedule.schedule_type = frequency_schedule_matching[
                    self.release_frequency
                ]
                refresh_schedule.next_run = next_run
                refresh_schedule.save()

    async def set_dormant(self) -> None:
        """
        Check if latest episode is less than 65 days old, and set
        `dormant` to true if so.
        """
        latest_ep: Episode | None
        try:
            latest_ep = await self.episodes.alatest("release_datetime")
        except ObjectDoesNotExist:
            latest_ep = None
        if not latest_ep or latest_ep.release_datetime is None:
            logger.warning("No latest episode. Cannot calculate dormancy.")
            return
        elif timezone.now() - latest_ep.release_datetime > datetime.timedelta(days=65):
            self.dormant = True
        else:
            self.dormant = False
        await self.asave()

    async def set_release_frequency(self, episodes: QuerySet["Episode"]) -> None:
        """
        Calculate and set the release frequency.
        """
        if await episodes.acount() < 5:  # noqa: PLR2004
            self.release_frequency = self.ReleaseFrequency.UNKNOWN
            logger.debug(
                f"Not enough episodes for {self.title} to do a release "
                "schedule analysis."
            )
        else:
            median_release_diff = await self.calculate_median_release_difference(
                episodes
            )
            if median_release_diff <= datetime.timedelta(days=2):
                self.release_frequency = self.ReleaseFrequency.DAILY
            elif median_release_diff <= datetime.timedelta(days=5):
                self.release_frequency = self.ReleaseFrequency.OFTEN
            elif median_release_diff <= datetime.timedelta(days=8):
                self.release_frequency = self.ReleaseFrequency.WEEKLY
            elif median_release_diff <= datetime.timedelta(days=15):
                self.release_frequency = self.ReleaseFrequency.BIWEEKLY
            elif median_release_diff <= datetime.timedelta(days=33):
                self.release_frequency = self.ReleaseFrequency.MONTHLY
            else:
                self.release_frequency = self.ReleaseFrequency.ADHOC
        await self.asave()

    @staticmethod
    async def calculate_median_release_difference(
        episodes: QuerySet["Episode"],
    ) -> datetime.timedelta:
        """
        Given a queryset of episodes, calculate the median difference and return it.

        Args:
            episodes (QuerySet[Episode]): Episodes to use for calculation.
        Returns:
            A timedelta object representing the median difference between releases.
        """
        release_dates: list[datetime.datetime | None] = [
            ep.release_datetime async for ep in episodes.order_by("release_datetime")
        ]
        last_release: datetime.datetime | None = None
        release_deltas: list[int] = []
        for release in release_dates:
            if last_release is not None and release is not None:
                release_deltas.append(int((release - last_release).total_seconds()))
            last_release = release
        median_release = median_high(release_deltas)
        return datetime.timedelta(seconds=median_release)

    async def analyze_host(self):
        """
        Attempt to determine the host for a given podcast based on what information we
        can see.
        """
        if self.generator is not None:
            if self.generator in list(KNOWN_GENERATOR_HOST_MAPPING):
                self.probable_feed_host = KNOWN_GENERATOR_HOST_MAPPING[self.generator]
            else:
                for key, value in KNOWN_PARTIAL_GENERATOR_HOST_MAPPING.items():
                    if key in self.generator:
                        self.probable_feed_host = value
        if self.probable_feed_host is None:
            # Evaluate last set of 10 episodes.
            if await self.episodes.aexists():
                async for ep in self.episodes.all().order_by("-release_datetime")[:10]:
                    if ep.download_url is not None:
                        for key, value in KNOWN_DOMAINS_HOST_MAPPING.items():
                            if (
                                self.probable_feed_host is None
                                and key in ep.download_url
                            ):
                                self.probable_feed_host = value
        if not self.probable_feed_host:
            return
        await self.asave()

    async def analyze_feed_for_third_party_analytics(self) -> None:
        """
        Check if we spot any known analytics trackers.
        """
        async for ep in self.episodes.all()[:10]:
            if ep.download_url is not None:
                for key, _value in KNOWN_TRACKING_DOMAINS.items():
                    if key in ep.download_url:
                        self.feed_contains_tracking_data = True
        await self.asave()


@dataclasses.dataclass
class PodcastAppearanceData:
    """
    Dataclass for sending back structured appearance data for an individual
    on a single podcast.

    Attributes:
        podcast (Podcast): Podcast the data relates to.
        hosted_episodes (QuerySet[Episode]): Episodes hosted by them.
        guested_episodes (QuerySet[Episode]): Episodes where they appeared as a guest.
    """

    podcast: Podcast
    hosted_episodes: QuerySet["Episode"]
    guested_episodes: QuerySet["Episode"]


class Person(UUIDTimeStampedModel):
    """
    People detected from structured data in podcast feed.
    Duplicates are possible if data is tracked lazily.

    Attributes:
        name (str): Name of the person.
        url (str | None): Reported URL of the person.
        img_url (str | None): Reported image URL of the person.
        hosted_episodes (QuerySet[Episode]): Episodes this person has hosted.
        guest_appearances (QuerySet[Episode]): Episodes this person has a
            guest appearance.
    """

    cached_properties: ClassVar[list[str]] = [
        "has_hosted",
        "has_guested",
        "distinct_podcasts",
    ]

    if TYPE_CHECKING:
        hosted_episodes: ManyToManyRelatedManager["Episode", "Episode"]
        guest_appearances: ManyToManyRelatedManager["Episode", "Episode"]

    name = models.CharField(max_length=250)
    url = models.URLField(
        null=True, blank=True, help_text=_("Website link for the person")
    )
    img_url = models.URLField(
        null=True, blank=True, help_text=_("URL of the person's avatar image.")
    )

    class Meta:
        verbose_name_plural = "People"
        ordering: ClassVar[list[str]] = ["name"]

    def __str__(self):  # no cov
        return self.name

    def get_absolute_url(self) -> str:
        return reverse_lazy("podcast_analyzer:person-detail", kwargs={"id": self.id})

    @cached_property
    def has_hosted(self) -> int:
        """
        Counts the number of episodes where they have been listed as a host.
        """
        return self.hosted_episodes.count()  # no cov

    @cached_property
    def has_guested(self) -> int:
        """
        Counting the number of guest appearances.
        """
        return self.guest_appearances.count()  # no cov

    def get_total_episodes(self) -> int:
        """Get the total number of episodes this person appeared on."""
        return self.hosted_episodes.count() + self.guest_appearances.count()

    def get_distinct_podcasts(self):
        """
        Return a queryset of the distinct podcasts this person has appeared in.
        """
        hosted_podcasts = Podcast.objects.filter(
            id__in=list(
                self.hosted_episodes.all()
                .values_list("podcast__id", flat=True)
                .distinct()
            )
        )
        logger.debug(f"Found {hosted_podcasts.count()} unique hosted podcasts...")
        guested_podcasts = Podcast.objects.filter(
            id__in=list(
                self.guest_appearances.all()
                .values_list("podcast__id", flat=True)
                .distinct()
            )
        )
        logger.debug(f"Found {guested_podcasts.count()} unique guest podcasts...")
        combined_podcast_ids = set(
            [p.id for p in hosted_podcasts] + [p.id for p in guested_podcasts]
        )
        logger.debug(f"Found {len(combined_podcast_ids)} unique podcasts ids...")
        combined_podcasts = Podcast.objects.filter(
            id__in=list(combined_podcast_ids)
        ).order_by("title")
        logger.debug(f"Found {combined_podcasts.count()} unique podcasts...")
        return combined_podcasts

    def get_podcasts_with_appearance_counts(self) -> list[PodcastAppearanceData]:
        """
        Provide podcast appearance data for each distinct podcast they have appeared on.
        """
        podcasts = []
        if self.hosted_episodes.exists() or self.guest_appearances.exists():
            for podcast in self.get_distinct_podcasts():
                podcasts.append(
                    PodcastAppearanceData(
                        podcast=podcast,
                        hosted_episodes=self.hosted_episodes.filter(podcast=podcast),
                        guested_episodes=self.guest_appearances.filter(podcast=podcast),
                    )
                )
        return podcasts

    @cached_property
    def distinct_podcasts(self) -> int:
        """
        Get a count of the number of unique podcasts this person has appeared on.
        """
        return self.get_distinct_podcasts().count()


class Season(UUIDTimeStampedModel):
    """
    A season for a given podcast.

    Attributes:
        podcast (Podcast): The podcast the season belongs to.
        season_number (int): The season number.
        analysis_group (QuerySet[AnalysisGroup]): Analysis Groups this is assigned to.
    """

    if TYPE_CHECKING:
        episodes: RelatedManager["Episode"]

    podcast = models.ForeignKey(
        Podcast, on_delete=models.CASCADE, related_name="seasons"
    )
    season_number = models.PositiveIntegerField()
    analysis_group = models.ManyToManyField(
        AnalysisGroup, related_name="seasons", blank=True
    )

    class Meta:
        ordering: ClassVar[list[str]] = ["podcast__title", "season_number"]

    def __str__(self):  # no cov
        return f"{self.podcast.title} ({self.season_number}"


class Episode(UUIDTimeStampedModel):
    """
    Represents a single episode of a podcast.

    Attributes:
        podcast (Podcast): The podcast this episode belongs to.
        guid (str): GUID of the episode
        title (str | None): Title of the episode
        ep_type (str): Episode type, e.g full, bonus, trailer
        season (Season | None): Season the episode belongs to.
        ep_num (int | None): Episode number
        release_datetime (datetime | None): Date and time the episode was released.
        episode_url (str | None): URL of the episode page.
        mime_type (str | None): Reported mime type of the episode.
        download_url (str | None): URL of the episode file.
        itunes_duration (int | None): Duration of the episode in seconds.
        file_size (int | None): Size of the episode file in bytes.
        itunes_explict (bool): Does this episode have the explicit flag?
        show_notes (str | None): Show notes for the episode, if provided.
        cw_present (bool): Did we detect a content warning?
        transcript_detected (bool): Did we detect a transcript?
        hosts_detected_from_feed (QuerySet[Person]): Hosts found in the
            feed information.
        guests_detected_from_feed (QuerySet[Person]): Guests found in the
            feed information.
        analysis_group (QuerySet[AnalysisGroup]): Analysis Groups this is assigned to.

    """

    podcast = models.ForeignKey(
        Podcast, on_delete=models.CASCADE, related_name="episodes"
    )
    guid = models.CharField(max_length=250, db_index=True)
    title = models.CharField(
        max_length=250, help_text=_("Title of episode"), null=True, blank=True
    )
    ep_type = models.CharField(
        max_length=15,
        default="full",
        help_text=_(
            "Episode type per itunes tag if available. Assumes full if not available."
        ),
    )
    season = models.ForeignKey(
        Season,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_("iTunes season, if specified."),
        related_name="episodes",
    )
    ep_num = models.PositiveIntegerField(
        null=True, blank=True, help_text="iTunes specified episode number, if any."
    )
    release_datetime = models.DateTimeField(
        help_text=_("When episode was released."), null=True, blank=True
    )
    episode_url = models.URLField(
        help_text=_("URL for episode page."), null=True, blank=True
    )
    mime_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text=_("Mime type of enclosure as reported by feed."),
    )
    download_url = models.URLField(
        max_length=400, help_text=_("URL for episode download."), null=True, blank=True
    )
    itunes_duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Duration in seconds per itunes attributes if available."),
    )
    file_size = models.PositiveIntegerField(
        help_text=_("Size of file based on enclosure `length` attribute."),
        null=True,
        blank=True,
    )
    itunes_explicit = models.BooleanField(
        default=False, help_text=_("iTunes explicit tag.")
    )
    show_notes = models.TextField(null=True, blank=True)
    cw_present = models.BooleanField(
        default=False, help_text=_("Any detection of CWs in show notes?")
    )
    transcript_detected = models.BooleanField(
        default=False, help_text=_("Any transcript link detected?")
    )
    hosts_detected_from_feed = models.ManyToManyField(
        Person, related_name="hosted_episodes", blank=True
    )
    guests_detected_from_feed = models.ManyToManyField(
        Person, related_name="guest_appearances", blank=True
    )
    analysis_group = models.ManyToManyField(
        AnalysisGroup, related_name="episodes", blank=True
    )

    class Meta:
        ordering: ClassVar[list[str]] = ["-release_datetime"]

    def __str__(self):  # no cov
        return f"{self.title}"

    def get_absolute_url(self):
        return reverse_lazy(
            "podcast_analyzer:episode-detail",
            kwargs={"podcast_id": self.podcast.id, "id": self.id},
        )

    @property
    def duration(self) -> datetime.timedelta | None:
        """
        Attempts to convert the duration of the episode into a timedelta
        for better display.
        """
        if self.itunes_duration is not None:
            return datetime.timedelta(seconds=self.itunes_duration)
        return None

    def get_file_size_in_mb(self) -> float:
        """Convert the size of the file in bytes to MB."""
        if self.file_size:
            return self.file_size / 1048597
        return 0.0

    @classmethod
    def create_or_update_episode_from_feed(
        cls,
        podcast: Podcast,
        episode_dict: dict[str, Any],
        *,
        update_existing_episodes: bool = False,
    ) -> bool:
        """
        Given a dict of episode data from podcastparser, create or update the episode
        and return a bool indicating if a record was touched.

        Args:
            podcast (Podcast): The instance of the podcast being updated.
            episode_dict (dict[str, Any]): A dict representing the episode as created by `podcastparser`.
            update_existing_episodes (bool): Update data in existing records? Default: False
        Returns:
            True or False if a record was created or updated.
        """  # noqa: E501
        if len(episode_dict.get("enclosures", [])) == 0:
            return False
        ep, created = cls.objects.get_or_create(
            podcast=podcast, guid=episode_dict["guid"]
        )
        if update_existing_episodes or created:
            description = episode_dict.get("description", "")
            ep.title = episode_dict["title"]
            ep.itunes_explicit = episode_dict.get("explicit", False)
            ep.ep_type = episode_dict.get("type", "full")
            ep.show_notes = description
            ep.episode_url = episode_dict.get("link", None)
            ep.release_datetime = datetime.datetime.fromtimestamp(
                episode_dict.get("published", timezone.now().timestamp()),
                tz=timezone.get_fixed_timezone(0),
            )
            enclosure = episode_dict["enclosures"][0]
            if enclosure["file_size"] >= 0:
                ep.file_size = enclosure["file_size"]
            ep.mime_type = enclosure["mime_type"]
            ep.download_url = enclosure["url"]
            ep.ep_num = episode_dict.get("number", None)
            ep.itunes_duration = episode_dict.get("total_time", None)
            season = episode_dict.get("season", None)
            if season is not None:
                season, created = Season.objects.get_or_create(
                    podcast=podcast, season_number=season
                )
                ep.season = season
            if (
                episode_dict.get("transcript_url", None) is not None
                or "transcript" in description.lower()
            ):
                ep.transcript_detected = True
            if (
                "CW" in description
                or "content warning" in description.lower()
                or "trigger warning" in description.lower()
                or "content note" in description.lower()
            ):
                ep.cw_present = True
            people = episode_dict.get("persons", [])
            for person in people:
                role = person.get("role", "host")
                if role in ("host", "guest"):
                    persona, created = Person.objects.get_or_create(
                        name=person["name"], url=person.get("href", None)
                    )
                    img = person.get("img", None)
                    if persona.img_url is None and img is not None:
                        persona.img_url = img
                        persona.save()
                    if role == "guest":
                        ep.guests_detected_from_feed.add(persona)
                    else:
                        ep.hosts_detected_from_feed.add(persona)
            ep.save()
            return True
        return False


def calculate_median_episode_duration(episodes: Iterable[Episode]) -> int:
    """
    Given an iterable of episode objects, calculate the median duration.

    If not a QuerySet, first convert to a queryset to order and extract values.

    Args:
        episodes (Iterable[Episode]): An iterable of episode objects,
            e.g. a list or QuerySet

    Returns:
        int: The median duration in seconds.
    """

    if isinstance(episodes, QuerySet):
        if not episodes.exists():
            return 0
        return median_high(
            episodes.order_by("itunes_duration").values_list(
                "itunes_duration", flat=True
            )
        )
    else:
        if isinstance(episodes, Sized) and len(episodes) == 0:
            return 0
        return median_high(
            Episode.objects.filter(id__in=[e.id for e in episodes])
            .order_by("itunes_duration")
            .values_list("itunes_duration", flat=True)
        )

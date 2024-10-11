# seed_database_itunes.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from django.core.management.base import CommandError
from django.db import transaction
from django_typer.management import TyperCommand
from rich.progress import Progress

from podcast_analyzer.models import ItunesCategory


class Command(TyperCommand):
    """Seeds the database with initial iTunes categories."""

    help = "Seed database with iTunes categories and update site data."

    @transaction.atomic
    def handle(self) -> None:
        """Check to ensure Itunes category don't already exist,
        and then creates them if so.
        """
        if ItunesCategory.objects.exists():
            msg = (
                "This command cannot be run when the ITunes categories "
                "are already populated!"
            )
            raise CommandError(msg)
        self.stdout.write("Seeding database...")
        num_categories = create_itunes_categories()
        self.stdout.write(f"Added {num_categories} iTunes categories to database!")


def create_itunes_categories() -> int:
    """
    Create the iTunes categories based on the list as of March 31, 2023.
    """
    itunes_category_list = {
        "Art": [
            "Books",
            "Design",
            "Fashion & Beauty",
            "Food",
            "Performing Arts",
            "Visual Arts",
        ],
        "Business": [
            "Careers",
            "Entrepreneurship",
            "Investing",
            "Management",
            "Marketing",
            "Non-Profit",
        ],
        "Comedy": [
            "Comedy Interviews",
            "Improv",
            "Stand-Up",
        ],
        "Education": [
            "Courses",
            "How To",
            "Language Learning",
            "Self-Improvement",
        ],
        "Fiction": [
            "Comedy Fiction",
            "Drama",
            "Science Fiction",
        ],
        "Government": [],
        "History": [],
        "Health & Fitness": [
            "Alternative Health",
            "Fitness",
            "Medicine",
            "Mental Health",
            "Nutrition",
            "Sexuality",
        ],
        "Kids & Family": [
            "Education for Kids",
            "Parenting",
            "Pets & Animals",
            "Stories for Kids",
        ],
        "Leisure": [
            "Animation & Manga",
            "Automotive",
            "Aviation",
            "Crafts",
            "Games",
            "Hobbies",
            "Home & Garden",
            "Video Games",
        ],
        "Music": [
            "Music Commentary",
            "Music History",
            "Music Interviews",
        ],
        "News": [
            "Business News",
            "Daily News",
            "Entertainment News",
            "News Commentary",
            "Politics",
            "Sports News",
            "Tech News",
        ],
        "Religion & Spirituality": [
            "Buddhism",
            "Christianity",
            "Hinduism",
            "Islam",
            "Judaism",
            "Religion",
            "Sprituality",
        ],
        "Science": [
            "Astronomy",
            "Chemistry",
            "Earth Sciences",
            "Life Sciences",
            "Mathematics",
            "Natural Sciences",
            "Nature",
            "Physics",
            "Social Sciences",
        ],
        "Society & Culture": [
            "Documentary",
            "Personal Journals",
            "Philosophy",
            "Places & Travel",
            "Relationships",
        ],
        "Sports": [
            "Baseball",
            "Basketball",
            "Cricket",
            "Fantasy Sports",
            "Football",
            "Golf",
            "Hockey",
            "Rugby",
            "Soccer",
            "Swimming",
            "Tennis",
            "Volleyball",
            "Wilderness",
            "Wrestling",
        ],
        "Technology": [],
        "True Crime": [],
        "TV & Film": [
            "After Shows",
            "Film History",
            "Film Interviews",
            "Film Reviews",
            "TV Reviews",
        ],
    }
    created: int = 0
    with Progress() as progress:
        task = progress.add_task("[cyan]Creating iTunes categories...", steps=19)
        for cat, subs in itunes_category_list.items():
            parent = ItunesCategory.objects.create(name=cat)
            created += 1
            if len(subs) > 0:  # type: ignore
                for sub in subs:  # type: ignore
                    ItunesCategory.objects.create(name=sub, parent_category=parent)
                    created += 1
            progress.update(task, advance=1)
    return created

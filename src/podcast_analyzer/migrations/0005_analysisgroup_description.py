# Generated by Django 5.1.2 on 2024-10-24 15:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("podcast_analyzer", "0004_remove_episode_tags_delete_tagulous_episode_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="analysisgroup",
            name="description",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Description of group for your future reference.",
            ),
        ),
    ]
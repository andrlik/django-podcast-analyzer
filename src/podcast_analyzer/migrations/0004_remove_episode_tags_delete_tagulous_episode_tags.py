# Generated by Django 5.1.2 on 2024-10-21 20:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("podcast_analyzer", "0003_alter_podcast_itunes_categories"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="episode",
            name="tags",
        ),
        migrations.DeleteModel(
            name="Tagulous_Episode_tags",
        ),
    ]

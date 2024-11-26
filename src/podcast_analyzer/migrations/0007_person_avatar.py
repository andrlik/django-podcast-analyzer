# Generated by Django 5.1.2 on 2024-11-26 22:02

import podcast_analyzer.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("podcast_analyzer", "0006_person_merged_at_person_merged_into"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="avatar",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=podcast_analyzer.models.avatar_directory_path,
            ),
        ),
    ]
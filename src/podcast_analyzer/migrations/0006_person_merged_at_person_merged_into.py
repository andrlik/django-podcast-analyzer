# Generated by Django 5.1.2 on 2024-11-21 14:16

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("podcast_analyzer", "0005_analysisgroup_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="merged_at",
            field=models.DateTimeField(
                blank=True, help_text="When the record was merged", null=True
            ),
        ),
        migrations.AddField(
            model_name="person",
            name="merged_into",
            field=models.ForeignKey(
                blank=True,
                help_text="A primary record this person has been merged into.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="merged_records",
                to="podcast_analyzer.person",
            ),
        ),
    ]

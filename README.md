# Django Podcast Analyzer

A simple [Django](https://www.djangoproject.com) app that allows you to follow the feeds of various podcasts and glean interesting information from them.

[![PyPI](https://img.shields.io/pypi/v/django-podcast-analyzer)](https://pypi.org/project/django-podcast-analyzer/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-markov)
![PyPI - Versions from Framework Classifiers](https://img.shields.io/pypi/frameworkversions/django/django-markov)
[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/andrlik/django-podcast-analyzer/blob/main/.pre-commit-config.yaml)
[![License](https://img.shields.io/github/license/andrlik/django-podcast-analyzer)](https://github.com/andrlik/django-podcast-analyzer/blob/main/LICENSE)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Security: bandit](https://img.shields.io/badge/security-bandit-green.svg)](https://github.com/PyCQA/bandit)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)
[![Semantic Versions](https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--versions-e10079.svg)](https://github.com/andrlik/django-podcast-analyzer/releases)
![Test results](https://github.com/andrlik/django-podcast-analyzer/actions/workflows/ci.yml/badge.svg)
[![Coverage Status](https://coveralls.io/repos/github/andrlik/django-podcast-analyzer/badge.svg?branch=main)](https://coveralls.io/github/andrlik/django-podcast-analyzer?branch=main)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://andrlik.github.io/django-podcast-analyzer/)

## Warning

This is early stage! Things that still need to be done:

- Simplify templates so you can easily integrate them without a lot of styling opinions.
- Analysis group reporting views.
- Finish test coverage.
- Improved docs.

## Installation

Via pip:

```bash
python -m pip install django-podcast-analyzer
```

Via uv:

```bash
uv pip install django-podcast-analyzer
```

Then add it and our dependencies to your list of installed apps.

```python
# settings.py

# Your setup may vary.
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "django.forms",
    ...,
    # Here are our explict dependencies
    "tagulous",
    "django_q",
    "podcast_analyzer",
]
```

We use [tagulous](https://django-tagulous.readthedocs.io/en/latest/) for tagging podcasts
and [django-q2](https://django-q2.readthedocs.io/en/master/index.html) to handle the scheduled
tasks related to fetching feeds and processing them.
See the documentation for both of those projects to identify any additional configuration needed.

Add it to your `urls.py`:

```python
# Your root urls.py

from django.urls import include, path

urlpatterns = [
    ...,
    path("podcasts/", include("podcast_analyzer.urls", namespace="podcasts")),
    ...,
]
```

Then run your migrations.

```bash
python manage.py migrate
```

You'll also want to seed the database with the known iTunes categories for podcasts. You can
do this via the provided management command. It will only do so if the respective tables are empty
so you won't get duplicates.

```bash
python manage.py seed_database_itunes
```

In order to run the application, you will also need to spawn a django-q cluster using
`python manage.py qcluster`. You can also use a runner like [honcho](https://honcho.readthedocs.io/en/latest/)
or a Supervisor app.

## Other Recommendations

For storage of podcast art and other media, it's recommended you consider using something like
[django-storages](https://django-storages.readthedocs.io/en/latest/).

## Development

Contributions are welcome! See our [contributing guide](https://andrlik.github.io/django-podcast-analyzer/latest/contributing/) for details.

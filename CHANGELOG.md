# Changelog

## Unreleased

[Compare the full difference](https://github.com/andrlik/django-podcast-analyzer/compare/v0.1.2...HEAD)

- Improved logic for getting distinct podcasts for Person records. [Commit](https://github.com/andrlik/django-podcast-analyzer/commit/615e02aa2f57b0e0540375dd21c199d8bb4533fc)
- If the actual mime type of Podcast cover art file is different from the reported type or file extension, update the file extension. [Commit](https://github.com/andrlik/django-podcast-analyzer/commit/75fdd0f2e2f2fd326e60e6ba14f01e76d0be0901)
- Removes all the legacy css code in favor of somewhat more bare templates that would be easier to incorporate into a different project. [Commit](https://github.com/andrlik/django-podcast-analyzer/commit/bb49a0fc59a0014e499c46a879c2d2de4c05119e)
- Add views and templates for People records. [Commit](https://github.com/andrlik/django-podcast-analyzer/commit/251431ca1e6659a7453678847de00a3318741c4e)
- Add views and templates for Episode records. [Commit](https://github.com/andrlik/django-podcast-analyzer/commit/f72c3b2aa206e9f85c71e5f0b856fa6ce181d42e)
- Add initial analysis group templates. [Commit](https://github.com/andrlik/django-podcast-analyzer/commit/a1be7bbd19ae121df19db201c5a8e12635eac8fc)
- Adds analysis group calculations around durations, related object counts, feed data properties, iTunes categories, etc. [Commit](https://github.com/andrlik/django-podcast-analyzer/commit/86e5819e26d6bf2efe413febf82c162cd8d42554)
- Exposes Podcast tags to views and templates, and removes the unused Episode level tags. [Commit](https://github.com/andrlik/django-podcast-analyzer/commit/e96f87e68712648c46190babc54bef546b14f259)

## 0.1.2

[Compare the full difference](https://github.com/andrlik/django-podcast-analyzer/compare/v0.1.1...v0.1.2)

- Minor documentation fix for PyPI

## 0.1.1

[Compare the full difference](https://github.com/andrlik/django-podcast-analyzer/compare/v0.1.0...v0.1.1)

- Rename `seed_database` to `seed_database_itunes`.

## 0.1.0

- Initial release

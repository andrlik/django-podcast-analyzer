# test_image_fetching.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from io import BytesIO

import pytest
from django.core.files import File

from podcast_analyzer import ImageRetrievalError
from podcast_analyzer.models import RemoteImageData, fetch_image_for_record


@pytest.mark.parametrize(
    "url,reported_mime_type,expected_filename",
    [
        ("https://example.com/imgs/cover.jpg", "image/jpeg", "cover.png"),
        (
            "https://example.com/imgs/podcasts/20/cover_art.jpg",
            "image/jpg",
            "cover_art.png",
        ),
        (
            "https://example.com/imgs/cover.jpg?size=200,200",
            "application/octet-stream",
            "cover.png",
        ),
    ],
)
def test_image_data_initialization(
    cover_art, url, reported_mime_type, expected_filename
):
    img_bytes = BytesIO(cover_art)
    rid = RemoteImageData(
        img_data=img_bytes, remote_url=url, reported_mime_type="image/jpeg"
    )
    assert rid.actual_mime_type == "image/png"
    assert rid.image_file is not None and isinstance(rid.image_file, File)
    assert rid.filename == expected_filename
    assert rid.is_valid()


@pytest.mark.django_db
def test_image_data_initialization_with_invalid(rss_feed_datastream):
    rid = RemoteImageData(
        img_data=rss_feed_datastream,
        remote_url="https://example.com/cover.jpg",
        reported_mime_type="image/jpeg",
    )
    assert not rid.is_valid()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 500])
async def test_fetch_image_for_record_http_error(httpx_mock, status_code):
    url = "https://example.com/imgs/cover.png"
    httpx_mock.add_response(url=url, status_code=status_code)
    with pytest.raises(ImageRetrievalError):
        await fetch_image_for_record(img_url=url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,reported_mime_type,expected_filename",
    [
        ("https://example.com/imgs/cover.jpg", "image/jpeg", "cover.png"),
        (
            "https://example.com/imgs/cover.jpg?size=200,200",
            "application/octet-stream",
            "cover.png",
        ),
        ("https://example.com/imgs/cover.png", "image/png", "cover.png"),
    ],
)
async def test_fetch_image_for_record_success(
    httpx_mock, cover_art, url, reported_mime_type, expected_filename
):
    headers = {"Content-Type": reported_mime_type}
    httpx_mock.add_response(url=url, headers=headers, content=cover_art)
    rid = await fetch_image_for_record(img_url=url)
    assert rid.filename == expected_filename
    assert rid.actual_mime_type == "image/png"
    assert rid.image_file is not None and isinstance(rid.image_file, File)

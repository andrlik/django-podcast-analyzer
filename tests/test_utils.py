# test_utils.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import pytest

from podcast_analyzer.utils import (
    filename_has_extension,
    update_file_extension_from_mime_type,
)


@pytest.mark.parametrize(
    "filename,expected_result",
    [
        ("monkey", False),
        (".monkey", False),
        ("monkey.", False),
        ("monkey.jpg", True),
        ("monkey.jpeg", True),
        ("monkey.gif", True),
        ("monkey.webp", True),
        ("monkey.png", True),
        ("monkey.docx", True),
    ],
)
def test_extension_detection(filename: str, expected_result: bool) -> None:
    assert filename_has_extension(filename) == expected_result


@pytest.mark.parametrize(
    "filename,mime_type,expected_filename",
    [
        ("monkey", "image/jpeg", "monkey.jpeg"),
        ("monkey.", "image/jpeg", "monkey.jpeg"),
        (".monkey", "image/jpeg", ".monkey.jpeg"),
        ("monkey.jpg", "image/jpeg", "monkey.jpeg"),
        ("monkey.jpg", "image/png", "monkey.png"),
        ("monkey.jpg", "image/gif", "monkey.gif"),
        ("monkey.jpg", "image/webp", "monkey.webp"),
        ("monkey.jpeg", "image/jpeg", "monkey.jpeg"),
    ],
)
def test_update_file_extension_from_mime_type(
    filename: str, mime_type: str, expected_filename: str
) -> None:
    assert (
        update_file_extension_from_mime_type(mime_type=mime_type, filename=filename)
        == expected_filename
    )

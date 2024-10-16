# utils.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

MIME_TYPE_FILE_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/gif": "gif",
    "image/webp": "webp",
}


def update_file_extension_from_mime_type(mime_type: str, filename: str) -> str:
    """
    Given the mime type and filename update the file extension.
    """
    if filename_has_extension(filename):
        filename_components = filename.rsplit(".", 1)
        base_filename = filename_components[0]
        existing_extension = filename_components[1]
        if existing_extension == MIME_TYPE_FILE_EXTENSIONS[mime_type]:
            return filename
    elif filename.endswith("."):
        base_filename = filename[:-1]
    else:
        base_filename = filename
    filename = f"{base_filename}.{MIME_TYPE_FILE_EXTENSIONS[mime_type]}"
    return filename


def filename_has_extension(filename: str) -> bool:
    """
    Checks that a filename has at least one extension.
    """
    if "." in filename[1:] and not filename.endswith("."):
        return True
    return False

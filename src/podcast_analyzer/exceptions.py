# exceptions.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

class FeedFetchError(Exception):
    """
    Raised when we are unable to retrieve remote feed data due to either
    server error or network connectivity.
    """

    pass


class FeedParseError(Exception):
    """
    Raised when parsing the content of a feed response results
    in a parsing error.
    """

    pass

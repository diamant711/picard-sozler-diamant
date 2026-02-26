# Picard Sözler (diamant fork)
# Fork of the original Picard Sözler plugin by Deniz Engin
# Modified and improved by diamant (2026)
#
# This fork improves:
# - Uses /api/search instead of /api/get
# - Prioritizes synced lyrics
# - Adds duration tolerance (+/- 2 seconds)
# - Smarter fallback handling
#
# Original project:
# Copyright (C) 2024 Deniz Engin <dev@dilbil.im>
#
# This program is free software under GPL-3.0-or-later.

PLUGIN_NAME = "Picard Sözler (diamant fork)"
PLUGIN_AUTHOR = "Deniz Engin (original) / diamant (fork maintainer)"
PLUGIN_DESCRIPTION = """
Sözler is a lyrics fetcher plugin for Picard.

This is a fork maintained by diamant.

Changes in this fork:
- Uses lrclib.net /api/search endpoint for better result coverage
- Prioritizes synced lyrics when available
- Falls back to plain lyrics only if synced are not found
- Adds duration tolerance (+/- 2 seconds) for better matching
- Improved logging and error handling

Uses the public API from lrclib.net.
No API key required.
"""
PLUGIN_VERSION = "0.1.0-diamant"
PLUGIN_API_VERSIONS = ["2.1"]
PLUGIN_LICENSE = "GPL-3.0-or-later"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0-standalone.html"

from functools import partial
from picard.metadata import register_track_metadata_processor
from picard import log


API_URL = "https://lrclib.net/api/search"
DURATION_TOLERANCE = 2  # seconds


def log_debug(msg):
    log.debug(f"{PLUGIN_NAME}: {msg}")


def log_error(msg):
    log.error(f"{PLUGIN_NAME}: {msg}")


def choose_best_result(results, target_duration):
    """
    Select the best lyrics result.

    Priority:
    1. Synced lyrics with matching duration (+/- tolerance)
    2. Synced lyrics without duration match
    3. Plain lyrics with matching duration
    4. Any plain lyrics
    """

    synced_duration_match = None
    synced_any = None
    plain_duration_match = None
    plain_any = None

    for result in results:
        if result.get("instrumental"):
            continue

        duration = result.get("duration")
        synced = result.get("syncedLyrics")
        plain = result.get("plainLyrics")

        duration_match = False
        if duration and target_duration:
            if abs(duration - target_duration) <= DURATION_TOLERANCE:
                duration_match = True

        if synced:
            if duration_match and not synced_duration_match:
                synced_duration_match = synced
            elif not synced_any:
                synced_any = synced

        if plain:
            if duration_match and not plain_duration_match:
                plain_duration_match = plain
            elif not plain_any:
                plain_any = plain

    return (
        synced_duration_match
        or synced_any
        or plain_duration_match
        or plain_any
    )


def process_response(album, metadata, data, reply, error):
    if error:
        log_error("API request failed")
        album._requests -= 1
        album._finalize_loading(None)
        return

    try:
        if not isinstance(data, list):
            log_error(f"Unexpected API response: {data}")
            return

        mins, secs = map(int, metadata.get("~length", "0:0").split(":"))
        target_duration = mins * 60 + secs

        log_debug(f"Processing {len(data)} results")
        lyrics = choose_best_result(data, target_duration)

        if lyrics:
            metadata["lyrics"] = lyrics
            log_debug("Lyrics successfully attached")
        else:
            log_debug("No suitable lyrics found")

    except Exception as e:
        log_error(f"Error processing response: {e}")

    finally:
        album._requests -= 1
        album._finalize_loading(None)


def process_track(album, metadata, track, release):
    try:
        mins, secs = map(int, metadata.get("~length", "0:0").split(":"))
        duration = mins * 60 + secs
    except Exception:
        duration = None

    query = {
        "artist_name": metadata.get("artist"),
        "track_name": metadata.get("title"),
    }

    log_debug(f"Querying API with: {query}")

    album.tagger.webservice.get_url(
        url=API_URL,
        handler=partial(process_response, album, metadata),
        parse_response_type="json",
        queryargs=query,
    )

    album._requests += 1


register_track_metadata_processor(process_track)

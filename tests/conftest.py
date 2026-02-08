"""Fixtures condivise per i test."""

import pytest
from pathlib import Path
import tempfile


@pytest.fixture
def tmp_cache_dir():
    """Crea una directory temporanea per la cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_lyrics():
    """Testi di esempio per i test."""
    return {
        "love_song": """
        I love you more than words can say
        My heart beats for you every day
        Forever and always, we'll be together
        Our love will last, in any weather
        """,
        "sad_song": """
        Tears falling like rain
        Broken heart, endless pain
        Alone in the darkness, crying out loud
        Lost in the shadows of a lonely crowd
        """,
        "happy_song": """
        Dancing in the sunshine bright
        Everything feels so right
        Happiness fills my soul today
        Nothing can take this joy away
        """
    }


@pytest.fixture
def mock_genius_response():
    """Risposta mock dell'API Genius."""
    return {
        "response": {
            "hits": [
                {
                    "type": "song",
                    "result": {
                        "id": 12345,
                        "title": "Test Song",
                        "primary_artist": {
                            "id": 1,
                            "name": "Test Artist"
                        },
                        "url": "https://genius.com/test-artist-test-song-lyrics",
                        "song_art_image_thumbnail_url": "https://images.genius.com/thumb.jpg",
                        "release_date_for_display": "January 1, 2024"
                    }
                }
            ]
        }
    }

"""Test per il modulo lyrics_fetcher."""

from unittest.mock import MagicMock, patch

import pytest

from lyrics_fetcher import LyricsFetcher, Song


class TestSong:
    """Test per la classe Song."""

    def test_to_dict(self):
        """Verifica la conversione in dizionario."""
        song = Song(
            id="123",
            title="Test Song",
            artist="Test Artist",
            lyrics="Some lyrics",
            url="https://example.com",
            thumbnail_url="https://example.com/thumb.jpg",
            release_date="2024"
        )
        d = song.to_dict()

        assert d["id"] == "123"
        assert d["title"] == "Test Song"
        assert d["artist"] == "Test Artist"
        assert d["lyrics"] == "Some lyrics"
        assert d["url"] == "https://example.com"

    def test_from_dict(self):
        """Verifica la creazione da dizionario."""
        data = {
            "id": "456",
            "title": "Another Song",
            "artist": "Another Artist",
            "lyrics": "More lyrics",
            "url": "https://test.com"
        }
        song = Song.from_dict(data)

        assert song.id == "456"
        assert song.title == "Another Song"
        assert song.artist == "Another Artist"
        assert song.lyrics == "More lyrics"

    def test_cleaned_lyrics(self):
        """Verifica che cleaned_lyrics rimuova le annotazioni."""
        song = Song(
            id="1",
            title="Test",
            artist="Test",
            lyrics="[Verse 1]\nHello world\n[Chorus]\nLa la la"
        )
        cleaned = song.cleaned_lyrics

        assert "[Verse 1]" not in cleaned
        assert "[Chorus]" not in cleaned
        assert "Hello world" in cleaned

    def test_cleaned_lyrics_cached(self):
        """Verifica che cleaned_lyrics sia cached."""
        song = Song(id="1", title="Test", artist="Test", lyrics="Test lyrics")
        _ = song.cleaned_lyrics
        assert song._cleaned_lyrics == "Test lyrics"


class TestLyricsFetcher:
    """Test per la classe LyricsFetcher."""

    def test_init_without_token_raises(self):
        """Verifica che l'inizializzazione senza token sollevi errore."""
        with patch("config.Config.GENIUS_API_TOKEN", None):
            with pytest.raises(ValueError, match="Token API Genius non configurato"):
                LyricsFetcher()

    def test_init_with_token(self, tmp_path):
        """Verifica l'inizializzazione con token."""
        with patch("config.Config.GENIUS_API_TOKEN", "test_token"):
            with patch("config.Config.CACHE_DIR", tmp_path):
                fetcher = LyricsFetcher()
                assert fetcher.api_token == "test_token"

    def test_search_uses_cache(self, tmp_path):
        """Verifica che la ricerca usi la cache."""
        with patch("config.Config.GENIUS_API_TOKEN", "test_token"):
            with patch("config.Config.CACHE_DIR", tmp_path):
                fetcher = LyricsFetcher()

                # Pre-popola la cache
                cache_data = [
                    {"id": "1", "title": "Cached Song", "artist": "Artist"}
                ]
                fetcher.cache.set("search:test:5", cache_data)

                # La ricerca dovrebbe usare la cache senza chiamare l'API
                with patch.object(fetcher, "_api_request") as mock_api:
                    songs = fetcher.search("test", limit=5)
                    mock_api.assert_not_called()
                    assert len(songs) == 1
                    assert songs[0].title == "Cached Song"

    def test_search_returns_songs(self, tmp_path):
        """Verifica che la ricerca restituisca oggetti Song."""
        mock_response = {
            "hits": [
                {
                    "type": "song",
                    "result": {
                        "id": 123,
                        "title": "Test Song",
                        "primary_artist": {"name": "Test Artist"},
                        "url": "https://genius.com/test",
                        "song_art_image_thumbnail_url": "https://img.com/thumb.jpg"
                    }
                }
            ]
        }

        with patch("config.Config.GENIUS_API_TOKEN", "test_token"):
            with patch("config.Config.CACHE_DIR", tmp_path):
                fetcher = LyricsFetcher()

                with patch.object(fetcher, "_api_request", return_value=mock_response):
                    songs = fetcher.search("test", limit=5)

                    assert len(songs) == 1
                    assert isinstance(songs[0], Song)
                    assert songs[0].title == "Test Song"
                    assert songs[0].artist == "Test Artist"

    def test_search_filters_non_songs(self, tmp_path):
        """Verifica che vengano filtrati i risultati non-song."""
        mock_response = {
            "hits": [
                {"type": "article", "result": {"title": "Article"}},
                {
                    "type": "song",
                    "result": {
                        "id": 1,
                        "title": "Real Song",
                        "primary_artist": {"name": "Artist"}
                    }
                }
            ]
        }

        with patch("config.Config.GENIUS_API_TOKEN", "test_token"):
            with patch("config.Config.CACHE_DIR", tmp_path):
                fetcher = LyricsFetcher()

                with patch.object(fetcher, "_api_request", return_value=mock_response):
                    songs = fetcher.search("test", limit=5)
                    assert len(songs) == 1
                    assert songs[0].title == "Real Song"

    def test_get_lyrics_uses_cache(self, tmp_path):
        """Verifica che get_lyrics usi la cache."""
        with patch("config.Config.GENIUS_API_TOKEN", "test_token"):
            with patch("config.Config.CACHE_DIR", tmp_path):
                fetcher = LyricsFetcher()
                song = Song(id="123", title="Test", artist="Artist", url="https://test.com")

                # Pre-popola la cache
                fetcher.cache.set("lyrics:123", "Cached lyrics content")

                with patch.object(fetcher, "_scrape_lyrics") as mock_scrape:
                    result = fetcher.get_lyrics(song)
                    mock_scrape.assert_not_called()
                    assert result.lyrics == "Cached lyrics content"

    def test_get_lyrics_skips_if_already_present(self, tmp_path):
        """Verifica che get_lyrics non faccia nulla se i lyrics sono già presenti."""
        with patch("config.Config.GENIUS_API_TOKEN", "test_token"):
            with patch("config.Config.CACHE_DIR", tmp_path):
                fetcher = LyricsFetcher()
                song = Song(
                    id="123",
                    title="Test",
                    artist="Artist",
                    lyrics="Already have lyrics"
                )

                with patch.object(fetcher, "_scrape_lyrics") as mock_scrape:
                    result = fetcher.get_lyrics(song)
                    mock_scrape.assert_not_called()
                    assert result.lyrics == "Already have lyrics"

    def test_search_by_terms_removes_duplicates(self, tmp_path):
        """Verifica che search_by_terms rimuova i duplicati."""
        with patch("config.Config.GENIUS_API_TOKEN", "test_token"):
            with patch("config.Config.CACHE_DIR", tmp_path):
                fetcher = LyricsFetcher()

                # Mock search per restituire la stessa canzone per termini diversi
                def mock_search(query, limit):
                    return [Song(id="1", title="Same Song", artist="Artist")]

                with patch.object(fetcher, "search", side_effect=mock_search):
                    songs = fetcher.search_by_terms(["term1", "term2", "term3"])
                    # Dovrebbe esserci solo una canzone (duplicati rimossi)
                    assert len(songs) == 1

    def test_clear_cache(self, tmp_path):
        """Verifica che clear_cache svuoti la cache."""
        with patch("config.Config.GENIUS_API_TOKEN", "test_token"):
            with patch("config.Config.CACHE_DIR", tmp_path):
                fetcher = LyricsFetcher()
                fetcher.cache.set("key1", "value1")
                fetcher.clear_cache()
                assert fetcher.cache.get("key1") is None

    def test_get_cache_stats(self, tmp_path):
        """Verifica che get_cache_stats restituisca info corrette."""
        with patch("config.Config.GENIUS_API_TOKEN", "test_token"):
            with patch("config.Config.CACHE_DIR", tmp_path):
                fetcher = LyricsFetcher()
                fetcher.cache.set("key1", "value1")

                stats = fetcher.get_cache_stats()
                assert "cache_file" in stats
                assert stats["entries"] >= 1
                assert "expiry_hours" in stats

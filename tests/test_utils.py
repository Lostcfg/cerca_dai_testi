"""Test per il modulo utils."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from utils import (
    Cache,
    RateLimiter,
    truncate_text,
    clean_lyrics,
    format_duration,
    retry_on_error,
)


class TestCache:
    """Test per la classe Cache."""

    def test_set_and_get(self, tmp_path):
        """Verifica che set e get funzionino correttamente."""
        with patch("config.Config.CACHE_DIR", tmp_path):
            cache = Cache("test_cache.json")
            cache.set("key1", {"data": "value"})
            result = cache.get("key1")
            assert result == {"data": "value"}

    def test_get_nonexistent_key(self, tmp_path):
        """Verifica che get restituisca None per chiavi inesistenti."""
        with patch("config.Config.CACHE_DIR", tmp_path):
            cache = Cache("test_cache.json")
            result = cache.get("nonexistent")
            assert result is None

    def test_cache_expiry(self, tmp_path):
        """Verifica che la cache scada correttamente."""
        with patch("config.Config.CACHE_DIR", tmp_path):
            # Usa un valore molto piccolo ma > 0 per la scadenza
            cache = Cache("test_cache.json", expiry_hours=1)
            cache.set("key1", "value1")
            # Simula timestamp vecchio modificando direttamente la cache
            from datetime import datetime, timedelta
            old_time = datetime.now() - timedelta(hours=2)
            hashed_key = cache._generate_key("key1")
            cache._cache[hashed_key]["timestamp"] = old_time.isoformat()
            result = cache.get("key1")
            assert result is None

    def test_clear(self, tmp_path):
        """Verifica che clear svuoti la cache."""
        with patch("config.Config.CACHE_DIR", tmp_path):
            cache = Cache("test_cache.json")
            cache.set("key1", "value1")
            cache.set("key2", "value2")
            cache.clear()
            assert cache.get("key1") is None
            assert cache.get("key2") is None


class TestRateLimiter:
    """Test per la classe RateLimiter."""

    def test_acquire_under_limit(self):
        """Verifica che acquire funzioni sotto il limite."""
        limiter = RateLimiter(max_calls=5, period=60)
        start = time.time()
        for _ in range(5):
            limiter.acquire()
        elapsed = time.time() - start
        # Dovrebbe essere quasi istantaneo
        assert elapsed < 0.5

    def test_remaining(self):
        """Verifica che remaining restituisca il valore corretto."""
        limiter = RateLimiter(max_calls=5, period=60)
        assert limiter.remaining() == 5
        limiter.acquire()
        assert limiter.remaining() == 4
        limiter.acquire()
        assert limiter.remaining() == 3


class TestTruncateText:
    """Test per la funzione truncate_text."""

    def test_short_text(self):
        """Verifica che testi corti non vengano troncati."""
        text = "Testo corto"
        result = truncate_text(text, max_length=50)
        assert result == text

    def test_long_text(self):
        """Verifica che testi lunghi vengano troncati."""
        text = "Questa è una frase molto lunga che deve essere troncata"
        result = truncate_text(text, max_length=20)
        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")

    def test_truncate_at_word_boundary(self):
        """Verifica che il troncamento avvenga ai confini delle parole."""
        text = "Una frase con molte parole diverse"
        result = truncate_text(text, max_length=20)
        # Non dovrebbe tagliare a metà di una parola
        assert not result.rstrip(".").endswith("mol")


class TestCleanLyrics:
    """Test per la funzione clean_lyrics."""

    def test_remove_brackets(self):
        """Verifica la rimozione delle annotazioni tra parentesi quadre."""
        text = "[Verse 1]\nHello world\n[Chorus]\nLa la la"
        result = clean_lyrics(text)
        assert "[Verse 1]" not in result
        assert "[Chorus]" not in result
        assert "Hello world" in result
        assert "La la la" in result

    def test_remove_repeat_markers(self):
        """Verifica la rimozione dei marker di ripetizione."""
        text = "La la la (2x)\nNa na na (x3)"
        result = clean_lyrics(text)
        assert "(2x)" not in result
        assert "(x3)" not in result

    def test_normalize_whitespace(self):
        """Verifica la normalizzazione degli spazi."""
        text = "Hello\n\n\nWorld   with   spaces"
        result = clean_lyrics(text)
        assert "  " not in result
        assert "\n" not in result


class TestFormatDuration:
    """Test per la funzione format_duration."""

    def test_seconds_only(self):
        """Verifica il formato per durate < 1 minuto."""
        assert format_duration(45) == "45s"
        assert format_duration(0) == "0s"

    def test_minutes_and_seconds(self):
        """Verifica il formato per durate >= 1 minuto."""
        assert format_duration(90) == "1m 30s"
        assert format_duration(150) == "2m 30s"
        assert format_duration(3600) == "60m 0s"


class TestRetryOnError:
    """Test per il decorator retry_on_error."""

    def test_success_first_try(self):
        """Verifica che funzioni senza retry se non ci sono errori."""
        call_count = 0

        @retry_on_error(max_retries=3, delay=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure(self):
        """Verifica che riprovi in caso di errore."""
        call_count = 0

        @retry_on_error(max_retries=3, delay=0.01)
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Errore temporaneo")
            return "success"

        result = failing_then_success()
        assert result == "success"
        assert call_count == 2

    def test_max_retries_exceeded(self):
        """Verifica che sollevi eccezione dopo max retry."""
        @retry_on_error(max_retries=2, delay=0.01)
        def always_fails():
            raise ValueError("Sempre fallisce")

        with pytest.raises(ValueError):
            always_fails()

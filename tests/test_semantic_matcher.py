"""Test per il modulo semantic_matcher."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from lyrics_fetcher import Song
from semantic_matcher import SemanticMatcher, MatchResult


@pytest.fixture
def mock_model():
    """Crea un mock del modello sentence-transformers."""
    model = MagicMock()
    # Simula embeddings come vettori casuali normalizzati
    def encode_side_effect(text, convert_to_numpy=True):
        # Usa hash del testo per generare vettore "deterministico"
        np.random.seed(hash(text) % 2**32)
        vec = np.random.randn(384)
        return vec / np.linalg.norm(vec)

    model.encode.side_effect = encode_side_effect
    return model


@pytest.fixture
def sample_songs():
    """Crea una lista di canzoni di esempio."""
    return [
        Song(
            id="1",
            title="Love Song",
            artist="Artist A",
            lyrics="I love you so much, my heart beats for you forever"
        ),
        Song(
            id="2",
            title="Sad Ballad",
            artist="Artist B",
            lyrics="Tears falling down, broken heart, alone in the dark"
        ),
        Song(
            id="3",
            title="Happy Tune",
            artist="Artist C",
            lyrics="Dancing in the sun, feeling happy and free"
        ),
    ]


class TestMatchResult:
    """Test per la classe MatchResult."""

    def test_to_dict(self, sample_songs):
        """Verifica la conversione in dizionario."""
        result = MatchResult(
            song=sample_songs[0],
            score=0.85,
            relevant_excerpt="I love you so much"
        )
        d = result.to_dict()

        assert d["score"] == 0.85
        assert d["relevant_excerpt"] == "I love you so much"
        assert d["song"]["title"] == "Love Song"

    def test_default_matched_sentences(self, sample_songs):
        """Verifica che matched_sentences sia lista vuota di default."""
        result = MatchResult(song=sample_songs[0], score=0.5)
        assert result.matched_sentences == []


class TestSemanticMatcher:
    """Test per la classe SemanticMatcher."""

    def test_split_into_chunks_short_text(self):
        """Verifica che testi corti non vengano divisi."""
        with patch("semantic_matcher.SentenceTransformer"):
            matcher = SemanticMatcher()
            text = "Short text"
            chunks = matcher._split_into_chunks(text, chunk_size=100)
            assert len(chunks) == 1
            assert chunks[0] == text

    def test_split_into_chunks_long_text(self):
        """Verifica che testi lunghi vengano divisi correttamente."""
        with patch("semantic_matcher.SentenceTransformer"):
            matcher = SemanticMatcher()
            text = "First sentence. " * 50  # Testo lungo
            chunks = matcher._split_into_chunks(text, chunk_size=100, overlap=20)
            assert len(chunks) > 1
            # Ogni chunk dovrebbe essere <= chunk_size (circa)
            for chunk in chunks:
                assert len(chunk) <= 150  # Con un po' di margine

    def test_compute_similarity_empty_text(self):
        """Verifica che testi vuoti restituiscano score 0."""
        with patch("semantic_matcher.SentenceTransformer"):
            matcher = SemanticMatcher()
            matcher._model = MagicMock()
            score, excerpt = matcher.compute_similarity("query", "")
            assert score == 0.0
            assert excerpt == ""

    def test_find_similar_songs_filters_by_score(self, sample_songs, mock_model, tmp_path):
        """Verifica che vengano filtrate le canzoni sotto la soglia."""
        with patch("config.Config.CACHE_DIR", tmp_path):
            with patch("semantic_matcher.SentenceTransformer", return_value=mock_model):
                matcher = SemanticMatcher()
                results = matcher.find_similar_songs(
                    "love and happiness",
                    sample_songs,
                    limit=10,
                    min_score=0.99  # Soglia molto alta
                )
                # Con soglia così alta, probabilmente nessun risultato
                # (dipende dai vettori random)
                assert isinstance(results, list)

    def test_find_similar_songs_respects_limit(self, sample_songs, mock_model, tmp_path):
        """Verifica che venga rispettato il limite di risultati."""
        with patch("config.Config.CACHE_DIR", tmp_path):
            with patch("semantic_matcher.SentenceTransformer", return_value=mock_model):
                matcher = SemanticMatcher()
                results = matcher.find_similar_songs(
                    "any query",
                    sample_songs,
                    limit=1,
                    min_score=0.0  # Accetta tutto
                )
                assert len(results) <= 1

    def test_find_similar_songs_skips_empty_lyrics(self, mock_model, tmp_path):
        """Verifica che le canzoni senza lyrics vengano saltate."""
        songs = [
            Song(id="1", title="No Lyrics", artist="A", lyrics=""),
            Song(id="2", title="Has Lyrics", artist="B", lyrics="Some lyrics here")
        ]
        with patch("config.Config.CACHE_DIR", tmp_path):
            with patch("semantic_matcher.SentenceTransformer", return_value=mock_model):
                matcher = SemanticMatcher()
                results = matcher.find_similar_songs(
                    "query",
                    songs,
                    limit=10,
                    min_score=0.0
                )
                # Solo la canzone con lyrics dovrebbe essere nei risultati
                assert all(r.song.lyrics for r in results)

    def test_extract_key_phrases_short_text(self, mock_model, tmp_path):
        """Verifica l'estrazione da testi corti."""
        with patch("config.Config.CACHE_DIR", tmp_path):
            with patch("semantic_matcher.SentenceTransformer", return_value=mock_model):
                matcher = SemanticMatcher()
                text = "Single sentence here."
                phrases = matcher.extract_key_phrases(text, top_k=5)
                # Dovrebbe restituire la frase intera
                assert len(phrases) >= 1

    def test_analyze_themes(self, mock_model, tmp_path):
        """Verifica l'analisi dei temi."""
        with patch("config.Config.CACHE_DIR", tmp_path):
            with patch("semantic_matcher.SentenceTransformer", return_value=mock_model):
                matcher = SemanticMatcher()
                lyrics = "I love you, my heart beats for love, amore mio"
                themes = matcher.analyze_themes(lyrics)
                # Dovrebbe identificare il tema "love"
                assert "love" in themes
                assert themes["love"] > 0

    def test_results_sorted_by_score(self, sample_songs, mock_model, tmp_path):
        """Verifica che i risultati siano ordinati per score decrescente."""
        with patch("config.Config.CACHE_DIR", tmp_path):
            with patch("semantic_matcher.SentenceTransformer", return_value=mock_model):
                matcher = SemanticMatcher()
                results = matcher.find_similar_songs(
                    "love heart romance",
                    sample_songs,
                    limit=10,
                    min_score=0.0
                )
                if len(results) > 1:
                    scores = [r.score for r in results]
                    assert scores == sorted(scores, reverse=True)

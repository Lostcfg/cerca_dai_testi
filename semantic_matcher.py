"""
Modulo per il matching semantico tra testi.

Utilizza sentence-transformers per calcolare embeddings semantici
e trovare le canzoni con testi più simili all'input dell'utente.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from config import Config
from lyrics_fetcher import Song
from utils import Cache, truncate_text


@dataclass
class MatchResult:
    """
    Risultato del matching semantico.

    Contiene una canzone con il suo score di similarità
    e l'estratto più rilevante del testo.

    Attributes:
        song: La canzone matchata.
        score: Score di similarità (0-1).
        relevant_excerpt: Parte del testo più rilevante.
        matched_sentences: Frasi specifiche che hanno matchato.

    Example:
        >>> result = MatchResult(
        ...     song=song,
        ...     score=0.85,
        ...     relevant_excerpt="..."
        ... )
    """
    song: Song
    score: float
    relevant_excerpt: str = ""
    matched_sentences: List[str] = None

    def __post_init__(self):
        if self.matched_sentences is None:
            self.matched_sentences = []

    def to_dict(self) -> dict:
        """Converte il risultato in dizionario."""
        return {
            "song": self.song.to_dict(),
            "score": round(self.score, 4),
            "relevant_excerpt": self.relevant_excerpt,
            "matched_sentences": self.matched_sentences
        }


class SemanticMatcher:
    """
    Matcher semantico per confrontare testi usando embeddings.

    Utilizza modelli sentence-transformers pre-addestrati per
    calcolare la similarità semantica tra l'input dell'utente
    e i testi delle canzoni.

    Attributes:
        model: Modello sentence-transformers.
        cache: Cache per gli embeddings calcolati.
        logger: Logger del modulo.

    Example:
        >>> matcher = SemanticMatcher()
        >>> results = matcher.find_similar_songs(
        ...     "Voglio parlare di libertà",
        ...     songs
        ... )
        >>> for r in results:
        ...     print(f"{r.song.title}: {r.score:.2f}")
    """

    def __init__(self, model_name: Optional[str] = None):
        """
        Inizializza il SemanticMatcher.

        Args:
            model_name: Nome del modello da usare (default da Config).

        Note:
            Il modello viene caricato al primo utilizzo per
            risparmiare memoria se non necessario.
        """
        self.model_name = model_name or Config.EMBEDDING_MODEL
        self._model: Optional[SentenceTransformer] = None
        self.cache = Cache("embeddings_cache.json")
        self.logger = logging.getLogger("cerca_dai_testi.semantic_matcher")

    @property
    def model(self) -> SentenceTransformer:
        """
        Lazy loading del modello.

        Returns:
            SentenceTransformer: Modello caricato.
        """
        if self._model is None:
            self.logger.info(f"Caricamento modello: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            self.logger.info("Modello caricato con successo")
        return self._model

    def _get_embedding(self, text: str) -> np.ndarray:
        """
        Calcola l'embedding per un testo.

        Args:
            text: Testo da codificare.

        Returns:
            np.ndarray: Vettore embedding.
        """
        # Controlla cache
        cache_key = f"emb:{text[:100]}"  # Usa primi 100 char come chiave
        cached = self.cache.get(cache_key)
        if cached is not None:
            return np.array(cached)

        embedding = self.model.encode(text, convert_to_numpy=True)

        # Salva in cache (converti a lista per JSON)
        self.cache.set(cache_key, embedding.tolist())

        return embedding

    def _split_into_chunks(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 100
    ) -> List[str]:
        """
        Divide un testo lungo in chunk sovrapposti.

        Args:
            text: Testo da dividere.
            chunk_size: Dimensione massima di ogni chunk.
            overlap: Sovrapposizione tra chunk consecutivi.

        Returns:
            List[str]: Lista di chunk.
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Cerca di tagliare alla fine di una frase
            if end < len(text):
                # Cerca punto, esclamativo, interrogativo
                for sep in [". ", "! ", "? ", "\n"]:
                    last_sep = text[start:end].rfind(sep)
                    if last_sep > chunk_size * 0.5:
                        end = start + last_sep + len(sep)
                        break

            chunks.append(text[start:end].strip())
            start = end - overlap

        return chunks

    def compute_similarity(
        self,
        query: str,
        text: str
    ) -> Tuple[float, str]:
        """
        Calcola la similarità semantica tra query e testo.

        Per testi lunghi, divide in chunk e trova quello più simile.

        Args:
            query: Testo di query dell'utente.
            text: Testo della canzone.

        Returns:
            Tuple[float, str]: Score di similarità e chunk più rilevante.

        Example:
            >>> matcher = SemanticMatcher()
            >>> score, excerpt = matcher.compute_similarity(
            ...     "amore eterno",
            ...     "Ti amerò per sempre, il mio cuore è tuo"
            ... )
            >>> score > 0.5
            True
        """
        if not text:
            return 0.0, ""

        query_embedding = self._get_embedding(query)

        # Dividi il testo in chunk se necessario
        chunks = self._split_into_chunks(text)

        best_score = 0.0
        best_chunk = ""

        for chunk in chunks:
            chunk_embedding = self._get_embedding(chunk)

            # Cosine similarity
            similarity = np.dot(query_embedding, chunk_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding)
            )

            if similarity > best_score:
                best_score = float(similarity)
                best_chunk = chunk

        return best_score, truncate_text(best_chunk)

    def find_similar_songs(
        self,
        query: str,
        songs: List[Song],
        limit: int = Config.DEFAULT_LIMIT,
        min_score: float = Config.MIN_RELEVANCE_SCORE
    ) -> List[MatchResult]:
        """
        Trova le canzoni con testi più simili alla query.

        Args:
            query: Testo di ricerca dell'utente.
            songs: Lista di canzoni da confrontare.
            limit: Numero massimo di risultati.
            min_score: Score minimo per includere un risultato.

        Returns:
            List[MatchResult]: Risultati ordinati per similarità.

        Example:
            >>> matcher = SemanticMatcher()
            >>> songs = fetcher.get_songs_with_lyrics("love", limit=10)
            >>> results = matcher.find_similar_songs(
            ...     "broken heart and tears",
            ...     songs,
            ...     limit=5
            ... )
        """
        self.logger.info(f"Matching semantico per: {query[:50]}...")

        results = []

        for song in songs:
            if not song.lyrics:
                self.logger.debug(f"Skip {song.title}: lyrics mancanti")
                continue

            score, excerpt = self.compute_similarity(query, song.cleaned_lyrics)

            if score >= min_score:
                results.append(MatchResult(
                    song=song,
                    score=score,
                    relevant_excerpt=excerpt
                ))

        # Ordina per score decrescente
        results.sort(key=lambda x: x.score, reverse=True)

        self.logger.info(f"Trovati {len(results)} match sopra soglia {min_score}")

        return results[:limit]

    def find_best_matches_multi_query(
        self,
        queries: List[str],
        songs: List[Song],
        limit: int = Config.DEFAULT_LIMIT
    ) -> List[MatchResult]:
        """
        Trova match usando multiple query (per testi lunghi).

        Divide la query in parti e combina i risultati.

        Args:
            queries: Lista di query/frasi da cercare.
            songs: Canzoni da confrontare.
            limit: Numero massimo di risultati.

        Returns:
            List[MatchResult]: Risultati combinati.
        """
        song_scores: dict = {}

        for query in queries:
            results = self.find_similar_songs(
                query, songs,
                limit=len(songs),  # Non limitare qui
                min_score=0.0
            )

            for result in results:
                song_id = result.song.id
                if song_id not in song_scores:
                    song_scores[song_id] = {
                        "result": result,
                        "scores": []
                    }
                song_scores[song_id]["scores"].append(result.score)

        # Calcola score medio per ogni canzone
        final_results = []
        for song_id, data in song_scores.items():
            avg_score = sum(data["scores"]) / len(data["scores"])
            result = data["result"]
            result.score = avg_score
            if avg_score >= Config.MIN_RELEVANCE_SCORE:
                final_results.append(result)

        final_results.sort(key=lambda x: x.score, reverse=True)
        return final_results[:limit]

    def extract_key_phrases(self, text: str, top_k: int = 5) -> List[str]:
        """
        Estrae le frasi chiave da un testo.

        Utile per generare query di ricerca da un testo lungo.

        Args:
            text: Testo da analizzare.
            top_k: Numero di frasi da estrarre.

        Returns:
            List[str]: Frasi chiave estratte.

        Example:
            >>> matcher = SemanticMatcher()
            >>> phrases = matcher.extract_key_phrases(
            ...     "L'amore è una cosa meravigliosa. Il cuore batte forte."
            ... )
        """
        # Dividi in frasi
        import re
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if len(sentences) <= top_k:
            return sentences

        # Calcola embedding del testo completo
        text_embedding = self._get_embedding(text)

        # Calcola score per ogni frase
        sentence_scores = []
        for sentence in sentences:
            sentence_embedding = self._get_embedding(sentence)
            score = np.dot(text_embedding, sentence_embedding) / (
                np.linalg.norm(text_embedding) * np.linalg.norm(sentence_embedding)
            )
            sentence_scores.append((sentence, score))

        # Ordina per score
        sentence_scores.sort(key=lambda x: x[1], reverse=True)

        return [s[0] for s in sentence_scores[:top_k]]

    def analyze_themes(self, lyrics: str) -> dict:
        """
        Analizza i temi principali di un testo.

        Args:
            lyrics: Testo da analizzare.

        Returns:
            dict: Dizionario con temi e score di rilevanza.

        Example:
            >>> themes = matcher.analyze_themes("Ti amo con tutto il cuore...")
            >>> themes
            {'love': 0.92, 'romance': 0.85, ...}
        """
        theme_keywords = {
            "love": ["love", "amore", "heart", "cuore", "passion", "passione"],
            "sadness": ["sad", "triste", "tears", "lacrime", "cry", "piangere"],
            "happiness": ["happy", "felice", "joy", "gioia", "smile", "sorriso"],
            "freedom": ["free", "libero", "freedom", "libertà", "fly", "volare"],
            "nature": ["sun", "sole", "moon", "luna", "sky", "cielo", "sea", "mare"],
            "life": ["life", "vita", "live", "vivere", "death", "morte"],
            "party": ["dance", "ballare", "party", "festa", "night", "notte"]
        }

        lyrics_lower = lyrics.lower()
        themes = {}

        for theme, keywords in theme_keywords.items():
            count = sum(lyrics_lower.count(kw) for kw in keywords)
            if count > 0:
                # Normalizza rispetto alla lunghezza del testo
                themes[theme] = min(1.0, count / (len(lyrics.split()) / 50))

        return dict(sorted(themes.items(), key=lambda x: x[1], reverse=True))

    def clear_cache(self) -> None:
        """Svuota la cache degli embeddings."""
        self.cache.clear()
        self.logger.info("Cache embeddings svuotata")

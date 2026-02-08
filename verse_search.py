"""
Modulo per la ricerca per verso specifico.

Permette di cercare canzoni basandosi su singoli versi,
identificando corrispondenze esatte o semanticamente simili.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher

from lyrics_fetcher import Song
from semantic_matcher import SemanticMatcher


@dataclass
class VerseMatch:
    """
    Rappresenta una corrispondenza di verso.

    Attributes:
        song: Canzone contenente il verso.
        matched_verse: Verso trovato.
        verse_number: Numero del verso nel testo.
        section: Sezione (strofa, ritornello, etc.).
        similarity_score: Score di similarità (0-1).
        match_type: Tipo di match (exact, fuzzy, semantic).
        context_before: Versi precedenti.
        context_after: Versi successivi.
    """
    song: Song
    matched_verse: str
    verse_number: int
    section: str = ""
    similarity_score: float = 1.0
    match_type: str = "exact"
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "song": {
                "title": self.song.title,
                "artist": self.song.artist,
                "id": self.song.id
            },
            "matched_verse": self.matched_verse,
            "verse_number": self.verse_number,
            "section": self.section,
            "similarity_score": self.similarity_score,
            "similarity_percent": f"{self.similarity_score * 100:.1f}%",
            "match_type": self.match_type,
            "context_before": self.context_before,
            "context_after": self.context_after
        }

    def get_context(self, lines: int = 2) -> str:
        """Restituisce il verso con contesto."""
        parts = []
        for v in self.context_before[-lines:]:
            parts.append(f"  {v}")
        parts.append(f"→ {self.matched_verse}")
        for v in self.context_after[:lines]:
            parts.append(f"  {v}")
        return "\n".join(parts)


@dataclass
class VerseSearchResult:
    """
    Risultato della ricerca per verso.

    Attributes:
        query: Verso cercato.
        matches: Lista di corrispondenze trovate.
        total_songs_searched: Numero di canzoni analizzate.
        search_type: Tipo di ricerca effettuata.
    """
    query: str
    matches: List[VerseMatch]
    total_songs_searched: int
    search_type: str = "semantic"

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "query": self.query,
            "total_matches": len(self.matches),
            "total_songs_searched": self.total_songs_searched,
            "search_type": self.search_type,
            "matches": [m.to_dict() for m in self.matches]
        }


class VerseSearcher:
    """
    Ricercatore di versi specifici.

    Cerca versi esatti o semanticamente simili
    all'interno di una collezione di canzoni.

    Example:
        >>> searcher = VerseSearcher()
        >>> results = searcher.search_verse(
        ...     "non ho più lacrime da piangere",
        ...     songs,
        ...     search_type="semantic"
        ... )
        >>> for match in results.matches:
        ...     print(f"{match.song.title}: {match.matched_verse}")
    """

    # Pattern per identificare sezioni
    SECTION_PATTERNS = {
        r'\[(?:verse|strofa)\s*\d*\]': 'Strofa',
        r'\[(?:chorus|ritornello|rit\.?)\]': 'Ritornello',
        r'\[(?:pre-chorus|pre-ritornello)\]': 'Pre-Ritornello',
        r'\[(?:bridge|ponte)\]': 'Bridge',
        r'\[(?:outro|finale)\]': 'Outro',
        r'\[(?:intro)\]': 'Intro',
        r'\[(?:hook)\]': 'Hook',
    }

    def __init__(self):
        """Inizializza il ricercatore."""
        self.matcher = SemanticMatcher()
        self.logger = logging.getLogger("cerca_dai_testi.verse_search")

    def search_verse(
        self,
        verse_query: str,
        songs: List[Song],
        search_type: str = "semantic",
        min_similarity: float = 0.5,
        limit: int = 20,
        context_lines: int = 2
    ) -> VerseSearchResult:
        """
        Cerca un verso nelle canzoni.

        Args:
            verse_query: Verso da cercare.
            songs: Lista di canzoni in cui cercare.
            search_type: Tipo di ricerca (exact, fuzzy, semantic).
            min_similarity: Similarità minima per i match.
            limit: Numero massimo di risultati.
            context_lines: Linee di contesto da includere.

        Returns:
            VerseSearchResult: Risultato della ricerca.
        """
        self.logger.info(f"Ricerca verso: '{verse_query[:50]}...' in {len(songs)} canzoni")

        matches = []

        for song in songs:
            if not song.lyrics:
                continue

            song_matches = self._search_in_song(
                verse_query,
                song,
                search_type,
                min_similarity,
                context_lines
            )
            matches.extend(song_matches)

        # Ordina per score
        matches.sort(key=lambda x: x.similarity_score, reverse=True)

        # Limita risultati
        matches = matches[:limit]

        return VerseSearchResult(
            query=verse_query,
            matches=matches,
            total_songs_searched=len(songs),
            search_type=search_type
        )

    def search_multiple_verses(
        self,
        verse_queries: List[str],
        songs: List[Song],
        search_type: str = "semantic",
        min_similarity: float = 0.5
    ) -> Dict[str, VerseSearchResult]:
        """
        Cerca più versi contemporaneamente.

        Args:
            verse_queries: Lista di versi da cercare.
            songs: Canzoni in cui cercare.
            search_type: Tipo di ricerca.
            min_similarity: Similarità minima.

        Returns:
            Dict: Dizionario verso -> risultati.
        """
        results = {}
        for verse in verse_queries:
            results[verse] = self.search_verse(
                verse,
                songs,
                search_type,
                min_similarity
            )
        return results

    def find_similar_verses(
        self,
        verse: str,
        songs: List[Song],
        top_k: int = 10
    ) -> List[VerseMatch]:
        """
        Trova i versi più simili a quello dato.

        Args:
            verse: Verso di riferimento.
            songs: Canzoni in cui cercare.
            top_k: Numero di risultati.

        Returns:
            List[VerseMatch]: Versi più simili.
        """
        result = self.search_verse(
            verse,
            songs,
            search_type="semantic",
            min_similarity=0.3,
            limit=top_k
        )
        return result.matches

    def _search_in_song(
        self,
        query: str,
        song: Song,
        search_type: str,
        min_similarity: float,
        context_lines: int
    ) -> List[VerseMatch]:
        """Cerca il verso in una singola canzone."""
        matches = []
        lines = song.lyrics.split('\n')
        current_section = ""

        for i, line in enumerate(lines):
            line_clean = line.strip()

            if not line_clean:
                continue

            # Controlla se è un marcatore di sezione
            section = self._detect_section(line_clean)
            if section:
                current_section = section
                continue

            # Calcola similarità in base al tipo di ricerca
            if search_type == "exact":
                similarity = 1.0 if query.lower() in line_clean.lower() else 0.0
                match_type = "exact"
            elif search_type == "fuzzy":
                similarity = self._fuzzy_match(query, line_clean)
                match_type = "fuzzy"
            else:  # semantic
                similarity = self._semantic_match(query, line_clean)
                match_type = "semantic"

            if similarity >= min_similarity:
                # Ottieni contesto
                context_before = [
                    lines[j].strip()
                    for j in range(max(0, i - context_lines), i)
                    if lines[j].strip() and not self._detect_section(lines[j])
                ]
                context_after = [
                    lines[j].strip()
                    for j in range(i + 1, min(len(lines), i + context_lines + 1))
                    if lines[j].strip() and not self._detect_section(lines[j])
                ]

                matches.append(VerseMatch(
                    song=song,
                    matched_verse=line_clean,
                    verse_number=i + 1,
                    section=current_section,
                    similarity_score=similarity,
                    match_type=match_type,
                    context_before=context_before,
                    context_after=context_after
                ))

        return matches

    def _detect_section(self, line: str) -> Optional[str]:
        """Rileva se la linea è un marcatore di sezione."""
        line_lower = line.lower()
        for pattern, section_name in self.SECTION_PATTERNS.items():
            if re.match(pattern, line_lower, re.IGNORECASE):
                return section_name
        return None

    def _fuzzy_match(self, query: str, line: str) -> float:
        """Calcola match fuzzy tra query e linea."""
        query_lower = query.lower()
        line_lower = line.lower()

        # SequenceMatcher per similarità di stringhe
        ratio = SequenceMatcher(None, query_lower, line_lower).ratio()

        # Bonus se contiene parole chiave
        query_words = set(query_lower.split())
        line_words = set(line_lower.split())
        common_words = query_words & line_words

        if query_words:
            word_overlap = len(common_words) / len(query_words)
            ratio = (ratio + word_overlap) / 2

        return ratio

    def _semantic_match(self, query: str, line: str) -> float:
        """Calcola match semantico tra query e linea."""
        import numpy as np

        emb_query = self.matcher.get_embedding(query)
        emb_line = self.matcher.get_embedding(line)

        similarity = np.dot(emb_query, emb_line) / (
            np.linalg.norm(emb_query) * np.linalg.norm(emb_line)
        )

        return float(max(0, similarity))

    def extract_all_verses(self, song: Song) -> List[Tuple[int, str, str]]:
        """
        Estrae tutti i versi da una canzone.

        Args:
            song: Canzone da analizzare.

        Returns:
            List[Tuple]: Lista di (numero_verso, verso, sezione).
        """
        if not song.lyrics:
            return []

        verses = []
        lines = song.lyrics.split('\n')
        current_section = ""

        for i, line in enumerate(lines):
            line_clean = line.strip()

            if not line_clean:
                continue

            section = self._detect_section(line_clean)
            if section:
                current_section = section
                continue

            verses.append((i + 1, line_clean, current_section))

        return verses

    def find_repeated_verses(self, song: Song) -> Dict[str, int]:
        """
        Trova i versi ripetuti in una canzone.

        Args:
            song: Canzone da analizzare.

        Returns:
            Dict: Verso -> numero di ripetizioni.
        """
        if not song.lyrics:
            return {}

        from collections import Counter

        lines = song.lyrics.split('\n')
        clean_lines = [
            l.strip().lower()
            for l in lines
            if l.strip() and not self._detect_section(l)
        ]

        counts = Counter(clean_lines)
        return {verse: count for verse, count in counts.items() if count > 1}

    def find_rhyming_verses(
        self,
        songs: List[Song],
        min_verses: int = 2
    ) -> Dict[str, List[Tuple[Song, str]]]:
        """
        Trova versi che rimano tra diverse canzoni.

        Args:
            songs: Canzoni da analizzare.
            min_verses: Minimo versi per gruppo di rime.

        Returns:
            Dict: Suffisso -> lista di (canzone, verso).
        """
        # Raggruppa per finale di verso (semplificato)
        endings = {}

        for song in songs:
            if not song.lyrics:
                continue

            for line in song.lyrics.split('\n'):
                line_clean = line.strip()
                if not line_clean or self._detect_section(line_clean):
                    continue

                # Prendi ultime 3 lettere come "rima"
                words = line_clean.split()
                if words:
                    last_word = ''.join(c for c in words[-1].lower() if c.isalpha())
                    if len(last_word) >= 3:
                        ending = last_word[-3:]
                        if ending not in endings:
                            endings[ending] = []
                        endings[ending].append((song, line_clean))

        # Filtra gruppi con abbastanza versi
        return {
            ending: verses
            for ending, verses in endings.items()
            if len(verses) >= min_verses
        }

    def get_verse_statistics(self, song: Song) -> Dict:
        """
        Calcola statistiche sui versi di una canzone.

        Args:
            song: Canzone da analizzare.

        Returns:
            Dict: Statistiche sui versi.
        """
        verses = self.extract_all_verses(song)

        if not verses:
            return {"total_verses": 0}

        lengths = [len(v[1]) for v in verses]
        word_counts = [len(v[1].split()) for v in verses]

        sections = {}
        for _, _, section in verses:
            sections[section] = sections.get(section, 0) + 1

        repeated = self.find_repeated_verses(song)

        return {
            "total_verses": len(verses),
            "average_length": sum(lengths) / len(lengths),
            "max_length": max(lengths),
            "min_length": min(lengths),
            "average_words": sum(word_counts) / len(word_counts),
            "sections": sections,
            "repeated_verses": len(repeated),
            "unique_verses": len(verses) - sum(c - 1 for c in repeated.values())
        }

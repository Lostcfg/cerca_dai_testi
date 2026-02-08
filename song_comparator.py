"""
Modulo per il confronto tra canzoni.

Permette di confrontare due o più canzoni basandosi su:
- Similarità semantica dei testi
- Temi comuni
- Vocabolario condiviso
- Struttura emotiva
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from collections import Counter

from lyrics_fetcher import Song
from semantic_matcher import SemanticMatcher
from mood_analyzer import MoodAnalyzer, MoodAnalysisResult


@dataclass
class ThemeMatch:
    """
    Rappresenta un tema comune tra canzoni.

    Attributes:
        theme: Nome/descrizione del tema.
        keywords: Parole chiave associate.
        songs_with_theme: Titoli delle canzoni che contengono il tema.
        strength: Forza del tema (0-1).
    """
    theme: str
    keywords: List[str]
    songs_with_theme: List[str]
    strength: float = 0.0

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "theme": self.theme,
            "keywords": self.keywords,
            "songs_with_theme": self.songs_with_theme,
            "strength": self.strength
        }


@dataclass
class VocabularyAnalysis:
    """
    Analisi del vocabolario di una canzone.

    Attributes:
        unique_words: Parole uniche nel testo.
        word_frequency: Frequenza delle parole.
        rare_words: Parole rare/distintive.
        common_words: Parole comuni con altre canzoni.
    """
    unique_words: Set[str] = field(default_factory=set)
    word_frequency: Dict[str, int] = field(default_factory=dict)
    rare_words: List[str] = field(default_factory=list)
    common_words: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "unique_words_count": len(self.unique_words),
            "top_words": sorted(
                self.word_frequency.items(),
                key=lambda x: x[1],
                reverse=True
            )[:20],
            "rare_words": self.rare_words[:10],
            "common_words": self.common_words[:10]
        }


@dataclass
class SongComparisonResult:
    """
    Risultato del confronto tra due canzoni.

    Attributes:
        song1: Prima canzone.
        song2: Seconda canzone.
        semantic_similarity: Similarità semantica complessiva (0-1).
        verse_similarities: Similarità verso per verso.
        common_themes: Temi in comune.
        mood_comparison: Confronto dei mood.
        vocabulary_overlap: Sovrapposizione del vocabolario.
        shared_keywords: Parole chiave condivise.
        differences: Differenze principali.
    """
    song1: Song
    song2: Song
    semantic_similarity: float
    verse_similarities: List[Tuple[str, str, float]] = field(default_factory=list)
    common_themes: List[ThemeMatch] = field(default_factory=list)
    mood_comparison: Dict[str, any] = field(default_factory=dict)
    vocabulary_overlap: float = 0.0
    shared_keywords: List[str] = field(default_factory=list)
    differences: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "song1": {
                "title": self.song1.title,
                "artist": self.song1.artist
            },
            "song2": {
                "title": self.song2.title,
                "artist": self.song2.artist
            },
            "semantic_similarity": self.semantic_similarity,
            "semantic_similarity_percent": f"{self.semantic_similarity * 100:.1f}%",
            "verse_similarities": [
                {"verse1": v1[:50], "verse2": v2[:50], "score": s}
                for v1, v2, s in self.verse_similarities[:5]
            ],
            "common_themes": [t.to_dict() for t in self.common_themes],
            "mood_comparison": self.mood_comparison,
            "vocabulary_overlap": f"{self.vocabulary_overlap * 100:.1f}%",
            "shared_keywords": self.shared_keywords,
            "differences": self.differences
        }

    def get_similarity_level(self) -> str:
        """Restituisce una descrizione del livello di similarità."""
        if self.semantic_similarity >= 0.8:
            return "Molto simili"
        elif self.semantic_similarity >= 0.6:
            return "Simili"
        elif self.semantic_similarity >= 0.4:
            return "Moderatamente simili"
        elif self.semantic_similarity >= 0.2:
            return "Poco simili"
        else:
            return "Molto diverse"


@dataclass
class MultiComparisonResult:
    """
    Risultato del confronto tra più canzoni.

    Attributes:
        songs: Lista delle canzoni confrontate.
        similarity_matrix: Matrice di similarità NxN.
        common_themes: Temi comuni a tutte le canzoni.
        most_similar_pair: Coppia più simile.
        most_different_pair: Coppia più diversa.
        average_similarity: Similarità media.
    """
    songs: List[Song]
    similarity_matrix: List[List[float]]
    common_themes: List[ThemeMatch]
    most_similar_pair: Tuple[str, str, float]
    most_different_pair: Tuple[str, str, float]
    average_similarity: float

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "songs": [{"title": s.title, "artist": s.artist} for s in self.songs],
            "similarity_matrix": self.similarity_matrix,
            "common_themes": [t.to_dict() for t in self.common_themes],
            "most_similar_pair": {
                "song1": self.most_similar_pair[0],
                "song2": self.most_similar_pair[1],
                "score": self.most_similar_pair[2]
            },
            "most_different_pair": {
                "song1": self.most_different_pair[0],
                "song2": self.most_different_pair[1],
                "score": self.most_different_pair[2]
            },
            "average_similarity": self.average_similarity
        }


class SongComparator:
    """
    Comparatore di canzoni.

    Confronta canzoni basandosi su similarità semantica,
    temi comuni, vocabolario e mood.

    Example:
        >>> comparator = SongComparator()
        >>> result = comparator.compare(song1, song2)
        >>> print(f"Similarità: {result.semantic_similarity:.2%}")
    """

    # Stopwords italiane e inglesi
    STOPWORDS = {
        # Italiano
        "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
        "di", "da", "in", "con", "su", "per", "tra", "fra",
        "che", "chi", "cui", "quale", "quanto",
        "e", "o", "ma", "però", "se", "come", "quando", "dove",
        "non", "più", "già", "ancora", "mai", "sempre", "solo",
        "mi", "ti", "ci", "vi", "si", "me", "te", "lui", "lei", "noi", "voi", "loro",
        "mio", "tuo", "suo", "nostro", "vostro",
        "questo", "quello", "cosa", "tutto", "ogni", "altro",
        "essere", "avere", "fare", "dire", "andare", "venire",
        "è", "sono", "sei", "siamo", "siete", "ho", "hai", "ha", "abbiamo",
        # Inglese
        "the", "a", "an", "and", "or", "but", "if", "then", "when", "where",
        "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
        "my", "your", "his", "her", "its", "our", "their",
        "this", "that", "these", "those", "what", "which", "who", "whom",
        "to", "of", "in", "on", "at", "by", "for", "with", "from", "into",
        "not", "no", "yes", "just", "only", "also", "so", "as", "than",
        "all", "some", "any", "every", "each", "both", "few", "more", "most",
        "oh", "yeah", "uh", "ah", "ooh", "na", "la"
    }

    def __init__(self):
        """Inizializza il comparatore."""
        self.matcher = SemanticMatcher()
        self.mood_analyzer = MoodAnalyzer()
        self.logger = logging.getLogger("cerca_dai_testi.comparator")

    def compare(self, song1: Song, song2: Song) -> SongComparisonResult:
        """
        Confronta due canzoni.

        Args:
            song1: Prima canzone.
            song2: Seconda canzone.

        Returns:
            SongComparisonResult: Risultato dettagliato del confronto.
        """
        self.logger.info(f"Confronto: '{song1.title}' vs '{song2.title}'")

        # Calcola similarità semantica complessiva
        semantic_sim = self._compute_semantic_similarity(song1, song2)

        # Confronta versi
        verse_sims = self._compare_verses(song1, song2)

        # Trova temi comuni
        common_themes = self._find_common_themes(song1, song2)

        # Confronta mood
        mood_comparison = self._compare_moods(song1, song2)

        # Analizza vocabolario
        vocab_overlap, shared_keywords = self._analyze_vocabulary_overlap(song1, song2)

        # Identifica differenze
        differences = self._identify_differences(song1, song2, mood_comparison)

        return SongComparisonResult(
            song1=song1,
            song2=song2,
            semantic_similarity=semantic_sim,
            verse_similarities=verse_sims,
            common_themes=common_themes,
            mood_comparison=mood_comparison,
            vocabulary_overlap=vocab_overlap,
            shared_keywords=shared_keywords,
            differences=differences
        )

    def compare_multiple(self, songs: List[Song]) -> MultiComparisonResult:
        """
        Confronta più canzoni tra loro.

        Args:
            songs: Lista di canzoni da confrontare.

        Returns:
            MultiComparisonResult: Risultato del confronto multiplo.
        """
        if len(songs) < 2:
            raise ValueError("Servono almeno 2 canzoni per il confronto")

        n = len(songs)
        matrix = [[0.0] * n for _ in range(n)]

        # Calcola matrice di similarità
        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._compute_semantic_similarity(songs[i], songs[j])
                matrix[i][j] = sim
                matrix[j][i] = sim
                pairs.append((songs[i].title, songs[j].title, sim))

        # Trova coppia più simile e più diversa
        pairs.sort(key=lambda x: x[2], reverse=True)
        most_similar = pairs[0]
        most_different = pairs[-1]

        # Calcola media
        avg_sim = sum(p[2] for p in pairs) / len(pairs)

        # Trova temi comuni a tutte
        common_themes = self._find_common_themes_multiple(songs)

        return MultiComparisonResult(
            songs=songs,
            similarity_matrix=matrix,
            common_themes=common_themes,
            most_similar_pair=most_similar,
            most_different_pair=most_different,
            average_similarity=avg_sim
        )

    def _compute_semantic_similarity(self, song1: Song, song2: Song) -> float:
        """Calcola la similarità semantica tra due canzoni."""
        if not song1.lyrics or not song2.lyrics:
            return 0.0

        # Usa il matcher semantico esistente
        emb1 = self.matcher.get_embedding(song1.lyrics)
        emb2 = self.matcher.get_embedding(song2.lyrics)

        # Calcola cosine similarity
        import numpy as np
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

        return float(max(0, similarity))

    def _compare_verses(
        self,
        song1: Song,
        song2: Song,
        top_k: int = 5
    ) -> List[Tuple[str, str, float]]:
        """Trova i versi più simili tra le due canzoni."""
        if not song1.lyrics or not song2.lyrics:
            return []

        verses1 = [v.strip() for v in song1.lyrics.split('\n') if v.strip() and len(v.strip()) > 10]
        verses2 = [v.strip() for v in song2.lyrics.split('\n') if v.strip() and len(v.strip()) > 10]

        if not verses1 or not verses2:
            return []

        # Limita per performance
        verses1 = verses1[:30]
        verses2 = verses2[:30]

        similarities = []
        for v1 in verses1:
            for v2 in verses2:
                sim = self._compute_text_similarity(v1, v2)
                if sim > 0.3:  # Soglia minima
                    similarities.append((v1, v2, sim))

        # Ordina e prendi i top
        similarities.sort(key=lambda x: x[2], reverse=True)
        return similarities[:top_k]

    def _compute_text_similarity(self, text1: str, text2: str) -> float:
        """Calcola similarità tra due testi brevi."""
        emb1 = self.matcher.get_embedding(text1)
        emb2 = self.matcher.get_embedding(text2)

        import numpy as np
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return float(max(0, similarity))

    def _find_common_themes(self, song1: Song, song2: Song) -> List[ThemeMatch]:
        """Trova temi comuni tra due canzoni."""
        # Analizza mood di entrambe
        mood1 = self.mood_analyzer.analyze(song1.lyrics or "")
        mood2 = self.mood_analyzer.analyze(song2.lyrics or "")

        themes = []

        # Trova mood in comune
        common_moods = set(mood1.mood_scores.keys()) & set(mood2.mood_scores.keys())

        for mood_id in common_moods:
            preset = self.mood_analyzer.get_preset(mood_id)
            if preset:
                # Keywords trovate in entrambe
                kw1 = set(mood1.keywords_found.get(mood_id, []))
                kw2 = set(mood2.keywords_found.get(mood_id, []))
                common_kw = list(kw1 & kw2)

                if common_kw:
                    strength = (mood1.mood_scores[mood_id] + mood2.mood_scores[mood_id]) / 2
                    themes.append(ThemeMatch(
                        theme=preset.name,
                        keywords=common_kw,
                        songs_with_theme=[song1.title, song2.title],
                        strength=strength
                    ))

        # Ordina per forza
        themes.sort(key=lambda x: x.strength, reverse=True)
        return themes

    def _find_common_themes_multiple(self, songs: List[Song]) -> List[ThemeMatch]:
        """Trova temi comuni a tutte le canzoni."""
        all_moods = []
        for song in songs:
            mood = self.mood_analyzer.analyze(song.lyrics or "")
            all_moods.append((song.title, mood))

        # Trova mood presenti in tutte
        if not all_moods:
            return []

        common_mood_ids = set(all_moods[0][1].mood_scores.keys())
        for _, mood in all_moods[1:]:
            common_mood_ids &= set(mood.mood_scores.keys())

        themes = []
        for mood_id in common_mood_ids:
            preset = self.mood_analyzer.get_preset(mood_id)
            if preset:
                all_keywords = set()
                total_score = 0
                for title, mood in all_moods:
                    all_keywords.update(mood.keywords_found.get(mood_id, []))
                    total_score += mood.mood_scores[mood_id]

                themes.append(ThemeMatch(
                    theme=preset.name,
                    keywords=list(all_keywords),
                    songs_with_theme=[s.title for s in songs],
                    strength=total_score / len(songs)
                ))

        themes.sort(key=lambda x: x.strength, reverse=True)
        return themes

    def _compare_moods(self, song1: Song, song2: Song) -> Dict:
        """Confronta i mood delle due canzoni."""
        mood1 = self.mood_analyzer.analyze(song1.lyrics or "")
        mood2 = self.mood_analyzer.analyze(song2.lyrics or "")

        return {
            "song1_primary_mood": mood1.primary_mood,
            "song2_primary_mood": mood2.primary_mood,
            "moods_match": mood1.primary_mood == mood2.primary_mood,
            "song1_confidence": mood1.confidence,
            "song2_confidence": mood2.confidence,
            "song1_all_moods": dict(sorted(
                mood1.mood_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]),
            "song2_all_moods": dict(sorted(
                mood2.mood_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3])
        }

    def _analyze_vocabulary_overlap(
        self,
        song1: Song,
        song2: Song
    ) -> Tuple[float, List[str]]:
        """Analizza la sovrapposizione del vocabolario."""
        words1 = self._extract_meaningful_words(song1.lyrics or "")
        words2 = self._extract_meaningful_words(song2.lyrics or "")

        if not words1 or not words2:
            return 0.0, []

        # Jaccard similarity
        intersection = words1 & words2
        union = words1 | words2

        overlap = len(intersection) / len(union) if union else 0.0

        # Trova parole chiave condivise (le più significative)
        shared = list(intersection)

        # Conta frequenze combinate per ordinare
        text_combined = (song1.lyrics or "") + " " + (song2.lyrics or "")
        word_counts = Counter(
            w.lower() for w in text_combined.split()
            if w.lower() in shared
        )

        shared_keywords = [w for w, _ in word_counts.most_common(15)]

        return overlap, shared_keywords

    def _extract_meaningful_words(self, text: str) -> Set[str]:
        """Estrae parole significative da un testo."""
        words = text.lower().split()
        meaningful = set()

        for word in words:
            # Pulisci punteggiatura
            clean = ''.join(c for c in word if c.isalpha())
            if clean and len(clean) > 2 and clean not in self.STOPWORDS:
                meaningful.add(clean)

        return meaningful

    def _identify_differences(
        self,
        song1: Song,
        song2: Song,
        mood_comparison: Dict
    ) -> List[str]:
        """Identifica le differenze principali tra le canzoni."""
        differences = []

        # Differenza di mood
        if not mood_comparison.get("moods_match"):
            m1 = mood_comparison.get("song1_primary_mood", "sconosciuto")
            m2 = mood_comparison.get("song2_primary_mood", "sconosciuto")
            differences.append(f"Mood diverso: '{song1.title}' è {m1}, '{song2.title}' è {m2}")

        # Differenza di lunghezza
        len1 = len(song1.lyrics or "")
        len2 = len(song2.lyrics or "")
        if len1 > 0 and len2 > 0:
            ratio = max(len1, len2) / min(len1, len2)
            if ratio > 2:
                longer = song1.title if len1 > len2 else song2.title
                differences.append(f"'{longer}' ha un testo significativamente più lungo")

        # Differenza di artista
        if song1.artist.lower() != song2.artist.lower():
            differences.append(f"Artisti diversi: {song1.artist} vs {song2.artist}")

        return differences

    def get_similarity_summary(self, result: SongComparisonResult) -> str:
        """
        Genera un riassunto testuale del confronto.

        Args:
            result: Risultato del confronto.

        Returns:
            str: Riassunto leggibile.
        """
        lines = [
            f"Confronto: '{result.song1.title}' vs '{result.song2.title}'",
            f"Artisti: {result.song1.artist} vs {result.song2.artist}",
            "",
            f"Similarità semantica: {result.semantic_similarity:.1%} ({result.get_similarity_level()})",
            f"Sovrapposizione vocabolario: {result.vocabulary_overlap:.1%}",
            ""
        ]

        if result.common_themes:
            lines.append("Temi in comune:")
            for theme in result.common_themes[:3]:
                lines.append(f"  - {theme.theme}: {', '.join(theme.keywords[:5])}")
            lines.append("")

        if result.mood_comparison:
            m1 = result.mood_comparison.get("song1_primary_mood")
            m2 = result.mood_comparison.get("song2_primary_mood")
            if result.mood_comparison.get("moods_match"):
                lines.append(f"Mood: Entrambe hanno un tono {m1}")
            else:
                lines.append(f"Mood: '{result.song1.title}' è {m1}, '{result.song2.title}' è {m2}")
            lines.append("")

        if result.verse_similarities:
            lines.append("Versi più simili:")
            v1, v2, score = result.verse_similarities[0]
            lines.append(f"  \"{v1[:60]}...\"")
            lines.append(f"  \"{v2[:60]}...\"")
            lines.append(f"  (similarità: {score:.1%})")
            lines.append("")

        if result.shared_keywords:
            lines.append(f"Parole chiave condivise: {', '.join(result.shared_keywords[:10])}")

        if result.differences:
            lines.append("")
            lines.append("Differenze:")
            for diff in result.differences:
                lines.append(f"  - {diff}")

        return "\n".join(lines)

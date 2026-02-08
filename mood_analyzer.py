"""
Modulo per l'analisi del mood e ricerca per emozione.

Fornisce preset di ricerca basati su mood/emozioni
e analisi automatica del sentimento nei testi.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from config import Config


@dataclass
class MoodPreset:
    """
    Preset di ricerca basato su un mood/emozione.

    Attributes:
        name: Nome del mood (es. "triste", "felice").
        emoji: Emoji rappresentativa.
        description: Descrizione del mood.
        keywords_it: Parole chiave in italiano.
        keywords_en: Parole chiave in inglese.
        search_terms: Termini di ricerca suggeriti.
        color: Colore associato (hex).
    """
    name: str
    emoji: str
    description: str
    keywords_it: List[str]
    keywords_en: List[str]
    search_terms: List[str]
    color: str = "#6366f1"

    @property
    def all_keywords(self) -> List[str]:
        """Restituisce tutte le parole chiave."""
        return self.keywords_it + self.keywords_en


# Preset di mood predefiniti
MOOD_PRESETS: Dict[str, MoodPreset] = {
    "happy": MoodPreset(
        name="Felice",
        emoji="😊",
        description="Canzoni allegre e positive",
        keywords_it=["felice", "gioia", "allegria", "sorriso", "festa", "ballare", "ridere", "amore"],
        keywords_en=["happy", "joy", "smile", "party", "dance", "laugh", "love", "celebration"],
        search_terms=["happy song", "feel good", "party anthem", "canzone allegra"],
        color="#22c55e"
    ),
    "sad": MoodPreset(
        name="Triste",
        emoji="😢",
        description="Canzoni malinconiche e riflessive",
        keywords_it=["triste", "lacrime", "piangere", "dolore", "addio", "solitudine", "cuore spezzato"],
        keywords_en=["sad", "tears", "cry", "pain", "goodbye", "lonely", "heartbreak", "sorrow"],
        search_terms=["sad song", "heartbreak", "canzone triste", "ballad"],
        color="#6366f1"
    ),
    "romantic": MoodPreset(
        name="Romantico",
        emoji="💕",
        description="Canzoni d'amore e romantiche",
        keywords_it=["amore", "cuore", "passione", "bacio", "insieme", "eternamente", "anima gemella"],
        keywords_en=["love", "heart", "passion", "kiss", "together", "forever", "soulmate", "romance"],
        search_terms=["love song", "romantic", "canzone d'amore", "duet"],
        color="#ec4899"
    ),
    "energetic": MoodPreset(
        name="Energico",
        emoji="⚡",
        description="Canzoni cariche di energia",
        keywords_it=["energia", "forza", "potenza", "correre", "vincere", "combattere", "fuoco"],
        keywords_en=["energy", "power", "strong", "run", "win", "fight", "fire", "unstoppable"],
        search_terms=["workout music", "pump up", "energia", "motivational"],
        color="#f59e0b"
    ),
    "calm": MoodPreset(
        name="Calmo",
        emoji="🌙",
        description="Canzoni rilassanti e tranquille",
        keywords_it=["calma", "pace", "silenzio", "notte", "sogno", "riposo", "sereno", "mare"],
        keywords_en=["calm", "peace", "quiet", "night", "dream", "rest", "serene", "ocean"],
        search_terms=["relaxing music", "chill", "ambient", "peaceful"],
        color="#06b6d4"
    ),
    "angry": MoodPreset(
        name="Arrabbiato",
        emoji="😤",
        description="Canzoni intense e aggressive",
        keywords_it=["rabbia", "furia", "urlare", "distruggere", "odio", "vendetta", "rivoluzione"],
        keywords_en=["angry", "rage", "scream", "destroy", "hate", "revenge", "revolution", "fury"],
        search_terms=["angry song", "metal", "rage", "intense"],
        color="#ef4444"
    ),
    "nostalgic": MoodPreset(
        name="Nostalgico",
        emoji="🌅",
        description="Canzoni che evocano ricordi",
        keywords_it=["ricordi", "passato", "giovinezza", "tempo", "memoria", "ritorno", "ieri"],
        keywords_en=["memories", "past", "youth", "time", "remember", "return", "yesterday", "old times"],
        search_terms=["nostalgic", "throwback", "retro", "memories"],
        color="#8b5cf6"
    ),
    "hopeful": MoodPreset(
        name="Speranzoso",
        emoji="🌈",
        description="Canzoni di speranza e futuro",
        keywords_it=["speranza", "futuro", "domani", "sogno", "libertà", "volare", "nuovo inizio"],
        keywords_en=["hope", "future", "tomorrow", "dream", "freedom", "fly", "new beginning", "believe"],
        search_terms=["hopeful song", "inspirational", "speranza", "uplifting"],
        color="#10b981"
    ),
    "rebellious": MoodPreset(
        name="Ribelle",
        emoji="🤘",
        description="Canzoni di ribellione e anticonformismo",
        keywords_it=["ribelle", "libertà", "rivoluzione", "contro", "regole", "anarchia", "protesta"],
        keywords_en=["rebel", "freedom", "revolution", "against", "rules", "anarchy", "protest", "fight"],
        search_terms=["rebel song", "protest", "punk", "revolution"],
        color="#f97316"
    ),
    "dreamy": MoodPreset(
        name="Sognante",
        emoji="✨",
        description="Canzoni oniriche e atmosferiche",
        keywords_it=["sogno", "nuvole", "stelle", "volare", "magia", "infinito", "fantasia"],
        keywords_en=["dream", "clouds", "stars", "fly", "magic", "infinite", "fantasy", "ethereal"],
        search_terms=["dreamy", "atmospheric", "shoegaze", "ethereal"],
        color="#a855f7"
    )
}


@dataclass
class MoodAnalysisResult:
    """
    Risultato dell'analisi del mood.

    Attributes:
        primary_mood: Mood principale rilevato.
        mood_scores: Score per ogni mood (0-1).
        keywords_found: Parole chiave trovate.
        confidence: Confidenza dell'analisi (0-1).
    """
    primary_mood: str
    mood_scores: Dict[str, float]
    keywords_found: Dict[str, List[str]]
    confidence: float

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "primary_mood": self.primary_mood,
            "mood_scores": self.mood_scores,
            "keywords_found": self.keywords_found,
            "confidence": self.confidence
        }


class MoodAnalyzer:
    """
    Analizzatore di mood per testi di canzoni.

    Analizza il testo per identificare il mood prevalente
    e fornisce preset di ricerca basati su emozioni.

    Example:
        >>> analyzer = MoodAnalyzer()
        >>> result = analyzer.analyze("Lacrime scendono, il cuore spezzato")
        >>> print(result.primary_mood)
        'sad'
    """

    def __init__(self):
        """Inizializza l'analizzatore."""
        self.presets = MOOD_PRESETS
        self.logger = logging.getLogger("cerca_dai_testi.mood")

    def get_preset(self, mood_id: str) -> Optional[MoodPreset]:
        """
        Ottiene un preset per ID.

        Args:
            mood_id: ID del mood (es. "happy", "sad").

        Returns:
            Optional[MoodPreset]: Il preset se esiste.
        """
        return self.presets.get(mood_id)

    def list_presets(self) -> List[MoodPreset]:
        """
        Lista tutti i preset disponibili.

        Returns:
            List[MoodPreset]: Lista dei preset.
        """
        return list(self.presets.values())

    def get_search_query(self, mood_id: str) -> str:
        """
        Genera una query di ricerca per un mood.

        Args:
            mood_id: ID del mood.

        Returns:
            str: Query di ricerca combinata.
        """
        preset = self.get_preset(mood_id)
        if not preset:
            return ""

        # Combina alcune parole chiave
        keywords = preset.keywords_it[:3] + preset.keywords_en[:2]
        return " ".join(keywords)

    def analyze(self, text: str) -> MoodAnalysisResult:
        """
        Analizza il mood di un testo.

        Args:
            text: Testo da analizzare.

        Returns:
            MoodAnalysisResult: Risultato dell'analisi.
        """
        text_lower = text.lower()
        words = set(text_lower.split())

        mood_scores: Dict[str, float] = {}
        keywords_found: Dict[str, List[str]] = {}

        for mood_id, preset in self.presets.items():
            found = []
            for keyword in preset.all_keywords:
                if keyword.lower() in text_lower:
                    found.append(keyword)

            # Calcola score basato sul numero di keyword trovate
            if found:
                score = min(1.0, len(found) / 5)  # Normalizza
                mood_scores[mood_id] = score
                keywords_found[mood_id] = found

        # Trova il mood principale
        if mood_scores:
            primary_mood = max(mood_scores, key=mood_scores.get)
            confidence = mood_scores[primary_mood]
        else:
            primary_mood = "neutral"
            confidence = 0.0

        return MoodAnalysisResult(
            primary_mood=primary_mood,
            mood_scores=mood_scores,
            keywords_found=keywords_found,
            confidence=confidence
        )

    def suggest_mood_from_query(self, query: str) -> Optional[str]:
        """
        Suggerisce un mood basato sulla query utente.

        Args:
            query: Query dell'utente.

        Returns:
            Optional[str]: ID del mood suggerito.
        """
        result = self.analyze(query)
        if result.confidence > 0.2:
            return result.primary_mood
        return None


@dataclass
class SearchFilters:
    """
    Filtri avanzati per la ricerca.

    Attributes:
        mood: Mood/emozione da cercare.
        language: Lingua preferita ("it", "en", "any").
        min_score: Score minimo di rilevanza.
        year_from: Anno minimo di uscita.
        year_to: Anno massimo di uscita.
        exclude_artists: Artisti da escludere.
        include_artists: Artisti da includere preferenzialmente.
        genres: Generi preferiti.
    """
    mood: Optional[str] = None
    language: str = "any"
    min_score: float = 0.3
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    exclude_artists: List[str] = None
    include_artists: List[str] = None
    genres: List[str] = None

    def __post_init__(self):
        if self.exclude_artists is None:
            self.exclude_artists = []
        if self.include_artists is None:
            self.include_artists = []
        if self.genres is None:
            self.genres = []

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "mood": self.mood,
            "language": self.language,
            "min_score": self.min_score,
            "year_from": self.year_from,
            "year_to": self.year_to,
            "exclude_artists": self.exclude_artists,
            "include_artists": self.include_artists,
            "genres": self.genres
        }

    def matches_song(self, song, score: float) -> bool:
        """
        Verifica se una canzone passa i filtri.

        Args:
            song: Song da verificare.
            score: Score di rilevanza.

        Returns:
            bool: True se passa tutti i filtri.
        """
        # Filtro score
        if score < self.min_score:
            return False

        # Filtro artisti esclusi
        if self.exclude_artists:
            artist_lower = song.artist.lower()
            for excluded in self.exclude_artists:
                if excluded.lower() in artist_lower:
                    return False

        # Filtro anno
        if song.release_date:
            try:
                year = int(song.release_date.split()[-1])
                if self.year_from and year < self.year_from:
                    return False
                if self.year_to and year > self.year_to:
                    return False
            except (ValueError, IndexError):
                pass

        return True


class AdvancedSearch:
    """
    Ricerca avanzata con filtri e mood.

    Combina la ricerca semantica con filtri avanzati
    e preset di mood per risultati più mirati.
    """

    def __init__(self):
        """Inizializza la ricerca avanzata."""
        self.mood_analyzer = MoodAnalyzer()
        self.logger = logging.getLogger("cerca_dai_testi.advanced_search")

    def enhance_query_with_mood(
        self,
        query: str,
        mood_id: Optional[str] = None
    ) -> str:
        """
        Migliora la query aggiungendo termini di mood.

        Args:
            query: Query originale.
            mood_id: ID del mood (opzionale, auto-detect se None).

        Returns:
            str: Query migliorata.
        """
        if not mood_id:
            # Auto-detect mood dalla query
            mood_id = self.mood_analyzer.suggest_mood_from_query(query)

        if mood_id:
            preset = self.mood_analyzer.get_preset(mood_id)
            if preset:
                # Aggiungi alcune parole chiave del mood
                extra_terms = preset.keywords_it[:2] + preset.keywords_en[:1]
                return f"{query} {' '.join(extra_terms)}"

        return query

    def filter_results(
        self,
        results: list,
        filters: SearchFilters
    ) -> list:
        """
        Filtra i risultati secondo i criteri specificati.

        Args:
            results: Lista di MatchResult.
            filters: Filtri da applicare.

        Returns:
            list: Risultati filtrati.
        """
        filtered = []
        for result in results:
            if filters.matches_song(result.song, result.score):
                filtered.append(result)

        self.logger.info(
            f"Filtrati {len(results)} -> {len(filtered)} risultati"
        )
        return filtered

    def get_mood_suggestions(self, query: str) -> List[Tuple[str, MoodPreset, float]]:
        """
        Suggerisce mood basati sulla query.

        Args:
            query: Query dell'utente.

        Returns:
            List[Tuple]: Lista di (mood_id, preset, score).
        """
        analysis = self.mood_analyzer.analyze(query)
        suggestions = []

        for mood_id, score in sorted(
            analysis.mood_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]:
            preset = self.mood_analyzer.get_preset(mood_id)
            if preset:
                suggestions.append((mood_id, preset, score))

        return suggestions

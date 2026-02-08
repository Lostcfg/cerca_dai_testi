"""
Modulo per la gestione dei dati utente.

Gestisce:
- Cronologia delle ricerche
- Canzoni preferite
- Impostazioni utente (tema, preferenze)
- Export/Import dati
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from lyrics_fetcher import Song
from semantic_matcher import MatchResult


class Theme(Enum):
    """Temi disponibili per l'interfaccia."""
    DARK = "dark"
    LIGHT = "light"
    AUTO = "auto"


@dataclass
class SearchHistoryEntry:
    """
    Voce della cronologia ricerche.

    Attributes:
        query: Query di ricerca.
        timestamp: Data e ora della ricerca.
        results_count: Numero di risultati trovati.
        filters_used: Filtri applicati.
        top_results: Primi risultati (titoli).
    """
    query: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    results_count: int = 0
    filters_used: Dict = field(default_factory=dict)
    top_results: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "query": self.query,
            "timestamp": self.timestamp,
            "results_count": self.results_count,
            "filters_used": self.filters_used,
            "top_results": self.top_results
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SearchHistoryEntry":
        """Crea da dizionario."""
        return cls(
            query=data.get("query", ""),
            timestamp=data.get("timestamp", ""),
            results_count=data.get("results_count", 0),
            filters_used=data.get("filters_used", {}),
            top_results=data.get("top_results", [])
        )


@dataclass
class FavoriteSong:
    """
    Canzone preferita salvata.

    Attributes:
        song_id: ID della canzone (Genius).
        title: Titolo.
        artist: Artista.
        url: URL Genius.
        added_at: Data di aggiunta.
        notes: Note personali.
        tags: Tag personalizzati.
        lyrics_snippet: Estratto del testo.
    """
    song_id: int
    title: str
    artist: str
    url: str = ""
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    lyrics_snippet: str = ""

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "song_id": self.song_id,
            "title": self.title,
            "artist": self.artist,
            "url": self.url,
            "added_at": self.added_at,
            "notes": self.notes,
            "tags": self.tags,
            "lyrics_snippet": self.lyrics_snippet
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FavoriteSong":
        """Crea da dizionario."""
        return cls(
            song_id=data.get("song_id", 0),
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            url=data.get("url", ""),
            added_at=data.get("added_at", ""),
            notes=data.get("notes", ""),
            tags=data.get("tags", []),
            lyrics_snippet=data.get("lyrics_snippet", "")
        )

    @classmethod
    def from_song(cls, song: Song, notes: str = "", tags: List[str] = None) -> "FavoriteSong":
        """Crea da oggetto Song."""
        # Converti song.id (str) a int per FavoriteSong.song_id
        song_id = int(song.id) if isinstance(song.id, str) else song.id
        return cls(
            song_id=song_id,
            title=song.title,
            artist=song.artist,
            url=song.url or "",
            notes=notes,
            tags=tags or [],
            lyrics_snippet=(song.lyrics or "")[:200]
        )


@dataclass
class UserSettings:
    """
    Impostazioni utente.

    Attributes:
        theme: Tema interfaccia (dark/light/auto).
        language: Lingua preferita per i risultati.
        default_results: Numero predefinito di risultati.
        min_score: Score minimo predefinito.
        auto_save_history: Salva automaticamente la cronologia.
        max_history_items: Massimo voci in cronologia.
        show_lyrics_preview: Mostra anteprima testi.
        youtube_music: Usa YouTube Music invece di YouTube.
        notifications: Abilita notifiche.
    """
    theme: str = "dark"
    language: str = "any"
    default_results: int = 10
    min_score: float = 0.3
    auto_save_history: bool = True
    max_history_items: int = 100
    show_lyrics_preview: bool = True
    youtube_music: bool = False
    notifications: bool = True

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserSettings":
        """Crea da dizionario."""
        return cls(
            theme=data.get("theme", "dark"),
            language=data.get("language", "any"),
            default_results=data.get("default_results", 10),
            min_score=data.get("min_score", 0.3),
            auto_save_history=data.get("auto_save_history", True),
            max_history_items=data.get("max_history_items", 100),
            show_lyrics_preview=data.get("show_lyrics_preview", True),
            youtube_music=data.get("youtube_music", False),
            notifications=data.get("notifications", True)
        )


class UserDataManager:
    """
    Gestore dei dati utente.

    Salva e carica cronologia, preferiti e impostazioni
    in un file JSON locale.

    Example:
        >>> manager = UserDataManager()
        >>> manager.add_to_history("amore e libertà", results)
        >>> manager.add_favorite(song)
        >>> manager.settings.theme = "light"
        >>> manager.save()
    """

    DEFAULT_PATH = Path.home() / ".cerca_dai_testi" / "user_data.json"

    def __init__(self, data_path: Optional[Path] = None):
        """
        Inizializza il gestore.

        Args:
            data_path: Percorso del file dati. Default: ~/.cerca_dai_testi/user_data.json
        """
        self.data_path = data_path or self.DEFAULT_PATH
        self.logger = logging.getLogger("cerca_dai_testi.user_data")

        # Dati
        self.history: List[SearchHistoryEntry] = []
        self.favorites: List[FavoriteSong] = []
        self.settings = UserSettings()

        # Carica dati esistenti
        self._load()

    def _load(self) -> None:
        """Carica i dati dal file."""
        if not self.data_path.exists():
            self.logger.info("Nessun file dati esistente, inizializzazione vuota")
            return

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Carica cronologia
            self.history = [
                SearchHistoryEntry.from_dict(h)
                for h in data.get("history", [])
            ]

            # Carica preferiti
            self.favorites = [
                FavoriteSong.from_dict(f)
                for f in data.get("favorites", [])
            ]

            # Carica impostazioni
            self.settings = UserSettings.from_dict(data.get("settings", {}))

            self.logger.info(
                f"Caricati {len(self.history)} ricerche, "
                f"{len(self.favorites)} preferiti"
            )

        except Exception as e:
            self.logger.error(f"Errore caricamento dati: {e}")

    def save(self) -> None:
        """Salva i dati nel file."""
        # Crea directory se non esiste
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "history": [h.to_dict() for h in self.history],
            "favorites": [f.to_dict() for f in self.favorites],
            "settings": self.settings.to_dict(),
            "last_saved": datetime.now().isoformat()
        }

        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info("Dati salvati con successo")
        except Exception as e:
            self.logger.error(f"Errore salvataggio dati: {e}")

    # --- Cronologia ---

    def add_to_history(
        self,
        query: str,
        results: List[MatchResult] = None,
        filters: Dict = None
    ) -> None:
        """
        Aggiunge una ricerca alla cronologia.

        Args:
            query: Query di ricerca.
            results: Risultati ottenuti.
            filters: Filtri applicati.
        """
        if not self.settings.auto_save_history:
            return

        entry = SearchHistoryEntry(
            query=query,
            results_count=len(results) if results else 0,
            filters_used=filters or {},
            top_results=[r.song.title for r in (results or [])[:5]]
        )

        self.history.insert(0, entry)

        # Limita dimensione cronologia
        if len(self.history) > self.settings.max_history_items:
            self.history = self.history[:self.settings.max_history_items]

        self.save()

    def get_history(self, limit: int = 50) -> List[SearchHistoryEntry]:
        """Restituisce la cronologia recente."""
        return self.history[:limit]

    def search_history(self, keyword: str) -> List[SearchHistoryEntry]:
        """Cerca nella cronologia."""
        keyword_lower = keyword.lower()
        return [
            h for h in self.history
            if keyword_lower in h.query.lower()
        ]

    def clear_history(self) -> None:
        """Svuota la cronologia."""
        self.history = []
        self.save()

    def remove_from_history(self, index: int) -> bool:
        """Rimuove una voce dalla cronologia."""
        if 0 <= index < len(self.history):
            del self.history[index]
            self.save()
            return True
        return False

    def get_frequent_searches(self, top_k: int = 10) -> List[Tuple[str, int]]:
        """Restituisce le ricerche più frequenti."""
        from collections import Counter
        queries = [h.query.lower() for h in self.history]
        return Counter(queries).most_common(top_k)

    # --- Preferiti ---

    def add_favorite(
        self,
        song: Song,
        notes: str = "",
        tags: List[str] = None
    ) -> bool:
        """
        Aggiunge una canzone ai preferiti.

        Args:
            song: Canzone da aggiungere.
            notes: Note personali.
            tags: Tag personalizzati.

        Returns:
            bool: True se aggiunta, False se già presente.
        """
        # Controlla duplicati
        if self.is_favorite(song.id):
            self.logger.info(f"'{song.title}' già nei preferiti")
            return False

        favorite = FavoriteSong.from_song(song, notes, tags)
        self.favorites.append(favorite)
        self.save()

        self.logger.info(f"Aggiunto ai preferiti: '{song.title}'")
        return True

    def remove_favorite(self, song_id: int) -> bool:
        """Rimuove una canzone dai preferiti."""
        for i, fav in enumerate(self.favorites):
            if fav.song_id == song_id:
                del self.favorites[i]
                self.save()
                return True
        return False

    def is_favorite(self, song_id: int) -> bool:
        """Controlla se una canzone è nei preferiti."""
        return any(f.song_id == song_id for f in self.favorites)

    def get_favorites(self, limit: int = None) -> List[FavoriteSong]:
        """Restituisce i preferiti."""
        if limit:
            return self.favorites[:limit]
        return self.favorites

    def search_favorites(self, keyword: str) -> List[FavoriteSong]:
        """Cerca nei preferiti."""
        keyword_lower = keyword.lower()
        return [
            f for f in self.favorites
            if keyword_lower in f.title.lower()
            or keyword_lower in f.artist.lower()
            or any(keyword_lower in tag.lower() for tag in f.tags)
        ]

    def get_favorites_by_tag(self, tag: str) -> List[FavoriteSong]:
        """Filtra preferiti per tag."""
        tag_lower = tag.lower()
        return [
            f for f in self.favorites
            if any(tag_lower in t.lower() for t in f.tags)
        ]

    def update_favorite_notes(self, song_id: int, notes: str) -> bool:
        """Aggiorna le note di un preferito."""
        for fav in self.favorites:
            if fav.song_id == song_id:
                fav.notes = notes
                self.save()
                return True
        return False

    def add_tag_to_favorite(self, song_id: int, tag: str) -> bool:
        """Aggiunge un tag a un preferito."""
        for fav in self.favorites:
            if fav.song_id == song_id:
                if tag not in fav.tags:
                    fav.tags.append(tag)
                    self.save()
                return True
        return False

    def get_all_tags(self) -> List[str]:
        """Restituisce tutti i tag usati."""
        tags = set()
        for fav in self.favorites:
            tags.update(fav.tags)
        return sorted(tags)

    # --- Impostazioni ---

    def set_theme(self, theme: str) -> None:
        """Imposta il tema."""
        if theme in ["dark", "light", "auto"]:
            self.settings.theme = theme
            self.save()

    def get_theme(self) -> str:
        """Restituisce il tema corrente."""
        return self.settings.theme

    def update_settings(self, **kwargs) -> None:
        """Aggiorna le impostazioni."""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()

    # --- Export/Import ---

    def export_data(self, path: Path, include_history: bool = True) -> None:
        """
        Esporta tutti i dati in un file.

        Args:
            path: Percorso del file di export.
            include_history: Include la cronologia.
        """
        data = {
            "favorites": [f.to_dict() for f in self.favorites],
            "settings": self.settings.to_dict(),
            "exported_at": datetime.now().isoformat()
        }

        if include_history:
            data["history"] = [h.to_dict() for h in self.history]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Dati esportati in {path}")

    def import_data(self, path: Path, merge: bool = True) -> None:
        """
        Importa dati da un file.

        Args:
            path: Percorso del file da importare.
            merge: Se True, unisce ai dati esistenti.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Importa preferiti
        imported_favorites = [
            FavoriteSong.from_dict(f)
            for f in data.get("favorites", [])
        ]

        if merge:
            # Aggiungi solo quelli non presenti
            existing_ids = {f.song_id for f in self.favorites}
            for fav in imported_favorites:
                if fav.song_id not in existing_ids:
                    self.favorites.append(fav)
        else:
            self.favorites = imported_favorites

        # Importa cronologia
        if "history" in data:
            imported_history = [
                SearchHistoryEntry.from_dict(h)
                for h in data.get("history", [])
            ]
            if merge:
                self.history.extend(imported_history)
                # Riordina per timestamp
                self.history.sort(
                    key=lambda x: x.timestamp,
                    reverse=True
                )
            else:
                self.history = imported_history

        self.save()
        self.logger.info(f"Dati importati da {path}")

    def get_statistics(self) -> Dict:
        """Restituisce statistiche sui dati utente."""
        return {
            "total_searches": len(self.history),
            "total_favorites": len(self.favorites),
            "unique_artists": len(set(f.artist for f in self.favorites)),
            "total_tags": len(self.get_all_tags()),
            "frequent_searches": self.get_frequent_searches(5),
            "settings": self.settings.to_dict()
        }


# CSS per i temi
THEME_CSS = {
    "dark": """
        :root {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #1e1e2e;
            --text-primary: #e2e8f0;
            --text-secondary: #94a3b8;
            --accent: #60a5fa;
            --accent-hover: #3b82f6;
            --success: #22c55e;
            --warning: #eab308;
            --error: #ef4444;
            --border: rgba(255,255,255,0.1);
        }
    """,
    "light": """
        :root {
            --bg-primary: #f8fafc;
            --bg-secondary: #e2e8f0;
            --bg-card: #ffffff;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --success: #16a34a;
            --warning: #ca8a04;
            --error: #dc2626;
            --border: rgba(0,0,0,0.1);
        }
    """
}


def get_theme_css(theme: str = "dark") -> str:
    """Restituisce il CSS per il tema specificato."""
    return THEME_CSS.get(theme, THEME_CSS["dark"])

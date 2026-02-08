"""
Modulo per il recupero dei testi delle canzoni.

Fornisce un'interfaccia unificata per accedere alle API di lyrics,
con supporto per Genius API e caching integrato.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from config import Config
from utils import Cache, RateLimiter, retry_on_error, clean_lyrics


@dataclass
class Song:
    """
    Rappresenta una canzone con i suoi metadati.

    Attributes:
        id: ID univoco della canzone (da Genius).
        title: Titolo della canzone.
        artist: Nome dell'artista.
        lyrics: Testo completo della canzone.
        url: URL della pagina Genius.
        thumbnail_url: URL dell'immagine di copertina.
        release_date: Data di rilascio (opzionale).

    Example:
        >>> song = Song(
        ...     id="123",
        ...     title="Bohemian Rhapsody",
        ...     artist="Queen",
        ...     lyrics="Is this the real life...",
        ...     url="https://genius.com/..."
        ... )
    """
    id: str
    title: str
    artist: str
    lyrics: str = ""
    url: str = ""
    thumbnail_url: str = ""
    release_date: Optional[str] = None
    _cleaned_lyrics: str = field(default="", repr=False)

    @property
    def cleaned_lyrics(self) -> str:
        """Restituisce i lyrics puliti (senza annotazioni)."""
        if not self._cleaned_lyrics and self.lyrics:
            self._cleaned_lyrics = clean_lyrics(self.lyrics)
        return self._cleaned_lyrics

    def to_dict(self) -> dict:
        """Converte la canzone in dizionario."""
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "lyrics": self.lyrics,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "release_date": self.release_date
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Song":
        """Crea una Song da un dizionario."""
        return cls(
            id=data["id"],
            title=data["title"],
            artist=data["artist"],
            lyrics=data.get("lyrics", ""),
            url=data.get("url", ""),
            thumbnail_url=data.get("thumbnail_url", ""),
            release_date=data.get("release_date")
        )


class LyricsFetcher:
    """
    Classe per il recupero dei testi delle canzoni da Genius.

    Gestisce la ricerca di canzoni, il recupero dei testi,
    il caching e il rate limiting delle richieste API.

    Attributes:
        api_token: Token di autenticazione per Genius API.
        cache: Sistema di caching per i risultati.
        rate_limiter: Rate limiter per le chiamate API.
        logger: Logger per il modulo.

    Example:
        >>> fetcher = LyricsFetcher()
        >>> songs = fetcher.search("amore")
        >>> for song in songs:
        ...     print(f"{song.title} - {song.artist}")
    """

    def __init__(self, api_token: Optional[str] = None):
        """
        Inizializza il LyricsFetcher.

        Args:
            api_token: Token API di Genius (opzionale, usa Config se non fornito).

        Raises:
            ValueError: Se il token API non è configurato.
        """
        self.api_token = api_token or Config.GENIUS_API_TOKEN
        if not self.api_token:
            raise ValueError(
                "Token API Genius non configurato. "
                "Imposta GENIUS_API_TOKEN nel file .env"
            )

        self.cache = Cache("lyrics_cache.json")
        self.rate_limiter = RateLimiter()
        self.logger = logging.getLogger("cerca_dai_testi.lyrics_fetcher")

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "User-Agent": "CercaDaiTesti/1.0"
        })

    @retry_on_error(exceptions=(requests.RequestException,))
    def _api_request(
        self,
        endpoint: str,
        params: Optional[dict] = None
    ) -> dict:
        """
        Esegue una richiesta all'API di Genius.

        Args:
            endpoint: Endpoint dell'API (es. "/search").
            params: Parametri della query (opzionali).

        Returns:
            dict: Risposta JSON dell'API.

        Raises:
            requests.RequestException: In caso di errore di rete.
            ValueError: Se la risposta non è valida.
        """
        self.rate_limiter.acquire()

        url = f"{Config.GENIUS_BASE_URL}{endpoint}"
        self.logger.debug(f"API request: {url} params={params}")

        response = self._session.get(
            url,
            params=params,
            timeout=Config.REQUEST_TIMEOUT
        )
        response.raise_for_status()

        data = response.json()
        if "response" not in data:
            raise ValueError(f"Risposta API non valida: {data}")

        return data["response"]

    def search(
        self,
        query: str,
        limit: int = Config.DEFAULT_LIMIT
    ) -> List[Song]:
        """
        Cerca canzoni per parola chiave.

        Esegue una ricerca testuale nell'archivio Genius e restituisce
        le canzoni corrispondenti con i metadati base.

        Args:
            query: Testo da cercare.
            limit: Numero massimo di risultati (default 5).

        Returns:
            List[Song]: Lista di canzoni trovate.

        Example:
            >>> fetcher = LyricsFetcher()
            >>> songs = fetcher.search("love", limit=3)
            >>> len(songs)
            3
        """
        # Controlla cache
        cache_key = f"search:{query}:{limit}"
        cached = self.cache.get(cache_key)
        if cached:
            self.logger.debug(f"Cache hit per search: {query}")
            return [Song.from_dict(s) for s in cached]

        self.logger.info(f"Ricerca canzoni per: {query}")

        try:
            response = self._api_request("/search", {"q": query})
        except Exception as e:
            self.logger.error(f"Errore ricerca: {e}")
            return []

        songs = []
        hits = response.get("hits", [])[:limit]

        for hit in hits:
            if hit.get("type") != "song":
                continue

            result = hit.get("result", {})
            song = Song(
                id=str(result.get("id", "")),
                title=result.get("title", "Unknown"),
                artist=result.get("primary_artist", {}).get("name", "Unknown"),
                url=result.get("url", ""),
                thumbnail_url=result.get("song_art_image_thumbnail_url", ""),
                release_date=result.get("release_date_for_display")
            )
            songs.append(song)

        # Salva in cache
        self.cache.set(cache_key, [s.to_dict() for s in songs])

        self.logger.info(f"Trovate {len(songs)} canzoni")
        return songs

    def search_by_terms(
        self,
        terms: List[str],
        limit_per_term: int = 5
    ) -> List[Song]:
        """
        Cerca canzoni usando multipli termini di ricerca.

        Esegue ricerche separate per ogni termine e combina i risultati,
        rimuovendo i duplicati.

        Args:
            terms: Lista di termini da cercare.
            limit_per_term: Risultati massimi per termine.

        Returns:
            List[Song]: Lista combinata di canzoni uniche.

        Example:
            >>> fetcher = LyricsFetcher()
            >>> songs = fetcher.search_by_terms(["love", "heart"], limit_per_term=3)
        """
        seen_ids: set = set()
        all_songs: List[Song] = []

        for term in terms:
            songs = self.search(term, limit=limit_per_term)
            for song in songs:
                if song.id not in seen_ids:
                    seen_ids.add(song.id)
                    all_songs.append(song)

        return all_songs

    @retry_on_error(exceptions=(requests.RequestException,))
    def _scrape_lyrics(self, url: str) -> str:
        """
        Estrae i lyrics dalla pagina Genius.

        Genius non espone i lyrics via API, quindi è necessario
        fare scraping della pagina HTML.

        Args:
            url: URL della pagina Genius.

        Returns:
            str: Testo della canzone.
        """
        self.rate_limiter.acquire()

        self.logger.debug(f"Scraping lyrics da: {url}")

        response = requests.get(
            url,
            headers={"User-Agent": "CercaDaiTesti/1.0"},
            timeout=Config.REQUEST_TIMEOUT
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Genius usa diversi selettori per i lyrics
        lyrics_containers = soup.select('[data-lyrics-container="true"]')

        if lyrics_containers:
            # Nuovo formato Genius
            lyrics_parts = []
            for container in lyrics_containers:
                # Sostituisci <br> con newline
                for br in container.find_all("br"):
                    br.replace_with("\n")
                lyrics_parts.append(container.get_text())
            return "\n".join(lyrics_parts)

        # Fallback: vecchio formato
        lyrics_div = soup.select_one(".lyrics")
        if lyrics_div:
            return lyrics_div.get_text()

        self.logger.warning(f"Lyrics non trovati per: {url}")
        return ""

    def get_lyrics(self, song: Song) -> Song:
        """
        Recupera i lyrics completi per una canzone.

        Se i lyrics sono già presenti nella canzone, li restituisce
        direttamente. Altrimenti, li scarica dalla pagina Genius.

        Args:
            song: Canzone per cui recuperare i lyrics.

        Returns:
            Song: La stessa canzone con i lyrics popolati.

        Example:
            >>> fetcher = LyricsFetcher()
            >>> songs = fetcher.search("Bohemian Rhapsody", limit=1)
            >>> song = fetcher.get_lyrics(songs[0])
            >>> print(song.lyrics[:50])
            'Is this the real life? Is this just fantasy?'
        """
        if song.lyrics:
            return song

        # Controlla cache
        cache_key = f"lyrics:{song.id}"
        cached = self.cache.get(cache_key)
        if cached:
            self.logger.debug(f"Cache hit per lyrics: {song.title}")
            song.lyrics = cached
            return song

        if not song.url:
            self.logger.warning(f"URL mancante per: {song.title}")
            return song

        try:
            lyrics = self._scrape_lyrics(song.url)
            song.lyrics = lyrics

            # Salva in cache
            if lyrics:
                self.cache.set(cache_key, lyrics)

        except Exception as e:
            self.logger.error(f"Errore recupero lyrics per {song.title}: {e}")

        return song

    def get_songs_with_lyrics(
        self,
        query: str,
        limit: int = Config.DEFAULT_LIMIT
    ) -> List[Song]:
        """
        Cerca canzoni e recupera i lyrics per ognuna.

        Combina search() e get_lyrics() in un'unica operazione,
        restituendo solo le canzoni con lyrics validi.

        Args:
            query: Testo da cercare.
            limit: Numero massimo di risultati.

        Returns:
            List[Song]: Canzoni con lyrics popolati.

        Example:
            >>> fetcher = LyricsFetcher()
            >>> songs = fetcher.get_songs_with_lyrics("happiness", limit=3)
            >>> all(s.lyrics for s in songs)
            True
        """
        songs = self.search(query, limit=limit * 2)  # Cerca di più per compensare fallimenti

        songs_with_lyrics = []
        for song in songs:
            if len(songs_with_lyrics) >= limit:
                break

            song = self.get_lyrics(song)
            if song.lyrics:
                songs_with_lyrics.append(song)

        return songs_with_lyrics

    def get_popular_songs(
        self,
        genre: Optional[str] = None,
        limit: int = 20
    ) -> List[Song]:
        """
        Recupera canzoni popolari per costruire un dataset.

        Utile per la modalità offline o per pre-popolare la cache.

        Args:
            genre: Genere musicale (opzionale).
            limit: Numero di canzoni da recuperare.

        Returns:
            List[Song]: Lista di canzoni popolari.

        Note:
            Questa funzione usa termini di ricerca generici
            per trovare canzoni popolari.
        """
        search_terms = [
            "love", "heart", "life", "dream", "night",
            "amore", "cuore", "vita", "sogno", "notte"
        ]

        if genre:
            search_terms = [f"{genre} {term}" for term in search_terms[:5]]

        return self.search_by_terms(search_terms, limit_per_term=limit // len(search_terms))

    def clear_cache(self) -> None:
        """Svuota la cache dei lyrics."""
        self.cache.clear()
        self.logger.info("Cache svuotata")

    def get_cache_stats(self) -> dict:
        """
        Restituisce statistiche sulla cache.

        Returns:
            dict: Statistiche della cache.
        """
        return {
            "cache_file": str(self.cache.cache_file),
            "entries": len(self.cache._cache),
            "expiry_hours": self.cache.expiry_hours
        }

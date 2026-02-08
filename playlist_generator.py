"""
Modulo per la generazione di playlist.

Permette di creare playlist su Spotify o generare link YouTube
basati sui risultati della ricerca semantica.
"""

import json
import logging
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config import Config
from lyrics_fetcher import Song
from semantic_matcher import MatchResult

# Prova a importare spotipy (opzionale)
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIFY_AVAILABLE = True
except ImportError:
    SPOTIFY_AVAILABLE = False


@dataclass
class PlaylistTrack:
    """
    Rappresenta una traccia in una playlist.

    Attributes:
        title: Titolo della canzone.
        artist: Nome dell'artista.
        spotify_uri: URI Spotify (se disponibile).
        youtube_url: URL di ricerca YouTube.
        relevance_score: Score di rilevanza dalla ricerca.
        source: Fonte originale (genius, spotify, etc.).
    """
    title: str
    artist: str
    spotify_uri: Optional[str] = None
    youtube_url: Optional[str] = None
    relevance_score: float = 0.0
    source: str = "genius"

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "title": self.title,
            "artist": self.artist,
            "spotify_uri": self.spotify_uri,
            "youtube_url": self.youtube_url,
            "relevance_score": self.relevance_score,
            "source": self.source
        }


@dataclass
class Playlist:
    """
    Rappresenta una playlist generata.

    Attributes:
        name: Nome della playlist.
        description: Descrizione della playlist.
        tracks: Lista delle tracce.
        created_at: Data di creazione.
        spotify_url: URL della playlist Spotify (se creata).
    """
    name: str
    description: str = ""
    tracks: List[PlaylistTrack] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    spotify_url: Optional[str] = None

    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return {
            "name": self.name,
            "description": self.description,
            "tracks": [t.to_dict() for t in self.tracks],
            "created_at": self.created_at,
            "spotify_url": self.spotify_url,
            "track_count": len(self.tracks)
        }

    def save_json(self, path: Path) -> None:
        """Salva la playlist in formato JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def save_m3u(self, path: Path) -> None:
        """Salva la playlist in formato M3U."""
        lines = ["#EXTM3U", f"#PLAYLIST:{self.name}"]
        for track in self.tracks:
            lines.append(f"#EXTINF:-1,{track.artist} - {track.title}")
            if track.youtube_url:
                lines.append(track.youtube_url)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


class YouTubeGenerator:
    """
    Generatore di link YouTube per le canzoni.

    Crea URL di ricerca YouTube per ogni traccia,
    permettendo di aprirle direttamente nel browser.
    """

    SEARCH_URL = "https://www.youtube.com/results?search_query="
    MUSIC_URL = "https://music.youtube.com/search?q="

    def __init__(self, use_youtube_music: bool = False):
        """
        Inizializza il generatore.

        Args:
            use_youtube_music: Se True, usa YouTube Music invece di YouTube.
        """
        self.base_url = self.MUSIC_URL if use_youtube_music else self.SEARCH_URL
        self.logger = logging.getLogger("cerca_dai_testi.playlist")

    def generate_search_url(self, title: str, artist: str) -> str:
        """
        Genera URL di ricerca YouTube.

        Args:
            title: Titolo della canzone.
            artist: Nome dell'artista.

        Returns:
            str: URL di ricerca YouTube.
        """
        query = f"{artist} {title} official"
        encoded = urllib.parse.quote(query)
        return f"{self.base_url}{encoded}"

    def create_track(self, song: Song, score: float = 0.0) -> PlaylistTrack:
        """
        Crea una PlaylistTrack da una Song.

        Args:
            song: Canzone da convertire.
            score: Score di rilevanza.

        Returns:
            PlaylistTrack: Traccia con URL YouTube.
        """
        return PlaylistTrack(
            title=song.title,
            artist=song.artist,
            youtube_url=self.generate_search_url(song.title, song.artist),
            relevance_score=score,
            source="genius"
        )

    def open_in_browser(self, track: PlaylistTrack) -> None:
        """Apre la traccia nel browser."""
        if track.youtube_url:
            webbrowser.open(track.youtube_url)


class SpotifyGenerator:
    """
    Generatore di playlist Spotify.

    Richiede credenziali Spotify API configurate in .env:
    - SPOTIFY_CLIENT_ID
    - SPOTIFY_CLIENT_SECRET
    - SPOTIFY_REDIRECT_URI
    """

    SCOPES = "playlist-modify-public playlist-modify-private"

    def __init__(self):
        """
        Inizializza il generatore Spotify.

        Raises:
            ImportError: Se spotipy non è installato.
            ValueError: Se le credenziali non sono configurate.
        """
        if not SPOTIFY_AVAILABLE:
            raise ImportError(
                "spotipy non installato. Installa con: pip install spotipy"
            )

        self.client_id = Config.SPOTIFY_CLIENT_ID if hasattr(Config, 'SPOTIFY_CLIENT_ID') else None
        self.client_secret = Config.SPOTIFY_CLIENT_SECRET if hasattr(Config, 'SPOTIFY_CLIENT_SECRET') else None
        self.redirect_uri = Config.SPOTIFY_REDIRECT_URI if hasattr(Config, 'SPOTIFY_REDIRECT_URI') else "http://localhost:8888/callback"

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Credenziali Spotify non configurate. "
                "Imposta SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET in .env"
            )

        self._sp = None
        self.logger = logging.getLogger("cerca_dai_testi.spotify")

    @property
    def sp(self) -> "spotipy.Spotify":
        """Lazy loading del client Spotify con autenticazione."""
        if self._sp is None:
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=self.SCOPES
            )
            self._sp = spotipy.Spotify(auth_manager=auth_manager)
        return self._sp

    def search_track(self, title: str, artist: str) -> Optional[str]:
        """
        Cerca una traccia su Spotify.

        Args:
            title: Titolo della canzone.
            artist: Nome dell'artista.

        Returns:
            Optional[str]: URI Spotify della traccia, o None se non trovata.
        """
        query = f"track:{title} artist:{artist}"
        try:
            results = self.sp.search(q=query, type="track", limit=1)
            tracks = results.get("tracks", {}).get("items", [])
            if tracks:
                return tracks[0]["uri"]
        except Exception as e:
            self.logger.warning(f"Errore ricerca Spotify per '{title}': {e}")
        return None

    def create_track(self, song: Song, score: float = 0.0) -> PlaylistTrack:
        """
        Crea una PlaylistTrack cercando su Spotify.

        Args:
            song: Canzone da convertire.
            score: Score di rilevanza.

        Returns:
            PlaylistTrack: Traccia con URI Spotify (se trovata).
        """
        spotify_uri = self.search_track(song.title, song.artist)
        youtube_gen = YouTubeGenerator()

        return PlaylistTrack(
            title=song.title,
            artist=song.artist,
            spotify_uri=spotify_uri,
            youtube_url=youtube_gen.generate_search_url(song.title, song.artist),
            relevance_score=score,
            source="spotify" if spotify_uri else "genius"
        )

    def create_playlist(
        self,
        name: str,
        tracks: List[PlaylistTrack],
        description: str = "",
        public: bool = True
    ) -> Optional[str]:
        """
        Crea una playlist su Spotify.

        Args:
            name: Nome della playlist.
            tracks: Lista delle tracce.
            description: Descrizione della playlist.
            public: Se True, la playlist sarà pubblica.

        Returns:
            Optional[str]: URL della playlist creata, o None se fallisce.
        """
        # Filtra solo tracce con URI Spotify
        uris = [t.spotify_uri for t in tracks if t.spotify_uri]

        if not uris:
            self.logger.warning("Nessuna traccia trovata su Spotify")
            return None

        try:
            user = self.sp.current_user()
            user_id = user["id"]

            # Crea playlist
            playlist = self.sp.user_playlist_create(
                user_id,
                name,
                public=public,
                description=description or f"Generata da Cerca Dai Testi - {len(uris)} brani"
            )

            # Aggiungi tracce
            self.sp.playlist_add_items(playlist["id"], uris)

            self.logger.info(f"Playlist creata: {playlist['external_urls']['spotify']}")
            return playlist["external_urls"]["spotify"]

        except Exception as e:
            self.logger.error(f"Errore creazione playlist Spotify: {e}")
            return None


class PlaylistGenerator:
    """
    Generatore di playlist unificato.

    Coordina la generazione di playlist su diverse piattaforme
    (YouTube, Spotify) a partire dai risultati di ricerca.

    Example:
        >>> generator = PlaylistGenerator()
        >>> playlist = generator.from_search_results(
        ...     results,
        ...     name="La mia playlist",
        ...     query="amore e libertà"
        ... )
        >>> generator.export_html(playlist, Path("playlist.html"))
    """

    def __init__(self, use_spotify: bool = False):
        """
        Inizializza il generatore.

        Args:
            use_spotify: Se True, tenta di usare Spotify API.
        """
        self.youtube = YouTubeGenerator()
        self.spotify = None
        self.logger = logging.getLogger("cerca_dai_testi.playlist")

        if use_spotify:
            try:
                self.spotify = SpotifyGenerator()
                self.logger.info("Spotify API disponibile")
            except (ImportError, ValueError) as e:
                self.logger.warning(f"Spotify non disponibile: {e}")

    def from_search_results(
        self,
        results: List[MatchResult],
        name: Optional[str] = None,
        query: str = ""
    ) -> Playlist:
        """
        Crea una playlist dai risultati di ricerca.

        Args:
            results: Lista di MatchResult dalla ricerca semantica.
            name: Nome della playlist (auto-generato se non fornito).
            query: Query originale per la descrizione.

        Returns:
            Playlist: Playlist generata con tutte le tracce.
        """
        if not name:
            name = f"Cerca Dai Testi - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        tracks = []
        for result in results:
            if self.spotify:
                track = self.spotify.create_track(result.song, result.score)
            else:
                track = self.youtube.create_track(result.song, result.score)
            tracks.append(track)

        description = f"Playlist generata cercando: '{query}'" if query else ""

        return Playlist(
            name=name,
            description=description,
            tracks=tracks
        )

    def from_songs(
        self,
        songs: List[Song],
        name: str = "My Playlist"
    ) -> Playlist:
        """
        Crea una playlist da una lista di canzoni.

        Args:
            songs: Lista di Song.
            name: Nome della playlist.

        Returns:
            Playlist: Playlist generata.
        """
        tracks = []
        for song in songs:
            if self.spotify:
                track = self.spotify.create_track(song)
            else:
                track = self.youtube.create_track(song)
            tracks.append(track)

        return Playlist(name=name, tracks=tracks)

    def create_spotify_playlist(self, playlist: Playlist) -> Optional[str]:
        """
        Crea la playlist su Spotify.

        Args:
            playlist: Playlist da creare.

        Returns:
            Optional[str]: URL della playlist Spotify, o None se fallisce.
        """
        if not self.spotify:
            self.logger.error("Spotify non configurato")
            return None

        url = self.spotify.create_playlist(
            playlist.name,
            playlist.tracks,
            playlist.description
        )

        if url:
            playlist.spotify_url = url

        return url

    def export_html(self, playlist: Playlist, path: Path) -> None:
        """
        Esporta la playlist in formato HTML.

        Args:
            playlist: Playlist da esportare.
            path: Path del file HTML.
        """
        html = self._generate_html(playlist)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def _generate_html(self, playlist: Playlist) -> str:
        """Genera HTML per la playlist."""
        tracks_html = []
        for i, track in enumerate(playlist.tracks, 1):
            score_pct = track.relevance_score * 100
            tracks_html.append(f"""
            <tr>
                <td>{i}</td>
                <td><strong>{track.title}</strong></td>
                <td>{track.artist}</td>
                <td>{score_pct:.1f}%</td>
                <td>
                    <a href="{track.youtube_url}" target="_blank" class="btn btn-yt">YouTube</a>
                    {f'<a href="https://open.spotify.com/track/{track.spotify_uri.split(":")[-1]}" target="_blank" class="btn btn-sp">Spotify</a>' if track.spotify_uri else ''}
                </td>
            </tr>
            """)

        return f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{playlist.name}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e2e8f0;
            min-height: 100vh;
            padding: 2rem;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(90deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .meta {{ color: #94a3b8; margin-bottom: 2rem; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            overflow: hidden;
        }}
        th, td {{ padding: 1rem; text-align: left; }}
        th {{ background: rgba(255,255,255,0.1); font-weight: 600; }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        .btn {{
            display: inline-block;
            padding: 0.4rem 0.8rem;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.85rem;
            margin-right: 0.5rem;
        }}
        .btn-yt {{ background: #ef4444; color: white; }}
        .btn-sp {{ background: #22c55e; color: white; }}
        .btn:hover {{ opacity: 0.9; }}
        footer {{
            text-align: center;
            margin-top: 2rem;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{playlist.name}</h1>
        <p class="meta">
            {playlist.description}<br>
            {len(playlist.tracks)} brani • Generata il {playlist.created_at[:10]}
        </p>

        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Titolo</th>
                    <th>Artista</th>
                    <th>Score</th>
                    <th>Ascolta</th>
                </tr>
            </thead>
            <tbody>
                {"".join(tracks_html)}
            </tbody>
        </table>

        <footer>
            Generata con Cerca Dai Testi
        </footer>
    </div>
</body>
</html>"""

    def open_all_youtube(self, playlist: Playlist, limit: int = 5) -> None:
        """
        Apre le prime N tracce su YouTube nel browser.

        Args:
            playlist: Playlist da aprire.
            limit: Numero massimo di tab da aprire.
        """
        for track in playlist.tracks[:limit]:
            self.youtube.open_in_browser(track)

#!/usr/bin/env python3
"""
Cerca Dai Testi - Interfaccia Grafica

GUI moderna basata su Gradio per cercare canzoni
con testi semanticamente correlati.
"""

import gradio as gr
from typing import List, Tuple
from functools import partial
import json
from pathlib import Path
from datetime import datetime

from config import Config
from lyrics_fetcher import LyricsFetcher, Song
from semantic_matcher import SemanticMatcher, MatchResult
from mood_analyzer import MoodAnalyzer, MOOD_PRESETS
from user_data import UserDataManager, get_theme_css
from playlist_generator import PlaylistGenerator
from playlist_exporter import PlaylistExporter, ExportFormat, ExportOptions
from utils import setup_logging


# Inizializza componenti globali (lazy loading)
_fetcher = None
_matcher = None
_logger = None
_user_data = None
_mood_analyzer = None


def get_components():
    """Inizializza i componenti alla prima chiamata."""
    global _fetcher, _matcher, _logger, _user_data, _mood_analyzer

    if _logger is None:
        _logger = setup_logging()

    if _fetcher is None:
        try:
            Config.validate()
            _fetcher = LyricsFetcher()
        except ValueError as e:
            raise gr.Error(f"Configurazione mancante: {e}")

    if _matcher is None:
        _matcher = SemanticMatcher()

    if _user_data is None:
        _user_data = UserDataManager()

    if _mood_analyzer is None:
        _mood_analyzer = MoodAnalyzer()

    return _fetcher, _matcher, _user_data, _mood_analyzer


def search_songs(
    query: str,
    num_results: int,
    min_score: float,
    mood_filter: str,
    progress=gr.Progress()
):
    """
    Esegue la ricerca di canzoni.

    Args:
        query: Testo da cercare
        num_results: Numero di risultati
        min_score: Score minimo di rilevanza
        mood_filter: Filtro mood (opzionale)
        progress: Barra di progresso Gradio

    Returns:
        Tuple con HTML, JSON, status, dropdown choices
    """
    if not query or not query.strip():
        raise gr.Error("Inserisci un testo da cercare")

    try:
        fetcher, matcher, user_data, mood_analyzer = get_components()
    except Exception as e:
        raise gr.Error(str(e))

    progress(0.1, desc="Ricerca canzoni...")

    # Migliora query con mood se selezionato
    search_query = query
    if mood_filter and mood_filter != "Nessuno":
        mood_id = mood_filter.lower()
        preset = mood_analyzer.get_preset(mood_id)
        if preset:
            extra_terms = preset.keywords_it[:2]
            search_query = f"{query} {' '.join(extra_terms)}"

    # Estrai termini di ricerca
    words = search_query.split()
    if len(words) <= 10:
        search_terms = [search_query]
    else:
        search_terms = matcher.extract_key_phrases(search_query, top_k=3)
        stopwords = {"il", "la", "di", "che", "un", "a", "the", "and", "is", "of", "to"}
        keywords = [w for w in words if len(w) > 4 and w.lower() not in stopwords][:3]
        search_terms.extend(keywords)

    progress(0.2, desc="Scaricamento lyrics...")

    # Cerca canzoni
    all_songs = []
    for i, term in enumerate(search_terms[:4]):
        songs = fetcher.get_songs_with_lyrics(term, limit=num_results * 2)
        all_songs.extend(songs)
        progress(0.2 + (0.4 * (i + 1) / len(search_terms[:4])), desc=f"Ricerca: {term[:30]}...")

    # Rimuovi duplicati
    seen_ids = set()
    unique_songs = []
    for song in all_songs:
        if song.id not in seen_ids:
            seen_ids.add(song.id)
            unique_songs.append(song)

    if not unique_songs:
        return "<p style='text-align:center; color:#888;'>Nessuna canzone trovata</p>", "[]", "Nessun risultato", gr.update(choices=[]), get_history()

    progress(0.7, desc="Analisi semantica...")

    # Calcola similarità
    results = matcher.find_similar_songs(
        query,
        unique_songs,
        limit=num_results,
        min_score=min_score
    )

    progress(0.9, desc="Generazione risultati...")

    if not results:
        return "<p style='text-align:center; color:#888;'>Nessun risultato sopra la soglia di rilevanza</p>", "[]", "Nessun risultato", gr.update(choices=[]), get_history()

    # Salva in cronologia
    user_data.add_to_history(query, results, {"mood": mood_filter, "min_score": min_score})

    # Genera HTML
    html = generate_results_html(results, user_data)

    # Genera JSON per export
    json_data = json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2)

    # Genera opzioni per dropdown (usato sia per preferiti che playlist)
    song_choices = [f"{r.song.id}|{r.song.artist} - {r.song.title}" for r in results]

    progress(1.0, desc="Completato!")

    status = f"Trovati {len(results)} risultati"
    dropdown_update = gr.update(choices=song_choices, value=song_choices[0] if song_choices else None)

    # Aggiorna cronologia
    history_update = get_history()

    return html, json_data, status, dropdown_update, history_update


def generate_results_html(results: List[MatchResult], user_data: UserDataManager = None) -> str:
    """Genera HTML per i risultati."""
    html_parts = []

    for i, result in enumerate(results):
        song = result.song
        score_percent = result.score * 100

        # Colore badge in base allo score
        if score_percent >= 70:
            badge_color = "#22c55e"
        elif score_percent >= 50:
            badge_color = "#eab308"
        else:
            badge_color = "#f97316"

        # Check se è nei preferiti
        is_fav = user_data.is_favorite(song.id) if user_data else False
        fav_icon = "★" if is_fav else "☆"

        html_parts.append(f"""
        <div style="
            background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
            border-left: 4px solid {badge_color};
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        ">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                <div>
                    <span style="
                        background: {badge_color};
                        color: white;
                        padding: 4px 12px;
                        border-radius: 20px;
                        font-size: 14px;
                        font-weight: bold;
                    ">#{i + 1} - {score_percent:.1f}%</span>
                </div>
                <span style="font-size: 24px; cursor: pointer;" title="Preferito">{fav_icon}</span>
            </div>

            <h3 style="margin: 0 0 8px 0; color: #ffffff; font-size: 20px; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">
                {song.title}
            </h3>

            <p style="margin: 0 0 12px 0; color: #e2e8f0; font-size: 16px;">
                <strong style="color: #ffffff;">{song.artist}</strong>
                {f' • {song.release_date}' if song.release_date else ''}
            </p>

            {f'''
            <div style="
                background: rgba(0,0,0,0.4);
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 12px;
            ">
                <p style="margin: 0; color: #ffffff; font-style: italic; line-height: 1.6; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">
                    "{result.relevant_excerpt}"
                </p>
            </div>
            ''' if result.relevant_excerpt else ''}

            <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px;">
                {f'''
                <a href="{song.url}" target="_blank" style="
                    color: white;
                    text-decoration: none;
                    font-size: 13px;
                    padding: 8px 14px;
                    background: #eab308;
                    border-radius: 6px;
                    font-weight: 500;
                ">
                    🎵 Genius
                </a>
                ''' if song.url else ''}
                <a href="https://www.youtube.com/results?search_query={song.artist.replace(' ', '+')}+{song.title.replace(' ', '+')}" target="_blank" style="
                    color: white;
                    text-decoration: none;
                    font-size: 13px;
                    padding: 8px 14px;
                    background: #ef4444;
                    border-radius: 6px;
                    font-weight: 500;
                ">
                    ▶ YouTube
                </a>
                <button onclick="navigator.clipboard.writeText('{song.artist} - {song.title}')" style="
                    color: white;
                    font-size: 13px;
                    padding: 8px 14px;
                    background: #22c55e;
                    border-radius: 6px;
                    border: none;
                    cursor: pointer;
                    font-weight: 500;
                ">
                    ➕ Playlist
                </button>
                <button onclick="alert('Aggiunto ai preferiti: {song.title}')" style="
                    color: white;
                    font-size: 13px;
                    padding: 8px 14px;
                    background: #ec4899;
                    border-radius: 6px;
                    border: none;
                    cursor: pointer;
                    font-weight: 500;
                ">
                    ⭐ Preferiti
                </button>
            </div>
        </div>
        """)

    return "".join(html_parts)


def toggle_favorite(song_id: int, title: str, artist: str) -> str:
    """Aggiunge/rimuove dai preferiti."""
    _, _, user_data, _ = get_components()

    if user_data.is_favorite(song_id):
        user_data.remove_favorite(song_id)
        return f"Rimosso '{title}' dai preferiti"
    else:
        song = Song(id=song_id, title=title, artist=artist)
        user_data.add_favorite(song)
        return f"Aggiunto '{title}' ai preferiti"


# Playlist corrente in memoria
_current_playlist = []


def add_to_playlist_from_dropdown(selection: str) -> Tuple[str, str]:
    """Aggiunge una canzone alla playlist corrente."""
    global _current_playlist

    if not selection or selection == "":
        return "⚠️ Prima seleziona una canzone dal menu a tendina", get_playlist_html()

    try:
        if "|" not in selection:
            return f"⚠️ Formato selezione non valido: {selection}", get_playlist_html()

        parts = selection.split("|", 1)
        song_id = parts[0]  # Mantiene come stringa (Song.id è str)
        artist_title = parts[1] if len(parts) > 1 else "Unknown"

        if " - " in artist_title:
            artist, title = artist_title.split(" - ", 1)
        else:
            artist, title = "Unknown", artist_title

        # Controlla duplicati
        for item in _current_playlist:
            if item["id"] == song_id:
                return f"ℹ️ '{title}' è già nella playlist", get_playlist_html()

        _current_playlist.append({
            "id": song_id,
            "title": title,
            "artist": artist
        })

        return f"✅ Aggiunto '{title}' alla playlist! (Totale: {len(_current_playlist)} brani)", get_playlist_html()

    except Exception as e:
        return f"❌ Errore: {str(e)}", get_playlist_html()


def get_playlist_html() -> str:
    """Genera HTML della playlist corrente."""
    global _current_playlist

    if not _current_playlist:
        return "<p style='color:#888; text-align:center;'>Playlist vuota - aggiungi canzoni dai risultati</p>"

    html = f"<p style='color:#22c55e; margin-bottom:10px;'><strong>🎶 Playlist corrente: {len(_current_playlist)} brani</strong></p>"
    html += "<div style='max-height:200px; overflow-y:auto;'>"

    for i, item in enumerate(_current_playlist, 1):
        html += f"""
        <div style="background:rgba(255,255,255,0.05); padding:8px 12px; border-radius:6px; margin-bottom:4px; display:flex; justify-content:space-between; align-items:center;">
            <span style="color:#f1f5f9;"><strong>#{i}</strong> {item['artist']} - {item['title']}</span>
        </div>
        """

    html += "</div>"
    return html


def clear_current_playlist() -> Tuple[str, str]:
    """Svuota la playlist corrente."""
    global _current_playlist
    _current_playlist = []
    return "Playlist svuotata", get_playlist_html()


def export_current_playlist() -> str:
    """Esporta la playlist corrente."""
    global _current_playlist

    if not _current_playlist:
        return "Playlist vuota, nulla da esportare"

    from playlist_generator import Playlist, PlaylistTrack, YouTubeGenerator
    from playlist_exporter import PlaylistExporter, ExportFormat

    yt_gen = YouTubeGenerator()
    tracks = []

    for item in _current_playlist:
        track = PlaylistTrack(
            title=item["title"],
            artist=item["artist"],
            youtube_url=yt_gen.generate_search_url(item["title"], item["artist"])
        )
        tracks.append(track)

    playlist = Playlist(
        name=f"Playlist - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        description="Generata con Cerca Dai Testi",
        tracks=tracks
    )

    output_dir = Path.home() / ".cerca_dai_testi" / "playlists"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    exporter = PlaylistExporter()
    exporter.export(playlist, output_path, ExportFormat.HTML)

    return f"Playlist esportata in: {output_path}"


def add_to_favorites_from_dropdown(selection: str) -> Tuple[str, str]:
    """Aggiunge una canzone ai preferiti dal dropdown."""
    if not selection or selection == "":
        return "⚠️ Prima seleziona una canzone dal menu a tendina", get_favorites()

    try:
        # Formato: "id|artista - titolo"
        if "|" not in selection:
            return f"⚠️ Formato selezione non valido: {selection}", get_favorites()

        parts = selection.split("|", 1)
        song_id = parts[0]  # Mantiene come stringa (Song.id è str)
        artist_title = parts[1] if len(parts) > 1 else "Unknown"

        if " - " in artist_title:
            artist, title = artist_title.split(" - ", 1)
        else:
            artist, title = "Unknown", artist_title

        _, _, user_data, _ = get_components()

        # Converti a int per il check dei preferiti (FavoriteSong.song_id è int)
        song_id_int = int(song_id)
        if user_data.is_favorite(song_id_int):
            return f"ℹ️ '{title}' è già nei preferiti", get_favorites()

        song = Song(id=song_id, title=title, artist=artist)
        user_data.add_favorite(song)
        user_data.save()  # Forza salvataggio

        return f"✅ Aggiunto '{title}' ai preferiti!", get_favorites()

    except Exception as e:
        return f"❌ Errore: {str(e)}", get_favorites()


def get_history_initial() -> str:
    """Carica la cronologia iniziale."""
    return get_history("")


def get_history(search_filter: str = "") -> str:
    """Restituisce la cronologia come HTML."""
    try:
        _, _, user_data, _ = get_components()
        history = user_data.get_history(limit=1000)  # Mostra tutte le ricerche
    except Exception as e:
        return f"<p style='color: #ef4444;'>Errore caricamento cronologia: {e}</p>"

    if not history:
        return "<p style='color: #888; text-align: center;'>Nessuna ricerca nella cronologia</p>"

    # Filtra se c'è un termine di ricerca
    if search_filter and search_filter.strip():
        search_lower = search_filter.lower().strip()
        history = [h for h in history if search_lower in h.query.lower()]

    if not history:
        return f"<p style='color: #888; text-align: center;'>Nessun risultato per '{search_filter}'</p>"

    html_parts = [f"<p style='color:#94a3b8; margin-bottom:10px;'>📜 <strong>{len(history)}</strong> ricerche in cronologia</p>"]
    html_parts.append("<div style='max-height: 500px; overflow-y: auto;'>")

    for idx, entry in enumerate(history):
        timestamp = entry.timestamp[:16].replace("T", " ")

        # Mostra i top risultati
        results_html = ""
        if entry.top_results:
            results_list = ", ".join(entry.top_results[:3])
            if len(entry.top_results) > 3:
                results_list += f" (+{len(entry.top_results) - 3} altri)"
            results_html = f"""
            <p style="color: #60a5fa; margin: 8px 0 0 0; font-size: 12px;">
                🎵 {results_list}
            </p>
            """

        html_parts.append(f"""
        <div style="
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
        " data-index="{idx}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong style="color: #e2e8f0;">{entry.query[:80]}{'...' if len(entry.query) > 80 else ''}</strong>
                <span style="color: #64748b; font-size: 12px;">{timestamp}</span>
            </div>
            <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 13px;">
                {entry.results_count} risultati
            </p>
            {results_html}
        </div>
        """)

    html_parts.append("</div>")
    return "".join(html_parts)


def get_favorites() -> str:
    """Restituisce i preferiti come HTML."""
    try:
        _, _, user_data, _ = get_components()
        favorites = user_data.get_favorites()
    except Exception as e:
        return f"<p style='color: #ef4444;'>Errore caricamento preferiti: {e}</p>"

    if not favorites:
        return "<p style='color: #888; text-align: center;'>Nessuna canzone nei preferiti. Usa il dropdown 'Aggiungi ai preferiti' dopo una ricerca.</p>"

    html_parts = ["<div style='max-height: 400px; overflow-y: auto;'>"]

    for fav in favorites:
        html_parts.append(f"""
        <div style="
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            border-left: 3px solid #22c55e;
        ">
            <h4 style="margin: 0 0 4px 0; color: #e2e8f0;">{fav.title}</h4>
            <p style="color: #94a3b8; margin: 0; font-size: 14px;">{fav.artist}</p>
            {f'<p style="color: #64748b; margin: 8px 0 0 0; font-size: 12px; font-style: italic;">"{fav.notes}"</p>' if fav.notes else ''}
            {f'<div style="margin-top: 8px;">' + ''.join([f'<span style="background: #3b82f6; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-right: 4px;">{tag}</span>' for tag in fav.tags]) + '</div>' if fav.tags else ''}
        </div>
        """)

    html_parts.append("</div>")
    return "".join(html_parts)


def get_mood_buttons() -> str:
    """Genera i pulsanti mood."""
    buttons = []
    for mood_id, preset in MOOD_PRESETS.items():
        buttons.append(f"""
        <button style="
            background: {preset.color};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            margin: 4px;
            cursor: pointer;
            font-size: 14px;
        ">
            {preset.emoji} {preset.name}
        </button>
        """)
    return "".join(buttons)


def export_playlist(results_json: str, format_choice: str, playlist_name: str) -> Tuple[str, str]:
    """Esporta la playlist nel formato scelto."""
    if not results_json or results_json == "[]":
        return None, "Nessun risultato da esportare"

    try:
        results_data = json.loads(results_json)
    except:
        return None, "Errore parsing risultati"

    if not results_data:
        return None, "Nessun risultato da esportare"

    # Crea playlist
    from playlist_generator import Playlist, PlaylistTrack

    tracks = []
    for r in results_data:
        song_data = r.get("song", {})
        track = PlaylistTrack(
            title=song_data.get("title", "Unknown"),
            artist=song_data.get("artist", "Unknown"),
            relevance_score=r.get("score", 0)
        )
        tracks.append(track)

    playlist = Playlist(
        name=playlist_name or f"Cerca Dai Testi - {datetime.now().strftime('%Y-%m-%d')}",
        tracks=tracks
    )

    # Export
    exporter = PlaylistExporter()
    format_map = {
        "JSON": ExportFormat.JSON,
        "M3U": ExportFormat.M3U,
        "CSV": ExportFormat.CSV,
        "HTML": ExportFormat.HTML,
        "Markdown": ExportFormat.MARKDOWN,
        "TXT": ExportFormat.TXT,
    }

    format_enum = format_map.get(format_choice, ExportFormat.JSON)
    output_dir = Path.home() / ".cerca_dai_testi" / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_path = output_dir / f"{filename}.{format_enum.value}"

    exporter.export(playlist, output_path, format_enum)

    return str(output_path), f"Playlist esportata in {output_path}"


def clear_cache():
    """Svuota la cache."""
    global _fetcher, _matcher

    if _fetcher:
        _fetcher.clear_cache()
    if _matcher:
        _matcher.clear_cache()

    return "Cache svuotata con successo!"


def clear_history() -> Tuple[str, str]:
    """Svuota la cronologia."""
    _, _, user_data, _ = get_components()
    user_data.clear_history()
    return "Cronologia svuotata!", get_history()


def search_history(keyword: str) -> str:
    """Cerca nella cronologia."""
    return get_history(search_filter=keyword)


def get_history_dropdown_choices() -> list:
    """Restituisce le scelte per il dropdown cancellazione."""
    try:
        _, _, user_data, _ = get_components()
        history = user_data.get_history(limit=1000)
        choices = []
        for idx, entry in enumerate(history):
            timestamp = entry.timestamp[:16].replace("T", " ")
            label = f"{idx}|{entry.query[:40]}... ({timestamp})"
            choices.append(label)
        return choices
    except:
        return []


def delete_history_entry(selection: str) -> Tuple[str, str, list]:
    """Cancella una singola voce dalla cronologia."""
    if not selection or selection == "":
        return "⚠️ Seleziona una voce da cancellare", get_history(), get_history_dropdown_choices()

    try:
        idx = int(selection.split("|")[0])
        _, _, user_data, _ = get_components()

        if user_data.remove_from_history(idx):
            return f"✅ Voce #{idx + 1} cancellata", get_history(), get_history_dropdown_choices()
        else:
            return "❌ Voce non trovata", get_history(), get_history_dropdown_choices()
    except Exception as e:
        return f"❌ Errore: {e}", get_history(), get_history_dropdown_choices()


def save_settings(theme: str, default_results: int, default_score: float) -> str:
    """Salva le impostazioni utente."""
    _, _, user_data, _ = get_components()

    user_data.set_theme(theme.lower())
    user_data.update_settings(
        default_results=int(default_results),
        min_score=default_score
    )

    return f"Impostazioni salvate! Tema: {theme}"


def search_by_mood_name(mood_name: str) -> str:
    """Cerca per nome mood dal dropdown."""
    # Estrai l'ID dal nome (es. "😊 Felice" -> "happy")
    for mood_id, preset in MOOD_PRESETS.items():
        if preset.name in mood_name or preset.emoji in mood_name:
            return search_by_mood(mood_id)
    return "<p style='color: #ef4444;'>Mood non trovato</p>"


def search_by_mood(mood_id: str) -> str:
    """Cerca canzoni per mood."""
    try:
        fetcher, matcher, user_data, mood_analyzer = get_components()
    except Exception as e:
        return f"<p style='color: #ef4444;'>Errore: {e}</p>"

    preset = mood_analyzer.get_preset(mood_id)
    if not preset:
        return "<p style='color: #ef4444;'>Mood non trovato</p>"

    # Usa le keywords del mood come query
    query = " ".join(preset.keywords_it[:3] + preset.keywords_en[:2])

    # Cerca canzoni
    all_songs = []
    for term in preset.search_terms[:2]:
        songs = fetcher.get_songs_with_lyrics(term, limit=10)
        all_songs.extend(songs)

    # Rimuovi duplicati
    seen_ids = set()
    unique_songs = []
    for song in all_songs:
        if song.id not in seen_ids:
            seen_ids.add(song.id)
            unique_songs.append(song)

    if not unique_songs:
        return f"<p style='color: #94a3b8;'>Nessuna canzone trovata per mood {preset.name}</p>"

    # Calcola similarità
    results = matcher.find_similar_songs(query, unique_songs, limit=8, min_score=0.2)

    if not results:
        return f"<p style='color: #94a3b8;'>Nessun risultato per mood {preset.name}</p>"

    # Genera HTML risultati
    html_parts = [f"<h3 style='color: #f1f5f9; margin-bottom: 16px;'>{preset.emoji} Canzoni {preset.name}</h3>"]

    for i, result in enumerate(results, 1):
        song = result.song
        score_pct = result.score * 100
        html_parts.append(f"""
        <div style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 3px solid {preset.color};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong style="color: #f1f5f9;">#{i} {song.title}</strong>
                    <span style="color: #94a3b8;"> - {song.artist}</span>
                </div>
                <span style="color: {preset.color}; font-weight: bold;">{score_pct:.0f}%</span>
            </div>
            <div style="margin-top: 8px; display: flex; gap: 8px;">
                <a href="https://www.youtube.com/results?search_query={song.artist.replace(' ', '+')}+{song.title.replace(' ', '+')}" target="_blank" style="color: white; background: #ef4444; padding: 4px 10px; border-radius: 4px; text-decoration: none; font-size: 12px;">▶ YouTube</a>
                {f'<a href="{song.url}" target="_blank" style="color: white; background: #eab308; padding: 4px 10px; border-radius: 4px; text-decoration: none; font-size: 12px;">🎵 Genius</a>' if song.url else ''}
            </div>
        </div>
        """)

    return "".join(html_parts)


def apply_custom_theme(bg_color: str, card_color: str, text_color: str, accent_color: str) -> Tuple[str, str]:
    """Applica un tema personalizzato."""
    css = f"""
    <style id="dynamic-theme">
        .gradio-container, body, .main, .wrap, .app {{ background: {bg_color} !important; }}
        .block, .form, .container, .panel {{ background: {card_color} !important; border-color: {accent_color}44 !important; }}
        .prose, .label-wrap, span, p, h1, h2, h3, h4, h5, label, .markdown, div, strong, em {{
            color: {text_color} !important;
        }}
        a {{ color: {accent_color} !important; }}
        .gr-button-primary {{ background: {accent_color} !important; color: white !important; }}
        .gr-button-secondary {{ background: {card_color} !important; color: {text_color} !important; border: 1px solid {accent_color} !important; }}
        textarea, input, select, .input-text {{
            background: {card_color} !important;
            color: {text_color} !important;
            border-color: {accent_color}88 !important;
        }}
        .tab-nav button, .tabs button {{ color: {text_color} !important; background: {card_color} !important; }}
        .tab-nav button.selected, .tabs button.selected {{ background: {accent_color} !important; color: white !important; }}
        .accordion {{ background: {card_color} !important; color: {text_color} !important; }}
    </style>
    """
    return f"✅ Tema personalizzato applicato!", css


def on_theme_change(theme: str) -> Tuple[str, str]:
    """Gestisce il cambio tema."""
    _, _, user_data, _ = get_components()
    user_data.set_theme(theme.lower())

    themes_css = {
        "Light": """
        <style id="dynamic-theme">
            .gradio-container, .dark, body, .main, .wrap, .app { background: #f8fafc !important; }
            .block, .form, .container, .panel { background: #ffffff !important; border-color: #e2e8f0 !important; }
            .prose, .label-wrap, span, p, h1, h2, h3, h4, h5, label, .markdown, div, strong, em, a {
                color: #0f172a !important;
            }
            .gr-button { color: white !important; }
            .gr-button-secondary { background: #64748b !important; color: white !important; }
            textarea, input, select, .input-text {
                background: #f1f5f9 !important;
                color: #0f172a !important;
                border-color: #94a3b8 !important;
            }
            .tab-nav button, .tabs button { color: #0f172a !important; background: #e2e8f0 !important; }
            .tab-nav button.selected, .tabs button.selected { background: #3b82f6 !important; color: white !important; }
            .accordion { background: #f1f5f9 !important; }
        </style>
        """,
        "Dark": """
        <style id="dynamic-theme">
            .gradio-container, body, .main, .wrap, .app { background: #0f172a !important; }
            .block, .form, .container, .panel { background: #1e293b !important; border-color: #475569 !important; }
            .prose, .label-wrap, span, p, h1, h2, h3, h4, h5, label, .markdown, div, strong, em {
                color: #f8fafc !important;
            }
            a { color: #60a5fa !important; }
            .gr-button-primary { background: #3b82f6 !important; color: white !important; }
            .gr-button-secondary { background: #475569 !important; color: #f8fafc !important; }
            textarea, input, select, .input-text {
                background: #334155 !important;
                color: #f8fafc !important;
                border-color: #64748b !important;
            }
            .tab-nav button, .tabs button { color: #f8fafc !important; background: #334155 !important; }
            .tab-nav button.selected, .tabs button.selected { background: #3b82f6 !important; color: white !important; }
            .accordion { background: #1e293b !important; color: #f8fafc !important; }
        </style>
        """,
        "Ocean": """
        <style id="dynamic-theme">
            .gradio-container, body, .main, .wrap, .app { background: #082f49 !important; }
            .block, .form, .container, .panel { background: #0c4a6e !important; border-color: #0369a1 !important; }
            .prose, .label-wrap, span, p, h1, h2, h3, h4, h5, label, .markdown, div, strong, em {
                color: #f0f9ff !important;
            }
            a { color: #7dd3fc !important; }
            .gr-button-primary { background: #0ea5e9 !important; color: white !important; }
            .gr-button-secondary { background: #0369a1 !important; color: #f0f9ff !important; }
            textarea, input, select, .input-text {
                background: #075985 !important;
                color: #f0f9ff !important;
                border-color: #38bdf8 !important;
            }
            .tab-nav button, .tabs button { color: #f0f9ff !important; background: #0c4a6e !important; }
            .tab-nav button.selected, .tabs button.selected { background: #0ea5e9 !important; color: white !important; }
            .accordion { background: #0c4a6e !important; color: #f0f9ff !important; }
        </style>
        """,
        "Forest": """
        <style id="dynamic-theme">
            .gradio-container, body, .main, .wrap, .app { background: #052e16 !important; }
            .block, .form, .container, .panel { background: #14532d !important; border-color: #16a34a !important; }
            .prose, .label-wrap, span, p, h1, h2, h3, h4, h5, label, .markdown, div, strong, em {
                color: #f0fdf4 !important;
            }
            a { color: #86efac !important; }
            .gr-button-primary { background: #22c55e !important; color: white !important; }
            .gr-button-secondary { background: #166534 !important; color: #f0fdf4 !important; }
            textarea, input, select, .input-text {
                background: #166534 !important;
                color: #f0fdf4 !important;
                border-color: #4ade80 !important;
            }
            .tab-nav button, .tabs button { color: #f0fdf4 !important; background: #14532d !important; }
            .tab-nav button.selected, .tabs button.selected { background: #22c55e !important; color: white !important; }
            .accordion { background: #14532d !important; color: #f0fdf4 !important; }
        </style>
        """,
        "Sunset": """
        <style id="dynamic-theme">
            .gradio-container, body, .main, .wrap, .app { background: #431407 !important; }
            .block, .form, .container, .panel { background: #7c2d12 !important; border-color: #ea580c !important; }
            .prose, .label-wrap, span, p, h1, h2, h3, h4, h5, label, .markdown, div, strong, em {
                color: #fff7ed !important;
            }
            a { color: #fdba74 !important; }
            .gr-button-primary { background: #f97316 !important; color: white !important; }
            .gr-button-secondary { background: #9a3412 !important; color: #fff7ed !important; }
            textarea, input, select, .input-text {
                background: #9a3412 !important;
                color: #fff7ed !important;
                border-color: #fb923c !important;
            }
            .tab-nav button, .tabs button { color: #fff7ed !important; background: #7c2d12 !important; }
            .tab-nav button.selected, .tabs button.selected { background: #f97316 !important; color: white !important; }
            .accordion { background: #7c2d12 !important; color: #fff7ed !important; }
        </style>
        """,
        "Purple": """
        <style id="dynamic-theme">
            .gradio-container, body, .main, .wrap, .app { background: #2e1065 !important; }
            .block, .form, .container, .panel { background: #4c1d95 !important; border-color: #8b5cf6 !important; }
            .prose, .label-wrap, span, p, h1, h2, h3, h4, h5, label, .markdown, div, strong, em {
                color: #faf5ff !important;
            }
            a { color: #c4b5fd !important; }
            .gr-button-primary { background: #a855f7 !important; color: white !important; }
            .gr-button-secondary { background: #6b21a8 !important; color: #faf5ff !important; }
            textarea, input, select, .input-text {
                background: #581c87 !important;
                color: #faf5ff !important;
                border-color: #a78bfa !important;
            }
            .tab-nav button, .tabs button { color: #faf5ff !important; background: #4c1d95 !important; }
            .tab-nav button.selected, .tabs button.selected { background: #a855f7 !important; color: white !important; }
            .accordion { background: #4c1d95 !important; color: #faf5ff !important; }
        </style>
        """
    }

    css = themes_css.get(theme, themes_css["Dark"])
    return f"Tema: {theme}", css


def generate_playlist_from_results(
    results_json: str,
    name: str,
    description: str,
    format_choice: str
) -> Tuple[str, str]:
    """Genera una playlist dai risultati."""
    if not results_json or results_json == "[]":
        return "Nessun risultato disponibile. Esegui prima una ricerca.", ""

    try:
        results_data = json.loads(results_json)
    except:
        return "Errore nel parsing dei risultati.", ""

    if not results_data:
        return "Nessun risultato disponibile.", ""

    # Genera HTML preview con link YouTube
    from playlist_generator import YouTubeGenerator

    yt_gen = YouTubeGenerator()
    playlist_name = name or f"Playlist - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    tracks_html = []
    for i, r in enumerate(results_data, 1):
        song_data = r.get("song", {})
        title = song_data.get("title", "Unknown")
        artist = song_data.get("artist", "Unknown")
        score = r.get("score", 0) * 100

        yt_url = yt_gen.generate_search_url(title, artist)

        tracks_html.append(f"""
        <div style="
            background: rgba(255,255,255,0.05);
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        ">
            <div>
                <span style="color: #64748b; margin-right: 12px;">#{i}</span>
                <strong style="color: #e2e8f0;">{title}</strong>
                <span style="color: #94a3b8;"> - {artist}</span>
                <span style="color: #22c55e; margin-left: 8px; font-size: 12px;">{score:.0f}%</span>
            </div>
            <a href="{yt_url}" target="_blank" style="
                background: #ef4444;
                color: white;
                padding: 6px 12px;
                border-radius: 6px;
                text-decoration: none;
                font-size: 13px;
            ">▶ YouTube</a>
        </div>
        """)

    preview_html = f"""
    <div style="
        background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
        border-radius: 12px;
        padding: 20px;
        margin-top: 16px;
    ">
        <h3 style="color: #e2e8f0; margin: 0 0 8px 0;">🎵 {playlist_name}</h3>
        <p style="color: #94a3b8; margin: 0 0 16px 0;">{description or 'Generata con Cerca Dai Testi'}</p>
        <p style="color: #64748b; margin: 0 0 16px 0; font-size: 13px;">{len(results_data)} brani</p>

        <div style="max-height: 400px; overflow-y: auto;">
            {"".join(tracks_html)}
        </div>
    </div>
    """

    # Export file
    format_map = {
        "HTML (Web)": "html",
        "M3U (Player)": "m3u",
        "JSON (Dati)": "json",
        "Markdown": "md",
        "TXT": "txt"
    }
    ext = format_map.get(format_choice, "html")

    output_dir = Path.home() / ".cerca_dai_testi" / "playlists"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

    from playlist_generator import Playlist, PlaylistTrack
    from playlist_exporter import PlaylistExporter, ExportFormat

    tracks = []
    for r in results_data:
        song_data = r.get("song", {})
        track = PlaylistTrack(
            title=song_data.get("title", "Unknown"),
            artist=song_data.get("artist", "Unknown"),
            youtube_url=yt_gen.generate_search_url(
                song_data.get("title", ""),
                song_data.get("artist", "")
            ),
            relevance_score=r.get("score", 0)
        )
        tracks.append(track)

    playlist = Playlist(
        name=playlist_name,
        description=description or "Generata con Cerca Dai Testi",
        tracks=tracks
    )

    exporter = PlaylistExporter()
    format_enum_map = {
        "html": ExportFormat.HTML,
        "m3u": ExportFormat.M3U,
        "json": ExportFormat.JSON,
        "md": ExportFormat.MARKDOWN,
        "txt": ExportFormat.TXT
    }
    exporter.export(playlist, output_path, format_enum_map[ext])

    status = f"Playlist generata! Salvata in: {output_path}"
    return status, preview_html


def create_interface() -> gr.Blocks:
    """Crea l'interfaccia Gradio."""

    # Mood options
    mood_options = ["Nessuno"] + [preset.name for preset in MOOD_PRESETS.values()]

    with gr.Blocks(title="Cerca Dai Testi") as app:

        gr.Markdown("""
        # 🎵 Cerca Dai Testi

        Trova canzoni con testi semanticamente correlati al tuo argomento o testo.
        Inserisci una frase, un concetto o anche un intero paragrafo e scopri
        quali canzoni parlano di temi simili.
        """)

        with gr.Tabs():
            # Tab Ricerca
            with gr.TabItem("🔍 Ricerca"):
                with gr.Row():
                    with gr.Column(scale=2):
                        query_input = gr.Textbox(
                            label="Cosa vuoi cercare?",
                            placeholder="Es: 'voglio parlare di libertà e speranza' oppure 'broken heart and tears'",
                            lines=3,
                            max_lines=10
                        )

                        with gr.Row():
                            num_results = gr.Slider(
                                minimum=1,
                                maximum=20,
                                value=5,
                                step=1,
                                label="Numero risultati"
                            )

                            min_score = gr.Slider(
                                minimum=0.1,
                                maximum=0.9,
                                value=0.3,
                                step=0.05,
                                label="Score minimo"
                            )

                        mood_filter = gr.Dropdown(
                            choices=mood_options,
                            value="Nessuno",
                            label="Filtra per Mood"
                        )

                        with gr.Row():
                            search_btn = gr.Button("🔍 Cerca", variant="primary", size="lg")
                            clear_btn = gr.Button("🗑️ Svuota Cache", variant="secondary")

                    with gr.Column(scale=1):
                        gr.Markdown("""
                        ### Come funziona

                        1. **Inserisci** un testo o argomento
                        2. **Clicca** su Cerca
                        3. **Esplora** i risultati ordinati per rilevanza

                        ### Suggerimenti

                        - Usa frasi complete per risultati migliori
                        - Prova in italiano o inglese
                        - Lo score indica la similarità semantica
                        - Usa il filtro Mood per affinare i risultati
                        """)

                status_text = gr.Textbox(label="", interactive=False, visible=False)

                with gr.Row():
                    with gr.Column():
                        results_html = gr.HTML(
                            label="Risultati",
                            elem_classes=["results-container"]
                        )

                gr.Markdown("### ➕ Aggiungi ai Preferiti o Playlist")
                gr.Markdown("Dopo la ricerca, seleziona una canzone dal menu e clicca per aggiungerla:")

                with gr.Row():
                    song_dropdown = gr.Dropdown(
                        choices=[],
                        label="Seleziona canzone dai risultati",
                        interactive=True,
                        scale=3
                    )
                    add_fav_btn = gr.Button("⭐ Preferiti", variant="primary", scale=1)
                    add_to_playlist_btn = gr.Button("🎵 Playlist", variant="secondary", scale=1)

                action_status = gr.Markdown(value="")

                with gr.Accordion("📋 Playlist corrente", open=True):
                    current_playlist_html = gr.HTML(value="<p style='color:#888;'>Playlist vuota - aggiungi canzoni dopo una ricerca</p>")
                    with gr.Row():
                        clear_playlist_btn = gr.Button("🗑️ Svuota", variant="stop", size="sm")
                        export_current_playlist_btn = gr.Button("📥 Esporta", variant="secondary", size="sm")

                with gr.Accordion("📄 Esporta risultati", open=False):
                    with gr.Row():
                        export_format = gr.Dropdown(
                            choices=["JSON", "M3U", "CSV", "HTML", "Markdown", "TXT"],
                            value="JSON",
                            label="Formato"
                        )
                        playlist_name = gr.Textbox(
                            label="Nome playlist",
                            placeholder="La mia playlist"
                        )
                        export_btn = gr.Button("📥 Esporta", variant="secondary")

                    export_status = gr.Textbox(label="Export status", interactive=False)
                    json_output = gr.Code(
                        label="JSON",
                        language="json",
                        interactive=False,
                        visible=True
                    )

            # Tab Cronologia
            with gr.TabItem("📜 Cronologia"):
                gr.Markdown("### Cronologia Ricerche")

                with gr.Row():
                    history_search_input = gr.Textbox(
                        label="Cerca nella cronologia",
                        placeholder="Inserisci termine di ricerca...",
                        scale=3
                    )
                    history_search_btn = gr.Button("🔍 Cerca", variant="primary", scale=1)

                history_html = gr.HTML()

                with gr.Accordion("🗑️ Cancella voce singola", open=False):
                    with gr.Row():
                        history_delete_dropdown = gr.Dropdown(
                            choices=[],
                            label="Seleziona voce da cancellare",
                            interactive=True,
                            scale=3
                        )
                        history_delete_btn = gr.Button("❌ Cancella", variant="stop", scale=1)
                    history_delete_status = gr.Textbox(label="", interactive=False, visible=True)

                with gr.Row():
                    refresh_history_btn = gr.Button("🔄 Aggiorna", variant="secondary")
                    clear_history_btn = gr.Button("🗑️ Svuota tutta la cronologia", variant="stop")

            # Tab Preferiti
            with gr.TabItem("⭐ Preferiti"):
                favorites_html = gr.HTML()
                refresh_favorites_btn = gr.Button("🔄 Aggiorna", variant="secondary")

            # Tab Playlist
            with gr.TabItem("🎶 Playlist"):
                gr.Markdown("### Genera Playlist")
                gr.Markdown("Crea una playlist dai risultati della ricerca con link per ascoltare le canzoni.")

                with gr.Row():
                    with gr.Column():
                        playlist_name_gen = gr.Textbox(
                            label="Nome Playlist",
                            placeholder="La mia playlist",
                            value=""
                        )
                        playlist_description = gr.Textbox(
                            label="Descrizione",
                            placeholder="Playlist generata con Cerca Dai Testi",
                            lines=2
                        )

                    with gr.Column():
                        playlist_format = gr.Radio(
                            choices=["HTML (Web)", "M3U (Player)", "JSON (Dati)", "Markdown", "TXT"],
                            value="HTML (Web)",
                            label="Formato Export",
                            interactive=True
                        )

                generate_playlist_btn = gr.Button("🎵 Genera Playlist", variant="primary", size="lg")
                playlist_status = gr.Textbox(label="Status", interactive=False)

                playlist_preview = gr.HTML(label="Anteprima Playlist")

            # Tab Mood
            with gr.TabItem("🎭 Mood"):
                gr.Markdown("### Cerca per emozione")
                gr.Markdown("Clicca su un mood per trovare canzoni con quel tono emotivo.")

                mood_results = gr.HTML(label="Risultati Mood")

                # Crea bottoni per ogni mood in righe
                mood_items = list(MOOD_PRESETS.items())
                mood_btns = {}

                gr.Markdown("#### Clicca per cercare:")
                with gr.Row():
                    for mood_id, preset in mood_items[:5]:
                        mood_btns[mood_id] = gr.Button(
                            f"{preset.emoji} {preset.name}",
                            variant="secondary",
                            size="sm"
                        )
                with gr.Row():
                    for mood_id, preset in mood_items[5:10]:
                        mood_btns[mood_id] = gr.Button(
                            f"{preset.emoji} {preset.name}",
                            variant="secondary",
                            size="sm"
                        )
                with gr.Row():
                    for mood_id, preset in mood_items[10:15]:
                        mood_btns[mood_id] = gr.Button(
                            f"{preset.emoji} {preset.name}",
                            variant="secondary",
                            size="sm"
                        )
                with gr.Row():
                    for mood_id, preset in mood_items[15:]:
                        mood_btns[mood_id] = gr.Button(
                            f"{preset.emoji} {preset.name}",
                            variant="secondary",
                            size="sm"
                        )

            # Tab Impostazioni
            with gr.TabItem("⚙️ Impostazioni"):
                gr.Markdown("### Impostazioni")

                theme_css = gr.HTML(value="", visible=True)

                gr.Markdown("#### Temi Predefiniti")
                with gr.Row():
                    theme_choice = gr.Radio(
                        choices=["Dark", "Light", "Ocean", "Forest", "Sunset", "Purple", "Personalizzato"],
                        value="Dark",
                        label="Seleziona Tema",
                        interactive=True
                    )

                gr.Markdown("#### Editor Tema Personalizzato")
                gr.Markdown("Usa il selettore colori o inserisci il codice esadecimale")

                with gr.Row():
                    bg_picker = gr.ColorPicker(label="Sfondo", value="#0f172a", scale=1)
                    custom_bg_color = gr.Textbox(label="Hex Sfondo", value="#0f172a", max_lines=1, scale=2)
                    card_picker = gr.ColorPicker(label="Card", value="#1e293b", scale=1)
                    custom_card_color = gr.Textbox(label="Hex Card", value="#1e293b", max_lines=1, scale=2)

                with gr.Row():
                    text_picker = gr.ColorPicker(label="Testo", value="#f8fafc", scale=1)
                    custom_text_color = gr.Textbox(label="Hex Testo", value="#f8fafc", max_lines=1, scale=2)
                    accent_picker = gr.ColorPicker(label="Accent", value="#3b82f6", scale=1)
                    custom_accent_color = gr.Textbox(label="Hex Accent", value="#3b82f6", max_lines=1, scale=2)

                apply_custom_theme_btn = gr.Button("🎨 Applica Tema Personalizzato", variant="primary")

                gr.Markdown("---")
                gr.Markdown("#### Altre Impostazioni")

                with gr.Row():
                    default_results = gr.Slider(
                        minimum=5,
                        maximum=20,
                        value=10,
                        step=1,
                        label="Risultati predefiniti"
                    )

                    default_score = gr.Slider(
                        minimum=0.1,
                        maximum=0.9,
                        value=0.3,
                        step=0.05,
                        label="Score minimo predefinito"
                    )

                save_settings_btn = gr.Button("💾 Salva impostazioni", variant="primary")
                settings_status = gr.Textbox(label="Status", interactive=False)

        # Eventi
        search_btn.click(
            fn=search_songs,
            inputs=[query_input, num_results, min_score, mood_filter],
            outputs=[results_html, json_output, status_text, song_dropdown, history_html]
        )

        query_input.submit(
            fn=search_songs,
            inputs=[query_input, num_results, min_score, mood_filter],
            outputs=[results_html, json_output, status_text, song_dropdown, history_html]
        )

        # Eventi aggiungi a playlist
        add_to_playlist_btn.click(
            fn=add_to_playlist_from_dropdown,
            inputs=[song_dropdown],
            outputs=[action_status, current_playlist_html]
        )

        clear_playlist_btn.click(
            fn=clear_current_playlist,
            outputs=[action_status, current_playlist_html]
        )

        export_current_playlist_btn.click(
            fn=export_current_playlist,
            outputs=[action_status]
        )

        add_fav_btn.click(
            fn=add_to_favorites_from_dropdown,
            inputs=[song_dropdown],
            outputs=[action_status, favorites_html]
        )

        clear_btn.click(
            fn=clear_cache,
            outputs=[status_text]
        )

        export_btn.click(
            fn=export_playlist,
            inputs=[json_output, export_format, playlist_name],
            outputs=[gr.File(visible=False), export_status]
        )

        # Eventi cronologia
        refresh_history_btn.click(
            fn=get_history_initial,
            outputs=[history_html]
        ).then(
            fn=get_history_dropdown_choices,
            outputs=[history_delete_dropdown]
        )

        history_search_btn.click(
            fn=search_history,
            inputs=[history_search_input],
            outputs=[history_html]
        )

        history_search_input.submit(
            fn=search_history,
            inputs=[history_search_input],
            outputs=[history_html]
        )

        history_delete_btn.click(
            fn=delete_history_entry,
            inputs=[history_delete_dropdown],
            outputs=[history_delete_status, history_html, history_delete_dropdown]
        )

        clear_history_btn.click(
            fn=clear_history,
            outputs=[history_delete_status, history_html]
        ).then(
            fn=get_history_dropdown_choices,
            outputs=[history_delete_dropdown]
        )

        refresh_favorites_btn.click(
            fn=get_favorites,
            outputs=[favorites_html]
        )

        # Eventi playlist
        generate_playlist_btn.click(
            fn=generate_playlist_from_results,
            inputs=[json_output, playlist_name_gen, playlist_description, playlist_format],
            outputs=[playlist_status, playlist_preview]
        )

        # Eventi mood - collega ogni bottone
        for mood_id, btn in mood_btns.items():
            btn.click(
                fn=partial(search_by_mood, mood_id),
                outputs=[mood_results]
            )

        # Eventi impostazioni
        theme_choice.change(
            fn=on_theme_change,
            inputs=[theme_choice],
            outputs=[settings_status, theme_css]
        )

        # Sincronizza ColorPicker con Textbox (solo in una direzione per evitare loop)
        bg_picker.change(fn=lambda x: x, inputs=[bg_picker], outputs=[custom_bg_color])
        card_picker.change(fn=lambda x: x, inputs=[card_picker], outputs=[custom_card_color])
        text_picker.change(fn=lambda x: x, inputs=[text_picker], outputs=[custom_text_color])
        accent_picker.change(fn=lambda x: x, inputs=[accent_picker], outputs=[custom_accent_color])

        apply_custom_theme_btn.click(
            fn=apply_custom_theme,
            inputs=[custom_bg_color, custom_card_color, custom_text_color, custom_accent_color],
            outputs=[settings_status, theme_css]
        )

        save_settings_btn.click(
            fn=save_settings,
            inputs=[theme_choice, default_results, default_score],
            outputs=[settings_status]
        )

        # Carica dati iniziali
        # Carica dati iniziali
        app.load(fn=get_history_initial, outputs=[history_html])
        app.load(fn=get_history_dropdown_choices, outputs=[history_delete_dropdown])
        app.load(fn=get_favorites, outputs=[favorites_html])

        gr.Markdown("""
        ---
        <p style="text-align: center; color: #666;">
            Cerca Dai Testi • Powered by Genius API & Sentence Transformers
        </p>
        """)

    return app


def main():
    """Avvia l'applicazione GUI."""
    print("Avvio Cerca Dai Testi GUI...")
    print("L'interfaccia si aprirà nel browser.")

    app = create_interface()
    app.launch(
        share=False,
        show_error=True,
        server_name="0.0.0.0",
        server_port=7861
    )


if __name__ == "__main__":
    main()

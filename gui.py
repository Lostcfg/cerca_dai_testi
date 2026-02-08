#!/usr/bin/env python3
"""
Cerca Dai Testi - Interfaccia Grafica

GUI moderna basata su Gradio per cercare canzoni
con testi semanticamente correlati.
"""

import gradio as gr
from typing import List, Tuple
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
) -> Tuple[str, str, str]:
    """
    Esegue la ricerca di canzoni.

    Args:
        query: Testo da cercare
        num_results: Numero di risultati
        min_score: Score minimo di rilevanza
        mood_filter: Filtro mood (opzionale)
        progress: Barra di progresso Gradio

    Returns:
        Tuple con HTML dei risultati, JSON dei dati e messaggio status
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
        return "<p style='text-align:center; color:#888;'>Nessuna canzone trovata</p>", "[]", "Nessun risultato"

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
        return "<p style='text-align:center; color:#888;'>Nessun risultato sopra la soglia di rilevanza</p>", "[]", "Nessun risultato"

    # Salva in cronologia
    user_data.add_to_history(query, results, {"mood": mood_filter, "min_score": min_score})

    # Genera HTML
    html = generate_results_html(results, user_data)

    # Genera JSON per export
    json_data = json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2)

    progress(1.0, desc="Completato!")

    status = f"Trovati {len(results)} risultati"
    return html, json_data, status


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

            <h3 style="margin: 0 0 8px 0; color: #e2e8f0; font-size: 20px;">
                {song.title}
            </h3>

            <p style="margin: 0 0 12px 0; color: #94a3b8; font-size: 16px;">
                <strong>{song.artist}</strong>
                {f' • {song.release_date}' if song.release_date else ''}
            </p>

            {f'''
            <div style="
                background: rgba(0,0,0,0.3);
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 12px;
            ">
                <p style="margin: 0; color: #cbd5e1; font-style: italic; line-height: 1.6;">
                    "{result.relevant_excerpt}"
                </p>
            </div>
            ''' if result.relevant_excerpt else ''}

            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                {f'''
                <a href="{song.url}" target="_blank" style="
                    color: #60a5fa;
                    text-decoration: none;
                    font-size: 14px;
                    padding: 6px 12px;
                    background: rgba(96, 165, 250, 0.1);
                    border-radius: 6px;
                ">
                    Apri su Genius →
                </a>
                ''' if song.url else ''}
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


def get_history() -> str:
    """Restituisce la cronologia come HTML."""
    _, _, user_data, _ = get_components()
    history = user_data.get_history(limit=20)

    if not history:
        return "<p style='color: #888; text-align: center;'>Nessuna ricerca nella cronologia</p>"

    html_parts = ["<div style='max-height: 400px; overflow-y: auto;'>"]

    for entry in history:
        timestamp = entry.timestamp[:16].replace("T", " ")
        html_parts.append(f"""
        <div style="
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong style="color: #e2e8f0;">{entry.query[:50]}{'...' if len(entry.query) > 50 else ''}</strong>
                <span style="color: #64748b; font-size: 12px;">{timestamp}</span>
            </div>
            <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 13px;">
                {entry.results_count} risultati
            </p>
        </div>
        """)

    html_parts.append("</div>")
    return "".join(html_parts)


def get_favorites() -> str:
    """Restituisce i preferiti come HTML."""
    _, _, user_data, _ = get_components()
    favorites = user_data.get_favorites()

    if not favorites:
        return "<p style='color: #888; text-align: center;'>Nessuna canzone nei preferiti</p>"

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


def clear_history():
    """Svuota la cronologia."""
    _, _, user_data, _ = get_components()
    user_data.clear_history()
    return "Cronologia svuotata!"


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

                status_text = gr.Textbox(label="Status", interactive=False, visible=True)

                with gr.Row():
                    with gr.Column():
                        results_html = gr.HTML(
                            label="Risultati",
                            elem_classes=["results-container"]
                        )

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
                history_html = gr.HTML()
                with gr.Row():
                    refresh_history_btn = gr.Button("🔄 Aggiorna", variant="secondary")
                    clear_history_btn = gr.Button("🗑️ Svuota cronologia", variant="stop")

            # Tab Preferiti
            with gr.TabItem("⭐ Preferiti"):
                favorites_html = gr.HTML()
                refresh_favorites_btn = gr.Button("🔄 Aggiorna", variant="secondary")

            # Tab Mood
            with gr.TabItem("🎭 Mood"):
                gr.Markdown("### Cerca per emozione")
                gr.Markdown("Seleziona un mood per trovare canzoni con quel tono emotivo.")

                mood_grid = gr.HTML(value=f"""
                <div style="display: flex; flex-wrap: wrap; gap: 10px; padding: 20px;">
                    {"".join([f'''
                    <div style="
                        background: linear-gradient(135deg, {preset.color}88, {preset.color}44);
                        border: 2px solid {preset.color};
                        border-radius: 12px;
                        padding: 16px 24px;
                        text-align: center;
                        cursor: pointer;
                        transition: transform 0.2s;
                    " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                        <div style="font-size: 32px; margin-bottom: 8px;">{preset.emoji}</div>
                        <div style="color: white; font-weight: bold;">{preset.name}</div>
                        <div style="color: rgba(255,255,255,0.7); font-size: 12px; margin-top: 4px;">
                            {preset.description}
                        </div>
                    </div>
                    ''' for preset in MOOD_PRESETS.values()])}
                </div>
                """)

            # Tab Impostazioni
            with gr.TabItem("⚙️ Impostazioni"):
                gr.Markdown("### Impostazioni")

                with gr.Row():
                    theme_choice = gr.Radio(
                        choices=["Dark", "Light"],
                        value="Dark",
                        label="Tema"
                    )

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
            outputs=[results_html, json_output, status_text]
        )

        query_input.submit(
            fn=search_songs,
            inputs=[query_input, num_results, min_score, mood_filter],
            outputs=[results_html, json_output, status_text]
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

        refresh_history_btn.click(
            fn=get_history,
            outputs=[history_html]
        )

        clear_history_btn.click(
            fn=clear_history,
            outputs=[status_text]
        ).then(
            fn=get_history,
            outputs=[history_html]
        )

        refresh_favorites_btn.click(
            fn=get_favorites,
            outputs=[favorites_html]
        )

        # Carica dati iniziali
        app.load(fn=get_history, outputs=[history_html])
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

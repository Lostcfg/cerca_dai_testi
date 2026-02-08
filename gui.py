#!/usr/bin/env python3
"""
Cerca Dai Testi - Interfaccia Grafica

GUI moderna basata su Gradio per cercare canzoni
con testi semanticamente correlati.
"""

import gradio as gr
from typing import List, Tuple
import json

from config import Config
from lyrics_fetcher import LyricsFetcher
from semantic_matcher import SemanticMatcher, MatchResult
from utils import setup_logging


# Inizializza componenti globali (lazy loading)
_fetcher = None
_matcher = None
_logger = None


def get_components():
    """Inizializza i componenti alla prima chiamata."""
    global _fetcher, _matcher, _logger

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

    return _fetcher, _matcher


def search_songs(
    query: str,
    num_results: int,
    min_score: float,
    progress=gr.Progress()
) -> Tuple[str, str]:
    """
    Esegue la ricerca di canzoni.

    Args:
        query: Testo da cercare
        num_results: Numero di risultati
        min_score: Score minimo di rilevanza
        progress: Barra di progresso Gradio

    Returns:
        Tuple con HTML dei risultati e JSON dei dati
    """
    if not query or not query.strip():
        raise gr.Error("Inserisci un testo da cercare")

    try:
        fetcher, matcher = get_components()
    except Exception as e:
        raise gr.Error(str(e))

    progress(0.1, desc="Ricerca canzoni...")

    # Estrai termini di ricerca
    words = query.split()
    if len(words) <= 10:
        search_terms = [query]
    else:
        search_terms = matcher.extract_key_phrases(query, top_k=3)
        # Aggiungi parole chiave
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
        return "<p style='text-align:center; color:#888;'>Nessuna canzone trovata</p>", "[]"

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
        return "<p style='text-align:center; color:#888;'>Nessun risultato sopra la soglia di rilevanza</p>", "[]"

    # Genera HTML
    html = generate_results_html(results)

    # Genera JSON per export
    json_data = json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2)

    progress(1.0, desc="Completato!")

    return html, json_data


def generate_results_html(results: List[MatchResult]) -> str:
    """Genera HTML per i risultati."""
    html_parts = []

    for i, result in enumerate(results):
        song = result.song
        score_percent = result.score * 100

        # Colore badge in base allo score
        if score_percent >= 70:
            badge_color = "#22c55e"  # Verde
        elif score_percent >= 50:
            badge_color = "#eab308"  # Giallo
        else:
            badge_color = "#f97316"  # Arancione

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

            {f'''
            <a href="{song.url}" target="_blank" style="
                color: #60a5fa;
                text-decoration: none;
                font-size: 14px;
            ">
                Apri su Genius →
            </a>
            ''' if song.url else ''}
        </div>
        """)

    return "".join(html_parts)


def clear_cache():
    """Svuota la cache."""
    global _fetcher, _matcher

    if _fetcher:
        _fetcher.clear_cache()
    if _matcher:
        _matcher.clear_cache()

    return "Cache svuotata con successo!"


def create_interface() -> gr.Blocks:
    """Crea l'interfaccia Gradio."""

    with gr.Blocks(
        title="Cerca Dai Testi",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
        ),
        css="""
        .gradio-container { max-width: 1200px !important; }
        .results-container { min-height: 400px; }
        """
    ) as app:

        gr.Markdown("""
        # 🎵 Cerca Dai Testi

        Trova canzoni con testi semanticamente correlati al tuo argomento o testo.
        Inserisci una frase, un concetto o anche un intero paragrafo e scopri
        quali canzoni parlano di temi simili.
        """)

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
                """)

        with gr.Row():
            with gr.Column():
                results_html = gr.HTML(
                    label="Risultati",
                    elem_classes=["results-container"]
                )

        with gr.Accordion("📄 Esporta risultati (JSON)", open=False):
            json_output = gr.Code(
                label="JSON",
                language="json",
                interactive=False
            )

        status_msg = gr.Textbox(label="Status", visible=False)

        # Eventi
        search_btn.click(
            fn=search_songs,
            inputs=[query_input, num_results, min_score],
            outputs=[results_html, json_output]
        )

        query_input.submit(
            fn=search_songs,
            inputs=[query_input, num_results, min_score],
            outputs=[results_html, json_output]
        )

        clear_btn.click(
            fn=clear_cache,
            outputs=[status_msg]
        ).then(
            fn=lambda: gr.Info("Cache svuotata!"),
            outputs=[]
        )

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
        server_port=7860
    )


if __name__ == "__main__":
    main()

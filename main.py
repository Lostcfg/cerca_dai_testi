#!/usr/bin/env python3
"""
Cerca Dai Testi - Trova canzoni con testi attinenti al tuo argomento.

Entry point dell'applicazione con interfaccia a linea di comando.
Permette di cercare canzoni semanticamente correlate a un testo
o argomento fornito dall'utente.

Example:
    $ python main.py --text "voglio parlare di libertà"
    $ python main.py --file poesia.txt --limit 10
    $ python main.py --text "broken heart" --output results.json --verbose
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from config import Config, MESSAGES
from lyrics_fetcher import LyricsFetcher, Song
from semantic_matcher import SemanticMatcher, MatchResult
from utils import setup_logging, format_duration
import time


def parse_args() -> argparse.Namespace:
    """
    Configura e parsea gli argomenti della linea di comando.

    Returns:
        argparse.Namespace: Argomenti parsati.
    """
    parser = argparse.ArgumentParser(
        prog="cerca_dai_testi",
        description="Trova canzoni con testi semanticamente correlati al tuo input.",
        epilog="Esempio: python main.py --text 'amore eterno' --limit 5",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Input options (mutualmente esclusivi)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-t", "--text",
        type=str,
        help="Testo o argomento da cercare"
    )
    input_group.add_argument(
        "-f", "--file",
        type=Path,
        help="Path a un file di testo da usare come input"
    )

    # Output options
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=Config.DEFAULT_LIMIT,
        help=f"Numero massimo di risultati (default: {Config.DEFAULT_LIMIT})"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Salva i risultati in un file JSON"
    )

    # Search options
    parser.add_argument(
        "-s", "--search-terms",
        type=str,
        nargs="+",
        help="Termini aggiuntivi per la ricerca di canzoni"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=Config.MIN_RELEVANCE_SCORE,
        help=f"Score minimo di rilevanza (default: {Config.MIN_RELEVANCE_SCORE})"
    )

    # Behavior options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostra informazioni dettagliate durante l'esecuzione"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignora la cache e forza nuove richieste API"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Svuota la cache prima dell'esecuzione"
    )

    return parser.parse_args()


def read_input_file(file_path: Path) -> str:
    """
    Legge il contenuto di un file di testo.

    Args:
        file_path: Path del file da leggere.

    Returns:
        str: Contenuto del file.

    Raises:
        FileNotFoundError: Se il file non esiste.
        IOError: Se il file non può essere letto.
    """
    if not file_path.exists():
        raise FileNotFoundError(MESSAGES["file_not_found"].format(path=file_path))

    return file_path.read_text(encoding="utf-8")


def extract_search_terms(text: str, matcher: SemanticMatcher) -> List[str]:
    """
    Estrae termini di ricerca da un testo.

    Per testi brevi, usa il testo stesso.
    Per testi lunghi, estrae le frasi chiave.

    Args:
        text: Testo da analizzare.
        matcher: SemanticMatcher per l'estrazione.

    Returns:
        List[str]: Termini di ricerca estratti.
    """
    # Se il testo è breve, usalo direttamente
    words = text.split()
    if len(words) <= 10:
        return [text]

    # Per testi lunghi, estrai frasi chiave
    key_phrases = matcher.extract_key_phrases(text, top_k=5)

    # Aggiungi anche parole singole importanti
    # (filtro parole corte e comuni)
    stopwords = {"il", "la", "di", "che", "un", "a", "the", "and", "is", "of", "to"}
    keywords = [
        word for word in words
        if len(word) > 4 and word.lower() not in stopwords
    ][:5]

    return key_phrases + keywords


def format_result(result: MatchResult, index: int) -> str:
    """
    Formatta un risultato per la visualizzazione console.

    Args:
        result: Risultato da formattare.
        index: Posizione nella classifica.

    Returns:
        str: Risultato formattato.
    """
    song = result.song
    lines = [
        f"\n{'='*60}",
        f"#{index + 1} | Score: {result.score:.2%}",
        f"{'='*60}",
        f"Titolo:  {song.title}",
        f"Artista: {song.artist}",
    ]

    if song.url:
        lines.append(f"Link:    {song.url}")

    if song.release_date:
        lines.append(f"Anno:    {song.release_date}")

    if result.relevant_excerpt:
        lines.append(f"\nEstratto rilevante:")
        lines.append(f'"{result.relevant_excerpt}"')

    return "\n".join(lines)


def save_results(results: List[MatchResult], output_path: Path) -> None:
    """
    Salva i risultati in un file JSON.

    Args:
        results: Lista di risultati da salvare.
        output_path: Path del file di output.
    """
    data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(results),
        "results": [r.to_dict() for r in results]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> int:
    """
    Funzione principale dell'applicazione.

    Orchestrates the search flow:
    1. Parse arguments
    2. Load input text
    3. Search for songs
    4. Compute semantic similarity
    5. Display/save results

    Returns:
        int: Exit code (0 per successo, 1 per errore).
    """
    args = parse_args()

    # Setup logging
    logger = setup_logging(verbose=args.verbose)
    logger.info("Avvio Cerca Dai Testi")

    start_time = time.time()

    try:
        # Valida configurazione
        Config.validate()
    except ValueError as e:
        print(f"Errore configurazione: {e}", file=sys.stderr)
        return 1

    # Leggi input
    try:
        if args.text:
            input_text = args.text
        else:
            input_text = read_input_file(args.file)
            logger.info(f"Letto file: {args.file}")
    except FileNotFoundError as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1

    logger.info(f"Input: {input_text[:100]}...")

    # Inizializza componenti
    try:
        fetcher = LyricsFetcher()
        matcher = SemanticMatcher()
    except Exception as e:
        print(f"Errore inizializzazione: {e}", file=sys.stderr)
        return 1

    # Gestione cache
    if args.clear_cache:
        fetcher.clear_cache()
        matcher.clear_cache()
        logger.info("Cache svuotata")

    # Estrai termini di ricerca
    search_terms = extract_search_terms(input_text, matcher)
    if args.search_terms:
        search_terms.extend(args.search_terms)

    logger.info(f"Termini di ricerca: {search_terms}")

    # Cerca canzoni
    print("\nRicerca canzoni in corso...")
    all_songs: List[Song] = []

    for term in search_terms[:5]:  # Limita a 5 termini
        logger.debug(f"Ricerca per: {term}")
        songs = fetcher.get_songs_with_lyrics(
            term,
            limit=args.limit * 2  # Cerca più del necessario
        )
        all_songs.extend(songs)

    # Rimuovi duplicati
    seen_ids = set()
    unique_songs = []
    for song in all_songs:
        if song.id not in seen_ids:
            seen_ids.add(song.id)
            unique_songs.append(song)

    logger.info(f"Trovate {len(unique_songs)} canzoni uniche")

    if not unique_songs:
        print(MESSAGES["no_results"])
        return 0

    # Calcola similarità semantica
    print("Analisi semantica in corso...")
    results = matcher.find_similar_songs(
        input_text,
        unique_songs,
        limit=args.limit,
        min_score=args.min_score
    )

    elapsed = time.time() - start_time

    # Mostra risultati
    if not results:
        print(MESSAGES["no_results"])
        return 0

    print(f"\n{MESSAGES['search_complete'].format(count=len(results))}")
    print(f"Tempo di esecuzione: {format_duration(elapsed)}")

    for i, result in enumerate(results):
        print(format_result(result, i))

    # Salva risultati se richiesto
    if args.output:
        save_results(results, args.output)
        print(f"\nRisultati salvati in: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

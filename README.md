# Cerca Dai Testi

Trova canzoni con testi semanticamente correlati a un argomento o testo fornito.

## Funzionalità

### Core
- **Ricerca semantica**: Utilizza modelli NLP per trovare canzoni il cui testo è semanticamente simile al tuo input
- **Supporto multilingua**: Funziona con italiano, inglese, spagnolo, francese, tedesco e portoghese
- **Caching intelligente**: Memorizza risultati e embeddings per velocizzare ricerche ripetute
- **Rate limiting**: Gestisce automaticamente i limiti delle API

### Funzionalità Avanzate
- **Ricerca per Mood**: 10 preset emotivi (felice, triste, romantico, energico, calmo, arrabbiato, nostalgico, speranzoso, ribelle, sognante)
- **Confronto Canzoni**: Analisi semantica tra due o più canzoni con temi comuni e similarità
- **Ricerca per Verso**: Trova versi specifici con match esatto, fuzzy o semantico
- **Generazione Playlist**: Crea playlist con link YouTube e supporto Spotify API
- **Export Multiplo**: JSON, M3U, CSV, HTML, Markdown, TXT, XSPF
- **Cronologia Ricerche**: Salvataggio automatico con statistiche
- **Preferiti**: Salva canzoni con tag e note personali
- **Tema Dark/Light**: Personalizzazione interfaccia

### Interfacce
- **GUI Web**: Interfaccia moderna con Gradio
- **CLI**: Riga di comando con opzioni complete
- **API Modulare**: Import dei moduli in altri progetti

## Requisiti

- Python 3.9+
- Account Genius API (gratuito)
- (Opzionale) Credenziali Spotify per playlist

## Installazione

```bash
# Clona il repository
git clone https://github.com/Lostcfg/cerca_dai_testi.git
cd cerca_dai_testi

# Crea virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# oppure: venv\Scripts\activate  # Windows

# Installa dipendenze
pip install -r requirements.txt
```

## Setup API

### Genius (Obbligatorio)

1. Vai su https://genius.com/api-clients
2. Crea una nuova applicazione
3. Copia il "Client Access Token"
4. Crea il file `.env`:

```bash
cp esempio.env .env
# Modifica .env e inserisci il tuo token
```

### Spotify (Opzionale)

Per creare playlist su Spotify, aggiungi al `.env`:

```env
SPOTIFY_CLIENT_ID=il_tuo_client_id
SPOTIFY_CLIENT_SECRET=il_tuo_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

## Utilizzo

### Interfaccia Grafica (GUI)

```bash
python gui.py
```

Si aprirà un'interfaccia web su http://localhost:7861 con:

| Tab | Funzionalità |
|-----|-------------|
| **Ricerca** | Campo di ricerca, filtri, risultati con card colorate |
| **Cronologia** | Storico ricerche con possibilità di ripeterle |
| **Preferiti** | Canzoni salvate con tag e note |
| **Mood** | Griglia visuale per ricerca per emozione |
| **Impostazioni** | Tema, preferenze, export |

### CLI - Ricerca Base

```bash
# Ricerca da testo
python main.py --text "voglio parlare di libertà e speranza"

# Ricerca da file
python main.py --file mio_testo.txt --limit 10

# Con opzioni
python main.py --text "broken heart" \
    --limit 5 \
    --output risultati.json \
    --verbose
```

### Parametri CLI

| Parametro | Descrizione |
|-----------|-------------|
| `-t, --text` | Testo o argomento da cercare |
| `-f, --file` | File di testo da usare come input |
| `-l, --limit` | Numero massimo di risultati (default: 5) |
| `-o, --output` | Salva risultati in JSON |
| `-s, --search-terms` | Termini aggiuntivi per la ricerca |
| `--min-score` | Score minimo di rilevanza (default: 0.3) |
| `-v, --verbose` | Mostra info dettagliate |
| `--clear-cache` | Svuota la cache prima dell'esecuzione |

### Utilizzo Programmatico

```python
from lyrics_fetcher import LyricsFetcher
from semantic_matcher import SemanticMatcher
from mood_analyzer import MoodAnalyzer
from song_comparator import SongComparator

# Ricerca base
fetcher = LyricsFetcher()
matcher = SemanticMatcher()

songs = fetcher.get_songs_with_lyrics("amore", limit=10)
results = matcher.find_similar_songs("cuore spezzato", songs)

# Analisi mood
analyzer = MoodAnalyzer()
mood = analyzer.analyze("Lacrime e dolore nel cuore")
print(f"Mood: {mood.primary_mood}")  # "sad"

# Confronto canzoni
comparator = SongComparator()
comparison = comparator.compare(song1, song2)
print(f"Similarità: {comparison.semantic_similarity:.1%}")

# Ricerca per verso
from verse_search import VerseSearcher
searcher = VerseSearcher()
results = searcher.search_verse("non ho più lacrime", songs)
```

## Moduli

### `mood_analyzer.py`
Analisi delle emozioni nei testi con 10 preset:
- Felice, Triste, Romantico, Energico, Calmo
- Arrabbiato, Nostalgico, Speranzoso, Ribelle, Sognante

```python
from mood_analyzer import MoodAnalyzer, MOOD_PRESETS

analyzer = MoodAnalyzer()
result = analyzer.analyze(lyrics)
print(result.primary_mood, result.confidence)
```

### `song_comparator.py`
Confronto semantico tra canzoni:
- Similarità complessiva
- Versi più simili
- Temi in comune
- Analisi vocabolario

```python
from song_comparator import SongComparator

comparator = SongComparator()
result = comparator.compare(song1, song2)
print(comparator.get_similarity_summary(result))
```

### `verse_search.py`
Ricerca per verso specifico:
- Match esatto, fuzzy, semantico
- Contesto (versi prima/dopo)
- Rilevamento sezioni (strofa, ritornello)

```python
from verse_search import VerseSearcher

searcher = VerseSearcher()
results = searcher.search_verse(
    "cuore spezzato",
    songs,
    search_type="semantic",
    min_similarity=0.5
)
```

### `playlist_generator.py` / `playlist_exporter.py`
Generazione ed export playlist:

```python
from playlist_generator import PlaylistGenerator
from playlist_exporter import PlaylistExporter, ExportFormat

# Genera playlist
generator = PlaylistGenerator(use_spotify=True)
playlist = generator.from_search_results(results, name="My Playlist")

# Esporta in vari formati
exporter = PlaylistExporter()
exporter.export(playlist, Path("playlist.html"), ExportFormat.HTML)
exporter.export(playlist, Path("playlist.m3u"), ExportFormat.M3U)
```

### `user_data.py`
Gestione dati utente:

```python
from user_data import UserDataManager

manager = UserDataManager()

# Cronologia
manager.add_to_history("query", results)
history = manager.get_history(limit=10)

# Preferiti
manager.add_favorite(song, notes="Bella!", tags=["rock", "anni80"])
favorites = manager.get_favorites_by_tag("rock")

# Tema
manager.set_theme("light")  # o "dark"
```

## Esempio Output

```
Ricerca completata. Trovate 5 canzoni.
Tempo di esecuzione: 12s

============================================================
#1 | Score: 87.50%
============================================================
Titolo:  Volare
Artista: Domenico Modugno
Link:    https://genius.com/...

Estratto rilevante:
"Penso che un sogno così non ritorni mai più..."
```

## Struttura Progetto

```
cerca_dai_testi/
├── main.py                # Entry point CLI
├── gui.py                 # Interfaccia grafica (Gradio)
├── config.py              # Configurazioni
├── lyrics_fetcher.py      # Interfaccia Genius API
├── semantic_matcher.py    # Matching semantico NLP
├── utils.py               # Utilities (cache, logging, rate limit)
├── mood_analyzer.py       # Analisi mood/emozioni
├── song_comparator.py     # Confronto tra canzoni
├── verse_search.py        # Ricerca per verso specifico
├── playlist_generator.py  # Generazione playlist
├── playlist_exporter.py   # Export multi-formato
├── user_data.py           # Cronologia, preferiti, impostazioni
├── tests/                 # Test unitari
├── requirements.txt       # Dipendenze
└── esempio.env            # Template configurazione
```

## Troubleshooting

### "GENIUS_API_TOKEN non configurato"
Assicurati di aver creato il file `.env` con il token valido.

### "Rate limit raggiunto"
Attendi qualche minuto. Il programma gestisce automaticamente i limiti, ma richieste molto frequenti possono causare blocchi temporanei.

### Risultati non pertinenti
- Prova a usare frasi più specifiche
- Usa il filtro Mood per affinare
- Aumenta `--limit` per avere più scelta
- Abbassa `--min-score` se ottieni pochi risultati

### Modello NLP lento al primo avvio
Il modello sentence-transformers viene scaricato al primo utilizzo (~100MB). Le esecuzioni successive saranno più veloci.

### Spotify non funziona
- Verifica le credenziali in `.env`
- Assicurati di aver installato `spotipy`: `pip install spotipy`
- Al primo utilizzo, autorizza l'app nel browser

## Test

```bash
# Esegui tutti i test
python -m pytest tests/ -v

# Con coverage
python -m pytest tests/ --cov=. --cov-report=html
```

## Licenza

MIT License

## Contribuire

1. Fork del repository
2. Crea un branch (`git checkout -b feature/nuova-funzionalità`)
3. Commit (`git commit -m 'Aggiunta nuova funzionalità'`)
4. Push (`git push origin feature/nuova-funzionalità`)
5. Apri una Pull Request

# Cerca Dai Testi

Trova canzoni con testi semanticamente correlati a un argomento o testo fornito.

## Funzionalità

- **Ricerca semantica**: Utilizza modelli NLP per trovare canzoni il cui testo è semanticamente simile al tuo input
- **Supporto multilingua**: Funziona con italiano, inglese, spagnolo, francese, tedesco e portoghese
- **Caching intelligente**: Memorizza risultati e embeddings per velocizzare ricerche ripetute
- **Rate limiting**: Gestisce automaticamente i limiti delle API
- **Output flessibile**: Visualizza risultati a console o esporta in JSON
- **Interfaccia grafica**: GUI web moderna con Gradio

## Requisiti

- Python 3.9+
- Account Genius API (gratuito)

## Installazione

```bash
# Clona o scarica il progetto
cd cerca_dai_testi

# Crea virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# oppure: venv\Scripts\activate  # Windows

# Installa dipendenze
pip install -r requirements.txt
```

## Setup API

1. Vai su https://genius.com/api-clients
2. Crea una nuova applicazione
3. Copia il "Client Access Token"
4. Crea il file `.env`:

```bash
cp esempio.env .env
# Modifica .env e inserisci il tuo token
```

## Utilizzo

### Interfaccia Grafica (GUI)

```bash
python gui.py
```

Si aprirà un'interfaccia web su http://localhost:7860 con:
- Campo di ricerca per testo/argomento
- Slider per numero risultati e score minimo
- Risultati visualizzati con card colorate
- Export JSON dei risultati

### Ricerca da testo (CLI)

```bash
python main.py --text "voglio parlare di libertà e speranza"
```

### Ricerca da file

```bash
python main.py --file mio_testo.txt --limit 10
```

### Opzioni complete

```bash
python main.py --text "broken heart" \
    --limit 5 \
    --output risultati.json \
    --verbose
```

### Parametri

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

## Troubleshooting

### "GENIUS_API_TOKEN non configurato"
Assicurati di aver creato il file `.env` con il token valido.

### "Rate limit raggiunto"
Attendi qualche minuto. Il programma gestisce automaticamente i limiti, ma richieste molto frequenti possono causare blocchi temporanei.

### Risultati non pertinenti
- Prova a usare frasi più specifiche
- Aumenta `--limit` per avere più scelta
- Abbassa `--min-score` se ottieni pochi risultati

### Modello NLP lento al primo avvio
Il modello sentence-transformers viene scaricato al primo utilizzo (~100MB). Le esecuzioni successive saranno più veloci.

## Struttura Progetto

```
cerca_dai_testi/
├── main.py              # Entry point CLI
├── gui.py               # Interfaccia grafica (Gradio)
├── config.py            # Configurazioni
├── lyrics_fetcher.py    # Interfaccia Genius API
├── semantic_matcher.py  # Matching semantico NLP
├── utils.py             # Utilities (cache, logging, rate limit)
├── tests/               # Test unitari
├── requirements.txt     # Dipendenze
└── esempio.env          # Template configurazione
```

## Licenza

MIT License

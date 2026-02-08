"""
Modulo di configurazione per Cerca Dai Testi.

Gestisce il caricamento delle variabili d'ambiente, le costanti
dell'applicazione e i parametri di configurazione globali.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Carica variabili d'ambiente dal file .env
load_dotenv()


class Config:
    """
    Classe di configurazione centralizzata.

    Gestisce tutte le impostazioni dell'applicazione, incluse
    le API keys, i parametri di caching e le costanti operative.

    Attributes:
        GENIUS_API_TOKEN: Token per l'autenticazione con Genius API.
        CACHE_DIR: Directory per il caching dei risultati.
        CACHE_EXPIRY_HOURS: Ore dopo le quali la cache scade.
        DEFAULT_LIMIT: Numero di risultati di default.
        MAX_LIMIT: Numero massimo di risultati permessi.
        RATE_LIMIT_CALLS: Numero massimo di chiamate API per periodo.
        RATE_LIMIT_PERIOD: Periodo in secondi per il rate limiting.
        EMBEDDING_MODEL: Nome del modello sentence-transformers da usare.
        LOG_LEVEL: Livello di logging (DEBUG, INFO, WARNING, ERROR).
        LOG_FILE: Path del file di log (opzionale).

    Example:
        >>> from config import Config
        >>> config = Config()
        >>> print(config.GENIUS_API_TOKEN)
        'your_token_here'
    """

    # API Configuration
    GENIUS_API_TOKEN: Optional[str] = os.getenv("GENIUS_API_TOKEN")
    GENIUS_BASE_URL: str = "https://api.genius.com"

    # Cache Configuration
    CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", ".cache"))
    CACHE_EXPIRY_HOURS: int = int(os.getenv("CACHE_EXPIRY_HOURS", "24"))

    # Search Configuration
    DEFAULT_LIMIT: int = 5
    MAX_LIMIT: int = 50
    MIN_RELEVANCE_SCORE: float = 0.3

    # Rate Limiting
    RATE_LIMIT_CALLS: int = int(os.getenv("RATE_LIMIT_CALLS", "10"))
    RATE_LIMIT_PERIOD: int = int(os.getenv("RATE_LIMIT_PERIOD", "60"))

    # NLP Configuration
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL",
        "paraphrase-multilingual-MiniLM-L12-v2"
    )

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")

    # Request Configuration
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0

    @classmethod
    def validate(cls) -> bool:
        """
        Valida la configurazione corrente.

        Verifica che tutte le configurazioni necessarie siano presenti
        e abbiano valori validi.

        Returns:
            bool: True se la configurazione è valida, False altrimenti.

        Raises:
            ValueError: Se manca la GENIUS_API_TOKEN.

        Example:
            >>> Config.validate()
            True
        """
        if not cls.GENIUS_API_TOKEN:
            raise ValueError(
                "GENIUS_API_TOKEN non configurato. "
                "Imposta la variabile d'ambiente o crea un file .env"
            )
        return True

    @classmethod
    def get_cache_path(cls, cache_name: str) -> Path:
        """
        Restituisce il path completo per un file di cache.

        Args:
            cache_name: Nome del file di cache.

        Returns:
            Path: Path completo del file di cache.

        Example:
            >>> Config.get_cache_path("lyrics_cache.json")
            PosixPath('.cache/lyrics_cache.json')
        """
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return cls.CACHE_DIR / cache_name


# Costanti per messaggi
MESSAGES = {
    "no_results": "Nessuna canzone trovata per la query specificata.",
    "api_error": "Errore durante la comunicazione con l'API.",
    "rate_limit": "Rate limit raggiunto. Attendere prima di riprovare.",
    "invalid_input": "Input non valido. Fornire un testo o un file.",
    "file_not_found": "File non trovato: {path}",
    "search_complete": "Ricerca completata. Trovate {count} canzoni.",
}

# Supporto lingue per il modello multilingua
SUPPORTED_LANGUAGES = [
    "it",  # Italiano
    "en",  # Inglese
    "es",  # Spagnolo
    "fr",  # Francese
    "de",  # Tedesco
    "pt",  # Portoghese
]

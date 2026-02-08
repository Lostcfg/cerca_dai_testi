"""
Modulo di utilità per Cerca Dai Testi.

Contiene funzioni di supporto per caching, logging, rate limiting
e altre operazioni comuni utilizzate in tutto il progetto.
"""

import functools
import hashlib
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Optional, TypeVar

from config import Config

# Type variable per decorator generici
F = TypeVar("F", bound=Callable[..., Any])


def setup_logging(
    verbose: bool = False,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configura e restituisce il logger dell'applicazione.

    Imposta il formato dei log, il livello di logging e opzionalmente
    scrive i log su file.

    Args:
        verbose: Se True, imposta il livello a DEBUG.
        log_file: Path opzionale per salvare i log su file.

    Returns:
        logging.Logger: Logger configurato per l'applicazione.

    Example:
        >>> logger = setup_logging(verbose=True)
        >>> logger.debug("Messaggio di debug")
        2024-01-15 10:30:00 - cerca_dai_testi - DEBUG - Messaggio di debug
    """
    level = logging.DEBUG if verbose else getattr(
        logging, Config.LOG_LEVEL, logging.INFO
    )

    # Formato del log
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configura il logger root
    logger = logging.getLogger("cerca_dai_testi")
    logger.setLevel(level)

    # Rimuovi handler esistenti
    logger.handlers.clear()

    # Handler per console
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    logger.addHandler(console_handler)

    # Handler per file (opzionale)
    file_path = log_file or Config.LOG_FILE
    if file_path:
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        logger.addHandler(file_handler)

    return logger


class Cache:
    """
    Sistema di caching su disco con scadenza temporale.

    Memorizza i risultati delle ricerche per evitare chiamate API ripetute.
    Supporta scadenza automatica e invalidazione manuale.

    Attributes:
        cache_file: Path del file di cache.
        expiry_hours: Ore dopo le quali gli elementi scadono.
        _cache: Dizionario interno con i dati cached.
        _lock: Lock per thread-safety.

    Example:
        >>> cache = Cache("lyrics_cache.json")
        >>> cache.set("key1", {"data": "value"})
        >>> cache.get("key1")
        {'data': 'value'}
    """

    def __init__(
        self,
        cache_name: str = "cache.json",
        expiry_hours: Optional[int] = None
    ):
        """
        Inizializza il sistema di cache.

        Args:
            cache_name: Nome del file di cache.
            expiry_hours: Ore prima della scadenza (default da Config).
        """
        self.cache_file = Config.get_cache_path(cache_name)
        self.expiry_hours = expiry_hours or Config.CACHE_EXPIRY_HOURS
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        self._load()

    def _load(self) -> None:
        """Carica la cache dal disco se esiste."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cache = {}

    def _save(self) -> None:
        """Salva la cache su disco."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logging.getLogger("cerca_dai_testi").warning(
                f"Impossibile salvare cache: {e}"
            )

    def _is_expired(self, timestamp: str) -> bool:
        """Verifica se un elemento è scaduto."""
        cached_time = datetime.fromisoformat(timestamp)
        return datetime.now() - cached_time > timedelta(hours=self.expiry_hours)

    @staticmethod
    def _generate_key(data: str) -> str:
        """Genera una chiave hash per i dati."""
        return hashlib.md5(data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        Recupera un valore dalla cache.

        Args:
            key: Chiave dell'elemento da recuperare.

        Returns:
            Il valore cached se presente e non scaduto, None altrimenti.

        Example:
            >>> cache = Cache()
            >>> cache.get("my_key")
            {'cached': 'data'}
        """
        with self._lock:
            hashed_key = self._generate_key(key)
            if hashed_key in self._cache:
                entry = self._cache[hashed_key]
                if not self._is_expired(entry["timestamp"]):
                    return entry["data"]
                else:
                    del self._cache[hashed_key]
                    self._save()
            return None

    def set(self, key: str, value: Any) -> None:
        """
        Salva un valore nella cache.

        Args:
            key: Chiave per l'elemento.
            value: Valore da memorizzare (deve essere JSON-serializable).

        Example:
            >>> cache = Cache()
            >>> cache.set("my_key", {"result": [1, 2, 3]})
        """
        with self._lock:
            hashed_key = self._generate_key(key)
            self._cache[hashed_key] = {
                "data": value,
                "timestamp": datetime.now().isoformat()
            }
            self._save()

    def clear(self) -> None:
        """Svuota completamente la cache."""
        with self._lock:
            self._cache = {}
            self._save()

    def cleanup_expired(self) -> int:
        """
        Rimuove tutti gli elementi scaduti dalla cache.

        Returns:
            int: Numero di elementi rimossi.
        """
        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items()
                if self._is_expired(v["timestamp"])
            ]
            for key in expired_keys:
                del self._cache[key]
            if expired_keys:
                self._save()
            return len(expired_keys)


class RateLimiter:
    """
    Rate limiter per controllare la frequenza delle chiamate API.

    Implementa un algoritmo sliding window per limitare il numero
    di chiamate in un dato periodo di tempo.

    Attributes:
        max_calls: Numero massimo di chiamate permesse.
        period: Periodo in secondi per il conteggio.
        _calls: Lista di timestamp delle chiamate.
        _lock: Lock per thread-safety.

    Example:
        >>> limiter = RateLimiter(max_calls=10, period=60)
        >>> limiter.acquire()  # Aspetta se necessario
        >>> # Esegui chiamata API
    """

    def __init__(
        self,
        max_calls: Optional[int] = None,
        period: Optional[int] = None
    ):
        """
        Inizializza il rate limiter.

        Args:
            max_calls: Numero massimo di chiamate (default da Config).
            period: Periodo in secondi (default da Config).
        """
        self.max_calls = max_calls or Config.RATE_LIMIT_CALLS
        self.period = period or Config.RATE_LIMIT_PERIOD
        self._calls: list[float] = []
        self._lock = Lock()

    def acquire(self) -> None:
        """
        Acquisisce il permesso per una chiamata.

        Blocca l'esecuzione se il limite è stato raggiunto,
        attendendo fino a quando una chiamata può essere effettuata.

        Example:
            >>> limiter = RateLimiter()
            >>> limiter.acquire()
            >>> response = requests.get(url)
        """
        with self._lock:
            now = time.time()

            # Rimuovi chiamate fuori dal periodo
            self._calls = [
                call_time for call_time in self._calls
                if now - call_time < self.period
            ]

            # Aspetta se necessario
            if len(self._calls) >= self.max_calls:
                sleep_time = self._calls[0] + self.period - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self._calls = self._calls[1:]

            self._calls.append(time.time())

    def remaining(self) -> int:
        """
        Restituisce il numero di chiamate rimanenti.

        Returns:
            int: Numero di chiamate ancora disponibili nel periodo.
        """
        with self._lock:
            now = time.time()
            valid_calls = [
                call_time for call_time in self._calls
                if now - call_time < self.period
            ]
            return max(0, self.max_calls - len(valid_calls))


def retry_on_error(
    max_retries: int = Config.MAX_RETRIES,
    delay: float = Config.RETRY_DELAY,
    exceptions: tuple = (Exception,)
) -> Callable[[F], F]:
    """
    Decorator per ritentare una funzione in caso di errore.

    Riprova l'esecuzione della funzione decorata un numero specificato
    di volte con un delay esponenziale tra i tentativi.

    Args:
        max_retries: Numero massimo di tentativi.
        delay: Delay iniziale in secondi tra i tentativi.
        exceptions: Tuple di eccezioni da catturare.

    Returns:
        Callable: Funzione decorata con logica di retry.

    Example:
        >>> @retry_on_error(max_retries=3, delay=1.0)
        ... def fetch_data():
        ...     return requests.get(url)
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger("cerca_dai_testi")
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        logger.warning(
                            f"Tentativo {attempt + 1}/{max_retries} fallito: {e}. "
                            f"Riprovo tra {wait_time:.1f}s"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Tutti i {max_retries} tentativi falliti: {e}"
                        )

            raise last_exception  # type: ignore

        return wrapper  # type: ignore

    return decorator


def truncate_text(text: str, max_length: int = 200) -> str:
    """
    Tronca un testo alla lunghezza massima specificata.

    Aggiunge "..." se il testo viene troncato, cercando di
    tagliare alla fine di una parola.

    Args:
        text: Testo da troncare.
        max_length: Lunghezza massima (default 200).

    Returns:
        str: Testo troncato con "..." se necessario.

    Example:
        >>> truncate_text("Questo è un testo lungo", 15)
        'Questo è un...'
    """
    if len(text) <= max_length:
        return text

    truncated = text[:max_length]
    last_space = truncated.rfind(" ")

    if last_space > max_length * 0.7:
        truncated = truncated[:last_space]

    return truncated.rstrip() + "..."


def clean_lyrics(text: str) -> str:
    """
    Pulisce il testo dei lyrics rimuovendo elementi non necessari.

    Rimuove annotazioni, indicazioni di strofa/ritornello,
    e normalizza gli spazi.

    Args:
        text: Testo grezzo dei lyrics.

    Returns:
        str: Testo pulito e normalizzato.

    Example:
        >>> clean_lyrics("[Verse 1]\\nHello world\\n\\n[Chorus]\\nLa la la")
        'Hello world La la la'
    """
    import re

    # Rimuovi annotazioni tra parentesi quadre
    text = re.sub(r"\[.*?\]", "", text)

    # Rimuovi annotazioni tra parentesi tonde (es. "(x2)", "(2x)", "(x3)")
    text = re.sub(r"\(x?\d+x?\)", "", text)

    # Normalizza newlines e spazi multipli
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def format_duration(seconds: float) -> str:
    """
    Formatta una durata in secondi in formato leggibile.

    Args:
        seconds: Durata in secondi.

    Returns:
        str: Durata formattata (es. "2m 30s").

    Example:
        >>> format_duration(150.5)
        '2m 30s'
    """
    minutes, secs = divmod(int(seconds), 60)
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"

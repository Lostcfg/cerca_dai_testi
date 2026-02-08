# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Cerca Dai Testi** - A Python CLI tool that finds songs with lyrics semantically related to user-provided text or topics. Uses Genius API for lyrics retrieval and sentence-transformers for semantic matching.

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the CLI
python main.py --text "your search text"
python main.py --file input.txt --limit 10 --verbose

# Run tests
pytest tests/ -v
pytest tests/test_semantic_matcher.py -v  # Single test file

# Type checking
mypy *.py

# Linting
ruff check .
```

## Architecture

```
main.py                 # CLI entry point, orchestrates search flow
├── lyrics_fetcher.py   # Genius API client (search, lyrics scraping)
├── semantic_matcher.py # NLP engine (sentence-transformers embeddings)
├── utils.py            # Shared utilities (Cache, RateLimiter, logging)
└── config.py           # Configuration from environment variables
```

**Data Flow:**
1. `main.py` parses CLI args, reads input
2. `SemanticMatcher.extract_key_phrases()` extracts search terms from long texts
3. `LyricsFetcher.get_songs_with_lyrics()` searches Genius and scrapes lyrics
4. `SemanticMatcher.find_similar_songs()` computes cosine similarity between embeddings
5. Results ranked and displayed/saved

## Key Classes

- `Song` (dataclass): Represents a song with metadata and lyrics
- `MatchResult` (dataclass): Contains song, similarity score, relevant excerpt
- `LyricsFetcher`: Genius API wrapper with caching and rate limiting
- `SemanticMatcher`: Computes semantic similarity using sentence-transformers
- `Cache`: JSON-based disk cache with expiration
- `RateLimiter`: Sliding window rate limiter

## Configuration

Requires `GENIUS_API_TOKEN` in `.env` file. See `esempio.env` for all options.

## Code Style

- Type hints on all public functions
- Google-style docstrings
- Logging via `logging.getLogger("cerca_dai_testi")`
- Errors should be logged then raised/returned, not silently swallowed

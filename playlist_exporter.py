"""
Modulo per l'export di playlist in vari formati.

Supporta:
- JSON (strutturato)
- M3U/M3U8 (compatibile con player)
- CSV (per spreadsheet)
- HTML (pagina web standalone)
- TXT (testo semplice)
- Markdown (per documentazione)
- XSPF (XML Shareable Playlist Format)
"""

import csv
import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from enum import Enum

from playlist_generator import Playlist, PlaylistTrack


class ExportFormat(Enum):
    """Formati di export supportati."""
    JSON = "json"
    M3U = "m3u"
    M3U8 = "m3u8"
    CSV = "csv"
    HTML = "html"
    TXT = "txt"
    MARKDOWN = "md"
    XSPF = "xspf"


@dataclass
class ExportOptions:
    """
    Opzioni per l'export.

    Attributes:
        include_scores: Include gli score di rilevanza.
        include_urls: Include gli URL (YouTube/Spotify).
        include_lyrics: Include estratti dei testi.
        sort_by: Campo per ordinamento (score, title, artist).
        ascending: Ordine crescente.
    """
    include_scores: bool = True
    include_urls: bool = True
    include_lyrics: bool = False
    sort_by: str = "score"
    ascending: bool = False


class PlaylistExporter:
    """
    Esportatore di playlist in vari formati.

    Example:
        >>> exporter = PlaylistExporter()
        >>> exporter.export(playlist, Path("my_playlist.json"), ExportFormat.JSON)
        >>> exporter.export(playlist, Path("my_playlist.m3u"), ExportFormat.M3U)
    """

    def __init__(self):
        """Inizializza l'esportatore."""
        self.logger = logging.getLogger("cerca_dai_testi.exporter")

    def export(
        self,
        playlist: Playlist,
        path: Path,
        format: ExportFormat,
        options: ExportOptions = None
    ) -> Path:
        """
        Esporta la playlist nel formato specificato.

        Args:
            playlist: Playlist da esportare.
            path: Percorso del file di output.
            format: Formato di export.
            options: Opzioni di export.

        Returns:
            Path: Percorso del file creato.
        """
        options = options or ExportOptions()

        # Ordina tracce se richiesto
        tracks = self._sort_tracks(playlist.tracks, options)

        exporters = {
            ExportFormat.JSON: self._export_json,
            ExportFormat.M3U: self._export_m3u,
            ExportFormat.M3U8: self._export_m3u,
            ExportFormat.CSV: self._export_csv,
            ExportFormat.HTML: self._export_html,
            ExportFormat.TXT: self._export_txt,
            ExportFormat.MARKDOWN: self._export_markdown,
            ExportFormat.XSPF: self._export_xspf,
        }

        exporter = exporters.get(format)
        if not exporter:
            raise ValueError(f"Formato non supportato: {format}")

        # Assicura estensione corretta
        path = self._ensure_extension(path, format)

        exporter(playlist, tracks, path, options)

        self.logger.info(f"Playlist esportata in {path}")
        return path

    def export_all_formats(
        self,
        playlist: Playlist,
        output_dir: Path,
        base_name: str = None
    ) -> List[Path]:
        """
        Esporta la playlist in tutti i formati.

        Args:
            playlist: Playlist da esportare.
            output_dir: Directory di output.
            base_name: Nome base dei file.

        Returns:
            List[Path]: Percorsi dei file creati.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = base_name or self._sanitize_filename(playlist.name)

        paths = []
        for format in ExportFormat:
            path = output_dir / f"{base_name}.{format.value}"
            try:
                self.export(playlist, path, format)
                paths.append(path)
            except Exception as e:
                self.logger.error(f"Errore export {format.value}: {e}")

        return paths

    def _sort_tracks(
        self,
        tracks: List[PlaylistTrack],
        options: ExportOptions
    ) -> List[PlaylistTrack]:
        """Ordina le tracce secondo le opzioni."""
        if options.sort_by == "score":
            key = lambda t: t.relevance_score
        elif options.sort_by == "title":
            key = lambda t: t.title.lower()
        elif options.sort_by == "artist":
            key = lambda t: t.artist.lower()
        else:
            return tracks

        return sorted(tracks, key=key, reverse=not options.ascending)

    def _ensure_extension(self, path: Path, format: ExportFormat) -> Path:
        """Assicura che il file abbia l'estensione corretta."""
        ext = f".{format.value}"
        if not path.suffix.lower() == ext:
            return path.with_suffix(ext)
        return path

    def _sanitize_filename(self, name: str) -> str:
        """Pulisce un nome per usarlo come filename."""
        # Rimuovi caratteri non validi
        invalid = '<>:"/\\|?*'
        for char in invalid:
            name = name.replace(char, '_')
        return name[:100]  # Limita lunghezza

    # --- Esportatori ---

    def _export_json(
        self,
        playlist: Playlist,
        tracks: List[PlaylistTrack],
        path: Path,
        options: ExportOptions
    ) -> None:
        """Esporta in formato JSON."""
        data = {
            "name": playlist.name,
            "description": playlist.description,
            "created_at": playlist.created_at,
            "track_count": len(tracks),
            "tracks": []
        }

        for i, track in enumerate(tracks, 1):
            track_data = {
                "position": i,
                "title": track.title,
                "artist": track.artist
            }

            if options.include_scores:
                track_data["relevance_score"] = track.relevance_score
                track_data["relevance_percent"] = f"{track.relevance_score * 100:.1f}%"

            if options.include_urls:
                if track.youtube_url:
                    track_data["youtube_url"] = track.youtube_url
                if track.spotify_uri:
                    track_data["spotify_uri"] = track.spotify_uri
                    track_data["spotify_url"] = f"https://open.spotify.com/track/{track.spotify_uri.split(':')[-1]}"

            data["tracks"].append(track_data)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _export_m3u(
        self,
        playlist: Playlist,
        tracks: List[PlaylistTrack],
        path: Path,
        options: ExportOptions
    ) -> None:
        """Esporta in formato M3U/M3U8."""
        lines = [
            "#EXTM3U",
            f"#PLAYLIST:{playlist.name}"
        ]

        for track in tracks:
            # Durata sconosciuta = -1
            lines.append(f"#EXTINF:-1,{track.artist} - {track.title}")
            # Usa YouTube URL come riferimento
            if track.youtube_url:
                lines.append(track.youtube_url)
            else:
                lines.append(f"# {track.artist} - {track.title}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _export_csv(
        self,
        playlist: Playlist,
        tracks: List[PlaylistTrack],
        path: Path,
        options: ExportOptions
    ) -> None:
        """Esporta in formato CSV."""
        fieldnames = ["Position", "Title", "Artist"]

        if options.include_scores:
            fieldnames.extend(["Score", "Score %"])

        if options.include_urls:
            fieldnames.extend(["YouTube URL", "Spotify URI"])

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for i, track in enumerate(tracks, 1):
                row = {
                    "Position": i,
                    "Title": track.title,
                    "Artist": track.artist
                }

                if options.include_scores:
                    row["Score"] = f"{track.relevance_score:.4f}"
                    row["Score %"] = f"{track.relevance_score * 100:.1f}%"

                if options.include_urls:
                    row["YouTube URL"] = track.youtube_url or ""
                    row["Spotify URI"] = track.spotify_uri or ""

                writer.writerow(row)

    def _export_html(
        self,
        playlist: Playlist,
        tracks: List[PlaylistTrack],
        path: Path,
        options: ExportOptions
    ) -> None:
        """Esporta in formato HTML standalone."""
        tracks_html = []
        for i, track in enumerate(tracks, 1):
            score_pct = track.relevance_score * 100

            if score_pct >= 70:
                badge_color = "#22c55e"
            elif score_pct >= 50:
                badge_color = "#eab308"
            else:
                badge_color = "#f97316"

            links = []
            if track.youtube_url:
                links.append(f'<a href="{track.youtube_url}" target="_blank" class="btn btn-yt">YouTube</a>')
            if track.spotify_uri:
                spotify_id = track.spotify_uri.split(":")[-1]
                links.append(f'<a href="https://open.spotify.com/track/{spotify_id}" target="_blank" class="btn btn-sp">Spotify</a>')

            tracks_html.append(f"""
            <tr>
                <td>{i}</td>
                <td><strong>{track.title}</strong></td>
                <td>{track.artist}</td>
                <td><span class="score" style="background:{badge_color}">{score_pct:.1f}%</span></td>
                <td class="links">{' '.join(links)}</td>
            </tr>
            """)

        html = f"""<!DOCTYPE html>
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
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(90deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
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
        tr:nth-child(even) {{ background: rgba(255,255,255,0.02); }}
        .score {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
            color: white;
        }}
        .btn {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 13px;
            margin-right: 6px;
            transition: opacity 0.2s;
        }}
        .btn:hover {{ opacity: 0.8; }}
        .btn-yt {{ background: #ef4444; color: white; }}
        .btn-sp {{ background: #22c55e; color: white; }}
        .links {{ white-space: nowrap; }}
        footer {{
            text-align: center;
            margin-top: 2rem;
            color: #64748b;
            font-size: 14px;
        }}
        @media (max-width: 768px) {{
            table, thead, tbody, th, td, tr {{ display: block; }}
            tr {{ margin-bottom: 1rem; border-radius: 8px; padding: 1rem; }}
            td {{ padding: 0.5rem 0; border: none; }}
            td:first-child {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{playlist.name}</h1>
        <p class="meta">
            {playlist.description}<br>
            {len(tracks)} brani &bull; Generata il {playlist.created_at[:10]}
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
            Generata con Cerca Dai Testi &bull; {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </footer>
    </div>
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def _export_txt(
        self,
        playlist: Playlist,
        tracks: List[PlaylistTrack],
        path: Path,
        options: ExportOptions
    ) -> None:
        """Esporta in formato testo semplice."""
        lines = [
            f"{'=' * 60}",
            f"  {playlist.name}",
            f"{'=' * 60}",
            "",
            f"  {playlist.description}" if playlist.description else "",
            f"  {len(tracks)} brani",
            f"  Generata: {playlist.created_at[:10]}",
            "",
            f"{'-' * 60}",
            ""
        ]

        for i, track in enumerate(tracks, 1):
            line = f"{i:3}. {track.artist} - {track.title}"
            if options.include_scores:
                line += f" [{track.relevance_score * 100:.1f}%]"
            lines.append(line)

        lines.extend([
            "",
            f"{'-' * 60}",
            "",
            "Generata con Cerca Dai Testi"
        ])

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _export_markdown(
        self,
        playlist: Playlist,
        tracks: List[PlaylistTrack],
        path: Path,
        options: ExportOptions
    ) -> None:
        """Esporta in formato Markdown."""
        lines = [
            f"# {playlist.name}",
            "",
            f"> {playlist.description}" if playlist.description else "",
            "",
            f"**{len(tracks)} brani** | Generata: {playlist.created_at[:10]}",
            "",
            "---",
            "",
            "| # | Titolo | Artista |" + (" Score |" if options.include_scores else "") + (" Link |" if options.include_urls else ""),
            "|---|--------|---------|" + ("-------|" if options.include_scores else "") + ("------|" if options.include_urls else ""),
        ]

        for i, track in enumerate(tracks, 1):
            row = f"| {i} | **{track.title}** | {track.artist} |"

            if options.include_scores:
                row += f" {track.relevance_score * 100:.1f}% |"

            if options.include_urls:
                links = []
                if track.youtube_url:
                    links.append(f"[YT]({track.youtube_url})")
                if track.spotify_uri:
                    spotify_id = track.spotify_uri.split(":")[-1]
                    links.append(f"[Spotify](https://open.spotify.com/track/{spotify_id})")
                row += f" {' '.join(links)} |"

            lines.append(row)

        lines.extend([
            "",
            "---",
            "",
            "*Generata con [Cerca Dai Testi](https://github.com/Lostcfg/cerca_dai_testi)*"
        ])

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _export_xspf(
        self,
        playlist: Playlist,
        tracks: List[PlaylistTrack],
        path: Path,
        options: ExportOptions
    ) -> None:
        """Esporta in formato XSPF (XML Shareable Playlist Format)."""
        # Namespace XSPF
        ns = "http://xspf.org/ns/0/"

        root = ET.Element("playlist", version="1", xmlns=ns)
        root.set("xmlns", ns)

        # Metadata playlist
        title = ET.SubElement(root, "title")
        title.text = playlist.name

        if playlist.description:
            annotation = ET.SubElement(root, "annotation")
            annotation.text = playlist.description

        creator = ET.SubElement(root, "creator")
        creator.text = "Cerca Dai Testi"

        date = ET.SubElement(root, "date")
        date.text = playlist.created_at

        # Lista tracce
        tracklist = ET.SubElement(root, "trackList")

        for track in tracks:
            track_elem = ET.SubElement(tracklist, "track")

            title_elem = ET.SubElement(track_elem, "title")
            title_elem.text = track.title

            creator_elem = ET.SubElement(track_elem, "creator")
            creator_elem.text = track.artist

            if track.youtube_url and options.include_urls:
                location = ET.SubElement(track_elem, "location")
                location.text = track.youtube_url

            if options.include_scores:
                annotation = ET.SubElement(track_elem, "annotation")
                annotation.text = f"Relevance: {track.relevance_score * 100:.1f}%"

        # Scrivi file
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")

        with open(path, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)

    def get_supported_formats(self) -> List[str]:
        """Restituisce la lista dei formati supportati."""
        return [f.value for f in ExportFormat]

    def get_format_description(self, format: ExportFormat) -> str:
        """Restituisce la descrizione di un formato."""
        descriptions = {
            ExportFormat.JSON: "JSON strutturato - per elaborazione programmatica",
            ExportFormat.M3U: "M3U - compatibile con la maggior parte dei player",
            ExportFormat.M3U8: "M3U8 - M3U con supporto UTF-8",
            ExportFormat.CSV: "CSV - per spreadsheet (Excel, Google Sheets)",
            ExportFormat.HTML: "HTML - pagina web standalone",
            ExportFormat.TXT: "TXT - testo semplice",
            ExportFormat.MARKDOWN: "Markdown - per documentazione",
            ExportFormat.XSPF: "XSPF - formato XML standard per playlist",
        }
        return descriptions.get(format, "Formato sconosciuto")

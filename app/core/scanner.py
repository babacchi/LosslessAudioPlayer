"""High-performance music directory scanner with metadata & artwork extraction."""
import os
import hashlib
from pathlib import Path
from typing import Optional, List, Tuple
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC
from mutagen.mp4 import MP4
import soundfile as sf

from app.core.models import Track
from app.core.database import Database

SUPPORTED_EXTENSIONS = {
    ".flac", ".wav", ".aiff", ".aif", ".alac", ".m4a", ".mp3", ".ogg"
}

COVER_FILENAMES = {
    "cover.jpg", "cover.jpeg", "cover.png",
    "folder.jpg", "folder.jpeg", "folder.png",
    "front.jpg", "front.png", "album.jpg", "album.png"
}


def get_cover_cache_dir() -> Path:
    path = Path.home() / ".jukebox" / "covers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_cover_art(file_path: str, tags: Optional[mutagen.FileType] = None) -> Optional[str]:
    """Extract embedded cover art or look for companion cover image in folder."""
    cache_dir = get_cover_cache_dir()
    file_dir = os.path.dirname(file_path)

    # 1. First check companion cover image in directory
    for cover_name in COVER_FILENAMES:
        candidate = os.path.join(file_dir, cover_name)
        if os.path.exists(candidate):
            return candidate

    # 2. Extract embedded artwork from file tags
    try:
        if tags is None:
            tags = mutagen.File(file_path)

        art_data = None
        art_ext = "jpg"

        if isinstance(tags, FLAC):
            if tags.pictures:
                art_data = tags.pictures[0].data
                if "png" in tags.pictures[0].mime:
                    art_ext = "png"
        elif hasattr(tags, "tags") and tags.tags:
            # Check ID3 APIC frames
            for key in tags.tags.keys():
                if key.startswith("APIC:"):
                    apic: APIC = tags.tags[key]
                    art_data = apic.data
                    if "png" in getattr(apic, "mime", ""):
                        art_ext = "png"
                    break
        elif isinstance(tags, MP4):
            covs = tags.tags.get("covr", [])
            if covs:
                art_data = bytes(covs[0])

        if art_data:
            # Hash by album or file directory to avoid duplicate storage
            album_name = str(tags.get("album", [""])[0]) if hasattr(tags, "get") else ""
            artist_name = str(tags.get("artist", [""])[0]) if hasattr(tags, "get") else ""
            h = hashlib.sha1((file_dir + album_name + artist_name).encode("utf-8")).hexdigest()
            cover_file = cache_dir / f"{h}.{art_ext}"

            if not cover_file.exists():
                with open(cover_file, "wb") as f:
                    f.write(art_data)
            return str(cover_file)
    except Exception:
        pass

    return None


def parse_audio_file(file_path: str) -> Optional[Tuple[Track, Optional[str]]]:
    """Extract Track model and cover art path from audio file."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return None

    try:
        # Technical specs via soundfile
        try:
            info = sf.info(file_path)
            duration = float(info.duration)
            sample_rate = int(info.samplerate)
            channels = int(info.channels)
            file_format = info.format or ext[1:].upper()

            # Determine bit depth
            subtype = info.subtype or ""
            if "24" in subtype or "PCM_24" in subtype:
                bit_depth = 24
            elif "32" in subtype or "FLOAT" in subtype or "PCM_32" in subtype:
                bit_depth = 32
            elif "16" in subtype or "PCM_16" in subtype:
                bit_depth = 16
            else:
                bit_depth = 16
        except Exception:
            # Fallback if soundfile doesn't support the format directly
            duration = 0.0
            sample_rate = 44100
            channels = 2
            bit_depth = 16
            file_format = ext[1:].upper()

        # Metadata tags via mutagen
        tags = mutagen.File(file_path)

        # Accurate audio duration via mutagen (excludes embedded artwork / ID3 padding)
        if tags is not None and hasattr(tags, "info") and hasattr(tags.info, "length") and tags.info.length > 0:
            duration = float(tags.info.length)

        title = os.path.splitext(os.path.basename(file_path))[0]
        artist = "Unknown Artist"
        album = "Unknown Album"
        album_artist = ""
        composer = ""
        track_num = 1
        disc_num = 1
        year = None
        genre = ""

        if tags is not None:
            # Robust tag value extractor supporting lists, strings, and mutagen text objects
            def get_tag_val(candidate_keys):
                for k in candidate_keys:
                    if k in tags:
                        v = tags[k]
                        if hasattr(v, "text") and v.text:
                            return str(v.text[0]).strip()
                        if isinstance(v, (list, tuple)) and v:
                            return str(v[0]).strip()
                        return str(v).strip()

                all_items = []
                if hasattr(tags, "items"):
                    all_items = list(tags.items())
                elif hasattr(tags, "tags") and hasattr(tags.tags, "items"):
                    all_items = list(tags.tags.items())

                for tk, tv in all_items:
                    tk_str = str(tk).lower()
                    for ck in candidate_keys:
                        ck_lower = ck.lower()
                        if tk_str == ck_lower or tk_str.startswith(ck_lower + ":") or tk_str.endswith(":" + ck_lower):
                            if hasattr(tv, "text") and tv.text:
                                return str(tv.text[0]).strip()
                            if isinstance(tv, (list, tuple)) and tv:
                                return str(tv[0]).strip()
                            return str(tv).strip()
                return None

            t_val = get_tag_val(["title", "tit2", "\xa9nam"])
            if t_val:
                title = t_val

            a_val = get_tag_val(["artist", "tpe1", "\xa9art"])
            if a_val:
                artist = a_val

            al_val = get_tag_val(["album", "talb", "\xa9alb"])
            if al_val:
                album = al_val

            # Composer extraction
            c_val = get_tag_val(["composer", "tcom", "\xa9wrt"])
            if c_val:
                composer = c_val

            # Compilation check
            comp_val = get_tag_val(["compilation", "tcmp", "cpil"])
            is_compilation = False
            if comp_val in ("1", "true", "True", True, 1):
                is_compilation = True

            # Album Artist: takes absolute highest priority when present
            aa_val = get_tag_val([
                "albumartist", "album artist", "album_artist",
                "tpe2", "aart", "band", "ensemble"
            ])
            if aa_val and aa_val.strip():
                album_artist = aa_val.strip()
            elif is_compilation:
                album_artist = "Various Artists"
            else:
                album_artist = ""

            # Track number
            tr_val = get_tag_val(["tracknumber", "trck", "trkn"])
            if tr_val:
                try:
                    num_str = str(tr_val).split("/")[0]
                    track_num = int(num_str)
                except ValueError:
                    track_num = 1

            # Year / Date
            date_val = get_tag_val(["date", "tdrc", "\xa9day", "year"])
            if date_val:
                try:
                    year = int(str(date_val)[:4])
                except ValueError:
                    year = None

            # Genre
            g_val = get_tag_val(["genre", "tcon", "\xa9gen"])
            if g_val:
                genre = g_val

            if duration <= 0 and hasattr(tags.info, "length"):
                duration = float(tags.info.length)
            if sample_rate == 44100 and hasattr(tags.info, "sample_rate"):
                sample_rate = int(tags.info.sample_rate)
            if hasattr(tags.info, "bits_per_sample") and tags.info.bits_per_sample:
                bit_depth = int(tags.info.bits_per_sample)

        file_size = os.path.getsize(file_path)
        cover_path = extract_cover_art(file_path, tags)

        track = Track(
            file_path=os.path.abspath(file_path),
            title=title,
            artist=artist,
            album=album,
            album_artist=album_artist,
            composer=composer,
            track_number=track_num,
            disc_number=disc_num,
            year=year,
            genre=genre,
            duration=duration,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            channels=channels,
            format=file_format,
            file_size=file_size
        )
        return track, cover_path

    except Exception:
        return None


class ScannerSignals(QObject):
    progress = Signal(int, int, str)  # (current_index, total_files, current_file_path)
    finished = Signal(int)  # (total_tracks_added)


class LibraryScannerTask(QRunnable):
    def __init__(self, db: Database, folders: List[str]):
        super().__init__()
        self.db = db
        self.folders = folders
        self.signals = ScannerSignals()

    def run(self):
        all_files = []
        for folder in self.folders:
            if not os.path.exists(folder):
                continue
            for root, _, files in os.walk(folder):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        all_files.append(os.path.join(root, f))

        total = len(all_files)
        added_count = 0

        for idx, file_path in enumerate(all_files):
            self.signals.progress.emit(idx + 1, total, os.path.basename(file_path))
            parsed = parse_audio_file(file_path)
            if parsed:
                track, cover_path = parsed
                album_id = self.db.get_or_create_album_for_track(track, cover_path)
                track.album_id = album_id
                self.db.insert_or_update_track(track)
                if cover_path:
                    self.db.update_album_cover(album_id, cover_path)
                added_count += 1

        # Re-aggregate to ensure master album artist priority is applied across the newly scanned library
        self.db.regroup_albums()
        self.signals.finished.emit(added_count)

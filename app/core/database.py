"""SQLite database layer for library persistence and settings."""
import sqlite3
import os
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from app.core.models import Track, Album, Artist


def get_default_db_path() -> Path:
    home_dir = Path.home() / ".jukebox"
    home_dir.mkdir(parents=True, exist_ok=True)
    return home_dir / "library.db"


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_default_db_path()
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Folders monitored
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_scanned TIMESTAMP
                );
            """)

            # Albums table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS albums (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    year INTEGER,
                    genre TEXT,
                    cover_path TEXT,
                    track_count INTEGER DEFAULT 0,
                    total_duration REAL DEFAULT 0.0,
                    is_hires BOOLEAN DEFAULT 0,
                    sample_rate INTEGER DEFAULT 44100,
                    bit_depth INTEGER DEFAULT 16,
                    format TEXT DEFAULT 'FLAC',
                    UNIQUE(title, artist)
                );
            """)

            # Tracks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    album_id INTEGER,
                    file_path TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    album TEXT,
                    album_artist TEXT,
                    composer TEXT,
                    track_number INTEGER DEFAULT 1,
                    disc_number INTEGER DEFAULT 1,
                    year INTEGER,
                    genre TEXT,
                    duration REAL DEFAULT 0.0,
                    sample_rate INTEGER DEFAULT 44100,
                    bit_depth INTEGER DEFAULT 16,
                    channels INTEGER DEFAULT 2,
                    format TEXT DEFAULT 'FLAC',
                    bitrate INTEGER,
                    file_size INTEGER DEFAULT 0,
                    FOREIGN KEY (album_id) REFERENCES albums (id) ON DELETE SET NULL
                );
            """)

            try:
                cursor.execute("ALTER TABLE tracks ADD COLUMN composer TEXT;")
            except Exception:
                pass

            # Settings key-value store
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)

            # Indices for quick search and sorting
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracks_album_id ON tracks(album_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_albums_title ON albums(title);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_albums_artist ON albums(artist);")
            conn.commit()

    def is_group_by_album_artist(self) -> bool:
        return self.get_setting("group_by_album_artist", "1") == "1"

    def set_group_by_album_artist(self, enabled: bool):
        self.set_setting("group_by_album_artist", "1" if enabled else "0")
        self.regroup_albums()

    def get_or_create_album(self, title: str, artist: str, cover_path: Optional[str] = None) -> int:
        clean_title = (title or "Unknown Album").strip()
        clean_artist = (artist or "Unknown Artist").strip()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cover_path FROM albums WHERE title = ? AND artist = ?", (clean_title, clean_artist))
            row = cursor.fetchone()
            if row:
                album_id = row["id"]
                if cover_path and not row["cover_path"]:
                    cursor.execute("UPDATE albums SET cover_path = ? WHERE id = ?", (cover_path, album_id))
                    conn.commit()
                return album_id

            cursor.execute("""
                INSERT INTO albums (title, artist, cover_path)
                VALUES (?, ?, ?)
            """, (clean_title, clean_artist, cover_path))
            conn.commit()
            return cursor.lastrowid

    def get_or_create_album_for_track(self, track: Track, cover_path: Optional[str] = None) -> int:
        clean_title = (track.album or "Unknown Album").strip()
        if self.is_group_by_album_artist():
            # 1. If explicit Album Artist is present, it takes absolute highest priority
            if track.album_artist and track.album_artist.strip():
                eff_artist = track.album_artist.strip()
                return self.get_or_create_album(clean_title, eff_artist, cover_path)

            # 2. Check if an album with this title already exists
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, artist, cover_path FROM albums WHERE title = ? LIMIT 1", (clean_title,))
                row = cursor.fetchone()
                if row:
                    album_id = row["id"]
                    existing_artist = row["artist"]
                    track_artist = (track.artist or "Unknown Artist").strip()
                    if cover_path and not row["cover_path"]:
                        cursor.execute("UPDATE albums SET cover_path = ? WHERE id = ?", (cover_path, album_id))
                    if existing_artist != track_artist and existing_artist != "Various Artists":
                        cursor.execute("UPDATE albums SET artist = 'Various Artists' WHERE id = ?", (album_id,))
                    conn.commit()
                    return album_id

            # 3. New album with track's artist
            eff_artist = (track.artist or "Unknown Artist").strip()
            return self.get_or_create_album(clean_title, eff_artist, cover_path)
        else:
            eff_artist = (track.artist or "Unknown Artist").strip()
            return self.get_or_create_album(clean_title, eff_artist, cover_path)

    def regroup_albums(self):
        """Re-aggregate existing tracks into albums according to group_by_album_artist setting instantly."""
        is_group_by_aa = self.is_group_by_album_artist()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, album, artist, album_artist, file_path FROM tracks")
            track_rows = cursor.fetchall()

            if not track_rows:
                return

            cursor.execute("UPDATE tracks SET album_id = NULL")
            cursor.execute("DELETE FROM albums")

            # When Album Artist / Compilation grouping is ON:
            # Map each album title to its master artist
            album_to_master_artist = {}
            if is_group_by_aa:
                album_tracks_map = {}
                for tr in track_rows:
                    alb_title = (tr["album"] or "Unknown Album").strip()
                    if alb_title not in album_tracks_map:
                        album_tracks_map[alb_title] = []
                    album_tracks_map[alb_title].append(tr)

                for alb_title, tr_list in album_tracks_map.items():
                    # 1. Explicit album_artist on any track wins
                    explicit_aa = next((t["album_artist"].strip() for t in tr_list if t["album_artist"] and t["album_artist"].strip()), None)
                    if explicit_aa:
                        album_to_master_artist[alb_title] = explicit_aa
                    else:
                        # 2. Check distinct track artists
                        distinct_artists = list(dict.fromkeys(t["artist"].strip() for t in tr_list if t["artist"]))
                        if len(distinct_artists) == 1:
                            album_to_master_artist[alb_title] = distinct_artists[0]
                        else:
                            # Soundtrack / compilation with multiple composers or performers
                            album_to_master_artist[alb_title] = "Various Artists"

            album_cache = {}  # (title, artist) -> album_id
            for tr in track_rows:
                title = (tr["album"] or "Unknown Album").strip()
                if is_group_by_aa:
                    eff_artist = album_to_master_artist.get(title, "Various Artists")
                else:
                    eff_artist = (tr["artist"] or "Unknown Artist").strip()

                key = (title, eff_artist)
                if key not in album_cache:
                    cursor.execute("INSERT INTO albums (title, artist) VALUES (?, ?)", (title, eff_artist))
                    album_cache[key] = cursor.lastrowid

                alb_id = album_cache[key]
                cursor.execute("UPDATE tracks SET album_id = ? WHERE id = ?", (alb_id, tr["id"]))

            conn.commit()

        # Update stats and artwork for reconstructed albums
        for alb_id in album_cache.values():
            self.update_album_metadata(alb_id)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT file_path FROM tracks WHERE album_id = ? LIMIT 1", (alb_id,))
                sample_tr = cursor.fetchone()
                if sample_tr:
                    from app.core.scanner import extract_cover_art
                    cov = extract_cover_art(sample_tr["file_path"])
                    if cov:
                        cursor.execute("UPDATE albums SET cover_path = ? WHERE id = ?", (cov, alb_id))
                        conn.commit()

    def insert_or_update_track(self, track: Track) -> int:
        album_id = self.get_or_create_album_for_track(track)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tracks (
                    album_id, file_path, title, artist, album, album_artist,
                    composer, track_number, disc_number, year, genre, duration,
                    sample_rate, bit_depth, channels, format, bitrate, file_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    album_id = excluded.album_id,
                    title = excluded.title,
                    artist = excluded.artist,
                    album = excluded.album,
                    album_artist = excluded.album_artist,
                    composer = excluded.composer,
                    track_number = excluded.track_number,
                    disc_number = excluded.disc_number,
                    year = excluded.year,
                    genre = excluded.genre,
                    duration = excluded.duration,
                    sample_rate = excluded.sample_rate,
                    bit_depth = excluded.bit_depth,
                    channels = excluded.channels,
                    format = excluded.format,
                    bitrate = excluded.bitrate,
                    file_size = excluded.file_size
            """, (
                album_id, track.file_path, track.title, track.artist, track.album,
                track.album_artist, track.composer, track.track_number, track.disc_number,
                track.year, track.genre, track.duration, track.sample_rate,
                track.bit_depth, track.channels, track.format, track.bitrate, track.file_size
            ))
            track_id = cursor.lastrowid
            conn.commit()

        self.update_album_metadata(album_id)
        return track_id

    def update_album_metadata(self, album_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as cnt,
                    SUM(duration) as total_dur,
                    MAX(sample_rate) as max_sr,
                    MAX(bit_depth) as max_bd,
                    MIN(year) as min_yr,
                    genre,
                    format
                FROM tracks WHERE album_id = ?
            """, (album_id,))
            row = cursor.fetchone()
            if row and row["cnt"] > 0:
                is_hires = (row["max_sr"] or 0) >= 88200 or (row["max_bd"] or 0) >= 24
                cursor.execute("""
                    UPDATE albums SET
                        track_count = ?,
                        total_duration = ?,
                        sample_rate = ?,
                        bit_depth = ?,
                        year = ?,
                        genre = COALESCE(genre, ?),
                        format = COALESCE(?, format),
                        is_hires = ?
                    WHERE id = ?
                """, (
                    row["cnt"],
                    row["total_dur"] or 0.0,
                    row["max_sr"] or 44100,
                    row["max_bd"] or 16,
                    row["min_yr"],
                    row["genre"] or "",
                    row["format"] or "FLAC",
                    1 if is_hires else 0,
                    album_id
                ))
                conn.commit()

    def update_album_cover(self, album_id: int, cover_path: str):
        with self.get_connection() as conn:
            conn.execute("UPDATE albums SET cover_path = ? WHERE id = ?", (cover_path, album_id))
            conn.commit()

    def get_albums(self, search: str = "", sort_by: str = "title") -> List[Album]:
        order_clause = "title COLLATE NOCASE ASC"
        if sort_by == "artist":
            order_clause = "artist COLLATE NOCASE ASC, title COLLATE NOCASE ASC"
        elif sort_by == "year":
            order_clause = "year DESC, title COLLATE NOCASE ASC"
        elif sort_by == "hires":
            order_clause = "is_hires DESC, title COLLATE NOCASE ASC"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if search.strip():
                query = f"%{search.strip()}%"
                cursor.execute(f"""
                    SELECT * FROM albums
                    WHERE title LIKE ? OR artist LIKE ? OR genre LIKE ?
                    ORDER BY {order_clause}
                """, (query, query, query))
            else:
                cursor.execute(f"SELECT * FROM albums ORDER BY {order_clause}")

            rows = cursor.fetchall()
            albums = []
            for r in rows:
                albums.append(Album(
                    id=r["id"],
                    title=r["title"],
                    artist=r["artist"],
                    year=r["year"],
                    genre=r["genre"] or "",
                    cover_path=r["cover_path"],
                    track_count=r["track_count"],
                    total_duration=r["total_duration"],
                    is_hires=bool(r["is_hires"]),
                    sample_rate=r["sample_rate"],
                    bit_depth=r["bit_depth"],
                    format=r["format"] or "FLAC"
                ))
            return albums

    def get_album(self, album_id: int) -> Optional[Album]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM albums WHERE id = ?", (album_id,))
            r = cursor.fetchone()
            if not r:
                return None
            album = Album(
                id=r["id"],
                title=r["title"],
                artist=r["artist"],
                year=r["year"],
                genre=r["genre"] or "",
                cover_path=r["cover_path"],
                track_count=r["track_count"],
                total_duration=r["total_duration"],
                is_hires=bool(r["is_hires"]),
                sample_rate=r["sample_rate"],
                bit_depth=r["bit_depth"],
                format=r["format"] or "FLAC"
            )
            album.tracks = self.get_tracks_for_album(album_id)
            return album

    def get_tracks_for_album(self, album_id: int) -> List[Track]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tracks.*, albums.cover_path FROM tracks
                LEFT JOIN albums ON tracks.album_id = albums.id
                WHERE tracks.album_id = ?
                ORDER BY tracks.disc_number ASC, tracks.track_number ASC, tracks.title ASC
            """, (album_id,))
            return [self._row_to_track(r) for r in cursor.fetchall()]

    def get_artists(self, search: str = "", hires_only: bool = False) -> List[Artist]:
        """Fetch all distinct artists with aggregated stats and representative cover art."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            where_clauses = ["tracks.artist IS NOT NULL", "tracks.artist != ''"]
            params = []

            if search.strip():
                where_clauses.append("tracks.artist LIKE ?")
                params.append(f"%{search.strip()}%")

            where_sql = " AND ".join(where_clauses)
            query = f"""
                SELECT 
                    tracks.artist AS name,
                    COUNT(DISTINCT tracks.album_id) AS album_count,
                    COUNT(tracks.id) AS track_count,
                    SUM(tracks.duration) AS total_duration,
                    MAX(tracks.sample_rate) AS max_sr,
                    MAX(tracks.bit_depth) AS max_bd,
                    (
                        SELECT albums.cover_path FROM tracks AS t2
                        LEFT JOIN albums ON t2.album_id = albums.id
                        WHERE t2.artist = tracks.artist AND albums.cover_path IS NOT NULL AND albums.cover_path != ''
                        ORDER BY albums.is_hires DESC, albums.year DESC
                        LIMIT 1
                    ) AS cover_path
                FROM tracks
                WHERE {where_sql}
                GROUP BY tracks.artist
                ORDER BY tracks.artist COLLATE NOCASE ASC
            """
            cursor.execute(query, params)
            rows = cursor.fetchall()

            artists = []
            for r in rows:
                max_sr = r["max_sr"] or 44100
                max_bd = r["max_bd"] or 16
                is_hires = max_sr >= 88200 or max_bd >= 24
                if hires_only and not is_hires:
                    continue

                artists.append(Artist(
                    name=r["name"],
                    album_count=r["album_count"] or 0,
                    track_count=r["track_count"] or 0,
                    total_duration=r["total_duration"] or 0.0,
                    is_hires=is_hires,
                    sample_rate=max_sr,
                    bit_depth=max_bd,
                    cover_path=r["cover_path"]
                ))
            return artists

    def get_artist(self, name: str) -> Optional[Artist]:
        """Fetch a single artist by exact name, including their albums and tracks."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    tracks.artist AS name,
                    COUNT(DISTINCT tracks.album_id) AS album_count,
                    COUNT(tracks.id) AS track_count,
                    SUM(tracks.duration) AS total_duration,
                    MAX(tracks.sample_rate) AS max_sr,
                    MAX(tracks.bit_depth) AS max_bd,
                    (
                        SELECT albums.cover_path FROM tracks AS t2
                        LEFT JOIN albums ON t2.album_id = albums.id
                        WHERE t2.artist = tracks.artist AND albums.cover_path IS NOT NULL AND albums.cover_path != ''
                        ORDER BY albums.is_hires DESC, albums.year DESC
                        LIMIT 1
                    ) AS cover_path
                FROM tracks
                WHERE tracks.artist = ?
                GROUP BY tracks.artist
            """, (name,))
            r = cursor.fetchone()
            if not r:
                return None

            max_sr = r["max_sr"] or 44100
            max_bd = r["max_bd"] or 16
            artist = Artist(
                name=r["name"],
                album_count=r["album_count"] or 0,
                track_count=r["track_count"] or 0,
                total_duration=r["total_duration"] or 0.0,
                is_hires=(max_sr >= 88200 or max_bd >= 24),
                sample_rate=max_sr,
                bit_depth=max_bd,
                cover_path=r["cover_path"],
                albums=self.get_albums_for_artist(name),
                tracks=self.get_tracks_for_artist(name)
            )
            return artist

    def get_albums_for_artist(self, artist_name: str) -> List[Album]:
        """Fetch all albums where this artist is either the album artist or has tracks."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM albums 
                WHERE albums.artist = ? 
                   OR albums.id IN (SELECT DISTINCT album_id FROM tracks WHERE tracks.artist = ?)
                ORDER BY albums.year DESC, albums.title COLLATE NOCASE ASC
            """, (artist_name, artist_name))
            return [
                Album(
                    id=r["id"],
                    title=r["title"],
                    artist=r["artist"],
                    year=r["year"],
                    genre=r["genre"] or "",
                    cover_path=r["cover_path"],
                    track_count=r["track_count"],
                    total_duration=r["total_duration"],
                    is_hires=bool(r["is_hires"]),
                    sample_rate=r["sample_rate"],
                    bit_depth=r["bit_depth"],
                    format=r["format"] or "FLAC"
                )
                for r in cursor.fetchall()
            ]

    def get_tracks_for_artist(self, artist_name: str) -> List[Track]:
        """Fetch all tracks performed or composed by this artist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tracks.*, albums.cover_path FROM tracks
                LEFT JOIN albums ON tracks.album_id = albums.id
                WHERE tracks.artist = ?
                ORDER BY tracks.album COLLATE NOCASE ASC, tracks.disc_number ASC, tracks.track_number ASC, tracks.title ASC
            """, (artist_name,))
            return [self._row_to_track(r) for r in cursor.fetchall()]

    def get_all_tracks(self, search: str = "") -> List[Track]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if search.strip():
                query = f"%{search.strip()}%"
                cursor.execute("""
                    SELECT tracks.*, albums.cover_path FROM tracks
                    LEFT JOIN albums ON tracks.album_id = albums.id
                    WHERE tracks.title LIKE ? OR tracks.artist LIKE ? OR tracks.album LIKE ?
                    ORDER BY tracks.artist COLLATE NOCASE ASC, tracks.album COLLATE NOCASE ASC, tracks.track_number ASC
                """, (query, query, query))
            else:
                cursor.execute("""
                    SELECT tracks.*, albums.cover_path FROM tracks
                    LEFT JOIN albums ON tracks.album_id = albums.id
                    ORDER BY tracks.artist COLLATE NOCASE ASC, tracks.album COLLATE NOCASE ASC, tracks.track_number ASC
                """)
            return [self._row_to_track(r) for r in cursor.fetchall()]

    def _row_to_track(self, r: sqlite3.Row) -> Track:
        cov = r["cover_path"] if "cover_path" in r.keys() else None
        return Track(
            id=r["id"],
            album_id=r["album_id"],
            file_path=r["file_path"],
            title=r["title"],
            artist=r["artist"] or "Unknown Artist",
            album=r["album"] or "Unknown Album",
            album_artist=r["album_artist"] or "",
            composer=r["composer"] if ("composer" in r.keys() and r["composer"]) else "",
            track_number=r["track_number"] or 1,
            disc_number=r["disc_number"] or 1,
            year=r["year"],
            genre=r["genre"] or "",
            duration=r["duration"] or 0.0,
            sample_rate=r["sample_rate"] or 44100,
            bit_depth=r["bit_depth"] or 16,
            channels=r["channels"] or 2,
            format=r["format"] or "FLAC",
            bitrate=r["bitrate"],
            file_size=r["file_size"] or 0,
            cover_path=cov
        )

    def add_folder(self, folder_path: str):
        norm_path = os.path.abspath(folder_path)
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO folders (path) VALUES (?)
            """, (norm_path,))
            conn.commit()

    def get_folders(self) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT path FROM folders ORDER BY added_at ASC")
            return [r["path"] for r in cursor.fetchall()]

    def remove_folder(self, folder_path: str):
        norm_path = os.path.abspath(folder_path)
        with self.get_connection() as conn:
            conn.execute("DELETE FROM folders WHERE path = ?", (norm_path,))
            # Delete tracks that begin with folder_path
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM tracks WHERE file_path LIKE ?", (f"{norm_path}%",))
            track_ids = [r["id"] for r in cursor.fetchall()]
            if track_ids:
                conn.execute("DELETE FROM tracks WHERE file_path LIKE ?", (f"{norm_path}%",))
                # Delete orphaned albums
                conn.execute("""
                    DELETE FROM albums WHERE id NOT IN (SELECT DISTINCT album_id FROM tracks WHERE album_id IS NOT NULL)
                """)
            conn.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row is not None:
                return row["value"]
            return default

    def set_setting(self, key: str, value: Any):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, str(value)))
            conn.commit()

    def clear_all(self):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM tracks")
            conn.execute("DELETE FROM albums")
            conn.execute("DELETE FROM folders")
            conn.commit()

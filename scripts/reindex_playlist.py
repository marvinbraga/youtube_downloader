#!/usr/bin/env python3
"""Reindex a playlist that was downloaded into a single junk directory.

PROBLEM THIS FIXES
------------------
A playlist audio download went wrong: instead of one Folder + N individual
audio rows (what ``POST /audio/playlist`` produces), the DB ended up with a
single junk audio row whose ``id`` is the *playlist* id, while the N real
``.m4a`` files were dumped, named by TITLE, into
``downloads/audio/<playlist_id>/``.

This script reproduces the SAME end state the correct ``/audio/playlist`` flow
would have produced:

  * one Folder ``name=<playlist_title>``, ``description="Playlist"``
  * one ``ready`` audio row per video, ``id == video_id``, ``folder_id`` set,
    with field-for-field parity with a real individual download
    (see :func:`build_audio_row` for the exact spec)
  * each real file COPIED into the canonical per-video layout
    ``downloads/audio/<video_id>/<sanitized_title>.m4a``

Nothing is re-downloaded. The 19 files already on disk are reused.

HOW THE FILE<->VIDEO MATCH WORKS
--------------------------------
yt-dlp's audio ``outtmpl`` is ``{output_dir}/%(title)s.%(ext)s`` (see
``app/services/downloaders/youtube.py`` ``build_audio_opts``), and the app does
NOT set ``restrictfilenames``. So the on-disk basename of each file is exactly
``sanitize_filename(<video title>, restricted=False) + ".m4a"``.

We re-extract the playlist entries (``id``, ``title``) WITHOUT downloading,
compute the expected sanitized filename for each entry, and match it against
the files on disk. The match must be a perfect bijection (1:1 both directions);
if anything fails to match we ABORT and write nothing -- a partial / fuzzy
reindex is worse than the current broken-but-recoverable state.

RUNNING IT (inside the container; cwd must be /app so ``from app...`` resolves)
------------------------------------------------------------------------------
The application code lives in the image (it is NOT bind-mounted), so copy this
script into the running container first, then exec it. ``./data`` and
``./downloads`` ARE bind-mounted, so the script sees the real DB and files.

    # 1. copy the script into the running container
    docker cp scripts/reindex_playlist.py youtube-downloader:/app/scripts/reindex_playlist.py

    # 2a. DRY-RUN (default): reads only, prints the full plan, writes nothing
    docker exec -w /app youtube-downloader \
        python scripts/reindex_playlist.py --dry-run

    # 2b. APPLY: create folder + 19 rows, COPY files into the new layout
    docker exec -w /app youtube-downloader \
        python scripts/reindex_playlist.py --apply

    # 2c. FINALIZE (only after manual verification of --apply):
    #     delete the junk row + remove the original playlist directory
    docker exec -w /app youtube-downloader \
        python scripts/reindex_playlist.py --finalize

Pass a different playlist with --playlist-id / --playlist-title (the
"CATECISMO ROMANO" values are only defaults for the case this was written for).

SAFETY / CONCURRENCY
--------------------
Run this with the application (uvicorn) STOPPED, or against a quiesced
container. It opens the SAME async SQLite session factory the app uses; SQLite
does not love concurrent writers. The download queue must not be processing the
same playlist while this runs.

MODES
-----
--dry-run   (DEFAULT)  Read-only. Re-extract, sanitize, match, validate the
                       1:1 rule, and print the plan. NOTHING is written.
--apply                Idempotent. Create/reuse the Folder, create the missing
                       audio rows (skips video_ids that already exist), and COPY
                       (never move) each file into the new layout. Leaves the
                       junk row and the original files untouched.
--finalize             Destructive cleanup, run ONLY after verifying --apply.
                       Removes the junk row (id == playlist_id) and deletes the
                       original ``downloads/audio/<playlist_id>/`` directory.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# --- app imports (require cwd=/app) ----------------------------------------
try:
    from yt_dlp.utils import sanitize_filename

    from app.db.database import get_db_context
    from app.db.models import Audio, Folder
    from app.db.repositories import AudioRepository, FolderRepository
    from app.services.configs import AUDIO_DIR
    from app.services.managers import AudioDownloadManager
except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
    sys.stderr.write(
        f"\nERROR: cannot import the application ({exc}).\n"
        "Run this INSIDE the container with cwd=/app, e.g.:\n"
        "  docker exec -w /app youtube-downloader "
        "python scripts/reindex_playlist.py --dry-run\n\n"
    )
    raise SystemExit(2) from exc


DEFAULT_PLAYLIST_ID = "PLZ2pN5pwbV9D4wdhPxp6AGI-2erX7YQLq"
DEFAULT_PLAYLIST_TITLE = "CATECISMO ROMANO"
FOLDER_DESCRIPTION = "Playlist"
AUDIO_EXT = ".m4a"

# AUDIO_DIR == downloads/audio ; AUDIO_DIR.parent == downloads
# Stored ``path``/``directory`` columns are relative to AUDIO_DIR.parent, e.g.
# "audio/<video_id>/<file>.m4a" -- mirrors complete_download() in managers.py.
DOWNLOADS_ROOT = AUDIO_DIR.parent


def log(msg: str = "") -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Plan data structures
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Mapping:
    """One resolved video -> file mapping."""

    video_id: str
    raw_title: str  # exact entry title, stored verbatim in title/name
    watch_url: str  # per-video watch URL, stored in `url`
    sanitized_stem: str  # sanitize_filename(raw_title) -- the disk basename
    source_file: Path  # existing file in the junk playlist directory
    dest_path: Path  # downloads/audio/<video_id>/<sanitized_stem>.m4a
    rel_path: str  # "audio/<video_id>/<sanitized_stem>.m4a"
    rel_dir: str  # "audio/<video_id>"
    filesize: int


@dataclass
class Plan:
    playlist_id: str
    playlist_title: str
    source_dir: Path
    mappings: list[Mapping]


# ---------------------------------------------------------------------------
# Field-parity row builder (matches a real individual download exactly)
# ---------------------------------------------------------------------------
def build_audio_row(m: Mapping, folder_id: str, keywords_json: str) -> Audio:
    """Construct an Audio row identical to what an individual download yields.

    Parity reference: register_audio_for_download() + complete_download()
    in app/services/managers.py. Notably:
      * title/name carry the RAW (unsanitized) title -- only `path` is sanitized
        (verified against real rows: title has ':' while path has full-width
        '：').
      * transcription_status/path are the fresh-download defaults ("none"/""),
        NOT whatever a later transcription would set.
      * storage_backend is hardcoded "local" -- these are on-disk files and we
        deliberately do NOT trigger the S3 upload path even if STORAGE_BACKEND=s3.
    """
    return Audio(
        id=m.video_id,
        title=m.raw_title,
        name=f"{m.raw_title}{AUDIO_EXT}",
        source="youtube",
        external_id=m.video_id,
        youtube_id=m.video_id,
        url=m.watch_url,
        path=m.rel_path,
        directory=m.rel_dir,
        format="m4a",
        filesize=m.filesize,
        storage_backend="local",
        download_status="ready",
        download_progress=100,
        download_error="",
        transcription_status="none",
        transcription_path="",
        folder_id=folder_id,
        keywords=keywords_json,
    )


def _leading_serial(text: str) -> int | None:
    """Return the first integer found in ``text`` (e.g. "Catecismo 001." -> 1).

    Used only to CORROBORATE a single residual pairing: the leading serial of
    the residual entry and residual file must agree. ``int()`` normalizes
    zero-padding so "001" == "19"-style variance is handled.
    """
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


# ---------------------------------------------------------------------------
# Build + validate the plan (pure read; used by every mode)
# ---------------------------------------------------------------------------
async def build_plan(playlist_id: str, playlist_title: str) -> Plan:
    """Re-extract entries, match to disk files, and enforce the 1:1 rule.

    Raises SystemExit(1) with a detailed report if the bijection is broken.
    """
    source_dir = AUDIO_DIR / playlist_id
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

    log(f"Playlist id    : {playlist_id}")
    log(f"Playlist title : {playlist_title}")
    log(f"Playlist URL   : {playlist_url}")
    log(f"Source dir     : {source_dir}")
    log(f"Downloads root : {DOWNLOADS_ROOT}")
    log("")

    if not source_dir.is_dir():
        log(f"ABORT: source directory does not exist: {source_dir}")
        raise SystemExit(1)

    # --- files on disk ------------------------------------------------------
    all_files = sorted(p for p in source_dir.iterdir() if p.is_file())
    m4a_files = [p for p in all_files if p.suffix.lower() == AUDIO_EXT]
    stray = [p for p in all_files if p.suffix.lower() != AUDIO_EXT]
    if stray:
        log("ABORT: unexpected non-.m4a files in source dir (possible incomplete")
        log("       download -- e.g. .part fragments). Resolve manually first:")
        for p in stray:
            log(f"  - {p.name}")
        raise SystemExit(1)

    log(f"Found {len(m4a_files)} .m4a file(s) on disk.")

    # --- entries from yt-dlp (no download) ----------------------------------
    manager = AudioDownloadManager()
    log("Extracting playlist entries (flat, no download)...")
    info = await manager.extract_playlist_info(playlist_url)
    entries = info["entries"]
    log(f"Extracted {len(entries)} entry(ies) from the playlist.")
    log("")

    # --- match entry -> file ------------------------------------------------
    # Index files by their stem so each match is exact and consumed once.
    files_by_stem: dict[str, Path] = {p.stem: p for p in m4a_files}
    if len(files_by_stem) != len(m4a_files):
        log("ABORT: two files share the same stem -- cannot match unambiguously.")
        raise SystemExit(1)

    mappings: list[Mapping] = []
    # (video_id, raw_title, watch_url, expected sanitized stem)
    unmatched_entries: list[tuple[str, str, str, str]] = []
    consumed_stems: set[str] = set()

    for entry in entries:
        video_id = entry["id"]
        raw_title = entry["title"]
        watch_url = entry["url"]
        sanitized_stem = sanitize_filename(raw_title, restricted=False)

        src = files_by_stem.get(sanitized_stem)
        if src is None or sanitized_stem in consumed_stems:
            unmatched_entries.append((video_id, raw_title, watch_url, sanitized_stem))
            continue

        consumed_stems.add(sanitized_stem)
        rel_dir = f"audio/{video_id}"
        rel_path = f"{rel_dir}/{sanitized_stem}{AUDIO_EXT}"
        dest_path = DOWNLOADS_ROOT / rel_path
        mappings.append(
            Mapping(
                video_id=video_id,
                raw_title=raw_title,
                watch_url=watch_url,
                sanitized_stem=sanitized_stem,
                source_file=src,
                dest_path=dest_path,
                rel_path=rel_path,
                rel_dir=rel_dir,
                filesize=src.stat().st_size,
            )
        )

    unmatched_files = sorted(set(files_by_stem) - consumed_stems)

    # --- corroborated single-residual fallback ------------------------------
    # YouTube serves localized titles, so extract_flat can return one entry in a
    # different language than the title the file was named with (observed: entry
    # "Catechism 001..." vs file "Catecismo 001..."). When EXACTLY one entry and
    # one file remain, the pairing is forced -- but "forced" is only SAFE if a
    # video wasn't swapped in/out of the playlist (which would also leave 1+1,
    # but as two unrelated items). We corroborate with the leading serial number:
    # pair only if entry-serial == file-serial. >=2 unmatched on either side stays
    # an abort (genuinely ambiguous -> re-download is the fallback there).
    if len(unmatched_entries) == 1 and len(unmatched_files) == 1:
        e_vid, e_title, e_watch, _e_expected = unmatched_entries[0]
        res_stem = unmatched_files[0]
        res_file = files_by_stem[res_stem]
        e_serial = _leading_serial(e_title)
        f_serial = _leading_serial(res_stem)
        if e_serial is not None and e_serial == f_serial:
            rel_dir = f"audio/{e_vid}"
            rel_path = f"{rel_dir}/{res_stem}{AUDIO_EXT}"
            # Title comes from the FILE STEM (the faithful original-language
            # title), NOT the localized entry title. video_id from the entry.
            # Caveat: if a residual file carried sanitized chars (?:|"/), the
            # stem would store full-width variants -- not the case here.
            mappings.append(
                Mapping(
                    video_id=e_vid,
                    raw_title=res_stem,
                    watch_url=e_watch,
                    sanitized_stem=res_stem,
                    source_file=res_file,
                    dest_path=DOWNLOADS_ROOT / rel_path,
                    rel_path=rel_path,
                    rel_dir=rel_dir,
                    filesize=res_file.stat().st_size,
                )
            )
            consumed_stems.add(res_stem)
            unmatched_entries = []
            unmatched_files = []
            log("")
            log(
                f"FALLBACK: single residual paired by corroborating serial #{e_serial}:"
            )
            log(f"  entry title (localized): {e_title!r}  [video_id={e_vid}]")
            log(f"  file stem  (original)  : {res_stem!r}")
            log("  -> stored title taken from the file stem (faithful original).")

    # --- enforce the bijection ---------------------------------------------
    counts_ok = len(m4a_files) == len(entries)
    bijective = not unmatched_entries and not unmatched_files
    if not (counts_ok and bijective):
        log("=" * 72)
        log("ABORT: file<->entry match is not a clean 1:1 bijection. Writing nothing.")
        log("=" * 72)
        log(f"  files on disk : {len(m4a_files)}")
        log(f"  playlist entries: {len(entries)}")
        log(f"  matched pairs : {len(mappings)}")
        if unmatched_entries:
            log("")
            log(
                f"  UNMATCHED ENTRIES ({len(unmatched_entries)}) "
                "-- no file with the expected sanitized name:"
            )
            for vid, title, _watch, stem in unmatched_entries:
                log(f"    - video_id={vid}")
                log(f"        title         : {title!r}")
                log(f"        expected file : {stem}{AUDIO_EXT}")
        if unmatched_files:
            log("")
            log(
                f"  UNMATCHED FILES ({len(unmatched_files)}) "
                "-- on disk but no entry claims them:"
            )
            for stem in unmatched_files:
                log(f"    - {stem}{AUDIO_EXT}")
        log("")
        log("Likely cause: extract_flat titles differ from the titles the files")
        log("were originally named with (spacing/truncation), or the playlist")
        log("changed. Resolve manually; do NOT force a partial reindex.")
        raise SystemExit(1)

    log(f"OK: clean 1:1 match -- {len(mappings)} entries <-> {len(mappings)} files.")
    return Plan(
        playlist_id=playlist_id,
        playlist_title=playlist_title,
        source_dir=source_dir,
        mappings=mappings,
    )


def print_plan(plan: Plan) -> None:
    log("")
    log("=" * 72)
    log("PLAN")
    log("=" * 72)
    log(
        f"Folder to ensure : name={plan.playlist_title!r} "
        f"description={FOLDER_DESCRIPTION!r}"
    )
    log(f"Audio rows       : {len(plan.mappings)} (one per video, id == video_id)")
    log("")
    log(f"{'#':>2}  {'video_id':<13}  {'size(MB)':>9}  new path")
    log(f"{'--':>2}  {'-' * 13}  {'-' * 9}  {'-' * 40}")
    for i, m in enumerate(plan.mappings, 1):
        log(f"{i:>2}  {m.video_id:<13}  {m.filesize / 1_048_576:>9.1f}  {m.rel_path}")
        log(f"      from: {m.source_file.name}")
    log("")


# ---------------------------------------------------------------------------
# Keyword parity: reuse the real manager method (do NOT reimplement the regex)
# ---------------------------------------------------------------------------
def keywords_json_for(manager: AudioDownloadManager, raw_title: str) -> str:
    return json.dumps(manager._extract_keywords(raw_title))


# ---------------------------------------------------------------------------
# --apply
# ---------------------------------------------------------------------------
async def apply_plan(plan: Plan) -> None:
    manager = AudioDownloadManager()

    # 1) ensure folder (idempotent: reuse one matched by name+description) ----
    async with get_db_context() as session:
        folder_repo = FolderRepository(session)
        existing_folders = await folder_repo.get_all()
        folder = next(
            (
                f
                for f in existing_folders
                if f.name == plan.playlist_title[:255]
                and f.description == FOLDER_DESCRIPTION
            ),
            None,
        )
        if folder is None:
            created = await folder_repo.create(
                Folder(
                    name=plan.playlist_title[:255],
                    description=FOLDER_DESCRIPTION,
                    icon="playlist",
                )
            )
            folder_id = created.id
            log(f"Created folder: {folder_id} ({plan.playlist_title!r})")
        else:
            folder_id = folder.id
            log(f"Reusing existing folder: {folder_id} ({plan.playlist_title!r})")

    # 2) copy files + create rows (idempotent per video_id) -------------------
    created_rows = 0
    skipped_rows = 0
    copied_files = 0
    for m in plan.mappings:
        # copy file into the canonical layout (never move; never overwrite a
        # bigger/existing destination blindly)
        m.dest_path.parent.mkdir(parents=True, exist_ok=True)
        if m.dest_path.exists() and m.dest_path.stat().st_size == m.filesize:
            log(f"  file already in place: {m.rel_path}")
        else:
            import shutil

            shutil.copy2(m.source_file, m.dest_path)
            copied_files += 1
            log(f"  copied -> {m.rel_path}")

        async with get_db_context() as session:
            repo = AudioRepository(session)
            existing = await repo.get_by_id(m.video_id)
            if existing is not None:
                skipped_rows += 1
                log(f"  row already exists, skipping: id={m.video_id}")
                # make sure it points at our folder (parity with playlist flow)
                if existing.folder_id != folder_id:
                    await repo.update_folder(m.video_id, folder_id)
                    log(f"    re-pointed folder_id -> {folder_id}")
                continue
            row = build_audio_row(m, folder_id, keywords_json_for(manager, m.raw_title))
            await repo.create(row)
            created_rows += 1
            log(f"  created row: id={m.video_id} title={m.raw_title!r}")

    log("")
    log("=" * 72)
    log("APPLY COMPLETE")
    log("=" * 72)
    log(f"  folder_id    : {folder_id}")
    log(f"  rows created : {created_rows}")
    log(f"  rows skipped : {skipped_rows} (already existed)")
    log(f"  files copied : {copied_files}")
    log("")
    log("VERIFY (the junk row and original files are still in place):")
    log(
        f"  - API: GET /folders/{folder_id}/items should list "
        f"{len(plan.mappings)} audios, each filesize>0, folder_id set."
    )
    log("  - API: GET /audios/<video_id>/stream/ should play one of the items,")
    log(f"         e.g. /audios/{plan.mappings[0].video_id}/stream/")
    log(
        "  - DB : SELECT count(*) FROM audios WHERE folder_id = "
        f"'{folder_id}'; -> {len(plan.mappings)}"
    )
    log("")
    log("When satisfied, run --finalize to remove the junk row and original dir.")


# ---------------------------------------------------------------------------
# --finalize
# ---------------------------------------------------------------------------
async def finalize(plan: Plan) -> None:
    import shutil

    # 1) delete the junk row (id == playlist_id) -----------------------------
    async with get_db_context() as session:
        repo = AudioRepository(session)
        junk = await repo.get_by_id(plan.playlist_id)
        if junk is None:
            log(f"Junk row id={plan.playlist_id} not found (already removed).")
        else:
            await repo.delete(plan.playlist_id)
            log(f"Deleted junk row: id={plan.playlist_id}")

    # 2) remove the original playlist directory ------------------------------
    if plan.source_dir.is_dir():
        shutil.rmtree(plan.source_dir)
        log(f"Removed original directory: {plan.source_dir}")
    else:
        log(f"Original directory already gone: {plan.source_dir}")

    log("")
    log("FINALIZE COMPLETE.")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
async def run(args: argparse.Namespace) -> None:
    log(f"MODE: {args.mode}")
    log("")

    # build_plan is read-only and validates the 1:1 rule; every mode needs it.
    plan = await build_plan(args.playlist_id, args.playlist_title)
    print_plan(plan)

    if args.mode == "dry-run":
        log("DRY-RUN: validation passed, nothing was written.")
        log("Re-run with --apply to create the folder + rows and copy the files.")
        return

    if args.mode == "apply":
        await apply_plan(plan)
        return

    if args.mode == "finalize":
        log("FINALIZE: this removes the junk row and the original directory.")
        log("It assumes --apply was already run AND manually verified.")
        await finalize(plan)
        return


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reindex a mis-downloaded playlist into Folder + per-video rows.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--playlist-id",
        default=DEFAULT_PLAYLIST_ID,
        help="YouTube playlist id (default: the CATECISMO ROMANO case).",
    )
    parser.add_argument(
        "--playlist-title",
        default=DEFAULT_PLAYLIST_TITLE,
        help="Folder name to create/reuse (default: 'CATECISMO ROMANO').",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="mode",
        action="store_const",
        const="dry-run",
        help="(DEFAULT) read-only: validate and print the plan, write nothing.",
    )
    mode.add_argument(
        "--apply",
        dest="mode",
        action="store_const",
        const="apply",
        help="create folder + rows and COPY files into the new layout.",
    )
    mode.add_argument(
        "--finalize",
        dest="mode",
        action="store_const",
        const="finalize",
        help="remove the junk row and the original directory (after --apply).",
    )
    parser.set_defaults(mode="dry-run")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

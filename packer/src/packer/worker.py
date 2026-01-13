"""Worker primitives: per-chapter processing and per-volume orchestration."""

from __future__ import annotations

import concurrent.futures
import logging
import os
import shutil
import zipfile
from typing import Dict, List, Optional, Tuple

from .core import extract_chapter_number, format_volume_dir

logger = logging.getLogger(__name__)


def process_one(chapter_id: str, src_file: str, cfg) -> Tuple[str, str]:
    """Process a single chapter archive: validate, move and extract it.

    This performs the per-chapter atomic sequence:
    1. verify `ComicInfo.xml` inside the source archive (via `cfg.has_comicinfo`).
    2. ensure the volume directory exists (created by main thread or here if
       missing).
    3. move the archive into the volume directory.
    4. create a `Chapter XXX` (or `Chapter XXX.Y`) subdirectory and extract.

    Args:
        chapter_id: identifier as string, e.g. `'13'` for main chapters or
                    `'13.5'` for extras.
        src_file: path to the source `.cbz` archive (before moving).
        cfg: instance of `Config` providing runtime options (dest, serie,
             dry_run, verbose, force, has_comicinfo helper, etc.).

    Returns:
        Tuple[str, str]: (chapter_id, dest_archive_path) where dest_archive_path
                         points to the archive location inside the volume (or
                         original path in dry-run contexts).

    Raises:
        RuntimeError: on missing `ComicInfo.xml`, bad archives, or unsafe
                      extraction paths. Caller (process_volume) converts these
                      to an exit code and error log.
    """
    logger.debug(f"[worker] start chapter={chapter_id} file={src_file}")

    # Validate comicinfo
    logger.debug(f"[worker] verifying ComicInfo.xml in {src_file}")
    if not cfg.has_comicinfo(src_file):
        raise RuntimeError(f"Missing ComicInfo.xml in {src_file}")

    volume_dir = format_volume_dir(cfg.dest, cfg.serie, cfg.volume)
    if not os.path.exists(volume_dir):
        logger.debug(f"[worker] creating volume dir: {volume_dir}")
        if not cfg.dry_run:
            os.makedirs(volume_dir, exist_ok=True)
        else:
            logger.debug(f"[dry-run] mkdir {volume_dir}")
    else:
        logger.debug(f"[worker] volume dir exists: {volume_dir}")

    # Move archive
    dest_archive = os.path.join(volume_dir, os.path.basename(src_file))
    if cfg.dry_run:
        logger.debug(f"[dry-run] mv {src_file} -> {dest_archive}")
    else:
        logger.debug(f"[worker] moving archive to {dest_archive}")
        shutil.move(src_file, dest_archive)

    # Determine chapter dir name
    if "." in chapter_id:
        base_part, extra_part = chapter_id.split(".", 1)
        chapter_dir_name = f"Chapter {int(base_part):03d}.{extra_part}"
    else:
        chapter_dir_name = f"Chapter {int(chapter_id):03d}"
    chapter_dir = os.path.join(volume_dir, chapter_dir_name)

    if os.path.exists(chapter_dir):
        if cfg.force:
            logger.debug(f"[worker] force-remove existing chapter dir: {chapter_dir}")
            shutil.rmtree(chapter_dir)
            if not cfg.dry_run:
                os.makedirs(chapter_dir, exist_ok=True)
            else:
                logger.debug(f"[dry-run] mkdir {chapter_dir}")
        else:
            # According to rules: warn and skip
            logger.warning(f"chapter dir exists, skipping: {chapter_dir}")
            return chapter_id, dest_archive
    else:
        logger.debug(f"[worker] creating chapter dir: {chapter_dir}")
        if not cfg.dry_run:
            os.makedirs(chapter_dir, exist_ok=True)
        else:
            logger.debug(f"[dry-run] mkdir {chapter_dir}")

    # Safe extraction (prevent path traversal). In dry-run, inspect the original src file but do not extract
    # or depend on the moved `dest_archive` which doesn't exist in dry-run mode.
    try:
        archive_for_inspection = src_file if cfg.dry_run else dest_archive
        with zipfile.ZipFile(archive_for_inspection, "r") as z:
            names = z.namelist()
            for member in names:
                parts = member.split("/")
                if ".." in parts or member.startswith("/") or member.startswith("\\"):
                    raise RuntimeError(f"Unsafe path in archive: {member}")
            if cfg.dry_run:
                logger.debug(
                    f"[dry-run] extract {archive_for_inspection} -> {chapter_dir}"
                )
            else:
                z.extractall(chapter_dir)
                logger.debug(f"[worker] extracted {dest_archive} -> {chapter_dir}")
    except zipfile.BadZipFile:
        raise RuntimeError(f"Bad zip file: {archive_for_inspection}")

    return chapter_id, dest_archive


def process_volume(
    volume: int, chapter_range: List[int], available_files: List[str], cfg
) -> Tuple[int, List[str]]:
    """Process a single volume: map files to chapters then execute tasks.

    This function performs the following steps:
    - build a mapping of available `.cbz` files to chapter numbers and extras
      using `extract_chapter_number` with `cfg` patterns;
    - validate that all requested chapters exist and that mains are unique;
    - prepare tasks (main + extras) and log a planned summary at INFO level;
    - ensure the volume directory exists and execute tasks using a thread
      pool or serially according to `cfg.nb_worker`;
    - remove moved archives from `available_files` and return updated list.

    Args:
        volume: volume number being created.
        chapter_range: list of chapter integers to process for this volume.
        available_files: list of paths to candidate `.cbz` files (mutated by
                         removing moved items when not in dry-run).
        cfg: runtime Config with patterns and runtime flags.

    Returns:
        Tuple[int, List[str]]: (exit_code, remaining_available_files). Exit
        codes:
          0: success
          2: invalid CLI or batch spec
          3: missing chapter
          4: duplicate mains for a chapter
          5: task-specific TODO / not implemented
          6: extraction or processing error

    Notes:
        - The function logs errors and returns a non-zero exit code instead of
          raising to simplify top-level error handling.
    """
    # Build mapping using the provided patterns
    mapping: Dict[int, Dict[str, List[Tuple[Optional[str], str]]]] = {}
    for pth in list(available_files):
        matches = extract_chapter_number(
            pth, chapter_pat=cfg._chapter_pat, extra_pat=cfg._extra_pat
        )
        for base, extra in matches:
            entry = mapping.setdefault(base, {"mains": [], "extras": []})
            if extra is None:
                entry["mains"].append((None, pth))
            else:
                entry["extras"].append((extra, pth))

    # Validate presence & uniqueness for this volume's chapters
    for c in chapter_range:
        entry = mapping.get(c)
        if not entry or (not entry.get("mains") and not entry.get("extras")):
            logger.error(f"missing chapter {c}")
            return 3, available_files
        if len(entry.get("mains", [])) > 1:
            mains = [p for (_, p) in entry["mains"]]
            logger.error(f"multiple archives match chapter {c}: {mains}")
            return 4, available_files

    # Prepare tasks: include main archive for each requested chapter and any extras found
    tasks: List[Tuple[str, str]] = []  # (chapter_id, file)
    for c in chapter_range:
        entry = mapping.get(c, {"mains": [], "extras": []})
        if entry.get("mains"):
            _, main_file = entry["mains"][0]
            tasks.append((str(c), main_file))
        # Sort extras by numeric suffix (e.g., 16.1 before 16.2)
        extras = sorted(entry.get("extras", []), key=lambda pair: int(pair[0]))
        for extra_suffix, extra_file in extras:
            tasks.append((f"{c}.{extra_suffix}", extra_file))

    # Planned tasks are important summary info for the user
    logger.info(f"[info] planned tasks for volume {volume}:")
    for cid, f in tasks:
        logger.info(f"[info]  chapter {cid} -> {f}")

    # Ensure volume dir exists (main thread creates it to avoid races)
    volume_dir = format_volume_dir(cfg.dest, cfg.serie, volume)
    if not os.path.exists(volume_dir):
        logger.debug(f"[info] creating volume dir: {volume_dir}")
        if not cfg.dry_run:
            os.makedirs(volume_dir, exist_ok=True)
        else:
            logger.debug(f"[dry-run] mkdir {volume_dir}")
    else:
        logger.debug(f"[info] volume dir exists: {volume_dir}")

    moved_files: List[str] = []

    # Execute tasks (threaded as before)
    if cfg.nb_worker > 1:
        logger.debug(f"[info] Using ThreadPoolExecutor with {cfg.nb_worker} workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.nb_worker) as ex:
            futures = [ex.submit(process_one, c, f, cfg) for c, f in tasks]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    cid, dest = fut.result()
                    moved_files.append(dest if not cfg.dry_run else f"DRY:{cid}")
                    logger.debug(f"Processed: {(cid, dest)}")
                except Exception as e:
                    logger.error(f"{e}")
                    return 6, available_files
    else:
        for cid, f in tasks:
            logger.debug(f"[info] processing chapter {cid}")
            try:
                cid, dest = process_one(cid, f, cfg)
                moved_files.append(dest if not cfg.dry_run else f"DRY:{cid}")
                logger.debug(f"Processed: {(cid, dest)}")
            except Exception as e:
                logger.error(f"{e}")
                return 6, available_files

    # Remove moved files from available_files (non-dry-run)
    if not cfg.dry_run:
        for dest in moved_files:
            if dest and os.path.exists(dest):
                basename = os.path.basename(dest)
                for orig in list(available_files):
                    if os.path.basename(orig) == basename:
                        available_files.remove(orig)
                        break
    return 0, available_files

"""Worker primitives: per-chapter processing and per-volume orchestration."""

from __future__ import annotations

import concurrent.futures
import logging
import shutil
import zipfile
from pathlib import Path
from typing import List, Optional

from .core import extract_chapter_number, format_chapter_dir, format_volume_dir
from .exit_codes import DUPLICATE_CHAPTER, MISSING_CHAPTER, PROCESSING_ERROR, SUCCESS
from .types_ import ChapterToFilesMapping, ProcessResult, ProcessVolumeResult, Task

logger = logging.getLogger(__name__)


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract *zf* into *dest*, raising ValueError on path-traversal attempts."""
    resolved_dest = str(dest.resolve())
    for member in zf.infolist():
        resolved = str((dest / member.filename).resolve())
        if not (resolved == resolved_dest or resolved.startswith(resolved_dest + "/")):
            raise ValueError(f"Path traversal detected: {member.filename}")
    zf.extractall(dest)


def _ensure_dir(path: Path, dry_run: bool) -> None:
    """Create directory if it doesn't exist."""
    if not path.exists():
        logger.debug(f"[worker] creating dir: {path}")
        if not dry_run:
            path.mkdir(parents=True, exist_ok=True)
        else:
            logger.debug(f"[dry-run] mkdir {path}")
    else:
        logger.debug(f"[worker] dir exists: {path}")


def process_one(chapter_id: str, src_file: str, cfg) -> ProcessResult:
    """Process a single chapter archive: validate, move and extract it."""
    logger.debug(f"[worker] start chapter={chapter_id} file={src_file}")

    src_path = Path(src_file)

    logger.debug(f"[worker] verifying ComicInfo.xml in {src_path}")
    if not cfg.has_comicinfo(str(src_path)):
        raise RuntimeError(f"Missing ComicInfo.xml in {src_path}")

    volume_dir = Path(format_volume_dir(cfg.dest, cfg.serie, cfg.volume))
    _ensure_dir(volume_dir, cfg.dry_run)

    dest_archive = volume_dir / src_path.name
    if cfg.dry_run:
        logger.debug(f"[dry-run] mv {src_path} -> {dest_archive}")
    else:
        logger.debug(f"[worker] moving archive to {dest_archive}")
        shutil.move(str(src_path), str(dest_archive))

    if "." in chapter_id:
        base_part, extra_part = chapter_id.split(".", 1)
        chapter_dir_name = format_chapter_dir(base_part, extra_part)
    else:
        chapter_dir_name = format_chapter_dir(chapter_id, None)
    chapter_dir = volume_dir / chapter_dir_name

    if chapter_dir.exists():
        if cfg.force:
            logger.debug(f"[worker] force-remove existing chapter dir: {chapter_dir}")
            shutil.rmtree(str(chapter_dir))
            _ensure_dir(chapter_dir, cfg.dry_run)
        else:
            logger.warning(f"chapter dir exists, skipping: {chapter_dir}")
            return ProcessResult(chapter_id, str(dest_archive))
    else:
        _ensure_dir(chapter_dir, cfg.dry_run)

    # In dry-run, inspect the original src file — dest_archive doesn't exist yet.
    try:
        archive_for_inspection = src_path if cfg.dry_run else dest_archive
        with zipfile.ZipFile(str(archive_for_inspection), "r") as z:
            if cfg.dry_run:
                logger.debug(
                    f"[dry-run] extract {archive_for_inspection} -> {chapter_dir}"
                )
            else:
                _safe_extract(z, chapter_dir)
                logger.debug(f"[worker] extracted {dest_archive} -> {chapter_dir}")
    except zipfile.BadZipFile:
        raise RuntimeError(f"Bad zip file: {archive_for_inspection}")

    return ProcessResult(chapter_id, str(dest_archive))


def _plan_tasks(
    mapping: ChapterToFilesMapping, chapter_range: List[int]
) -> List[Task]:
    """Build ordered task list from the chapter mapping."""
    tasks: List[Task] = []
    for c in chapter_range:
        entry = mapping.get(c, {"mains": [], "extras": []})
        if entry.get("mains"):
            _, main_file = entry["mains"][0]
            tasks.append(Task(str(c), main_file))
        extras = sorted(
            entry.get("extras", []),
            key=lambda pair: int(pair[0]) if pair[0] is not None else 0,
        )
        for extra_suffix, extra_file in extras:
            tasks.append(Task(f"{c}.{extra_suffix}", extra_file))
    return tasks


def _copy_cover(volume_dir: Path, volume: int, cfg) -> None:
    """Copy the configured cover image into the volume directory."""
    if not cfg.covers:
        return
    for cm in cfg.covers:
        if cm.volume != volume:
            continue
        src = Path(cm.cover_path)
        if not src.exists():
            logger.warning(f"cover not found, skipping: {src}")
            break
        cover_dest = volume_dir / "cover.webp"
        if cfg.dry_run:
            logger.info(f"[DRY RUN] would copy cover {src} → {cover_dest}")
        else:
            shutil.copy2(str(src), str(cover_dest))
            logger.info(f"📷 Copied cover → {cover_dest}")
        break


def _run_tasks(tasks: List[Task], cfg) -> Optional[List[str]]:
    """Execute tasks sequentially or threaded; return moved-file list or None on error."""
    total_tasks = len(tasks)
    dry_prefix = "[DRY RUN] " if cfg.dry_run else ""
    moved_files: List[str] = []

    if cfg.nb_worker > 1:
        logger.debug(f"[info] Using ThreadPoolExecutor with {cfg.nb_worker} workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.nb_worker) as ex:
            futures = {
                ex.submit(process_one, t.chapter_id, t.src, cfg): (idx, t)
                for idx, t in enumerate(tasks, 1)
            }
            for fut in concurrent.futures.as_completed(futures):
                idx, t = futures[fut]
                logger.info(
                    f"{dry_prefix}[{idx}/{total_tasks}] Extracting chapter"
                    f" {t.chapter_id} — {Path(t.src).name}"
                )
                try:
                    result = fut.result()
                    moved_files.append(
                        result.dest_archive
                        if not cfg.dry_run
                        else f"DRY:{result.chapter_id}"
                    )
                    logger.debug(
                        f"Processed: {(result.chapter_id, result.dest_archive)}"
                    )
                except Exception as e:
                    logger.error(f"{e}")
                    return None
    else:
        for idx, t in enumerate(tasks, 1):
            logger.info(
                f"{dry_prefix}[{idx}/{total_tasks}] Extracting chapter"
                f" {t.chapter_id} — {Path(t.src).name}"
            )
            try:
                result = process_one(t.chapter_id, t.src, cfg)
                moved_files.append(
                    result.dest_archive
                    if not cfg.dry_run
                    else f"DRY:{result.chapter_id}"
                )
                logger.debug(f"Processed: {(result.chapter_id, result.dest_archive)}")
            except Exception as e:
                logger.error(f"{e}")
                return None

    return moved_files


def process_volume(
    volume: int, chapter_range: List[int], available_files: List[str], cfg
) -> ProcessVolumeResult:
    """Process a single volume: map files to chapters then execute tasks."""
    mapping: ChapterToFilesMapping = {}
    for pth in list(available_files):
        matches = extract_chapter_number(
            pth, chapter_pat=cfg.chapter_pat, extra_pat=cfg.extra_pat
        )
        for base, extra in matches:
            entry = mapping.setdefault(base, {"mains": [], "extras": []})
            if extra is None:
                entry["mains"].append((None, pth))
            else:
                entry["extras"].append((extra, pth))

    for c in chapter_range:
        ch_entry: Optional[dict[str, list]] = mapping.get(c)
        if not ch_entry or (not ch_entry.get("mains") and not ch_entry.get("extras")):
            logger.error(f"missing chapter {c}")
            return ProcessVolumeResult(MISSING_CHAPTER, available_files)
        if len(ch_entry.get("mains", [])) > 1:
            mains = [p for (_, p) in ch_entry["mains"]]
            logger.error(f"multiple archives match chapter {c}: {mains}")
            return ProcessVolumeResult(DUPLICATE_CHAPTER, available_files)

    tasks = _plan_tasks(mapping, chapter_range)

    logger.info(f"[info] planned tasks for volume {volume}:")
    for t in tasks:
        logger.info(f"[info]  chapter {t.chapter_id} -> {t.src}")

    volume_dir = Path(format_volume_dir(cfg.dest, cfg.serie, volume))
    _ensure_dir(volume_dir, cfg.dry_run)
    _copy_cover(volume_dir, volume, cfg)

    moved_files = _run_tasks(tasks, cfg)
    if moved_files is None:
        return ProcessVolumeResult(PROCESSING_ERROR, available_files)

    if not cfg.dry_run:
        for dest in moved_files:
            if dest and Path(dest).exists():
                basename = Path(dest).name
                for orig in list(available_files):
                    if Path(orig).name == basename:
                        available_files.remove(orig)
                        break

    return ProcessVolumeResult(SUCCESS, available_files)

"""Parallel conversion loop with comprehensive error handling and logging."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of a single volume conversion."""
    volume_path: Path
    output_path: Path | None
    success: bool
    error: str | None = None


class ConversionLogger:
    """Thread-safe logger that collects logs per volume."""

    def __init__(self):
        self._logs: dict[Path, list[tuple[int, str]]] = {}
        self._lock = threading.Lock()

    def log(self, volume: Path, level: int, message: str):
        """Add a log entry for a volume."""
        with self._lock:
            if volume not in self._logs:
                self._logs[volume] = []
            self._logs[volume].append((level, message))

    def get_logs(self, volume: Path) -> list[tuple[int, str]]:
        """Get all logs for a volume."""
        with self._lock:
            return self._logs.get(volume, []).copy()

    def flush_logs(self, volume: Path):
        """Print all buffered logs for a volume."""
        logs = self.get_logs(volume)
        if logs:
            print(f"\n{'='*60}")
            print(f"Logs for: {volume.name}")
            print('='*60)
            for level, msg in logs:
                level_name = logging.getLevelName(level)
                print(f"[{level_name}] {msg}")


def convert_single_volume(
    volume: Path,
    out_path: Path,
    dry_run: bool,
    force_regen: bool,
) -> ConversionResult:
    """Convert a single volume. This runs in a separate process.

    Note: This function must be picklable, so it can't reference
    the main module's convert_volume if that has issues.
    """
    # Import here to avoid issues with multiprocessing
    import logging
    from pathlib import Path

    # Create a local logger for this process
    local_logger = logging.getLogger(f'convertor.worker.{volume.name}')

    try:
        # Check if output exists
        if out_path.exists() and not force_regen:
            local_logger.info(f'Skipping existing: {out_path.name}')
            return ConversionResult(
                volume_path=volume,
                output_path=out_path,
                success=True,
            )

        local_logger.info(f'Converting: {volume.name} -> {out_path.name}')

        if dry_run:
            local_logger.info('DRY RUN - would convert')
            return ConversionResult(
                volume_path=volume,
                output_path=out_path,
                success=True,
            )

        # Import the actual conversion function
        # NOTE: Adjust this import to match your actual module structure
        from .kcc_adapter import  convert_volume

        # Do the actual conversion
        result_path = convert_volume(
            volume,
            out_path,
            dry_run=False,
        )

        local_logger.info(f'✓ Success: {out_path.name}')

        return ConversionResult(
            volume_path=volume,
            output_path=result_path,
            success=True,
        )

    except Exception as e:
        local_logger.error(f'✗ Failed: {str(e)}')
        return ConversionResult(
            volume_path=volume,
            output_path=None,
            success=False,
            error=str(e),
        )


def convert_volumes_parallel(
    volumes: list[Path],
    force_regen: bool = False,
    dry_run: bool = False,
    max_workers: int | None = None,
) -> dict[str, list[Path]]:
    """Convert multiple volumes in parallel.

    Args:
        volumes: List of volume directories to convert
        force_regen: Regenerate even if output exists
        dry_run: Don't actually convert
        max_workers: Max parallel workers (default: min(4, cpu_count))

    Returns:
        Dict with 'success' and 'failed' lists of volume paths
    """
    import os

    # FIX 1: Limit workers to prevent memory saturation
    # KCC is CPU + memory intensive, so we limit workers
    if max_workers is None:
        max_workers = min(4, os.cpu_count() or 1)

    logger.info(f'Starting parallel conversion with {max_workers} workers')
    logger.info(f'Processing {len(volumes)} volumes')

    results = {'success': [], 'failed': []}

    # FIX 2: Use ProcessPoolExecutor for isolation
    # Each KCC process gets its own memory space and temp files
    with ProcessPoolExecutor(max_workers=max_workers) as executor:

        # Submit all jobs
        future_to_volume = {}
        for vol in volumes:
            out_path = vol.with_suffix(vol.suffix + '.kepub.epub')

            future = executor.submit(
                convert_single_volume,
                vol,
                out_path,
                dry_run,
                force_regen,
            )
            future_to_volume[future] = vol

        # FIX 3: Process results as they complete, with progress
        completed = 0
        total = len(volumes)

        for future in as_completed(future_to_volume):
            completed += 1
            vol = future_to_volume[future]

            try:
                result = future.result()

                # Progress indicator
                logger.info(f'[{completed}/{total}] Completed: {vol.name}')

                if result.success:
                    results['success'].append(result.volume_path)
                else:
                    results['failed'].append(result.volume_path)
                    logger.error(f'  Failed: {result.error}')

            except Exception as e:
                # Handle exceptions from the worker process
                logger.error(f'[{completed}/{total}] Worker crashed for {vol.name}: {e}')
                results['failed'].append(vol)

    return results


def print_summary(results: dict[str, list[Path]]):
    """Print a nice summary of conversion results."""
    success_count = len(results['success'])
    failed_count = len(results['failed'])
    total = success_count + failed_count

    print(f"\n{'='*60}")
    print("CONVERSION SUMMARY")
    print('='*60)
    print(f"Total volumes:    {total}")
    print(f"✓ Successful:     {success_count}")
    print(f"✗ Failed:         {failed_count}")

    if results['failed']:
        print(f"\nFailed volumes:")
        for vol in results['failed']:
            print(f"  - {vol.name}")

    print('='*60)

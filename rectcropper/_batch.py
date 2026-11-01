"""Bounded, ordered batch processing with lightweight cross-process results."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import get_context
from numbers import Integral
from pathlib import Path
from typing import Optional, Tuple

from ._core import RectangleImageCrop


@dataclass(frozen=True)
class BatchResult:
    """Paths and coordinates for one input; images stay on disk, not in IPC."""
    input_path: Path
    crop_points: Tuple[tuple, ...]
    output_paths: Tuple[Path, ...]
    error: Optional[str] = None


def _process_file(task):
    index, source, output_root, output_format, options, on_error = task
    path = Path(source)
    try:
        cropper = RectangleImageCrop()
        cropper.open(path)
        cropper.crop(**options)
        # Indexing avoids collisions even for identical stems or repeated inputs.
        directory = Path(output_root) / f'{index:06d}-{path.stem}'
        cropper.save(directory, path.stem, output_format)
        boxes = tuple(cropper.get_crop_points())
        outputs = tuple(directory / f'{path.stem}_{i+1}.{output_format.lower()}'
                        for i in range(len(boxes)))
        return BatchResult(path, boxes, outputs)
    except Exception as exc:
        if on_error == 'raise':
            raise
        return BatchResult(path, (), (), f'{type(exc).__name__}: {exc}')


def crop_images(image_paths, *, output_dir, workers=1, max_pending=None,
                output_format='png', on_error='raise', **options):
    """Yield BatchResult metadata in input order while saving each file's crops.

    The default workers=1 uses no process pool. workers>1 uses spawn processes;
    invoke under an ``if __name__ == '__main__':`` guard in scripts. At most
    max_pending inputs (default 2*workers) are submitted at a time. The iterable
    is consumed lazily; Pillow images and component arrays never cross processes.

    Each input gets an index-stem subdirectory. Reusing output_dir across calls
    may overwrite matching paths. on_error='raise' propagates the first error in
    input order; 'collect' returns an error string in that input's BatchResult.
    Failed inputs may have partial output files. Closing iteration cancels queued
    tasks and waits for running jobs, which may still write files.
    """
    if isinstance(workers, bool) or not isinstance(workers, Integral):
        raise TypeError('workers must be a positive integer')
    if workers < 1:
        raise ValueError('workers must be a positive integer')
    if max_pending is None:
        max_pending = 2 * workers
    if isinstance(max_pending, bool) or not isinstance(max_pending, Integral):
        raise TypeError('max_pending must be a positive integer')
    if max_pending < 1:
        raise ValueError('max_pending must be a positive integer')
    if on_error not in ('raise', 'collect'):
        raise ValueError("on_error must be 'raise' or 'collect'")
    if not isinstance(output_format, str) or not output_format:
        raise ValueError('output_format must be a nonempty string')
    root = str(Path(output_dir).resolve())
    options = dict(options)
    options.setdefault('background_mode', 'border')
    tasks = ((index, str(Path(path).resolve()), root, output_format, options, on_error)
             for index, path in enumerate(image_paths))
    if workers == 1:
        for task in tasks:
            yield _process_file(task)
        return

    executor = ProcessPoolExecutor(max_workers=int(workers), mp_context=get_context('spawn'))
    pending = deque()
    try:
        for _ in range(max_pending):
            task = next(tasks, None)
            if task is None:
                break
            pending.append(executor.submit(_process_file, task))
        while pending:
            yield pending.popleft().result()
            task = next(tasks, None)
            if task is not None:
                pending.append(executor.submit(_process_file, task))
    finally:
        for future in pending:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)

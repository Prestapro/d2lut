"""Orchestrator for the full image-only recovery pipeline.

Runs the complete flow: enqueue -> fetch -> OCR -> stage -> promote
as a single callable, suitable for integration into the refresh daemon
or standalone CLI usage.

Requirements: 1.1, 2.1, 3.1, 12.1, 12.4, 12.5
"""

from __future__ import annotations

import logging
import subprocess
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Repo root (two levels up from this file: src/d2lut/overlay -> repo)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@dataclass(slots=True)
class ImageRecoveryResult:
    """Counts from each pipeline step."""

    enqueued: int = 0
    fetched: int = 0
    ocr_parsed: int = 0
    staged: int = 0
    promoted: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Step runner
# ---------------------------------------------------------------------------

def _run_script(
    step_name: str,
    script_path: Path,
    args: list[str],
    result: ImageRecoveryResult,
    quiet: bool,
) -> int:
    """Run a script as a subprocess. Returns 0 on success."""
    if not script_path.exists():
        msg = f"{step_name}: script not found: {script_path}"
        result.errors.append(msg)
        logger.error(msg)
        return 1

    env = dict(os.environ)
    env.setdefault("PYTHONPATH", str(_REPO_ROOT / "src"))
    cmd = [sys.executable, str(script_path)] + args

    if not quiet:
        logger.info("Running %s: %s", step_name, " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min per step
        )
        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "")[-500:]
            msg = f"{step_name}: exited with code {proc.returncode}"
            if stderr_tail:
                msg += f" — {stderr_tail.strip()}"
            result.errors.append(msg)
            logger.warning(msg)
        elif not quiet:
            logger.info("%s: OK", step_name)
        return proc.returncode
    except subprocess.TimeoutExpired:
        msg = f"{step_name}: timed out after 600s"
        result.errors.append(msg)
        logger.error(msg)
        return 1
    except Exception as exc:
        msg = f"{step_name}: {exc}"
        result.errors.append(msg)
        logger.error(msg, exc_info=True)
        return 1


# ---------------------------------------------------------------------------
# Callable-based step runner (for testing / in-process usage)
# ---------------------------------------------------------------------------

def _run_callable(
    step_name: str,
    fn: callable,
    result: ImageRecoveryResult,
    quiet: bool,
) -> int:
    """Run a callable step. Returns 0 on success."""
    try:
        rc = fn()
        rc = int(rc) if rc is not None else 0
        if rc != 0:
            msg = f"{step_name}: returned code {rc}"
            result.errors.append(msg)
            logger.warning(msg)
        elif not quiet:
            logger.info("%s: OK", step_name)
        return rc
    except Exception as exc:
        msg = f"{step_name}: {exc}"
        result.errors.append(msg)
        logger.error(msg, exc_info=True)
        return 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_image_recovery(
    db_path: str | Path,
    *,
    min_fg: float = 300.0,
    quiet: bool = False,
    market_key: str = "d2r_sc_ladder",
    topic_dir: str = "data/raw/d2jsp/topic_pages",
    image_out_dir: str = "data/raw/d2jsp/topic_images",
    scripts_dir: str | Path | None = None,
    step_callables: dict[str, callable] | None = None,
) -> ImageRecoveryResult:
    """Run the full image recovery pipeline.

    Steps (each is best-effort; failures are recorded but do not
    prevent subsequent steps from running where possible):

    1. enqueue — find new high-value image-only listings
    2. fetch   — download pending image attachments
    3. ocr     — OCR-parse downloaded images
    4. stage   — materialize OCR results as candidates
    5. promote — promote candidates to observed_prices

    Parameters
    ----------
    step_callables : dict, optional
        Override individual steps with callables (for testing).
        Keys: "enqueue", "fetch", "ocr", "stage", "promote".
        Each callable should return 0 on success.
    """
    db = str(Path(db_path))
    result = ImageRecoveryResult()
    sdir = Path(scripts_dir) if scripts_dir else _REPO_ROOT / "scripts"
    callables = step_callables or {}
    common = ["--db", db, "--market-key", market_key]

    steps = [
        (
            "enqueue",
            sdir / "enqueue_topic_image_recovery.py",
            common + ["--min-fg", str(min_fg), "--topic-dir", topic_dir],
        ),
        (
            "fetch",
            sdir / "fetch_image_market_queue.py",
            common + ["--status", "pending", "--out-dir", image_out_dir],
        ),
        (
            "ocr",
            sdir / "ocr_image_market_queue.py",
            common + ["--status", "downloaded"],
        ),
        (
            "stage",
            sdir / "materialize_image_ocr_candidates.py",
            common + ["--min-fg", str(min_fg)],
        ),
        (
            "promote",
            sdir / "promote_image_ocr_candidates.py",
            common + ["--min-fg", str(min_fg)],
        ),
    ]

    for step_name, script, args in steps:
        if step_name in callables:
            _run_callable(step_name, callables[step_name], result, quiet)
        else:
            _run_script(step_name, script, args, result, quiet)

    if not quiet:
        logger.info(
            "Image recovery complete: errors=%d",
            len(result.errors),
        )

    return result

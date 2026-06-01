"""
Metadata Agent — Background Watcher

Polls Gmail and Google Drive on a schedule, automatically processes any new
CSV / JSON / SQL attachments through the metadata agent, and saves results
to the memory store and outputs/ directory.

Already-processed files are tracked in outputs/memory.db so nothing is
run twice. For Drive, a file that is re-uploaded (new modifiedTime) is
treated as a new version and re-processed.

Usage
-----
Run alongside the Streamlit UI in a separate terminal:

    python watcher.py                     # poll every 60 minutes (default)
    python watcher.py --interval 30       # poll every 30 minutes
    python watcher.py --once              # single poll then exit

Windows Task Scheduler (run once per hour automatically):
    Program : python
    Arguments: "C:\\...\\metadata-agent\\watcher.py" --once
    Start in : C:\\...\\metadata-agent
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.agents import MetadataAgent
from src.config import AgentConfig
from src.extractors import extract
from src.memory.memory_store import is_processed, mark_processed

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("outputs/watcher.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("watcher")

# ── Core processing ────────────────────────────────────────────────────────

def _process_file(tmp_path: str, filename: str, source_label: str) -> bool:
    """Run the metadata agent on one downloaded file. Returns True on success."""
    try:
        log.info(f"  Extracting profile: {filename}")
        profile = extract(tmp_path)

        log.info(f"  Running agent on {profile.dataset_name} ({len(profile.fields)} fields)…")
        config = AgentConfig()
        agent = MetadataAgent(config)
        metadata, quality = agent.generate(profile)

        status = "PASS" if quality.passed else "FAIL"
        log.info(
            f"  Done — quality {quality.overall_score:.0f}/100 {status}  "
            f"| {len(metadata.fields)} fields  "
            f"| {sum(1 for f in metadata.fields if f.is_pii)} PII  "
            f"| source: {source_label}"
        )
        return True

    except Exception as exc:
        log.error(f"  Agent failed on {filename}: {exc}")
        return False

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── Gmail poll ─────────────────────────────────────────────────────────────

def poll_gmail() -> int:
    """Fetch unprocessed Gmail attachments and run the agent on each."""
    try:
        from src.connectors.gmail_connector import (
            download_attachment,
            list_emails_with_attachments,
        )
    except ImportError:
        log.warning("Google libraries not installed — skipping Gmail poll")
        return 0

    try:
        emails = list_emails_with_attachments(max_results=50)
    except Exception as exc:
        log.error(f"Gmail listing failed: {exc}")
        return 0

    processed = 0
    for email in emails:
        for att in email["attachments"]:
            # Dedup key: message ID + attachment ID (stable across polls)
            source_id = f"{email['message_id']}:{att['attachment_id']}"
            if is_processed("gmail", source_id):
                continue

            log.info(
                f"New Gmail attachment: {att['filename']}"
                f"  |  from: {email['sender'][:50]}"
                f"  |  subject: {email['subject'][:60]}"
            )

            try:
                tmp = download_attachment(
                    email["message_id"], att["attachment_id"], att["filename"]
                )
            except Exception as exc:
                log.error(f"Download failed for {att['filename']}: {exc}")
                mark_processed("gmail", source_id, att["filename"], success=False)
                continue

            success = _process_file(
                tmp, att["filename"], f"Gmail/{email['subject'][:40]}"
            )
            mark_processed("gmail", source_id, att["filename"], success=success)
            if success:
                processed += 1

    return processed


# ── Drive poll ─────────────────────────────────────────────────────────────

def poll_drive() -> int:
    """Fetch unprocessed (or updated) Drive files and run the agent on each."""
    try:
        from src.connectors.drive_connector import download_drive_file, list_drive_files
    except ImportError:
        log.warning("Google libraries not installed — skipping Drive poll")
        return 0

    try:
        files = list_drive_files(max_results=50)
    except Exception as exc:
        log.error(f"Drive listing failed: {exc}")
        return 0

    processed = 0
    for f in files:
        # Include modifiedTime in the key so a re-uploaded file is reprocessed
        source_id = f"{f['id']}:{f.get('modified', '')}"
        if is_processed("drive", source_id):
            continue

        log.info(
            f"New Drive file: {f['name']}"
            f"  |  modified: {(f.get('modified') or '')[:10]}"
        )

        try:
            tmp = download_drive_file(f["id"], f["name"])
        except Exception as exc:
            log.error(f"Download failed for {f['name']}: {exc}")
            mark_processed("drive", source_id, f["name"], success=False)
            continue

        success = _process_file(tmp, f["name"], "Drive")
        mark_processed("drive", source_id, f["name"], success=success)
        if success:
            processed += 1

    return processed


# ── Poll orchestration ─────────────────────────────────────────────────────

def poll_once() -> None:
    log.info("━━━ Poll starting ━━━")
    gmail_n = poll_gmail()
    drive_n = poll_drive()
    total = gmail_n + drive_n
    log.info(
        f"━━━ Poll complete — {total} file(s) processed "
        f"(Gmail: {gmail_n}  Drive: {drive_n}) ━━━"
    )


def run_loop(interval_minutes: int) -> None:
    log.info(f"Watcher started — polling every {interval_minutes} minute(s). Press Ctrl+C to stop.")
    while True:
        poll_once()
        next_time = datetime.now().strftime("%H:%M")
        log.info(f"Sleeping {interval_minutes} min. Next poll at ~{next_time}.")
        time.sleep(interval_minutes * 60)


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Ensure outputs/ exists for the log file
    Path("outputs").mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(
        description="Metadata agent background watcher — auto-processes Gmail and Drive attachments"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        metavar="MINUTES",
        help="Poll interval in minutes (default: 60)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Poll once and exit (use with Windows Task Scheduler)",
    )
    args = parser.parse_args()

    if args.once:
        poll_once()
    else:
        run_loop(args.interval)

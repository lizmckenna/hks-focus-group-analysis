"""Shared constants, CSV loader, and text cleaning utilities."""

import re
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SOURCE_DIR = Path.home() / "Desktop" / "Focus Group transcripts deidentified"
SITE_DIR = PROJECT_ROOT / "site"
TEMPLATE_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

PROGRAMS = ["MPP1", "MCMPA", "MPAID", "MIXED", "MPP2"]

PROGRAM_LABELS = {
    "MPP1": "MPP1",
    "MPP1s": "MPP1",
    "MCMPAs": "MCMPA",
    "MCMPA": "MCMPA",
    "MPAIDs": "MPAID",
    "MPAID": "MPAID",
    "MIXED": "MIXED",
    "MPP2s": "MPP2",
    "MPP2": "MPP2",
}

# Files mapped to program labels
FILE_PROGRAM_MAP = {
    "ZOOM0002_MPP1s_2_10_deidentified.csv": "MPP1",
    "ZOOM0004_MCMPAs_2_11_deidentified.csv": "MCMPA",
    "ZOOM0004_MPAIDs_2_10_deidentified.csv": "MPAID",
    "ZOOM0005_MIXED_2_12_deidentified.csv": "MIXED",
    "ZOOM0006_MPP2s_2_12_deidentified.csv": "MPP2",
}

# Minimum word count for a standalone turn (below this, merge with adjacent)
MIN_TURN_WORDS = 3


def parse_csv_line(line):
    """Parse a single CSV line into speaker, timestamp, text."""
    # Format: "Speaker Label: ,MM:SS,text[,extra]" or "Speaker Label: ,HH:MM:SS,text[,extra]"
    match = re.match(r'^(.+?):\s*,(\d+:\d+(?::\d+)?),(.+?)(?:,(?:Unnamed.*)?)?$', line.strip())
    if match:
        speaker = match.group(1).strip()
        timestamp = match.group(2).strip()
        # Remove surrounding quotes from text
        text = match.group(3).strip().strip('"').strip()
        return speaker, timestamp, text
    return None, None, None


def load_transcript(filepath):
    """Load a single transcript CSV into a list of (speaker, timestamp, text) tuples."""
    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            speaker, timestamp, text = parse_csv_line(line)
            if speaker and text:
                # Normalize speaker labels
                if speaker.lower() in ('xmoderator', 'moderator'):
                    speaker = 'Moderator'
                rows.append({
                    'speaker': speaker,
                    'timestamp': timestamp,
                    'text': text,
                })
    return rows


def consolidate_turns(rows, min_words=MIN_TURN_WORDS):
    """Consolidate consecutive utterances from the same speaker into full turns.

    Short interjections (< min_words) from a different speaker are kept separate
    but the surrounding speaker's turn is not broken.
    """
    if not rows:
        return []

    consolidated = []
    current = dict(rows[0])

    for row in rows[1:]:
        if row['speaker'] == current['speaker']:
            # Same speaker — merge
            current['text'] += ' ' + row['text']
            current['timestamp_end'] = row['timestamp']
        else:
            # Different speaker — finalize current and start new
            consolidated.append(current)
            current = dict(row)

    consolidated.append(current)
    return consolidated


def timestamp_to_seconds(ts):
    """Convert MM:SS or HH:MM:SS timestamp to total seconds."""
    parts = ts.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def clean_text(text):
    """Basic text cleaning for NLP."""
    text = re.sub(r'\[NAME\]', '', text)
    text = re.sub(r'#NAME\?', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

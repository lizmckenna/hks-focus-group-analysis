"""Parse raw CSV transcripts into a unified, cleaned DataFrame."""

import pandas as pd
from utils import (
    SOURCE_DIR, DATA_DIR, FILE_PROGRAM_MAP,
    load_transcript, consolidate_turns, timestamp_to_seconds, clean_text
)

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_turns = []
    turn_id = 0

    for filename, program in FILE_PROGRAM_MAP.items():
        filepath = SOURCE_DIR / filename
        print(f"Parsing {filename} ({program})...")

        rows = load_transcript(filepath)
        turns = consolidate_turns(rows)

        for turn in turns:
            is_moderator = turn['speaker'] == 'Moderator'
            text = turn['text']
            cleaned = clean_text(text)
            word_count = len(cleaned.split())

            all_turns.append({
                'turn_id': turn_id,
                'program': program,
                'speaker': turn['speaker'],
                'is_moderator': is_moderator,
                'timestamp': turn['timestamp'],
                'timestamp_seconds': timestamp_to_seconds(turn['timestamp']),
                'text': text,
                'text_clean': cleaned,
                'word_count': word_count,
            })
            turn_id += 1

    df = pd.DataFrame(all_turns)

    # Summary stats
    total = len(df)
    students = df[~df['is_moderator']]
    print(f"\nTotal turns: {total}")
    print(f"Student turns: {len(students)}")
    print(f"Moderator turns: {total - len(students)}")
    print(f"\nStudent turns by program:")
    print(students.groupby('program').size())
    print(f"\nTotal student words: {students['word_count'].sum()}")

    # Save
    outpath = DATA_DIR / "cleaned_turns.csv"
    df.to_csv(outpath, index=False)
    print(f"\nSaved to {outpath}")

    # Also save student-only turns for downstream analysis
    student_outpath = DATA_DIR / "student_turns.csv"
    students.to_csv(student_outpath, index=False)
    print(f"Saved student turns to {student_outpath}")


if __name__ == "__main__":
    main()

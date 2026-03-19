"""Keyword extraction and theme co-occurrence analysis."""

import json
import pandas as pd
import numpy as np
import spacy
from collections import Counter, defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from itertools import combinations

from utils import DATA_DIR, PROGRAMS


def extract_program_keywords(df):
    """Extract distinctive TF-IDF keywords per program."""
    print("Extracting distinctive keywords per program...")
    program_keywords = {}

    # Build corpus: one "document" per program (all text concatenated)
    program_texts = {}
    for program in PROGRAMS:
        mask = df['program'] == program
        if mask.sum() == 0:
            continue
        program_texts[program] = ' '.join(df.loc[mask, 'text_clean'].tolist())

    programs = list(program_texts.keys())
    texts = [program_texts[p] for p in programs]

    tfidf = TfidfVectorizer(
        max_features=3000,
        stop_words='english',
        ngram_range=(1, 2),
        min_df=1,
    )
    matrix = tfidf.fit_transform(texts)
    feature_names = tfidf.get_feature_names_out()

    for i, program in enumerate(programs):
        scores = matrix[i].toarray().flatten()
        top_idx = scores.argsort()[-30:][::-1]
        keywords = [(feature_names[j], float(scores[j])) for j in top_idx if scores[j] > 0]
        program_keywords[program] = keywords

    return program_keywords


def extract_noun_phrases(df):
    """Extract noun phrases using spaCy."""
    print("Loading spaCy model...")
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        print("Downloading spaCy model...")
        from spacy.cli import download
        download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")

    print("Extracting noun phrases...")
    program_phrases = defaultdict(Counter)

    for program in PROGRAMS:
        mask = df['program'] == program
        texts = df.loc[mask, 'text_clean'].tolist()
        for doc in nlp.pipe(texts, batch_size=50, n_process=1):
            for chunk in doc.noun_chunks:
                phrase = chunk.text.lower().strip()
                if len(phrase.split()) >= 2 and len(phrase) > 5:
                    program_phrases[program][phrase] += 1

    # Convert to serializable format
    result = {}
    for program, counter in program_phrases.items():
        result[program] = [
            {'phrase': phrase, 'count': count}
            for phrase, count in counter.most_common(50)
        ]

    return result


def compute_theme_cooccurrence(df, themes):
    """Compute how often themes co-occur within the same speaker turn or nearby turns."""
    print("Computing theme co-occurrence...")

    theme_ids = [int(tid) for tid in themes.keys()]
    n = len(theme_ids)
    cooccurrence = np.zeros((n, n), dtype=int)
    id_to_idx = {tid: i for i, tid in enumerate(theme_ids)}

    # Group by program and look at window-based co-occurrence
    window_size = 5  # turns

    for program in df['program'].unique():
        prog_df = df[df['program'] == program].sort_values('timestamp_seconds')
        clusters = prog_df['cluster'].values

        for i in range(len(clusters)):
            if clusters[i] == -1:
                continue
            if clusters[i] not in id_to_idx:
                continue

            for j in range(i + 1, min(i + window_size + 1, len(clusters))):
                if clusters[j] == -1 or clusters[j] == clusters[i]:
                    continue
                if clusters[j] not in id_to_idx:
                    continue

                idx_a = id_to_idx[clusters[i]]
                idx_b = id_to_idx[clusters[j]]
                cooccurrence[idx_a][idx_b] += 1
                cooccurrence[idx_b][idx_a] += 1

    # Build network edges
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if cooccurrence[i][j] > 0:
                edges.append({
                    'source': theme_ids[i],
                    'target': theme_ids[j],
                    'weight': int(cooccurrence[i][j]),
                })

    # Build nodes
    nodes = []
    for tid_str, theme in themes.items():
        nodes.append({
            'id': int(tid_str),
            'label': theme['label'],
            'size': theme['size'],
        })

    return {'nodes': nodes, 'edges': edges}


def main():
    df = pd.read_csv(DATA_DIR / "student_turns_clustered.csv")
    with open(DATA_DIR / "draft_themes.json") as f:
        themes = json.load(f)

    # Program-distinctive keywords
    program_keywords = extract_program_keywords(df)

    # Noun phrases
    noun_phrases = extract_noun_phrases(df)

    # Theme co-occurrence
    network = compute_theme_cooccurrence(df, themes)

    # Save outputs
    with open(DATA_DIR / "program_keywords.json", 'w') as f:
        json.dump(program_keywords, f, indent=2)

    with open(DATA_DIR / "noun_phrases.json", 'w') as f:
        json.dump(noun_phrases, f, indent=2)

    with open(DATA_DIR / "theme_network.json", 'w') as f:
        json.dump(network, f, indent=2)

    print("\nProgram keywords summary:")
    for program, kws in program_keywords.items():
        top5 = [kw[0] for kw in kws[:5]]
        print(f"  {program}: {', '.join(top5)}")

    print(f"\nTheme network: {len(network['nodes'])} nodes, {len(network['edges'])} edges")
    print("Saved to data/program_keywords.json, noun_phrases.json, theme_network.json")


if __name__ == "__main__":
    main()

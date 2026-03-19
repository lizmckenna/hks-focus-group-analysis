"""Sentiment analysis: VADER scores, sentiment arcs, theme-level distributions."""

import json
import pandas as pd
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from utils import DATA_DIR, PROGRAMS


def analyze_sentiment(df):
    """Apply VADER sentiment to each turn."""
    print("Running VADER sentiment analysis...")
    analyzer = SentimentIntensityAnalyzer()

    scores = []
    for text in df['text_clean']:
        vs = analyzer.polarity_scores(str(text))
        scores.append(vs)

    score_df = pd.DataFrame(scores)
    df['sentiment_compound'] = score_df['compound'].values
    df['sentiment_pos'] = score_df['pos'].values
    df['sentiment_neg'] = score_df['neg'].values
    df['sentiment_neu'] = score_df['neu'].values

    # Classify sentiment
    df['sentiment_label'] = df['sentiment_compound'].apply(
        lambda x: 'positive' if x >= 0.05 else ('negative' if x <= -0.05 else 'neutral')
    )

    return df


def compute_sentiment_arcs(df):
    """Compute rolling sentiment over each session's timeline."""
    print("Computing sentiment arcs...")
    arcs = {}

    for program in PROGRAMS:
        prog_df = df[df['program'] == program].sort_values('timestamp_seconds')
        if len(prog_df) < 3:
            continue

        # Rolling average with window of 5 turns
        window = min(5, len(prog_df))
        prog_df = prog_df.copy()
        prog_df['sentiment_rolling'] = (
            prog_df['sentiment_compound'].rolling(window=window, center=True, min_periods=1).mean()
        )

        arcs[program] = {
            'timestamps': prog_df['timestamp_seconds'].tolist(),
            'sentiment_raw': prog_df['sentiment_compound'].tolist(),
            'sentiment_rolling': prog_df['sentiment_rolling'].tolist(),
            'texts': prog_df['text'].tolist(),
            'speakers': prog_df['speaker'].tolist(),
        }

    return arcs


def compute_theme_sentiment(df, themes):
    """Compute sentiment distributions per theme."""
    print("Computing theme-level sentiment...")
    theme_sentiment = {}

    for tid, theme in themes.items():
        cid = int(tid)
        mask = df['cluster'] == cid
        if mask.sum() == 0:
            continue

        cluster_df = df[mask]
        sentiments = cluster_df['sentiment_compound'].tolist()

        theme_sentiment[tid] = {
            'label': theme['label'],
            'sentiments': sentiments,
            'mean': float(np.mean(sentiments)),
            'median': float(np.median(sentiments)),
            'std': float(np.std(sentiments)),
            'positive_pct': float((cluster_df['sentiment_label'] == 'positive').mean()),
            'negative_pct': float((cluster_df['sentiment_label'] == 'negative').mean()),
            'neutral_pct': float((cluster_df['sentiment_label'] == 'neutral').mean()),
        }

        # Cross-program sentiment for this theme
        program_sentiment = {}
        for program in PROGRAMS:
            prog_mask = mask & (df['program'] == program)
            if prog_mask.sum() > 0:
                prog_sentiments = df.loc[prog_mask, 'sentiment_compound'].tolist()
                program_sentiment[program] = {
                    'sentiments': prog_sentiments,
                    'mean': float(np.mean(prog_sentiments)),
                    'count': int(prog_mask.sum()),
                }
        theme_sentiment[tid]['by_program'] = program_sentiment

    return theme_sentiment


def extract_vivid_quotes(df, themes, n_per_theme=10):
    """Extract the most emotionally intense quotes per theme."""
    print("Extracting vivid quotes...")
    vivid = {}

    for tid, theme in themes.items():
        cid = int(tid)
        mask = df['cluster'] == cid
        if mask.sum() == 0:
            continue

        cluster_df = df[mask].copy()
        # Most emotionally intense = highest absolute compound score
        cluster_df['intensity'] = cluster_df['sentiment_compound'].abs()

        # Get top positive and top negative
        top_positive = (
            cluster_df[cluster_df['sentiment_compound'] > 0]
            .nlargest(n_per_theme // 2, 'sentiment_compound')
        )
        top_negative = (
            cluster_df[cluster_df['sentiment_compound'] < 0]
            .nsmallest(n_per_theme // 2, 'sentiment_compound')
        )
        top_intense = cluster_df.nlargest(n_per_theme, 'intensity')

        def quotes_from_df(sub_df):
            return [
                {
                    'text': row['text'],
                    'program': row['program'],
                    'speaker': row['speaker'],
                    'sentiment': round(row['sentiment_compound'], 3),
                }
                for _, row in sub_df.iterrows()
            ]

        vivid[tid] = {
            'label': theme['label'],
            'most_positive': quotes_from_df(top_positive),
            'most_negative': quotes_from_df(top_negative),
            'most_intense': quotes_from_df(top_intense),
        }

    return vivid


def main():
    df = pd.read_csv(DATA_DIR / "student_turns_clustered.csv")
    with open(DATA_DIR / "draft_themes.json") as f:
        themes = json.load(f)

    # Sentiment analysis
    df = analyze_sentiment(df)

    # Save updated dataframe
    df.to_csv(DATA_DIR / "student_turns_sentiment.csv", index=False)

    # Sentiment arcs
    arcs = compute_sentiment_arcs(df)
    with open(DATA_DIR / "sentiment_arcs.json", 'w') as f:
        json.dump(arcs, f, indent=2)

    # Theme-level sentiment
    theme_sentiment = compute_theme_sentiment(df, themes)
    with open(DATA_DIR / "theme_sentiment.json", 'w') as f:
        json.dump(theme_sentiment, f, indent=2)

    # Vivid quotes
    vivid = extract_vivid_quotes(df, themes)
    with open(DATA_DIR / "vivid_quotes.json", 'w') as f:
        json.dump(vivid, f, indent=2)

    # Summary
    print(f"\nSentiment summary:")
    print(f"  Positive: {(df['sentiment_label'] == 'positive').sum()} turns")
    print(f"  Neutral:  {(df['sentiment_label'] == 'neutral').sum()} turns")
    print(f"  Negative: {(df['sentiment_label'] == 'negative').sum()} turns")
    print(f"\nSentiment by program:")
    for program in PROGRAMS:
        mask = df['program'] == program
        if mask.sum() > 0:
            mean = df.loc[mask, 'sentiment_compound'].mean()
            print(f"  {program}: mean={mean:.3f} (n={mask.sum()})")

    print("\nSaved sentiment data to data/")


if __name__ == "__main__":
    main()

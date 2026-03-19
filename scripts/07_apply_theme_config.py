"""Apply hand-crafted theme configuration to replace auto-generated labels.

Reads themes_config.json (human-curated labels, descriptions, quotes)
and merges with clustering data to produce final themes.json.
"""

import json
import pandas as pd
from utils import DATA_DIR, PROGRAMS


def main():
    # Load cluster data
    df = pd.read_csv(DATA_DIR / "student_turns_sentiment.csv")
    with open(DATA_DIR / "themes_config.json") as f:
        config = json.load(f)
    with open(DATA_DIR / "theme_sentiment.json") as f:
        theme_sentiment = json.load(f)

    noise_clusters = set(config["noise_clusters"])

    themes = {}
    for theme_id, tc in config["themes"].items():
        cluster_ids = tc["clusters"]

        # Aggregate data from all clusters in this theme
        mask = df["cluster"].isin(cluster_ids)
        theme_df = df[mask]

        if len(theme_df) == 0:
            continue

        # Program distribution
        prog_dist = theme_df["program"].value_counts().to_dict()

        # Aggregate sentiment from component clusters
        all_sentiments = theme_df["sentiment_compound"].tolist()
        import numpy as np
        mean_sent = float(np.mean(all_sentiments)) if all_sentiments else 0
        pos_pct = float((theme_df["sentiment_label"] == "positive").mean())
        neg_pct = float((theme_df["sentiment_label"] == "negative").mean())
        neu_pct = float((theme_df["sentiment_label"] == "neutral").mean())

        # Cross-program sentiment
        by_program = {}
        for program in PROGRAMS:
            prog_mask = mask & (df["program"] == program)
            if prog_mask.sum() > 0:
                prog_sents = df.loc[prog_mask, "sentiment_compound"].tolist()
                by_program[program] = {
                    "sentiments": prog_sents,
                    "mean": float(np.mean(prog_sents)),
                    "count": int(prog_mask.sum()),
                }

        themes[theme_id] = {
            "id": theme_id,
            "label": tc["label"],
            "description": tc["description"],
            "whats_working": tc["whats_working"],
            "areas_for_improvement": tc["areas_for_improvement"],
            "curated_quotes": tc["curated_quotes"],
            "discussion_question": tc.get("discussion_question", ""),
            "clusters": cluster_ids,
            "size": int(mask.sum()),
            "program_distribution": prog_dist,
            "sentiment": {
                "mean": mean_sent,
                "positive_pct": pos_pct,
                "negative_pct": neg_pct,
                "neutral_pct": neu_pct,
                "by_program": by_program,
            },
        }

    # Save final themes
    with open(DATA_DIR / "themes.json", "w") as f:
        json.dump(themes, f, indent=2)

    print(f"Generated {len(themes)} themes from {sum(len(t['clusters']) for t in themes.values())} clusters:")
    for tid, t in themes.items():
        print(f"  {t['label']} ({t['size']} turns, clusters {t['clusters']})")

    print(f"\nExcluded {len(noise_clusters)} noise clusters: {sorted(noise_clusters)}")
    noise_count = df["cluster"].isin(noise_clusters).sum()
    unclustered = (df["cluster"] == -1).sum()
    print(f"  {noise_count} noise turns + {unclustered} unclustered = {noise_count + unclustered} excluded")
    print(f"\nSaved to {DATA_DIR / 'themes.json'}")


if __name__ == "__main__":
    main()

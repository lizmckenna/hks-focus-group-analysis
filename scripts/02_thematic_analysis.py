"""Thematic analysis: embeddings, clustering, topic modeling, auto-labeling."""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation, NMF
import umap
import hdbscan

from utils import DATA_DIR

MIN_CLUSTER_SIZE = 8
N_TOPICS_LDA = 12
N_TOPICS_NMF = 12


def load_student_turns():
    df = pd.read_csv(DATA_DIR / "student_turns.csv")
    # Filter out very short turns (< 5 words) for clustering quality
    df = df[df['word_count'] >= 5].reset_index(drop=True)
    return df


def generate_embeddings(texts):
    print("Loading sentence-transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"Generating embeddings for {len(texts)} texts...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
    return embeddings


def cluster_embeddings(embeddings):
    print("Running UMAP dimensionality reduction...")
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=15,
        min_dist=0.1,
        metric='cosine',
        random_state=42,
    )
    coords_2d = reducer.fit_transform(embeddings)

    # Also get higher-dim for clustering
    reducer_cluster = umap.UMAP(
        n_components=10,
        n_neighbors=15,
        min_dist=0.0,
        metric='cosine',
        random_state=42,
    )
    coords_cluster = reducer_cluster.fit_transform(embeddings)

    print("Running HDBSCAN clustering...")
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=3,
        metric='euclidean',
        cluster_selection_method='eom',
    )
    labels = clusterer.fit_predict(coords_cluster)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    noise = (labels == -1).sum()
    print(f"Found {n_clusters} clusters, {noise} noise points")

    return coords_2d, labels


def extract_cluster_info(df, labels, embeddings):
    """Extract keywords and central quotes for each cluster."""
    df = df.copy()
    df['cluster'] = labels

    clusters = {}
    for cid in sorted(set(labels)):
        if cid == -1:
            continue

        mask = df['cluster'] == cid
        cluster_texts = df.loc[mask, 'text_clean'].tolist()
        cluster_programs = df.loc[mask, 'program'].value_counts().to_dict()

        # TF-IDF keywords for this cluster
        tfidf = TfidfVectorizer(max_features=500, stop_words='english', ngram_range=(1, 2))
        try:
            tfidf_matrix = tfidf.fit_transform(cluster_texts)
            feature_names = tfidf.get_feature_names_out()
            mean_tfidf = tfidf_matrix.mean(axis=0).A1
            top_idx = mean_tfidf.argsort()[-15:][::-1]
            keywords = [feature_names[i] for i in top_idx]
        except ValueError:
            keywords = []

        # Central quotes: closest to cluster centroid in embedding space
        cluster_embeddings = embeddings[mask.values]
        centroid = cluster_embeddings.mean(axis=0)
        distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
        central_indices = distances.argsort()[:15]
        central_quotes = [
            {
                'text': df.loc[mask, 'text'].iloc[i],
                'program': df.loc[mask, 'program'].iloc[i],
                'speaker': df.loc[mask, 'speaker'].iloc[i],
            }
            for i in central_indices
        ]

        clusters[int(cid)] = {
            'size': int(mask.sum()),
            'keywords': keywords,
            'central_quotes': central_quotes,
            'program_distribution': cluster_programs,
        }

    return clusters


def run_topic_models(df):
    """Run LDA and NMF for cross-validation with embedding clusters."""
    print("Running topic models (LDA + NMF)...")
    tfidf = TfidfVectorizer(
        max_features=2000,
        stop_words='english',
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.85,
    )
    tfidf_matrix = tfidf.fit_transform(df['text_clean'])
    feature_names = tfidf.get_feature_names_out()

    # LDA
    lda = LatentDirichletAllocation(
        n_components=N_TOPICS_LDA,
        random_state=42,
        max_iter=30,
    )
    lda.fit(tfidf_matrix)

    lda_topics = []
    for i, topic in enumerate(lda.components_):
        top_words = [feature_names[j] for j in topic.argsort()[-10:][::-1]]
        lda_topics.append({'topic_id': i, 'keywords': top_words, 'method': 'LDA'})

    # NMF
    nmf = NMF(
        n_components=N_TOPICS_NMF,
        random_state=42,
        max_iter=300,
    )
    nmf.fit(tfidf_matrix)

    nmf_topics = []
    for i, topic in enumerate(nmf.components_):
        top_words = [feature_names[j] for j in topic.argsort()[-10:][::-1]]
        nmf_topics.append({'topic_id': i, 'keywords': top_words, 'method': 'NMF'})

    return lda_topics, nmf_topics


def generate_theme_labels(clusters, lda_topics, nmf_topics):
    """Generate descriptive theme labels based on keywords and quotes.

    Uses heuristic labeling based on keyword analysis. For Claude-assisted
    labeling, run scripts/label_themes_claude.py after this step.
    """
    themes = {}

    for cid, info in clusters.items():
        keywords = info['keywords']
        quotes = [q['text'] for q in info['central_quotes'][:5]]

        # Heuristic label from top keywords
        label = " / ".join(keywords[:3]).title()

        themes[str(cid)] = {
            'id': cid,
            'label': label,
            'description': f"Cluster around: {', '.join(keywords[:6])}",
            'keywords': keywords,
            'representative_quotes': [
                {'text': q['text'], 'program': q['program'], 'speaker': q['speaker']}
                for q in info['central_quotes']
            ],
            'size': info['size'],
            'program_distribution': info['program_distribution'],
        }

    return themes


def main():
    df = load_student_turns()
    print(f"Loaded {len(df)} student turns for analysis")

    # Step A: Embedding-based clustering
    embeddings = generate_embeddings(df['text_clean'].tolist())

    # Save embeddings for reuse
    np.save(DATA_DIR / "embeddings.npy", embeddings)

    coords_2d, labels = cluster_embeddings(embeddings)

    # Save 2D coordinates
    df['umap_x'] = coords_2d[:, 0]
    df['umap_y'] = coords_2d[:, 1]
    df['cluster'] = labels
    df.to_csv(DATA_DIR / "student_turns_clustered.csv", index=False)

    # Extract cluster info
    clusters = extract_cluster_info(df, labels, embeddings)

    # Step B: Topic models
    lda_topics, nmf_topics = run_topic_models(df)

    # Save topic model results
    with open(DATA_DIR / "topic_models.json", 'w') as f:
        json.dump({'lda': lda_topics, 'nmf': nmf_topics}, f, indent=2)

    # Step C: Generate theme labels
    themes = generate_theme_labels(clusters, lda_topics, nmf_topics)

    # Save draft themes
    with open(DATA_DIR / "draft_themes.json", 'w') as f:
        json.dump(themes, f, indent=2)

    print(f"\nGenerated {len(themes)} themes:")
    for tid, theme in themes.items():
        print(f"  [{tid}] {theme['label']} ({theme['size']} turns)")
        print(f"       Keywords: {', '.join(theme['keywords'][:6])}")

    print(f"\nSaved to {DATA_DIR / 'draft_themes.json'}")
    print("Run scripts/label_themes_claude.py for improved labels (optional)")


if __name__ == "__main__":
    main()

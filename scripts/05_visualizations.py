"""Generate all visualizations using curated theme names."""

import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import networkx as nx

from utils import DATA_DIR, SITE_DIR, PROGRAMS

# Design constants
BG_COLOR = '#ffffff'
TEXT_COLOR = '#111111'
GRID_COLOR = '#e5e5e5'

# Color palette for themes (distinguishable but not garish)
THEME_COLORS = [
    '#2563eb',  # blue
    '#dc2626',  # red
    '#059669',  # green
    '#d97706',  # amber
    '#7c3aed',  # violet
    '#db2777',  # pink
    '#0891b2',  # cyan
    '#65a30d',  # lime
    '#ea580c',  # orange
    '#6366f1',  # indigo
    '#14b8a6',  # teal
    '#f59e0b',  # yellow
]

PROGRAM_COLORS = {
    'MPP1': '#2563eb',
    'MCMPA': '#dc2626',
    'MPAID': '#059669',
    'MIXED': '#d97706',
    'MPP2': '#7c3aed',
}

PLOTLY_TEMPLATE = 'plotly_white'


def load_curated_themes():
    """Load curated themes, building a cluster-to-theme mapping."""
    themes_path = DATA_DIR / "themes.json"
    if not themes_path.exists():
        themes_path = DATA_DIR / "draft_themes.json"
    with open(themes_path) as f:
        themes = json.load(f)

    # Build cluster_id -> theme mapping
    cluster_to_theme = {}
    for tid, theme in themes.items():
        for cid in theme.get('clusters', []):
            cluster_to_theme[cid] = {
                'theme_id': tid,
                'label': theme['label'],
            }

    return themes, cluster_to_theme


def wrap_text(text, width=60):
    """Wrap text for hover labels."""
    words = text.split()
    lines = []
    current = []
    length = 0
    for w in words:
        if length + len(w) + 1 > width and current:
            lines.append(' '.join(current))
            current = [w]
            length = len(w)
        else:
            current.append(w)
            length += len(w) + 1
    if current:
        lines.append(' '.join(current))
    return '<br>'.join(lines)


def base_layout(**kwargs):
    layout = dict(
        template=PLOTLY_TEMPLATE,
        font=dict(family='Inter, -apple-system, sans-serif', color=TEXT_COLOR, size=13),
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=BG_COLOR,
        margin=dict(l=50, r=30, t=50, b=50),
        xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        hoverlabel=dict(
            bgcolor='white',
            font_size=12,
            font_family='Inter, sans-serif',
            namelength=-1,
        ),
    )
    layout.update(kwargs)
    return layout


def save_plotly(fig, name):
    out_dir = DATA_DIR / "charts"
    out_dir.mkdir(exist_ok=True)
    fig.write_html(
        str(out_dir / f"{name}.html"),
        full_html=False,
        include_plotlyjs='cdn',
        config={'displayModeBar': False},
    )
    print(f"  Saved {name}.html")


def theme_scatter(df, themes, cluster_to_theme):
    """2D scatter plot colored by curated theme."""
    print("Generating theme map scatter...")

    # Assign curated theme labels and colors
    theme_ids = list(themes.keys())
    color_map = {tid: THEME_COLORS[i % len(THEME_COLORS)] for i, tid in enumerate(theme_ids)}

    fig = go.Figure()

    # Noise / unclustered / excluded cluster points
    themed_clusters = set()
    for tid, theme in themes.items():
        for cid in theme.get('clusters', []):
            themed_clusters.add(cid)
    noise_mask = ~df['cluster'].isin(themed_clusters)
    if noise_mask.sum() > 0:
        noise_df = df[noise_mask]
        fig.add_trace(go.Scatter(
            x=noise_df['umap_x'], y=noise_df['umap_y'],
            mode='markers',
            marker=dict(size=3, color='#d0d0d0', opacity=0.25),
            text=[wrap_text(t[:150]) for t in noise_df['text']],
            hovertemplate='<b>Not themed</b><br>%{text}<extra></extra>',
            name='Not themed (filler/intros)',
            showlegend=True,
        ))

    # Themed points
    for tid, theme in themes.items():
        cluster_ids = theme.get('clusters', [])
        mask = df['cluster'].isin(cluster_ids)
        cluster_df = df[mask]
        if len(cluster_df) == 0:
            continue

        fig.add_trace(go.Scatter(
            x=cluster_df['umap_x'], y=cluster_df['umap_y'],
            mode='markers',
            marker=dict(
                size=7,
                color=color_map.get(tid, '#888'),
                opacity=0.75,
                line=dict(width=0.5, color='#fff'),
            ),
            text=[wrap_text(t[:200]) for t in cluster_df['text']],
            customdata=np.stack([
                cluster_df['program'].values,
                cluster_df['speaker'].values,
            ], axis=-1),
            hovertemplate=(
                '<b>%{customdata[0]}</b> · %{customdata[1]}<br>'
                '%{text}<extra>' + theme['label'] + '</extra>'
            ),
            name=theme['label'],
        ))

    fig.update_layout(**base_layout(
        title='Theme Map: All Student Utterances by Semantic Similarity',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        legend=dict(
            font=dict(size=10),
            bgcolor='rgba(255,255,255,0.95)',
            bordercolor='#e5e5e5',
            borderwidth=1,
        ),
        height=700,
    ))

    save_plotly(fig, 'theme_scatter')


def theme_network_viz(themes, cluster_to_theme):
    """Theme co-occurrence network using curated theme names."""
    print("Generating theme co-occurrence network...")

    # Load raw network data and remap to curated themes
    with open(DATA_DIR / "theme_network.json") as f:
        raw_network = json.load(f)

    # Build aggregated network with curated theme names
    from collections import defaultdict
    edge_weights = defaultdict(int)
    node_sizes = defaultdict(int)

    for node in raw_network['nodes']:
        cid = node['id']
        if cid in cluster_to_theme:
            tid = cluster_to_theme[cid]['theme_id']
            node_sizes[tid] += node['size']

    for edge in raw_network['edges']:
        src = edge['source']
        tgt = edge['target']
        if src in cluster_to_theme and tgt in cluster_to_theme:
            src_tid = cluster_to_theme[src]['theme_id']
            tgt_tid = cluster_to_theme[tgt]['theme_id']
            if src_tid != tgt_tid:
                key = tuple(sorted([src_tid, tgt_tid]))
                edge_weights[key] += edge['weight']

    if not node_sizes:
        print("  No network to visualize")
        return

    G = nx.Graph()
    for tid in node_sizes:
        G.add_node(tid, label=themes[tid]['label'], size=node_sizes[tid])
    for (u, v), w in edge_weights.items():
        G.add_edge(u, v, weight=w)

    pos = nx.spring_layout(G, k=2.5, seed=42)

    theme_ids = list(themes.keys())
    color_map = {tid: THEME_COLORS[i % len(THEME_COLORS)] for i, tid in enumerate(theme_ids)}

    fig = go.Figure()
    max_weight = max(edge_weights.values()) if edge_weights else 1

    for (u, v), w in edge_weights.items():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        width = 1 + 5 * (w / max_weight)
        opacity = 0.15 + 0.5 * (w / max_weight)
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            mode='lines',
            line=dict(width=width, color=f'rgba(150,150,150,{opacity})'),
            showlegend=False,
            hoverinfo='skip',
        ))

    node_x = [pos[n][0] for n in G.nodes()]
    node_y = [pos[n][1] for n in G.nodes()]
    node_sizes_list = [G.nodes[n]['size'] for n in G.nodes()]
    node_labels = [G.nodes[n]['label'] for n in G.nodes()]
    node_colors = [color_map.get(n, '#888') for n in G.nodes()]
    max_size = max(node_sizes_list) if node_sizes_list else 1

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        marker=dict(
            size=[18 + 35 * (s / max_size) for s in node_sizes_list],
            color=node_colors,
            line=dict(width=2, color='#fff'),
        ),
        text=[l[:30] for l in node_labels],
        textposition='top center',
        textfont=dict(size=10),
        hovertemplate=['<b>%s</b><br>%d utterances<extra></extra>' % (l, s)
                       for l, s in zip(node_labels, node_sizes_list)],
        showlegend=False,
    ))

    fig.update_layout(**base_layout(
        title='Theme Co-occurrence Network',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=600,
    ))

    save_plotly(fig, 'theme_network')


def sentiment_arcs_viz(arcs):
    """Sentiment arcs with better hover showing actual quotes."""
    print("Generating sentiment arcs...")

    fig = make_subplots(
        rows=len(arcs), cols=1,
        subplot_titles=[f'{prog} Session' for prog in arcs.keys()],
        shared_xaxes=False,
        vertical_spacing=0.06,
    )

    for i, (program, arc) in enumerate(arcs.items(), 1):
        ts = arc['timestamps']
        minutes = [t / 60 for t in ts]

        # Build hover text showing quote + sentiment
        hover_texts = []
        for j, text in enumerate(arc['texts']):
            sent = arc['sentiment_raw'][j]
            short = text[:200]
            if len(text) > 200:
                last_space = short.rfind(' ')
                if last_space > 100:
                    short = short[:last_space] + '...'
            hover_texts.append(
                f"<b>Sentiment: {sent:.2f}</b><br>{wrap_text(short)}"
            )

        fig.add_trace(go.Scatter(
            x=minutes,
            y=arc['sentiment_raw'],
            mode='markers',
            marker=dict(
                size=5,
                color=[PROGRAM_COLORS.get(program, '#888')] * len(minutes),
                opacity=0.4,
            ),
            showlegend=False,
            hovertemplate='%{text}<extra></extra>',
            text=hover_texts,
        ), row=i, col=1)

        fig.add_trace(go.Scatter(
            x=minutes,
            y=arc['sentiment_rolling'],
            mode='lines',
            line=dict(width=2.5, color=PROGRAM_COLORS.get(program, '#333')),
            showlegend=False,
            hoverinfo='skip',
        ), row=i, col=1)

        fig.add_hline(y=0, line_dash='dot', line_color='#ccc', row=i, col=1)

    fig.update_layout(**base_layout(
        title='Sentiment Arcs: Emotional Trajectory Through Each Session',
        height=250 * len(arcs),
    ))
    for i in range(1, len(arcs) + 1):
        fig.update_xaxes(title_text='Minutes into session', row=i, col=1)
        fig.update_yaxes(title_text='Sentiment', range=[-1, 1], row=i, col=1)

    save_plotly(fig, 'sentiment_arcs')


def cross_program_heatmap(df, themes, cluster_to_theme):
    """Programs x curated themes heatmap."""
    print("Generating cross-program heatmap...")

    theme_ids = list(themes.keys())
    theme_labels = [themes[tid]['label'] for tid in theme_ids]

    matrix = []
    hover_texts = []
    for program in PROGRAMS:
        row = []
        hover_row = []
        for tid in theme_ids:
            cluster_ids = themes[tid].get('clusters', [])
            mask = df['cluster'].isin(cluster_ids) & (df['program'] == program)
            count = mask.sum()
            row.append(count)
            if count > 0:
                sample = df.loc[mask, 'text'].iloc[0]
                short = sample[:150]
                if len(sample) > 150:
                    short = short[:short.rfind(' ')] + '...'
                hover_row.append(f'{program}: {themes[tid]["label"]}<br>{count} turns<br>"{wrap_text(short)}"')
            else:
                hover_row.append(f'{program}: {themes[tid]["label"]}<br>0 turns')
        matrix.append(row)
        hover_texts.append(hover_row)

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=theme_labels,
        y=PROGRAMS,
        hovertext=hover_texts,
        hovertemplate='%{hovertext}<extra></extra>',
        colorscale=[[0, '#f0f0f0'], [0.5, '#6366f1'], [1, '#1e1b4b']],
        showscale=True,
        colorbar=dict(title='Turns', len=0.5),
    ))

    fig.update_layout(**base_layout(
        title='Theme Distribution Across Programs',
        xaxis=dict(tickangle=45, tickfont=dict(size=9)),
        yaxis=dict(tickfont=dict(size=11)),
        height=420,
    ))

    save_plotly(fig, 'cross_program_heatmap')


def sentiment_violin(themes):
    """Violin plots using curated theme sentiment data."""
    print("Generating sentiment violin plots...")

    with open(DATA_DIR / "theme_sentiment.json") as f:
        raw_sentiment = json.load(f)

    fig = go.Figure()
    theme_ids = list(themes.keys())
    color_map = {tid: THEME_COLORS[i % len(THEME_COLORS)] for i, tid in enumerate(theme_ids)}

    for tid, theme in themes.items():
        # Aggregate sentiments from component clusters
        all_sentiments = []
        for cid in theme.get('clusters', []):
            cid_str = str(cid)
            if cid_str in raw_sentiment:
                all_sentiments.extend(raw_sentiment[cid_str].get('sentiments', []))

        if not all_sentiments:
            continue

        fig.add_trace(go.Violin(
            y=all_sentiments,
            name=theme['label'][:30],
            box_visible=True,
            meanline_visible=True,
            line_color=color_map.get(tid, '#333'),
            fillcolor=color_map.get(tid, '#e5e5e5'),
            opacity=0.5,
        ))

    fig.update_layout(**base_layout(
        title='Sentiment Distribution by Theme',
        yaxis_title='Sentiment (VADER compound)',
        xaxis=dict(tickangle=45, tickfont=dict(size=9)),
        height=500,
        showlegend=False,
    ))

    save_plotly(fig, 'sentiment_violin')


def program_radar(df, themes):
    """Radar charts using curated themes."""
    print("Generating program radar charts...")

    theme_ids = list(themes.keys())
    theme_labels = [themes[tid]['label'][:20] for tid in theme_ids]

    fig = go.Figure()

    for program in PROGRAMS:
        prog_total = (df['program'] == program).sum()
        if prog_total == 0:
            continue

        values = []
        for tid in theme_ids:
            cluster_ids = themes[tid].get('clusters', [])
            mask = df['cluster'].isin(cluster_ids) & (df['program'] == program)
            values.append(mask.sum() / prog_total * 100)

        fig.add_trace(go.Scatterpolar(
            r=values + [values[0]],
            theta=theme_labels + [theme_labels[0]],
            name=program,
            line=dict(color=PROGRAM_COLORS.get(program, '#888'), width=2),
            fill='toself',
            opacity=0.5,
        ))

    fig.update_layout(**base_layout(
        title='Relative Theme Emphasis by Program',
        polar=dict(
            bgcolor=BG_COLOR,
            radialaxis=dict(visible=True, gridcolor=GRID_COLOR),
            angularaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(size=9)),
        ),
        height=600,
    ))

    save_plotly(fig, 'program_radar')


def generate_wordclouds(program_keywords):
    """Generate per-program word clouds."""
    print("Generating word clouds...")

    out_dir = DATA_DIR / "img"
    out_dir.mkdir(parents=True, exist_ok=True)

    for program, keywords in program_keywords.items():
        freq = {kw: score for kw, score in keywords if score > 0}
        if not freq:
            continue

        wc = WordCloud(
            width=800, height=400,
            background_color='white',
            color_func=lambda *args, **kwargs: PROGRAM_COLORS.get(program, '#333333'),
            prefer_horizontal=0.7,
            max_words=60,
            relative_scaling=0.5,
        )
        wc.generate_from_frequencies(freq)

        fig, ax = plt.subplots(1, 1, figsize=(10, 5))
        ax.imshow(wc, interpolation='bilinear')
        ax.axis('off')
        fig.savefig(str(out_dir / f"wordcloud_{program}.png"), dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close(fig)
        print(f"  Saved wordcloud_{program}.png")


def main():
    df = pd.read_csv(DATA_DIR / "student_turns_sentiment.csv")
    themes, cluster_to_theme = load_curated_themes()

    with open(DATA_DIR / "sentiment_arcs.json") as f:
        arcs = json.load(f)
    with open(DATA_DIR / "program_keywords.json") as f:
        program_keywords = json.load(f)

    theme_scatter(df, themes, cluster_to_theme)
    theme_network_viz(themes, cluster_to_theme)
    sentiment_arcs_viz(arcs)
    cross_program_heatmap(df, themes, cluster_to_theme)
    sentiment_violin(themes)
    program_radar(df, themes)
    generate_wordclouds(program_keywords)

    print("\nAll visualizations generated!")


if __name__ == "__main__":
    main()

"""Build the complete static website from analysis outputs and templates."""

import json
import shutil
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader

from utils import DATA_DIR, SITE_DIR, TEMPLATE_DIR, STATIC_DIR, PROGRAMS

CHARTS_DIR = DATA_DIR / "charts"


def load_chart_html(name):
    path = CHARTS_DIR / f"{name}.html"
    if path.exists():
        return path.read_text()
    return f'<p>Chart "{name}" not found.</p>'


def build_program_sentiment_arc(arcs, program):
    if program not in arcs:
        return '<p>No sentiment arc data.</p>'
    arc = arcs[program]
    minutes = [t / 60 for t in arc['timestamps']]
    PROGRAM_COLORS = {'MPP1': '#2563eb', 'MCMPA': '#dc2626', 'MPAID': '#059669', 'MIXED': '#d97706', 'MPP2': '#7c3aed'}

    hover_texts = []
    for j, text in enumerate(arc['texts']):
        sent = arc['sentiment_raw'][j]
        short = text[:200]
        if len(text) > 200:
            last_space = short.rfind(' ')
            if last_space > 100:
                short = short[:last_space] + '...'
        hover_texts.append(f"<b>Sentiment: {sent:.2f}</b><br>{short}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=minutes, y=arc['sentiment_raw'],
        mode='markers',
        marker=dict(size=5, color=PROGRAM_COLORS.get(program, '#888'), opacity=0.4),
        text=hover_texts,
        hovertemplate='%{text}<extra></extra>',
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=minutes, y=arc['sentiment_rolling'],
        mode='lines',
        line=dict(width=2.5, color=PROGRAM_COLORS.get(program, '#333')),
        showlegend=False,
        hoverinfo='skip',
    ))
    fig.add_hline(y=0, line_dash='dot', line_color='#ccc')
    fig.update_layout(
        template='plotly_white',
        font=dict(family='Inter, sans-serif', color='#111', size=13),
        paper_bgcolor='#fff', plot_bgcolor='#fff',
        margin=dict(l=50, r=30, t=30, b=50),
        xaxis_title='Minutes into session',
        yaxis_title='Sentiment',
        yaxis=dict(range=[-1, 1]),
        height=300,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, config={'displayModeBar': False})


def main():
    df = pd.read_csv(DATA_DIR / "student_turns_sentiment.csv")

    themes_path = DATA_DIR / "themes.json"
    if not themes_path.exists():
        themes_path = DATA_DIR / "draft_themes.json"
    with open(themes_path) as f:
        themes = json.load(f)

    with open(DATA_DIR / "vivid_quotes.json") as f:
        vivid = json.load(f)
    with open(DATA_DIR / "sentiment_arcs.json") as f:
        arcs = json.load(f)
    with open(DATA_DIR / "program_keywords.json") as f:
        program_keywords = json.load(f)

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "themes").mkdir(exist_ok=True)
    (SITE_DIR / "programs").mkdir(exist_ok=True)

    static_dest = SITE_DIR / "static"
    if static_dest.exists():
        shutil.rmtree(static_dest)
    shutil.copytree(str(STATIC_DIR), str(static_dest))

    img_dest = SITE_DIR / "static" / "img"
    img_dest.mkdir(exist_ok=True)
    img_src = DATA_DIR / "img"
    if img_src.exists():
        for img_file in img_src.glob("*.png"):
            shutil.copy2(str(img_file), str(img_dest / img_file.name))

    year = datetime.now().year

    def ctx(static_prefix='static/', root='', **extra):
        c = {'year': year, 'static_prefix': static_prefix, 'root': root}
        c.update(extra)
        return c

    # ==================== INDEX PAGE ====================
    print("Building index.html...")

    sorted_themes_list = sorted(themes.items(), key=lambda x: x[1]['size'], reverse=True)

    # Key findings with FULL descriptions and multiple quotes (no truncation)
    key_findings = []
    for tid, theme in sorted_themes_list:
        key_findings.append({
            'id': tid,
            'label': theme['label'],
            'description': theme['description'],
            'quotes': theme.get('curated_quotes', [])[:5],
        })

    positive_quotes = [
        {'text': 'It oftentimes exceeded my expectations in terms of rigor and also coherence between the different classes. I\'ve been really impressed by the rigor, maybe too much at times where the pace has been difficult to manage.', 'program': 'MPAID', 'note': 'On the MPAID core'},
        {'text': 'My experience with my professors here has been deeply inspiring. No matter whatever priorities they had, they treated me, their students, as their top priority.', 'program': 'MCMPA', 'note': 'On faculty investment'},
        {'text': 'The fact that no one really uses their phones, everyone is paying attention, almost everyone comes prepared. In fact, there is the social pressure that if you don\'t prepare, you\'ll be found out, which I think is great.', 'program': 'MPP1', 'note': 'Positive take on peer accountability'},
    ]

    tpl = env.get_template("index.html")
    html = tpl.render(
        **ctx(title="Overview"),
        n_themes=len(themes),
        n_programs=len(PROGRAMS),
        key_findings=key_findings,
        positive_quotes=positive_quotes,
        theme_scatter_html=load_chart_html('theme_scatter'),
        heatmap_html=load_chart_html('cross_program_heatmap'),
    )
    (SITE_DIR / "index.html").write_text(html)

    # ==================== THEMES INDEX ====================
    print("Building themes/index.html...")
    tpl = env.get_template("themes_index.html")

    # Low-frequency items with GROUPED quotes (for toggle)
    low_freq = [
        {
            'quotes': [
                {'text': 'Sometimes class discussions are like simulacra of discussion rather than actual discussion. It\'s clear what you\'re not allowed to say.', 'program': 'MCMPA'},
                {'text': 'I noticed that there\'s not much disagreement with what students are saying, even if something might be factually incorrect or questionable.', 'program': 'MPP1', 'note': 'On lack of pushback'},
                {'text': 'Instructor pushback, maybe. People aren\'t being challenged in the sense of their ideas being challenged.', 'program': 'MPP1', 'note': 'Ideas going unchallenged'},
                {'text': 'If basic inaccuracy is allowed to stand in a classroom, you\'re robbing that person of the opportunity to learn, you\'re robbing the entire class as well. If we don\'t uphold each other to a certain level of intellectual rigor, the classroom becomes a poorer place intellectually.', 'program': 'MPP1', 'note': 'On intellectual standards'},
            ],
            'why': 'Multiple students across programs describe a classroom culture where factual inaccuracies go uncorrected and dissenting views are self-censored. If students perceive unspoken limits on what can be said, the democratic classroom culture may be more constrained than faculty realize. This potentially challenges a core assumption about HKS pedagogy.',
            'discussion_question': 'Are there systematic patterns in which topics or perspectives students feel they cannot raise? Do professors have the tools and incentives to push back on inaccurate claims in discussion?',
        },
        {
            'quotes': [
                {'text': 'People should fail more classes. There\'s this very strong aversion in the culture to people being able to fail. Graduating students who put in very little effort damages the brand.', 'program': 'MPP2'},
                {'text': 'The people that are doing that work and showing up at class, and then they get worse grades than the kids that they know didn\'t read a single thing. That just erodes all of the structure of how the educational compact should be.', 'program': 'MIXED', 'note': 'On effort not being rewarded'},
            ],
            'why': 'These comments directly challenge the de facto grade distribution. If students perceive that effort is not meaningfully rewarded or penalized, it undermines the educational compact and potentially signals to employers that the degree does not differentiate.',
            'discussion_question': 'What is the actual grade distribution at HKS, and does it reflect genuine differentiation in student performance?',
        },
        {
            'quotes': [
                {'text': 'I don\'t know if I can say I am a public administration professional.', 'program': 'MIXED', 'note': 'MPA dual degree on career identity'},
                {'text': 'For structural reasons, I am not leaving this school with the complete toolkit in terms of policy that I was hoping to have.', 'program': 'MCMPA', 'note': 'MCMPA on career readiness'},
            ],
            'why': 'If students completing their degrees cannot articulate a professional identity or feel their toolkit is incomplete, this is a signal about program design, not individual student preparation.',
            'discussion_question': 'Are students graduating with a clear professional identity and actionable skills? What would need to change for that to be consistently true?',
        },
    ]

    html = tpl.render(
        **ctx(static_prefix='../static/', root='../', title="Themes"),
        n_themes=len(themes),
        themes=themes,
        themes_sorted=sorted_themes_list,
        network_html=load_chart_html('theme_network'),
        low_frequency_items=low_freq,
    )
    (SITE_DIR / "themes" / "index.html").write_text(html)

    # ==================== THEME DETAIL PAGES ====================
    print("Building theme detail pages...")
    tpl = env.get_template("theme_detail.html")
    for tid, theme in themes.items():
        html = tpl.render(
            **ctx(static_prefix='../static/', root='../', title=theme['label']),
            theme=theme,
        )
        (SITE_DIR / "themes" / f"{tid}.html").write_text(html)

    # ==================== PROGRAMS INDEX ====================
    print("Building programs/index.html...")
    tpl = env.get_template("programs_index.html")

    program_infos = []
    for program in PROGRAMS:
        mask = df['program'] == program
        if mask.sum() == 0:
            continue
        program_infos.append({
            'id': program,
            'n_turns': int(mask.sum()),
            'mean_sentiment': float(df.loc[mask, 'sentiment_compound'].mean()),
        })

    html = tpl.render(
        **ctx(static_prefix='../static/', root='../', title="Programs"),
        programs=program_infos,
        heatmap_html=load_chart_html('cross_program_heatmap'),
        radar_html=load_chart_html('program_radar'),
    )
    (SITE_DIR / "programs" / "index.html").write_text(html)

    # ==================== PROGRAM DETAIL PAGES ====================
    print("Building program detail pages...")
    tpl = env.get_template("program_detail.html")

    for program in PROGRAMS:
        mask = df['program'] == program
        if mask.sum() == 0:
            continue
        prog_df = df[mask]

        top_themes = []
        for tid, theme in themes.items():
            cluster_ids = theme.get('clusters', [])
            count = prog_df['cluster'].isin(cluster_ids).sum()
            if count > 0:
                sample = ''
                for q in theme.get('curated_quotes', []):
                    if q['program'] == program:
                        sample = q['text']
                        break
                if not sample:
                    prog_cluster_df = prog_df[prog_df['cluster'].isin(cluster_ids)]
                    if len(prog_cluster_df) > 0:
                        sample = prog_cluster_df['text'].iloc[0]
                top_themes.append({
                    'id': tid,
                    'label': theme['label'],
                    'count': count,
                    'sample_quote': sample,
                })
        top_themes.sort(key=lambda x: x['count'], reverse=True)

        arc_html = build_program_sentiment_arc(arcs, program)
        kws = program_keywords.get(program, [])

        html = tpl.render(
            **ctx(static_prefix='../static/', root='../', title=program),
            program_id=program,
            n_turns=int(mask.sum()),
            total_words=int(prog_df['word_count'].sum()),
            mean_sentiment=float(prog_df['sentiment_compound'].mean()),
            sentiment_arc_html=arc_html,
            top_themes=top_themes[:10],
            keywords=kws[:20],
        )
        (SITE_DIR / "programs" / f"{program.lower()}.html").write_text(html)

    # ==================== SENTIMENT PAGE ====================
    print("Building sentiment.html...")
    tpl = env.get_template("sentiment.html")

    total = len(df)
    pct_pos = (df['sentiment_label'] == 'positive').sum() / total
    pct_neg = (df['sentiment_label'] == 'negative').sum() / total
    pct_neu = (df['sentiment_label'] == 'neutral').sum() / total

    # Get substantive positive/negative quotes (not filler)
    # Filter to turns with enough substance (>15 words)
    substantive = df[df['word_count'] > 15].copy()

    top_pos = substantive.nlargest(15, 'sentiment_compound')
    top_neg = substantive.nsmallest(15, 'sentiment_compound')

    # Deduplicate against curated quotes used elsewhere
    used_quotes = set()
    for tid, theme in themes.items():
        for q in theme.get('curated_quotes', []):
            used_quotes.add(q['text'][:50])

    def make_quote_list(quote_df, limit=8):
        quotes = []
        for _, row in quote_df.iterrows():
            text = str(row['text'])
            if text[:50] in used_quotes:
                continue
            # Smart truncation: get the substantive part
            if len(text) > 300:
                # Find a good break point
                break_point = text[:300].rfind('.')
                if break_point > 150:
                    text = text[:break_point + 1]
                else:
                    break_point = text[:300].rfind(',')
                    if break_point > 200:
                        text = text[:break_point] + '...'
                    else:
                        text = text[:300] + '...'
            quotes.append({
                'text': text,
                'program': row['program'],
                'speaker': row['speaker'],
                'sentiment': float(row['sentiment_compound']),
            })
            if len(quotes) >= limit:
                break
        return quotes

    all_positive = make_quote_list(top_pos)
    all_negative = make_quote_list(top_neg)

    prog_sent = {}
    for program in PROGRAMS:
        mask = df['program'] == program
        if mask.sum() > 0:
            prog_sent[program] = {
                'mean': float(df.loc[mask, 'sentiment_compound'].mean()),
                'count': int(mask.sum()),
            }

    html = tpl.render(
        **ctx(title="Sentiment"),
        pct_positive=pct_pos,
        pct_neutral=pct_neu,
        pct_negative=pct_neg,
        arcs_html=load_chart_html('sentiment_arcs'),
        violin_html=load_chart_html('sentiment_violin'),
        top_positive=all_positive,
        top_negative=all_negative,
        program_sentiment=prog_sent,
    )
    (SITE_DIR / "sentiment.html").write_text(html)

    # ==================== ACTION ITEMS PAGE ====================
    print("Building action-items.html...")
    tpl = env.get_template("action_items.html")

    # Non-redundant action items: focus on things needing follow-up
    # that are NOT already well-covered in theme pages
    action_items = [
        {
            'theme_label': 'Intellectual Pushback in Discussions',
            'program': 'MPP1, MCMPA',
            'quote': 'If basic inaccuracy is allowed to stand in a classroom, you\'re robbing that person of the opportunity to learn, you\'re robbing the entire class as well.',
            'context': 'Multiple students described professors not correcting factual errors or pushing back on weak arguments in discussion. This was framed as both a rigor issue and a missed learning opportunity. The concern is too vague to act on without knowing which courses and what kinds of inaccuracies are at stake.',
            'follow_up': 'Suggest Maria or SLATE follow up to gather particular examples of discussions where factual inaccuracies went uncorrected (without citing specific students or professors) so the task force can understand the scope and develop guidance for discussion facilitation.',
        },
        {
            'theme_label': 'Career Readiness and Professional Identity',
            'program': 'MCMPA, MIXED',
            'quote': 'For structural reasons, I am not leaving this school with the complete toolkit in terms of policy that I was hoping to have.',
            'context': 'Several students (especially MCMPAs and MPA dual degrees) expressed doubt about whether their degree is preparing them for specific professional roles. This goes beyond course content to program identity.',
            'follow_up': 'Suggest Maria or SLATE follow up to gather more specific information about which skills or competencies students feel are missing, so the task force can assess whether this reflects gaps in curriculum, advising, or career support.',
        },
        {
            'theme_label': 'Discussion Domination',
            'program': 'MCMPA',
            'quote': 'Oftentimes there\'s one or two people who take up the entirety of the class. In 75 percent of my classes, I\'ve experienced this.',
            'context': 'This is distinct from the participation/class size issue. Even in well-sized classes, students describe a pattern where a small number of peers dominate discussion while professors do not intervene.',
            'follow_up': 'Suggest Maria or SLATE follow up to understand what professors currently do (or do not do) to manage discussion equity, so the task force can assess whether faculty development resources address this.',
        },
        {
            'theme_label': 'AI in Coursework',
            'program': 'MPP2, MIXED',
            'quote': 'Students who are using AI in ways that are patently obvious and professors find it really hard because the disciplinary process is challenging.',
            'context': 'AI use in assignments came up in multiple groups but was not deeply explored. Students perceive inconsistent policies and enforcement. This is likely to intensify.',
            'follow_up': 'This warrants its own dedicated investigation. Suggest a targeted survey or working group on AI policies, student expectations, and faculty capacity to address AI-assisted work.',
        },
    ]

    html = tpl.render(
        **ctx(title="Action Items"),
        action_items=action_items,
        general_recommendations=[],
    )
    (SITE_DIR / "action-items.html").write_text(html)

    # ==================== METHODOLOGY PAGE ====================
    print("Building methodology.html...")
    tpl = env.get_template("methodology.html")
    html = tpl.render(**ctx(title="Methodology"))
    (SITE_DIR / "methodology.html").write_text(html)

    print(f"\nSite built at {SITE_DIR}")
    print(f"Pages: {len(list(SITE_DIR.rglob('*.html')))} HTML files")


if __name__ == "__main__":
    main()

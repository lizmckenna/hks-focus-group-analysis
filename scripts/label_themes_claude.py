"""Improve theme labels by analyzing cluster content more carefully.

Uses heuristic analysis of quotes and keywords to generate
descriptive theme names. No external API calls needed.
"""

import json
import re
from collections import Counter
from utils import DATA_DIR


STOP_WORDS = {
    'like', 'think', 'know', 'just', 'yeah', 'okay', 'right', 'really',
    'going', 'thing', 'things', 'want', 'say', 'said', 'lot', 'kind',
    'actually', 'also', 'something', 'much', 'way', 'good', 'one',
    'would', 'could', 'get', 'got', 'make', 'well', 'even', 'still',
    'mean', 'sure', 'come', 'feel', 'don', 'doesn', 'didn', 've',
    'maybe', 'pretty', 'little', 'big', 'sort', 'guess', 'basically',
    'obviously', 'definitely', 'probably', 'especially', 'thank',
    'sorry', 'yes', 'oh', 'yeah', 'hmm', 'okay', 'hi', 'hello',
    'the', 'and', 'that', 'this', 'but', 'for', 'not', 'you', 'are',
    'was', 'were', 'with', 'have', 'has', 'had', 'been', 'can', 'will',
    'all', 'they', 'them', 'their', 'there', 'from', 'what', 'when',
    'who', 'which', 'how', 'some', 'very', 'more', 'than', 'into',
    'only', 'each', 'about', 'being', 'here', 'then', 'name', 'its',
    'because', 'though', 'through', 'too', 'many', 'those', 'these',
    'other', 'same', 'both', 'own', 'such', 'after', 'before',
    'where', 'why', 'does', 'did', 'doing', 'done', 'let', 'our',
}


def extract_meaningful_keywords(texts, n=10):
    """Extract keywords, filtering out conversational filler."""
    words = Counter()
    bigrams = Counter()

    for text in texts:
        text = re.sub(r'\[NAME\]', '', text.lower())
        tokens = re.findall(r'\b[a-z]{3,}\b', text)
        meaningful = [t for t in tokens if t not in STOP_WORDS]
        words.update(meaningful)

        for i in range(len(meaningful) - 1):
            bigrams[f"{meaningful[i]} {meaningful[i+1]}"] += 1

    # Combine unigrams and bigrams, preferring bigrams
    combined = {}
    for bg, count in bigrams.most_common(20):
        if count >= 2:
            combined[bg] = count * 2  # boost bigrams
    for w, count in words.most_common(30):
        if w not in combined:
            combined[w] = count

    sorted_kw = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in sorted_kw[:n]]


def infer_theme_label(keywords, quotes):
    """Infer a descriptive theme label from keywords and quotes."""
    kw_set = set(keywords[:8])
    quote_text = ' '.join(quotes[:5]).lower()

    # Pattern matching for common academic themes
    patterns = [
        (['professor', 'feedback', 'grading'], 'Professor Feedback & Grading Practices'),
        (['feedback', 'course', 'evaluation'], 'Course Evaluation & Feedback Systems'),
        (['feedback', 'professor'], 'Quality of Instructor Feedback'),
        (['grade', 'grading', 'evaluation'], 'Grading & Evaluation Concerns'),
        (['evaluate', 'grade', 'evaluation'], 'Grading & Evaluation Concerns'),
        (['participation', 'class', 'discussion'], 'Classroom Participation & Discussion'),
        (['participation', 'grade'], 'Participation Grading'),
        (['cold', 'calling', 'call'], 'Cold Calling & Classroom Dynamics'),
        (['reading', 'readings', 'course'], 'Course Readings & Materials'),
        (['core', 'courses', 'curriculum'], 'Core Curriculum Experience'),
        (['core', 'mpaid'], 'Core Curriculum & MPAID Experience'),
        (['class', 'classes', 'teaching'], 'Teaching Quality & Classroom Experience'),
        (['rigor', 'standards', 'expectations'], 'Academic Rigor & Standards'),
        (['professor', 'office', 'hours'], 'Faculty Accessibility & Office Hours'),
        (['community', 'students', 'peers'], 'Student Community & Peer Learning'),
        (['career', 'professional', 'skills'], 'Career & Professional Development'),
        (['diverse', 'diversity', 'perspectives'], 'Diversity of Perspectives'),
        (['international', 'students'], 'International Student Experience'),
        (['mpaid', 'hometown', 'hello'], 'Introductions & Background'),
        (['phone', 'rule', 'rules'], 'Classroom Rules & Phone Policies'),
        (['vote', 'votes'], 'Voting & Decision Exercises'),
    ]

    for required_kws, label in patterns:
        if sum(1 for kw in required_kws if any(kw in k for k in kw_set)) >= 2:
            return label

    # Fallback: build from top keywords
    top = [k for k in keywords[:3] if len(k) > 3]
    if top:
        return ' & '.join(w.title() for w in top[:2])

    return 'General Discussion'


def main():
    with open(DATA_DIR / "draft_themes.json") as f:
        themes = json.load(f)

    print("Improving theme labels...\n")

    for tid, theme in themes.items():
        quotes = [q['text'] for q in theme['representative_quotes']]
        meaningful_kw = extract_meaningful_keywords(quotes)
        label = infer_theme_label(meaningful_kw, quotes)

        # Build a better description from actual quotes
        snippet = quotes[0][:150] if quotes else ''
        desc = f"Students discuss {label.lower()}. Example: \"{snippet}...\""

        theme['label'] = label
        theme['description'] = desc
        theme['keywords'] = meaningful_kw + theme['keywords']

        print(f"  [{tid}] {label}")
        print(f"       Keywords: {', '.join(meaningful_kw[:5])}")

    with open(DATA_DIR / "draft_themes.json", 'w') as f:
        json.dump(themes, f, indent=2)

    # Also save as themes.json (the "final" version)
    with open(DATA_DIR / "themes.json", 'w') as f:
        json.dump(themes, f, indent=2)

    print(f"\nSaved improved themes to {DATA_DIR / 'draft_themes.json'}")


if __name__ == "__main__":
    main()

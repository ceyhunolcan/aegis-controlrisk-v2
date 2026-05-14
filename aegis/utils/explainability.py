# Turning component dicts into one-liner narrative for memos / dashboard.


def _humanize(snake):
    return snake.replace("_", " ").strip().title()


def explain_components(components, top_n=4):
    if not components:
        return []
    pairs = []
    for k, v in components.items():
        try:
            pairs.append((k, float(v)))
        except (TypeError, ValueError):
            continue
    pairs.sort(key=lambda x: -x[1])
    return [f"{_humanize(k)}: {v:.1f}/100" for k, v in pairs[:top_n]]


def label_for_score(score, mapping):
    """Pick a label by walking thresholds in descending order. eg
    {"Critical": 80, "High": 65, "Moderate": 45, "Low": 0}"""
    if not mapping:
        return "Unknown"
    items = sorted(mapping.items(), key=lambda x: -x[1])
    for label, threshold in items:
        if score >= threshold:
            return label
    return items[-1][0]

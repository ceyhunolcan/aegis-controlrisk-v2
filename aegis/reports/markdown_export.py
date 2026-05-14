# Helper for dumping arbitrary analysis sub-dicts as markdown. The Streamlit
# app uses this for the "raw data" tabs. Recursive but bounded.
from pathlib import Path


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 100 else f"{v:,.1f}"
    return str(v)


def dict_to_markdown(d, heading_level=2, max_depth=5):
    if max_depth <= 0:
        return f"_(depth limit; type={type(d).__name__})_"

    if isinstance(d, dict):
        # scalar leaves first, then nested keys as sub-headings
        scalars = {k: v for k, v in d.items() if not isinstance(v, (dict, list))}
        nested  = {k: v for k, v in d.items() if isinstance(v, (dict, list))}

        out = []
        if scalars:
            out.extend(f"- **{k}:** {_fmt(v)}" for k, v in scalars.items())
            out.append("")
        for k, v in nested.items():
            hashes = "#" * min(heading_level, 6)
            out.append(f"{hashes} {k}")
            out.append("")
            out.append(dict_to_markdown(v, min(heading_level + 1, 6), max_depth - 1))
            out.append("")
        return "\n".join(out).rstrip()

    if isinstance(d, list):
        if not d:
            return "_(empty list)_"
        if all(isinstance(x, dict) for x in d):
            out = []
            for i, item in enumerate(d, start=1):
                out.append(f"**Item {i}**")
                out.append("")
                out.append(dict_to_markdown(item, min(heading_level + 1, 6), max_depth - 1))
                out.append("")
            return "\n".join(out).rstrip()
        return "\n".join(f"- {_fmt(x)}" for x in d)

    return _fmt(d)


def save_markdown_report(content, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)

"""Helpers for turning pandoc's LaTeX table output into something nimeart.cls lays out well."""
import re

def brace_groups(t, i):
    """Return (groups, end) for consecutive {...} groups (and [..] options) starting at index i."""
    groups = []
    while i < len(t) and t[i] in "[{":
        if t[i] == "[":
            j = t.find("]", i); i = j + 1; continue
        depth, j = 1, i + 1
        while j < len(t) and depth:
            depth += {"{": 1, "}": -1}.get(t[j], 0); j += 1
        groups.append(t[i + 1:j - 1]); i = j
    return groups, i

def plain_words(t):
    t = re.sub(r"\\begin\{[^}]*\}|\\end\{[^}]*\}", " ", t)
    t = re.sub(r"\[[a-zA-Z0-9,=. ]*\]", " ", t)      # [t], [htbp] options
    t = re.sub(r"\\[A-Za-z]+\*?", " ", t)          # commands
    t = re.sub(r"\\\\|[&{}\[\]%@]", " ", t)          # row breaks, braces, specials
    t = re.sub(r"\(\s*-\s*\d+\s*\)\s*\*\s*[\d.]+(\s*\+\s*\d+)?", " ", t)  # leftovers of (\linewidth - 4\tabcolsep) * \real{x}
    return re.sub(r"\s+", " ", t).strip(" .;:,")

def table_caption_text(inner):
    """Text content of a pandoc longtable body, excluding images: multicolumn texts and plain cells."""
    body = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}|\\includegraphics\[[^\]]*\]\{[^}]+\}", " ", inner, flags=re.S)
    texts = []
    pos = 0
    while True:
        i = body.find("\\multicolumn", pos)
        if i < 0: break
        groups, end = brace_groups(body, i + len("\\multicolumn"))
        if groups: texts.append(plain_words(groups[-1]))
        body = body[:i] + " " + body[end:]; pos = i
    # strip remaining >{...}/p{...} specs and minipage wrappers, then take what's left
    for nm in (">", "p"):
        pos = 0
        while True:
            i = body.find(nm + "{", pos)
            if i < 0: break
            _, end = brace_groups(body, i + 1)
            body = body[:i] + " " + body[end:]; pos = i
    rest = plain_words(body)
    if rest: texts.append(rest)
    seen = []
    for t in texts:
        if t and t not in seen: seen.append(t)
    return " — ".join(seen)

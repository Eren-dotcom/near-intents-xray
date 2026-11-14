#!/usr/bin/env python3
"""Shared helpers for build_report.py: number formatting, verdict rules and inline-SVG charts."""
import datetime as dt, html, json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = json.load(open(os.path.join(ROOT, "data", "derived", "numbers.json")))
TESTS = json.load(open(os.path.join(ROOT, "thesis_tests.json")))["tests"]
INK, MUTE, LINE, BG = "#16181d", "#6b7280", "#e5e7eb", "#fbfaf7"
C1, C2, C3, GOOD, BAD, WARN = "#0b6e4f", "#c2410c", "#1d4ed8", "#0b6e4f", "#b42318", "#a16207"
e = html.escape


def usd(x, d=1):
    if x is None:
        return "n/a"
    a = abs(x)
    for lim, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= lim:
            return f"${x / lim:.{d}f}{suf}"
    return f"${x:.2f}" if a < 10 else f"${x:.0f}"


def pct(x, d=1):
    return "n/a" if x is None else f"{x * 100:.{d}f}%"


def num(x):
    return "n/a" if x is None else f"{x:,.0f}"


def ci(v, f=pct):
    return f"{f(v[0])} (95% CI {f(v[1])} to {f(v[2])})"


def short(a):
    if a and len(a) == 64:
        return a[:6] + "…" + a[-4:]
    if a and a.startswith("0x") and len(a) == 42:
        return a[:6] + "…" + a[-4:]
    return a or "?"


def dig(path):
    cur = N
    for p in path.split("."):
        cur = cur[int(p)] if isinstance(cur, list) else cur.get(p)
        if cur is None:
            return None
    return cur


def judge(t, v):
    """Apply one rule from thesis_tests.json to a value or a [point, lo, hi] triple."""
    if v is None:
        return "no data", None, None, None
    p, lo, hi = v if isinstance(v, list) else (v, v, v)
    if lo is None:
        lo = hi = p
    if t["rule"] == "between":
        if t["low"] <= lo and hi <= t["high"]:
            verdict = "supported"
        elif hi < t["low"] or lo > t["high"]:
            verdict = "contradicted"
        else:
            verdict = "inconclusive"
    else:
        th, above = t["threshold"], t["rule"] == "above"
        if (lo > th and above) or (hi < th and not above):
            verdict = "supported"
        elif (hi < th and above) or (lo > th and not above):
            verdict = "contradicted"
        else:
            verdict = "inconclusive"
    return verdict, p, lo, hi


def verdicts():
    out = []
    for t in TESTS:
        verdict, p, lo, hi = judge(t, dig(t["metric"]))
        out.append({**t, "verdict": verdict, "value": p, "lo": lo, "hi": hi})
    return out


# ---------- SVG ----------
def hbars(rows, width=560, label_w=150, fmt=pct, color=C1, xmax=None):
    """rows: [(label, point, lo, hi, title)]"""
    rh, pad = 26, 6
    h = len(rows) * rh + 24
    xmax = xmax or max([r[3] or r[1] for r in rows] + [1e-9]) * 1.08
    pw = width - label_w - 70
    s = [f'<svg viewBox="0 0 {width} {h}" role="img" class="chart">']
    for g in range(5):
        x = label_w + pw * g / 4
        s.append(f'<line x1="{x:.1f}" y1="4" x2="{x:.1f}" y2="{h - 18}" stroke="{LINE}"/>')
        s.append(f'<text x="{x:.1f}" y="{h - 4}" font-size="10" fill="{MUTE}" text-anchor="middle">{e(fmt(xmax * g / 4, 0))}</text>')
    for i, (lab, p, lo, hi, title) in enumerate(rows):
        if len(lab) > 22:
            lab = lab[:12] + "…" + lab[-8:]
        y = 4 + i * rh
        bw = max(1, pw * p / xmax)
        s.append(f'<text x="{label_w - 8}" y="{y + 15}" font-size="11.5" fill="{INK}" text-anchor="end">{e(lab)}</text>')
        s.append(f'<rect x="{label_w}" y="{y + pad}" width="{bw:.1f}" height="{rh - 2 * pad}" fill="{color}" rx="2"><title>{e(title)}</title></rect>')
        if lo is not None and hi is not None:
            x1, x2 = label_w + pw * lo / xmax, label_w + pw * min(hi, xmax) / xmax
            ym = y + rh / 2
            s.append(f'<line x1="{x1:.1f}" y1="{ym}" x2="{x2:.1f}" y2="{ym}" stroke="{INK}" stroke-width="1.2"/>'
                     f'<line x1="{x1:.1f}" y1="{ym - 4}" x2="{x1:.1f}" y2="{ym + 4}" stroke="{INK}"/>'
                     f'<line x1="{x2:.1f}" y1="{ym - 4}" x2="{x2:.1f}" y2="{ym + 4}" stroke="{INK}"/>')
        s.append(f'<text x="{width - 4}" y="{y + 15}" font-size="11" fill="{MUTE}" text-anchor="end">{e(fmt(p))}</text>')
    s.append("</svg>")
    return "".join(s)


def lines(series, labels, width=560, height=230, fmt=usd, right=None, right_fmt=None):
    """series: [(name, color, [values])] on the left axis; right: (name, color, values)."""
    L, R, T, B = 52, 52 if right else 12, 12, 34
    pw, ph = width - L - R, height - T - B
    n = len(labels)
    allv = [v for _, _, vs in series for v in vs if v is not None]
    ymax = max(allv + [1e-9]) * 1.1
    X = lambda i: L + (pw * i / max(1, n - 1))
    Y = lambda v: T + ph * (1 - v / ymax)
    s = [f'<svg viewBox="0 0 {width} {height}" role="img" class="chart">']
    for g in range(5):
        y = T + ph * g / 4
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{LINE}"/>')
        s.append(f'<text x="{L - 6}" y="{y + 3:.1f}" font-size="10" fill="{MUTE}" text-anchor="end">{e(fmt(ymax * (1 - g / 4), 0))}</text>')
    step = max(1, n // 6)
    for i in range(0, n, step):
        s.append(f'<text x="{X(i):.1f}" y="{height - 18}" font-size="10" fill="{MUTE}" text-anchor="middle">{e(labels[i][5:] if len(labels[i]) > 7 else labels[i])}</text>')

    def path(vs, yf):
        d, pen = [], False
        for i, v in enumerate(vs):
            if v is None:
                pen = False
                continue
            d.append(f'{"L" if pen else "M"}{X(i):.1f},{yf(v):.1f}')
            pen = True
        return " ".join(d)
    lx = L
    for name, color, vs in series:
        s.append(f'<path d="{path(vs, Y)}" fill="none" stroke="{color}" stroke-width="2"/>')
        s.append(f'<rect x="{lx}" y="{height - 10}" width="10" height="3" fill="{color}"/><text x="{lx + 14}" y="{height - 5}" font-size="10.5" fill="{INK}">{e(name)}</text>')
        lx += 22 + 6.2 * len(name)
    if right:
        name, color, vs = right
        vv = [v for v in vs if v is not None]
        rmax = max(vv + [1e-9]) * 1.1
        YR = lambda v: T + ph * (1 - v / rmax)
        s.append(f'<path d="{path(vs, YR)}" fill="none" stroke="{color}" stroke-width="1.6" stroke-dasharray="4 3"/>')
        for g in range(5):
            y = T + ph * g / 4
            s.append(f'<text x="{L + pw + 6}" y="{y + 3:.1f}" font-size="10" fill="{color}">{e((right_fmt or fmt)(rmax * (1 - g / 4), 0))}</text>')
        s.append(f'<rect x="{lx}" y="{height - 10}" width="10" height="3" fill="{color}"/><text x="{lx + 14}" y="{height - 5}" font-size="10.5" fill="{INK}">{e(name)} (right axis, dashed)</text>')
    s.append("</svg>")
    return "".join(s)


def cols(labels, vals, width=560, height=200, fmt=usd, color=C1, line=None, line_fmt=None, line_name=""):
    L, R, T, B = 52, 46 if line else 12, 12, 34
    pw, ph = width - L - R, height - T - B
    n = len(vals)
    ymax = max(vals + [1e-9]) * 1.1
    bw = pw / n
    s = [f'<svg viewBox="0 0 {width} {height}" role="img" class="chart">']
    for g in range(5):
        y = T + ph * g / 4
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{LINE}"/>')
        s.append(f'<text x="{L - 6}" y="{y + 3:.1f}" font-size="10" fill="{MUTE}" text-anchor="end">{e(fmt(ymax * (1 - g / 4), 0))}</text>')
    for i, v in enumerate(vals):
        hh = ph * v / ymax
        s.append(f'<rect x="{L + i * bw + 1:.1f}" y="{T + ph - hh:.1f}" width="{max(1, bw - 2):.1f}" height="{hh:.1f}" fill="{color}"><title>{e(labels[i])}: {e(fmt(v))}</title></rect>')
    step = max(1, n // 8)
    for i in range(0, n, step):
        s.append(f'<text x="{L + i * bw + bw / 2:.1f}" y="{height - 18}" font-size="10" fill="{MUTE}" text-anchor="middle">{e(labels[i])}</text>')
    if line:
        vv = [v for v in line if v is not None]
        rmax = max(vv + [1e-9]) * 1.15
        d, pen = [], False
        for i, v in enumerate(line):
            if v is None:
                pen = False
                continue
            d.append(f'{"L" if pen else "M"}{L + i * bw + bw / 2:.1f},{T + ph * (1 - v / rmax):.1f}')
            pen = True
        s.append(f'<path d="{" ".join(d)}" fill="none" stroke="{C2}" stroke-width="2"/>')
        for g in range(5):
            y = T + ph * g / 4
            s.append(f'<text x="{L + pw + 6}" y="{y + 3:.1f}" font-size="10" fill="{C2}">{e(line_fmt(rmax * (1 - g / 4)))}</text>')
        s.append(f'<rect x="{L}" y="{height - 10}" width="10" height="3" fill="{C2}"/><text x="{L + 14}" y="{height - 5}" font-size="10.5" fill="{INK}">{e(line_name)} (right axis)</text>')
    s.append("</svg>")
    return "".join(s)


def table(head, rows, cls=""):
    h = "".join(f"<th>{e(x)}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'



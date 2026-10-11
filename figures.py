"""Figures for the write-up. Regenerates every figure from the results files.

  uv run python figures.py

Writes results/figures/{header,phrasings,which,how,famous_number,where_we_look,when}.{png,svg} (PNG 1600 px wide),
results/figures/numbers.md (every number each figure draws) and results/figures/captions.md.
Inputs: prompts/{neutral,labeled}.jsonl, results/s1/neutral_qwen{3b,7b}.jsonl (re-scored with score.py),
results/s1/judge_qwen{3b,7b}.jsonl, results/s2/word_probe_qwen7b.json, results/s2/acts_word_qwen7b_meta.jsonl and the
7B tokenizer (token strip only).
"""
import json
import random
import re
import textwrap
from collections import Counter, defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle, Wedge  # noqa: E402

from common import PROMPTS, RESULTS, chat_prompt, read_jsonl  # noqa: E402
from score import score  # noqa: E402

OUT = RESULTS / "figures"
WIDTH_IN, DPI = 10.0, 160  # 1600 px wide
NUMS = ["1/3", "1/2", "1/4"]
COL = {"1/3": "#3b6fb6", "1/2": "#e08a2b", "1/4": "#3a9a5b", "other": "#9a9a9a"}
APP2NUM = {"A": "1/3", "B": "1/2", "C": "1/4"}
VAR2NUM = {"angle at the center": "1/3", "distance from the center": "1/2", "midpoint in the disk": "1/4"}
VAR_SHORT = {"angle at the center": "angle", "distance from the center": "distance", "midpoint in the disk": "midpoint"}
INK = "#222222"
THR_ORDER = ["triangle", "rsqrt3", "numeric"]
THR_LABEL = {"triangle": "triangle", "rsqrt3": "r√3", "numeric": "numeric"}
RAD_ORDER = ["unspecified", "1", "2", "5"]
RAD_LABEL = {"unspecified": "no r", "1": "r=1", "2": "r=2", "5": "r=5"}
STRIP_EXAMPLE = (2, 7)  # 7B derived 1/2; first variable word at answer token 68 (chosen for fit; median is 110)
RECALLED_EXAMPLE = (12, 26)  # 7B recalled 1/3: computes 2/3, boxes 1/3
RECALLED_LINES = [0, None, 10, None, 18, None, 22, None, 26, 28, 29, None, 31]  # None = "…"
RECALLED_MARK = {26: "other", 29: "boxed"}

plt.rcParams.update({
    "font.size": 15, "axes.labelsize": 16, "xtick.labelsize": 14, "ytick.labelsize": 14, "legend.fontsize": 14,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white", "hatch.linewidth": 1.6, "svg.fonttype": "none", "text.usetex": False,
})
NUMBERS, CAPTIONS = [], {}


def note(fig, lines):
    NUMBERS.append(f"## {fig}\n")
    NUMBERS.extend(lines)
    NUMBERS.append("")


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    w = fig.get_size_inches()[0]
    fig.savefig(OUT / f"{name}.png", dpi=1600 / w)
    fig.savefig(OUT / f"{name}.svg")
    plt.close(fig)


def esc(s):
    return s.replace("$", r"\$")


def recalled_patch_kw(num):
    return dict(facecolor=matplotlib.colors.to_rgba(COL[num], 0.18), edgecolor=COL[num], hatch="//", linewidth=1.2)


# ---------------------------------------------------------------- data
def neutral_prompts():
    return {r["wording_id"]: r for r in read_jsonl(PROMPTS / "neutral.jsonl")}


def numbers_per_phrasing(tag):
    out = defaultdict(Counter)
    for r in read_jsonl(RESULTS / "s1" / f"neutral_{tag}.jsonl"):
        if r.get("kind") != "answer":
            continue
        a = score(r["answer"])["approach_number"]
        out[r["wording_id"]][APP2NUM.get(a, "other")] += 1
    return out


def judge(tag):
    return read_jsonl(RESULTS / "s1" / f"judge_{tag}.jsonl")


# ---------------------------------------------------------------- 1 header
GEO_LW = 1.2
GEO_INK = "#1f3a5f"  # circle, chords, radius, robot
GEO_TRI = "#c4c4c4"


def dot(ax, xy, size=6.5, color=GEO_INK):
    ax.plot([xy[0]], [xy[1]], "o", ms=size, mfc=color, mec="white", mew=1.0, zorder=6)


def robot(ax, x0, y0, s):
    """Small puzzled line robot: rounded square head, dot eyes, antenna with a ball, one raised and one flat eyebrow, short flat mouth."""
    kw = dict(color=GEO_INK, lw=GEO_LW, solid_capstyle="round")
    ax.add_patch(FancyBboxPatch((x0 - 0.5 * s, y0 - 0.5 * s), s, s, boxstyle=f"round,pad=0,rounding_size={0.22 * s}",
                                fill=False, lw=GEO_LW, ec=GEO_INK))
    for ex in (-0.2, 0.2):
        ax.add_patch(Circle((x0 + ex * s, y0 + 0.05 * s), 0.055 * s, color=GEO_INK, lw=0))
    ax.plot([x0 - 0.32 * s, x0 - 0.08 * s], [y0 + 0.2 * s, y0 + 0.2 * s], **kw)  # flat eyebrow
    ax.plot([x0 + 0.08 * s, x0 + 0.32 * s], [y0 + 0.24 * s, y0 + 0.33 * s], **kw)  # raised eyebrow
    ax.plot([x0 - 0.12 * s, x0 + 0.12 * s], [y0 - 0.24 * s, y0 - 0.24 * s], **kw)  # short flat mouth
    ax.plot([x0, x0], [y0 + 0.5 * s, y0 + 0.75 * s], **kw)  # antenna
    ax.add_patch(Circle((x0, y0 + 0.81 * s), 0.06 * s, fill=False, lw=GEO_LW, ec=GEO_INK))
    ax.text(x0 + 0.85 * s, y0 + 0.1 * s, "?", fontsize=30, color=GEO_INK, ha="center", va="center", fontweight="light")


def fig_header():
    rng = np.random.default_rng(3)
    fig = plt.figure(figsize=(WIDTH_IN, WIDTH_IN / 2.9))
    axes = [fig.add_axes([0.05 + i * 0.33, 0.36, 0.24, 0.62]) for i in range(3)]
    tri = [np.deg2rad(90 + 120 * i) for i in range(3)]
    lines = []
    for ax in axes:
        ax.set_aspect("equal"); ax.axis("off"); ax.set_xlim(-1.12, 1.12); ax.set_ylim(-1.12, 1.12)
        ax.add_patch(Polygon([[np.cos(a), np.sin(a)] for a in tri], closed=True, fill=False, lw=GEO_LW, ec=GEO_TRI))
        ax.add_patch(Circle((0, 0), 1, fill=False, lw=GEO_LW, ec=GEO_INK))
    # (a) one endpoint at the top vertex; favourable arc = the third opposite it, shaded as a thin band inside the circle
    ax = axes[0]
    p = tri[0]
    ax.add_patch(Wedge((0, 0), 1.0, np.rad2deg(p) + 120, np.rad2deg(p) + 240, width=0.1, color=COL["1/3"], alpha=0.35, lw=0))
    q = p + np.deg2rad(rng.uniform(140, 220))
    ax.plot([np.cos(p), np.cos(q)], [np.sin(p), np.sin(q)], color=GEO_INK, lw=GEO_LW)
    for a in (p, q):
        dot(ax, (np.cos(a), np.sin(a)))
    lines.append(f"(a) endpoints at {np.rad2deg(p) % 360:.0f}° and {np.rad2deg(q) % 360:.0f}°; shaded arc 210°–330° (one third), 1/3 color")
    # (b) full radius, inner half shaded along the line, point in that half, chord at right angles
    ax = axes[1]
    th, dd = np.deg2rad(262), 0.15  # illustration: radius tilted 8° off 270° (not perpendicular to an edge), point in the inner half; chord ends >= 13° from the vertices
    u = np.array([np.cos(th), np.sin(th)]); v = np.array([-u[1], u[0]])
    ends = [th + np.arccos(dd), th - np.arccos(dd)]
    away = min(abs((np.rad2deg(th - t) + 180) % 360 - 180) for t in tri)
    gap = min(abs((np.rad2deg(e - t) + 180) % 360 - 180) for e in ends for t in tri)
    assert away >= 40 and dd < 0.5, away
    ax.plot([0, u[0]], [0, u[1]], color=GEO_INK, lw=GEO_LW, zorder=2)
    band_pt = 0.2 * ax.get_position().width * fig.get_size_inches()[0] * 72 / 2.24  # 0.2 r in points
    ax.plot([0, 0.5 * u[0]], [0, 0.5 * u[1]], color=COL["1/2"], lw=band_pt, alpha=0.45, solid_capstyle="butt", zorder=1)  # inner half: center to midpoint
    h = np.sqrt(1 - dd ** 2)
    c1, c2 = dd * u + h * v, dd * u - h * v
    ax.plot([c1[0], c2[0]], [c1[1], c2[1]], color=GEO_INK, lw=GEO_LW)
    dot(ax, dd * u)
    lines.append(f"(b) radius at {np.rad2deg(th):.0f}°, point at {dd:.2f} r; chord ends at {np.rad2deg(ends[0]) % 360:.0f}° and "
                 f"{np.rad2deg(ends[1]) % 360:.0f}° (nearest vertex {gap:.0f}° away; radius {away:.0f}° from every vertex); inner half of the radius (center to 0.5 r) drawn as a thicker line, 1/2 color")
    # (c) inner circle r/2 filled, random midpoint inside, its chord
    ax = axes[2]
    ax.add_patch(Circle((0, 0), 0.5, color=COL["1/4"], alpha=0.25, lw=0))
    rr, ph = 0.3, rng.uniform(0, 2 * np.pi)
    m = rr * np.array([np.cos(ph), np.sin(ph)])
    u = m / np.linalg.norm(m); v = np.array([-u[1], u[0]]); h = np.sqrt(1 - rr ** 2)
    ax.plot([(m + h * v)[0], (m - h * v)[0]], [(m + h * v)[1], (m - h * v)[1]], color=GEO_INK, lw=GEO_LW)
    dot(ax, m)
    lines.append(f"(c) midpoint at {rr:.2f} r, angle {np.rad2deg(ph) % 360:.0f}°; inner disk of radius r/2 filled, 1/4 color")
    for ax, num in zip(axes, NUMS):
        dot(ax, (0, 0), size=4.5)  # center
        ax.text(0.5, 0.03, num, transform=ax.transAxes, ha="center", va="top", fontsize=13, color=COL[num], fontweight="bold")
    rax = fig.add_axes([0.44, 0.02, 0.12, 0.27]); rax.set_aspect("equal"); rax.axis("off")
    rax.set_xlim(-0.9, 1.4); rax.set_ylim(-0.9, 1.0)
    robot(rax, 0.0, 0.0, 0.9)
    save(fig, "header")
    note("header", lines + ["numbers under the panels: (a) 1/3, (b) 1/2, (c) 1/4"])
    CAPTIONS["header"] = ("Three ways to draw a chord at random in the same circle, with the inscribed equilateral triangle: "
                          "(a) two random points on the circle, (b) a random point on a random radius, with the chord at right "
                          "angles to it, (c) a random midpoint in the disk. Shaded: where the chord comes out longer than the "
                          "triangle's side. Each way gives a different probability.")


# ---------------------------------------------------------------- 2 phrasings
def fig_phrasings():
    P = neutral_prompts()
    rng = random.Random(0)
    numeric = rng.choice([w for w in P if P[w]["threshold"] == "numeric"])
    no_r = rng.choice([w for w in P if w != 0 and "radius" not in P[w]["text"]])
    lab = [r for r in read_jsonl(PROMPTS / "labeled.jsonl") if r["wording_id"] == 0 and r["approach"] == "C"]
    L = rng.choice(lab)
    clause = L["text"].replace(P[0]["text"], "").strip()
    boxes = [("canonical problem statement", P[0]["text"], None),
             (f"rephrasing {numeric}: numeric comparison length", P[numeric]["text"], None),
             (f"rephrasing {no_r}: no radius", P[no_r]["text"], None),
             (f"canonical statement plus a clause for {APP2NUM[L['approach']]}", L["text"], clause)]
    fig = plt.figure(figsize=(WIDTH_IN, 9.0 * 0.88))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0.12, 1)
    y = 0.97
    width_chars = 78
    for head, text, hl in boxes:
        ax.text(0.04, y, head, fontsize=14, color="#555555", va="top", style="italic")
        y -= 0.04
        if hl is None:
            spans = [(w, False) for w in textwrap.wrap(text, width_chars)]
        else:
            before, after = text.split(hl) if hl in text else (text, "")
            spans = [(w, False) for w in textwrap.wrap(before.strip(), width_chars)]
            spans += [(w, True) for w in textwrap.wrap(hl, width_chars)]
            spans += [(w, False) for w in textwrap.wrap(after.strip(), width_chars)]
        top = y + 0.012
        for w, is_hl in spans:
            kw = dict(bbox=dict(boxstyle="square,pad=0.15", fc=matplotlib.colors.to_rgba(COL[APP2NUM[L["approach"]]], 0.25), ec="none")) if is_hl else {}
            ax.text(0.06, y, esc(w), fontsize=15, va="top", family="DejaVu Sans", **kw)
            y -= 0.038
        ax.add_patch(Rectangle((0.035, y + 0.012), 0.93, top - y - 0.006, fill=False, ec="#bbbbbb", lw=1.2))
        y -= 0.045
    save(fig, "phrasings")
    note("phrasings", [f"canonical id 0; rephrasings id {numeric} (numeric comparison length) and id {no_r} (no radius), picked with "
                       f"random.Random(0) within those groups; specified prompt {L['id']} (approach {L['approach']}, description "
                       f"{L['desc_id']}, clause {L['position']} the problem)",
                       f"highlighted clause: \"{clause}\""])
    CAPTIONS["phrasings"] = ("Prompts as the model sees them. Top: the canonical Bertrand problem statement and two of the 17 "
                             "rephrasings, one stating the comparison length as a number and one giving no radius. Bottom: the "
                             "canonical statement plus a clause that states the approach for 1/4 (highlighted).")


# ---------------------------------------------------------------- 3 which
def fig_which():
    P = neutral_prompts()
    order = sorted(P, key=lambda w: (THR_ORDER.index(P[w]["threshold"]), RAD_ORDER.index(P[w]["radius"]), w))
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH_IN, 7.6), sharex=True)
    fig.subplots_adjust(left=0.09, right=0.985, top=0.9, bottom=0.2, hspace=0.18)
    lines = [f"x order (comparison length, radius, id): " + ", ".join(f"{w}({THR_LABEL[P[w]['threshold']]},{RAD_LABEL[P[w]['radius']]})" for w in order)]
    GAP = 0.7  # extra space between threshold groups
    x = np.array([i + GAP * THR_ORDER.index(P[w]["threshold"]) for i, w in enumerate(order)])
    for ax, tag, name in zip(axes, ["qwen3b", "qwen7b"], ["3B", "7B"]):
        C = numbers_per_phrasing(tag)
        bottom = np.zeros(len(order))
        for k in NUMS + ["other"]:
            v = np.array([C[w][k] for w in order])
            ax.bar(x, v, bottom=bottom, color=COL[k], width=0.78, label=k, edgecolor="white", linewidth=0.6)
            bottom += v
        ax.set_ylim(0, 30); ax.set_yticks([0, 10, 20, 30]); ax.set_ylabel(f"{name}\nsamples")
        lines.append(f"{name} per phrasing (1/3, 1/2, 1/4, other): " + "; ".join(
            f"{w}: {C[w]['1/3']},{C[w]['1/2']},{C[w]['1/4']},{C[w]['other']}" for w in order))
    axes[0].legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.02), frameon=False)
    ax = axes[1]
    ax.set_xticks(x); ax.set_xticklabels([str(w) for w in order])
    trans = matplotlib.transforms.blended_transform_factory(ax.transData, ax.transAxes)
    # radius subgroups and threshold groups below the ticks
    for thr in THR_ORDER:
        idx = [i for i, w in enumerate(order) if P[w]["threshold"] == thr]
        for rad in RAD_ORDER:
            sub = [x[i] for i in idx if P[order[i]]["radius"] == rad]
            if sub:
                ax.text(np.mean(sub), -0.25, RAD_LABEL[rad], transform=trans, ha="center", va="top", fontsize=10.5, color="#555555")
        ax.text(np.mean(x[idx]), -0.42, THR_LABEL[thr], transform=trans, ha="center", va="top", fontsize=16)
        ax.annotate("", xy=(x[idx[0]] - 0.4, -0.38), xytext=(x[idx[-1]] + 0.4, -0.38), xycoords=trans, textcoords=trans,
                    arrowprops=dict(arrowstyle="-", color="#777777", lw=1.4))
        if thr != THR_ORDER[-1]:
            for a in axes:
                a.axvline(x[idx[-1]] + 0.5 + GAP / 2, color="#cccccc", lw=1.2, zorder=0)
    ax.text(-0.01, -0.035, "phrasing", transform=ax.transAxes, ha="right", va="top", fontsize=13, color="#555555")
    save(fig, "which")
    note("which", lines)
    CAPTIONS["which"] = ("Which number each model gives on each phrasing of the neutral problem (30 samples per phrasing, "
                         "temperature 0.7, label = final number). Phrasings are grouped by how the comparison length is stated "
                         "(triangle side, r√3, or a number) and by radius (\"no r\": radius not given).")


# ---------------------------------------------------------------- 4 how
def fig_how():
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 6.2))
    fig.subplots_adjust(left=0.1, right=0.6, top=0.97, bottom=0.17)
    lines = []
    xs, labels = [], []
    for i, num in enumerate(NUMS):
        for j, (tag, name) in enumerate([("qwen3b", "3B"), ("qwen7b", "7B")]):
            x = i * 2.6 + j * 1.0
            J = [r for r in judge(tag) if r["final_number"] == num]
            der = Counter(r["variable"] for r in J if r["derived_or_recalled"] == "derived")
            rec = Counter(r["variable"] for r in J if r["derived_or_recalled"] == "recalled")
            b = 0
            for var in ["angle at the center", "distance from the center", "midpoint in the disk"] + sorted(set(der) - set(VAR2NUM)):
                if der.get(var):
                    ax.bar(x, der[var], bottom=b, width=0.85, color=COL[VAR2NUM.get(var, "other")], edgecolor="white", lw=0.6)
                    b += der[var]
            nrec = sum(rec.values())
            ax.bar(x, nrec, bottom=b, width=0.85, facecolor=matplotlib.colors.to_rgba(COL[num], 0.18), edgecolor=COL[num],
                   hatch="//", lw=0)  # hatch only; the hatch takes the edge color
            ax.bar(x, nrec, bottom=b, width=0.85, fill=False, edgecolor="white", lw=0.6)  # same edge as the solid bars
            ax.text(x, b + nrec + 3, f"{b}/{nrec}", ha="center", va="bottom", fontsize=12)
            xs.append(x); labels.append(name)
            lines.append(f"{name} {num}: explained {b} (" + ", ".join(f"{k} {v}" for k, v in der.items()) +
                         f"); unexplained {nrec} (" + ", ".join(f"{k} {v}" for k, v in rec.most_common()) + ")")
        ax.text(i * 2.6 + 0.5, -0.13, num, transform=matplotlib.transforms.blended_transform_factory(ax.transData, ax.transAxes),
                ha="center", va="top", fontsize=20, color=COL[num], fontweight="bold")
    ax.set_xticks(xs); ax.set_xticklabels(labels)
    ax.set_ylabel("answers ending in that number")
    from matplotlib.patches import Patch
    handles = [Patch(color=COL["1/3"], label="angle at the center"), Patch(color=COL["1/2"], label="distance from the center"),
               Patch(color=COL["1/4"], label="midpoint in the disk"),
               Patch(facecolor=matplotlib.colors.to_rgba(COL["other"], 0.18), edgecolor=COL["other"], hatch="//", lw=0, label="unexplained\n(hatched, in the\nnumber's color)")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False, title="explained:",
              title_fontsize=14, alignment="left")
    ax.text(1.03, 0.45, "bar labels: explained/unexplained", transform=ax.transAxes, fontsize=12, color="#555555")
    save(fig, "how")
    note("how", lines)
    CAPTIONS["how"] = ("How the neutral answers ending in 1/3, 1/2 or 1/4 got there, by hand judgment. Solid: explained "
                       "(the written steps produce the number), colored by the variable treated as evenly spread; every "
                       "explained 1/3 uses the angle, every explained 1/2 the distance, every explained 1/4 the midpoint, so the "
                       "colors match the numbers. Hatched: unexplained (the working gives something else, or the number is "
                       "just stated). 3B: 361 answers; 7B: 400.")


# ---------------------------------------------------------------- 5 famous number
def latex_to_mathtext(s):
    """Answer LaTeX -> matplotlib mathtext. Inline \\( \\) -> $ $, display \\[ \\] -> one $ $ block.
    \\text{..} -> \\mathrm{..}, \\boxed{x} -> x (the box is drawn as a highlight)."""
    s = s.strip()
    s = re.sub(r"\\text\{([^{}]*)\}", lambda m: r"\mathrm{" + m.group(1).replace(" ", r"\ ") + "}", s)
    s = re.sub(r"\\boxed\{(.*)\}", r"\1", s)
    s = s.replace(r"\left(", "(").replace(r"\right)", ")").replace(r"\frac", r"\dfrac")  # full-size fractions
    if s.startswith(r"\[") and s.endswith(r"\]"):
        return "$" + s[2:-2].strip() + "$"
    return re.sub(r"\\\((.*?)\\\)", lambda m: "$" + m.group(1).strip() + "$", s.replace("$", r"\$"))


def fig_famous():
    P = neutral_prompts()
    fig = plt.figure(figsize=(WIDTH_IN, 8.8))
    ax = fig.add_axes([0.08, 0.14, 0.33, 0.80])
    lines = []
    for j, (tag, name, col) in enumerate([("qwen3b", "3B", "#9fb6d8"), ("qwen7b", "7B", "#3b3b3b")]):
        J = judge(tag)
        for i, thr in enumerate(THR_ORDER):
            S = [r for r in J if P[r["wording_id"]]["threshold"] == thr]
            d = sum(r["derived_or_recalled"] == "derived" for r in S)
            share = d / len(S)
            x = i + (j - 0.5) * 0.38
            ax.bar(x, 100 * share, width=0.36, color=col, label=name if i == 0 else None)
            ax.text(x, 100 * share + 1.5, f"{100 * share:.0f}%", ha="center", va="bottom", fontsize=12)
            ax.text(x, 3, f"{d}/\n{len(S)}", ha="center", va="bottom", fontsize=10, color="white" if j else INK)
            lines.append(f"{name} {THR_LABEL[thr]}: explained {d}/{len(S)} = {100 * share:.0f}%")
    ax.set_xticks(range(3)); ax.set_xticklabels([THR_LABEL[t] for t in THR_ORDER])
    ax.set_ylim(0, 115); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_ylabel("explained share (%)")
    ax.set_xlabel("comparison length")
    ax.legend(loc="upper left", frameon=False, ncol=2)
    # right: one recalled 1/3, math rendered
    rows = {(r["wording_id"], r["sample"]): r for r in read_jsonl(RESULTS / "s1" / "neutral_qwen7b.jsonl") if r.get("kind") == "answer"}
    ans = rows[RECALLED_EXAMPLE]["answer"].split("\n")
    tx = fig.add_axes([0.46, 0.02, 0.53, 0.96]); tx.axis("off"); tx.set_xlim(0, 1); tx.set_ylim(0, 1)
    tx.text(0.0, 0.99, f"7B, phrasing {RECALLED_EXAMPLE[0]}, sample {RECALLED_EXAMPLE[1]} (shortened)", fontsize=12,
            color="#555555", va="top", style="italic")
    y = 0.93
    shown = []
    hl = {"other": "#f6d7d7", "boxed": matplotlib.colors.to_rgba(COL["1/3"], 0.3)}
    renderer = fig.canvas.get_renderer()

    def below(t, pad):  # next y: under the rendered text (the pad leaves room for a highlight box)
        bb = t.get_window_extent(renderer)
        return tx.transData.inverted().transform((0, bb.y0))[1] - pad

    for li in RECALLED_LINES:
        if li is None:
            y = below(tx.text(0.0, y, "…", fontsize=13, va="top", color="#888888"), 0.006); continue
        mark = RECALLED_MARK.get(li)
        raw = ans[li].strip()
        if raw.startswith(r"\[") and " = " in raw:  # long display line: break at '=' signs, at most 2 '=' per row
            body = raw[2:-2].strip().split(" = ")
            parts = [" = ".join(body[:2])] + ["= " + " = ".join(body[k:k + 2]) for k in range(2, len(body), 2)]
            segs = [latex_to_mathtext(r"\[" + p_ + r"\]") for p_ in parts]
        elif raw.startswith(r"\["):
            segs = [latex_to_mathtext(raw)]
        else:
            segs = textwrap.wrap(latex_to_mathtext(raw), 58)
        for sg in segs:
            kw = dict(bbox=dict(boxstyle="square,pad=0.2", fc=hl[mark], ec=COL["1/3"] if mark == "boxed" else "none")) if mark else {}
            is_math = sg.startswith("$") and sg.endswith("$") and sg.count("$") == 2
            y = below(tx.text(0.02 if is_math else 0.0, y, sg, fontsize=12.5, va="top", **kw), 0.022 if mark else 0.008)
        shown.append(li)
    tx.text(0.0, y - 0.01, "red: the working computes 2/3     blue: the boxed answer is 1/3", fontsize=11, color="#555555", va="top")
    save(fig, "famous_number")
    lines.append(f"right panel: 7B phrasing {RECALLED_EXAMPLE[0]} sample {RECALLED_EXAMPLE[1]}, answer lines {shown}, math "
                 f"rendered with mathtext; highlighted line 26 (computes 2/3) and line 29 (boxed 1/3)")
    note("famous number", lines)
    CAPTIONS["famous_number"] = ("Left: share of hand-judged answers whose steps actually produce their number, by how the "
                                 "comparison length is stated. Right: an unexplained 1/3 from the 7B (real answer, lines removed where "
                                 "marked …): the working gives 2/3, the boxed answer is the famous 1/3.")


# ---------------------------------------------------------------- 6 where we look
def fig_where():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
    meta = {(r["wording_id"], r["sample"]): r for r in read_jsonl(RESULTS / "s2" / "acts_word_qwen7b_meta.jsonl")[1:]}
    m = meta[STRIP_EXAMPLE]
    rows = {(r["wording_id"], r["sample"]): r for r in read_jsonl(RESULTS / "s1" / "neutral_qwen7b.jsonl") if r.get("kind") == "answer"}
    ans = rows[STRIP_EXAMPLE]["answer"]
    a_ids = tok(ans, add_special_tokens=False).input_ids
    p_ids = tok(chat_prompt(tok, m["prompt"]), add_special_tokens=False).input_ids
    t = m["word_tok"]
    w_end = t + len(tok(" " + m["word_match"], add_special_tokens=False).input_ids)  # tokens of the branch word
    median_t = int(np.median([r["word_tok"] for r in meta.values()]))
    toks = [("p", i, tok.decode([p_ids[i]])) for i in range(len(p_ids) - 4, len(p_ids))]
    toks += [("a", i, tok.decode([a_ids[i]])) for i in range(0, min(w_end + 3, len(a_ids)))]
    marks = {t - k: k for k in (30, 10, 5, 1)}
    fig = plt.figure(figsize=(WIDTH_IN, 6.6))
    ax = fig.add_axes([0.01, 0.01, 0.98, 0.98]); ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    x, y, row_h, cw, box_h = 1.0, 84.0, 15.0, 1.02, 6.4
    pos = {}
    for kind, i, s in toks:
        disp = s.replace("\n", "↵").replace(" ", "·") if s.strip() == "" else s.replace("\n", "↵")
        w = max(2.2, cw * len(disp) + 1.0)
        if x + w > 99:
            x, y = 1.0, y - row_h
        if kind == "p":
            fc, ec, ls = "white", "#9a9a9a", "--"
        elif t <= i < w_end:
            fc, ec, ls = matplotlib.colors.to_rgba(COL["1/2"], 0.45), "#c8c8c8", "-"
        elif i < 60:
            fc, ec, ls = "#e4e4e4", "#c8c8c8", "-"
        else:
            fc, ec, ls = "white", "#c8c8c8", "-"
        ax.add_patch(Rectangle((x, y - box_h / 2), w - 0.3, box_h, fc=fc, ec=ec, lw=0.8, ls=ls))
        ax.text(x + (w - 0.3) / 2, y, esc(disp), ha="center", va="center", fontsize=11.5, family="DejaVu Sans",
                color="#666666" if kind == "p" else INK)
        if kind == "a" and i in marks:  # small labeled dot directly above the box
            cx = x + (w - 0.3) / 2
            ax.plot([cx], [y + box_h / 2 + 1.6], "o", ms=5, color=INK)
            ax.text(cx, y + box_h / 2 + 2.8, str(marks[i]), ha="center", va="bottom", fontsize=11.5, fontweight="bold")
        pos[(kind, i)] = (x, y, w - 0.3)
        x += w
    lp = pos[("p", len(p_ids) - 1)]
    ax.annotate("prompt (dashed); last prompt token", xy=(lp[0] + lp[2] / 2, lp[1] + box_h / 2), xytext=(lp[0] + 3, lp[1] + 9.5),
                fontsize=12, arrowprops=dict(arrowstyle="->", color=INK), ha="left", color="#555555")
    bx, by, bw = pos[("a", t)]
    ax.text(bx, by - box_h / 2 - 1.2, "branch word", fontsize=12, color=COL["1/2"], fontweight="bold", va="top")
    lx, ly, lw_ = pos[("a", 59)]
    ax.text(1.0, by - row_h - 1.0, "grey boxes: the first 60 answer tokens, used by the earlier probe", fontsize=12, color="#555555", va="center")
    ax.text(1.0, by - row_h - 6.0, "dots: 30, 10, 5 and 1 tokens before the branch word", fontsize=12, color="#555555", va="center")
    save(fig, "where_we_look")
    note("where we look", [f"7B phrasing {STRIP_EXAMPLE[0]} sample {STRIP_EXAMPLE[1]} (final number {m['final_number']}, explained); "
                           f"prompt {len(p_ids)} tokens, last 4 shown; answer tokens 0–{min(w_end + 3, len(a_ids)) - 1} shown; "
                           f"first 60 answer tokens (0–59) shaded grey; branch word \"{m['word_match']}\" (tokens {t}–{w_end - 1}); "
                           f"dots at answer tokens {t - 30}, {t - 10}, {t - 5}, {t - 1}",
                           f"for the caption: branch word of this answer at answer token {t}; median branch-word position "
                           f"over the {len(meta)} answers: token {median_t}"])
    CAPTIONS["where_we_look"] = (f"Where the probes look, on one real 7B answer (phrasing {STRIP_EXAMPLE[0]}, sample "
                                 f"{STRIP_EXAMPLE[1]}). Dashed: the end of the prompt; the last prompt token is the reading "
                                 f"probe's position. Grey: the first 60 answer tokens, used by the earlier probe. "
                                 f"Highlighted: the first word that names the variable (the branch word, here at token {t}); "
                                 f"dots mark positions 30, 10, 5 and 1 tokens before it. This answer was chosen for fit; "
                                 f"the branch word usually comes around token {median_t}.")


# ---------------------------------------------------------------- 7 when
def fig_when():
    W = json.loads((RESULTS / "s2" / "word_probe_qwen7b.json").read_text(encoding="utf-8"))
    L = "22"
    ks = W["offsets"]
    probe = [100 * W["curves"]["main"][str(k)][L]["bal"] for k in ks]
    words = [100 * W["words"][str(k)]["prompt_plus_answer_text"]["bal"] for k in ks]
    within = [100 * W["best_rerun"][str(k)]["null_within"]["bal_p95"] for k in ks]
    assert W["best_layer"] == 22
    xs = np.arange(len(ks))  # equal spacing; labels are the offsets
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 6.0))
    fig.subplots_adjust(left=0.1, right=0.97, top=0.97, bottom=0.14)
    ax.plot(xs, probe, "-o", color=INK, lw=3, ms=8, label="probe on the residual stream (layer 22)")
    ax.plot(xs, words, "-s", color="#c0504d", lw=2.4, ms=7, label="words only (prompt + answer text so far)")
    ax.plot(xs, within, "-^", color="#7f7f7f", lw=2.4, ms=7, label="labels shuffled within phrasing, 95th pct")
    ax.axhline(100 / 3, ls="--", color="#999999", lw=1.6)
    ax.text(0.0, 34.5, "chance 33%", color="#777777", fontsize=13)
    ax.set_xticks(xs); ax.set_xticklabels([str(k) for k in ks]); ax.set_xlim(-0.4, len(ks) - 0.6)
    ax.set_ylim(25, 90)
    ax.set_xlabel("tokens before the branch word")
    ax.set_ylabel("balanced accuracy (%)")
    ax.legend(loc="upper left", frameon=False)
    save(fig, "when")
    note("when", [f"x (tokens before the branch word, equally spaced): {ks}",
                  "probe, layer 22, balanced accuracy (%): " + ", ".join(f"{v:.1f}" for v in probe),
                  "words only, prompt + answer text up to that point (%): " + ", ".join(f"{v:.1f}" for v in words),
                  "within-phrasing shuffle, 95th percentile, 50 shuffles (%): " + ", ".join(f"{v:.1f}" for v in within),
                  "chance: 33.3%", f"n per offset: " + ", ".join(str(W['curves']['main'][str(k)][L]['n']) for k in ks)])
    CAPTIONS["when"] = ("When the final number becomes readable in the 7B's answer. x: position, in tokens before the "
                        "first word that names the variable (positions equally spaced); y: balanced accuracy of a linear "
                        "probe for the final number (1/3, 1/2, 1/4), test phrasings unseen in training. Black: probe on the "
                        "residual stream at layer 22. Red: a classifier on the words alone. Grey: what shuffling labels "
                        "within each phrasing reaches (95th percentile of 50 shuffles); a probe above this line reads more than the phrasing.")


# ---------------------------------------------------------------- 8 when, supported vs unsupported
def fig_when_su():
    B = json.loads((RESULTS / "s2" / "word_probe_binary_qwen7b.json").read_text(encoding="utf-8"))
    L, ks = str(B["layer"]), B["offsets"]
    xs = np.arange(len(ks))
    sup = [100 * B["curves"]["supported"][str(k)][L]["bal"] for k in ks]
    uns = [100 * B["curves"]["unsupported"][str(k)][L]["bal"] for k in ks]
    sup_null = [100 * B["nulls"]["supported"][str(k)]["null_within"]["bal_p95"] for k in ks]
    uns_null = [100 * B["nulls"]["unsupported"][str(k)]["null_within"]["bal_p95"] for k in ks]
    mt = [100 * B["matched"][str(k)]["mean"] for k in ks]
    lo = [100 * B["matched"][str(k)]["p5"] for k in ks]
    hi = [100 * B["matched"][str(k)]["p95"] for k in ks]
    c = B["counts"]
    C_SUP, C_UNS, C_MT = INK, "#a0522d", "#6f8fb8"
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 6.2))
    fig.subplots_adjust(left=0.1, right=0.97, top=0.97, bottom=0.14)
    ax.fill_between(xs, lo, hi, color=C_MT, alpha=0.15, lw=0)
    ax.plot(xs, sup, "-o", color=C_SUP, lw=3, ms=8, label=f"explained (n={c['supported']['n']})")
    ax.plot(xs, mt, "-D", color=C_MT, lw=2.2, ms=6,
            label=f"explained, random {c['unsupported']['n']}-answer subsets (mean of {B['n_subsets']})")
    ax.plot(xs, uns, "-s", color=C_UNS, lw=3, ms=8, label=f"unexplained (n={c['unsupported']['n']})")
    ax.plot(xs, sup_null, "--", color=C_SUP, lw=1.6, alpha=0.7, label="within-phrasing shuffle, 95th pct (explained)")
    ax.plot(xs, uns_null, "--", color=C_UNS, lw=1.6, alpha=0.7, label="within-phrasing shuffle, 95th pct (unexplained)")
    ax.axhline(50, ls=":", color="#999999", lw=1.6)
    ax.text(len(ks) - 0.65, 27, "dotted: chance 50%", color="#777777", fontsize=13, ha="right")
    ax.set_xticks(xs); ax.set_xticklabels([str(k) for k in ks]); ax.set_xlim(-0.4, len(ks) - 0.6)
    ax.set_ylim(25, 102)
    ax.set_xlabel("tokens before the branch word")
    ax.set_ylabel("balanced accuracy, 1/3 vs not (%)")
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    save(fig, "when_supported_vs_unsupported")
    med = B["median_anchor_token"]
    note("when, explained vs unexplained", [
        f"x (tokens before the branch word, equally spaced): {ks}; layer {L}; label 1/3 vs not",
        "explained probe (%): " + ", ".join(f"{v:.1f}" for v in sup),
        "explained within-phrasing shuffle 95th pct (%): " + ", ".join(f"{v:.1f}" for v in sup_null),
        "explained, 56-answer subsets, mean (%): " + ", ".join(f"{v:.1f}" for v in mt),
        "explained, 56-answer subsets, 5th–95th pct band (%): " + ", ".join(f"{a:.1f}–{b:.1f}" for a, b in zip(lo, hi)),
        "unexplained probe (%): " + ", ".join(f"{v:.1f}" for v in uns),
        "unexplained within-phrasing shuffle 95th pct (%): " + ", ".join(f"{v:.1f}" for v in uns_null),
        "chance: 50%",
        f"n: explained {c['supported']['n']} ({c['supported']['one_third']} 1/3 / {c['supported']['not_one_third']} not; "
        f"328 / 333 at k = 30 / 20), unexplained {c['unsupported']['n']} ({c['unsupported']['one_third']} / {c['unsupported']['not_one_third']})",
        f"median anchor token: explained {med['supported']:.0f}, unexplained {med['unsupported']:.0f}"])
    CAPTIONS["when_supported_vs_unsupported"] = (
        f"Whether the 7B's final number is 1/3 can be read from the residual stream (layer {L}) at positions before the "
        f"first word that names the variable, for answers whose steps produce the boxed number (explained, n = "
        f"{c['supported']['n']}) and answers whose steps do not (unexplained, n = {c['unsupported']['n']}). Light blue: the "
        f"explained probe on random subsets the size and class mix of the unexplained set (mean of {B['n_subsets']}, band "
        f"5th–95th percentile). Dashed: 95th percentile of labels shuffled within phrasing; a probe above its line reads "
        f"more than the phrasing. The unexplained curve rests on {c['unsupported']['n']} answers. Median position of the "
        f"branch word: token {med['supported']:.0f} (explained), {med['unsupported']:.0f} (unexplained).")


def main():
    for f in (fig_header, fig_phrasings, fig_which, fig_how, fig_famous, fig_where, fig_when, fig_when_su):
        f()
    (OUT / "numbers.md").write_text("# Numbers drawn in each figure\n\n" + "\n".join(NUMBERS) + "\n", encoding="utf-8")
    (OUT / "captions.md").write_text("# Figure captions\n\n" + "\n\n".join(f"**{k}.** {v}" for k, v in CAPTIONS.items()) + "\n",
                                     encoding="utf-8")
    print("\n".join(NUMBERS))


if __name__ == "__main__":
    main()

"""Stage 1 summary.

Answers are re-scored from their text with the current score.py (the fields stored at generation time are
overwritten). Reads results/s1/{labeled,neutral}_{tag}.jsonl for every model tag present and writes results/s1/summary.md, plus
results/s1/samples_{tag}.md with 30 random answers for a manual read of the scorer. For the 3B it also writes
results/s1/read_neutral_qwen3b.md (every neutral answer) and read_labeled_qwen3b.md (60 labeled answers) for
hand reading. The next-word check (nextword_*.jsonl) is not read. Primary label = final number (approach_number: 1/3 A, 1/2 B, 1/4 C); the method
stated in the text (approach_text) is kept as a check next to it. Rates are reported side by side; there are no
thresholds here.

Per model: labeled accuracy (all / non-canonical phrasings / canonical / held-out splits), labeled x answered
confusion, text/number agreement, neutral approach distribution per problem statement (with the samples that end in
a canonical number but state no method), and two variation readings on the number label: across phrasings (does the
mix of approaches differ between phrasings more than it does when the labels are shuffled across phrasings) and
across samples (how often samples of one phrasing land on the same approach, next to what independent draws from
the pooled mix would give). Prose says "phrasing" / "problem statement"; file names and keys keep "wording".
"""
import random
from collections import Counter, defaultdict
from statistics import mean

import numpy as np

from common import APPROACHES, APPROACH_LABEL, RESULTS, load_prompts, read_jsonl, utf8_stdout
from score import score

S1 = RESULTS / "s1"
TEXT_LABELS = ["A", "B", "C", "multiple", "none"]
NUM_LABELS = ["A", "B", "C", "other", "multiple", "none"]
N_PERM = 5000
READ_TAGS = ["qwen3b"]  # models whose answers get hand-reading files (read_{neutral,labeled}_{tag}.md)
N_READ_LABELED = 60


def md_table(header, rows):
    out = ["| " + " | ".join(str(h) for h in header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def pct(k, n):
    return f"{100 * k / n:.0f}% ({k}/{n})" if n else "–"


def tags():
    return sorted({p.stem.split("_", 1)[1] for p in S1.glob("*_qwen*.jsonl") if p.stem.split("_", 1)[0] in ("labeled", "neutral")})


def load(tag):
    meta, data = {}, {}
    for kind in ["labeled", "neutral"]:
        rows = read_jsonl(S1 / f"{kind}_{tag}.jsonl")
        meta[kind] = [r for r in rows if r.get("kind") == "meta"]  # one per generating run
        data[kind] = [r for r in rows if r.get("kind") == "answer"]
        for r in data[kind]:  # re-score from the text so scorer changes apply without regenerating
            r.update(score(r["answer"]))
    return meta, data


def acc(rows, key="approach_number"):
    return pct(sum(r[key] == r["approach"] for r in rows), len(rows))


def dist_str(rows, key="approach_number"):
    labels = TEXT_LABELS if key == "approach_text" else NUM_LABELS
    c = Counter(r[key] for r in rows)
    return " ".join(f"{x}:{c[x]}" for x in labels if c[x]) or "–"


def chi2_stat(table):
    table = np.asarray(table, float)
    rs, cs = table.sum(1, keepdims=True), table.sum(0, keepdims=True)
    exp = rs @ cs / table.sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(exp > 0, (table - exp) ** 2 / exp, 0.0)
    return float(term.sum())


def across_wordings(N, key="approach_number"):
    """Spread of the wording x {A,B,C} counts (chi-square statistic) and the share of label shufflings across
    wordings that spread at least as much."""
    rows = [r for r in N if r[key] in APPROACHES]
    wids = sorted({r["wording_id"] for r in rows})
    if len(wids) < 2 or len({r[key] for r in rows}) < 2:
        return None
    widx = {w: i for i, w in enumerate(wids)}
    aidx = {a: i for i, a in enumerate(APPROACHES)}
    w = np.array([widx[r["wording_id"]] for r in rows])
    a = np.array([aidx[r[key]] for r in rows])

    def table(a_):
        t = np.zeros((len(wids), 3))
        np.add.at(t, (w, a_), 1)
        return t

    obs = chi2_stat(table(a))
    rng = np.random.default_rng(0)
    perm = np.array([chi2_stat(table(rng.permutation(a))) for _ in range(N_PERM)])
    df = (len(wids) - 1) * (len(set(a.tolist())) - 1)
    return dict(chi2=obs, df=df, p_perm=float((perm >= obs - 1e-9).mean()), n=len(rows), n_wordings=len(wids))


def across_samples(N, key="approach_number"):
    """Within-wording majority share among A/B/C-labeled samples, next to iid draws from the pooled mix."""
    by = defaultdict(list)
    for r in N:
        if r[key] in APPROACHES:
            by[r["wording_id"]].append(r[key])
    groups = [v for v in by.values() if len(v) >= 2]
    if not groups:
        return None
    pooled = Counter(a for v in groups for a in v)
    p = np.array([pooled[a] for a in APPROACHES], float)
    p /= p.sum()
    maj = [max(Counter(v).values()) / len(v) for v in groups]
    rng = np.random.default_rng(0)
    sim = []
    for _ in range(2000):
        sim.append(mean(np.bincount(rng.choice(3, size=len(v), p=p), minlength=3).max() / len(v) for v in groups))
    return dict(n_wordings=len(groups), mean_majority=mean(maj), single=sum(m == 1.0 for m in maj),
                expected_iid=float(np.mean(sim)), pooled={a: pooled[a] for a in APPROACHES})


def section(tag, meta, data):
    L, N = data["labeled"], data["neutral"]
    out = [f"## {tag}", ""]
    runs = []
    for k, ms in meta.items():
        for m in ms:
            runs.append(f"{k}: {m['time']}, {m['device']} {m['dtype']}, T={m['temperature']}, n_samples={m['n_samples']}, "
                        f"max_new_tokens={m['max_new_tokens']}, repetition_penalty={m.get('repetition_penalty')}")
        if ms:
            runs[-1] += f" ({len(data[k])} {k} answers in all)"
    out += ["Runs: " + "; ".join(runs) if runs else "No runs found.", ""]

    # 1. side by side: labeled follow rate next to neutral share, number label first, stated method as a check
    rows = []
    for a in APPROACHES:
        la = [r for r in L if r["approach"] == a]
        rows.append([APPROACH_LABEL[a],
                     pct(sum(r["approach_number"] == a for r in la), len(la)), pct(sum(r["approach_number"] == a for r in N), len(N)),
                     pct(sum(r["approach_text"] == a for r in la), len(la)), pct(sum(r["approach_text"] == a for r in N), len(N))])
    ct, cn = Counter(r["approach_text"] for r in L), Counter(r["approach_text"] for r in N)
    kt, kn = Counter(r["approach_number"] for r in L), Counter(r["approach_number"] for r in N)
    for o in ["other", "multiple", "none"]:
        rows.append([o, pct(kt[o], len(L)), pct(kn[o], len(N)),
                     pct(ct[o], len(L)) if o != "other" else "", pct(cn[o], len(N)) if o != "other" else ""])
    out += ["### Approach rates (final number primary, stated method as a check)", "",
            "Labeled columns: share of answers to prompts labeled with that approach whose label is that approach. "
            "Neutral columns: share of all neutral samples with that label. other/multiple/none rows are shares of all "
            "labeled answers / all neutral samples.", "",
            md_table(["approach", "labeled, number", "neutral, number", "labeled, stated (check)", "neutral, stated (check)"], rows), ""]

    if L:
        subsets = [("all phrasings", L), ("non-canonical phrasings (id != 0)", [r for r in L if r["wording_id"] != 0]),
                   ("canonical problem statement (id 0)", [r for r in L if r["wording_id"] == 0]),
                   ("held-out phrasings", [r for r in L if r["heldout_wording"]]),
                   ("held-out descriptions", [r for r in L if r["heldout_desc"]]),
                   ("held-out phrasing and description", [r for r in L if r["heldout_wording"] and r["heldout_desc"]])]
        rows = [[name, len(rs), acc(rs, "approach_number"), acc(rs, "approach_text")] for name, rs in subsets]
        out += ["### Labeled accuracy (answer label = labeled approach)", "",
                md_table(["subset", "n", "number", "stated (check)"], rows), ""]

        rows = [[APPROACH_LABEL[a], len(la)] + [Counter(r["approach_number"] for r in la)[x] for x in NUM_LABELS]
                for a in APPROACHES for la in [[r for r in L if r["approach"] == a]]]
        out += ["### Labeled approach × final number", "", md_table(["labeled", "n"] + NUM_LABELS, rows), ""]
        rows = [[APPROACH_LABEL[a], len(la)] + [Counter(r["approach_text"] for r in la)[x] for x in TEXT_LABELS]
                for a in APPROACHES for la in [[r for r in L if r["approach"] == a]]]
        out += ["### Labeled approach × stated method (check)", "", md_table(["labeled", "n"] + TEXT_LABELS, rows), ""]

    # 2. number / stated method agreement
    rows = []
    for name, rs in [("labeled", L), ("neutral", N), ("both", L + N)]:
        both = [r for r in rs if r["agree"] is not None]
        rows.append([name, len(rs), pct(len(both), len(rs)), pct(sum(r["agree"] for r in both), len(both))])
    out += ["### Number / stated method agreement", "",
            "both in A/B/C: answers where the final number and the stated method each map to one approach; agree: share of "
            "those where they match.", "", md_table(["set", "n", "both in A/B/C", "agree"], rows), ""]
    for name, rs in [("labeled", L), ("neutral", N)]:
        if rs:
            rows = [[k] + [sum(r["approach_number"] == k and r["approach_text"] == t for r in rs) for t in TEXT_LABELS] for k in NUM_LABELS]
            out += [f"#### {name}: number label (rows) × stated method (columns)", "", md_table(["number \\ stated"] + TEXT_LABELS, rows), ""]

    if L:
        by = defaultdict(list)
        for r in L:
            by[(r["approach"], r["desc_id"], r["heldout_desc"])].append(r)
        rows = [[d, a, "held out" if h else "", acc(rs), dist_str(rs), acc(rs, "approach_text"), dist_str(rs, "approach_text")]
                for (a, d, h), rs in sorted(by.items())]
        out += ["### Follow rate per description", "",
                md_table(["desc", "approach", "", "followed (number)", "final numbers", "followed (stated, check)", "stated methods"], rows), ""]
        rows = []
        for key in ["frame", "position", "heldout_wording"]:
            by = defaultdict(list)
            for r in L:
                by[r[key]].append(r)
            rows += [[f"{key}={k}", acc(rs), acc(rs, "approach_text")] for k, rs in sorted(by.items())]
        out += ["### Follow rate per clause frame / position / phrasing split", "", md_table(["", "number", "stated (check)"], rows), ""]

    # 3. neutral distribution per wording
    rows = []
    for w in load_prompts("neutral"):
        wid = w["wording_id"]
        ns = [r for r in N if r["wording_id"] == wid]
        ls = [r for r in L if r["wording_id"] == wid]
        abc = [r["approach_number"] for r in ns if r["approach_number"] in APPROACHES]
        maj = f"{max(Counter(abc).values()) / len(abc):.1f} ({len(abc)})" if abc else "–"
        silent = Counter(r["approach_number"] for r in ns if r["approach_number"] in APPROACHES and r["approach_text"] == "none")
        silent_s = " ".join(f"{a}:{silent[a]}" for a in APPROACHES if silent[a]) or "–"
        rows.append([wid, "H" if w["heldout_wording"] else "", dist_str(ns) if ns else "–", maj, silent_s if ns else "–",
                     dist_str(ns, "approach_text") if ns else "–", acc(ls) if ls else "–",
                     w["text"][:90] + ("…" if len(w["text"]) > 90 else "")])
    out += ["### Neutral samples per problem statement (H = held-out phrasing)", "",
            "majority: share of the most frequent approach among the phrasing's samples ending in 1/3, 1/2 or 1/4 (count of "
            "such samples). number, no method: samples ending in a canonical number whose text states no method, by number. "
            "labeled followed: final-number follow rate on the phrasing's labeled prompts.", "",
            md_table(["id", "", "final number", "majority", "number, no method", "stated method (check)", "labeled followed", "problem statement"], rows), ""]

    if N:
        rows = []
        for key, name in [("approach_number", "final number"), ("approach_text", "stated method (check)")]:
            aw, asmp = across_wordings(N, key), across_samples(N, key)
            if asmp:
                rows.append([name, "pooled mix over samples labeled A/B/C (phrasings with at least 2 such samples)",
                             " ".join(f"{a}:{n}" for a, n in asmp["pooled"].items())])
            if aw:
                rows.append([name, f"does the mix differ across phrasings more than with shuffled labels? ({aw['n_wordings']} "
                                   f"phrasings, {aw['n']} samples)",
                             f"spread {aw['chi2']:.1f} (df {aw['df']}); {100 * aw['p_perm']:.1f}% of {N_PERM} shufflings of the "
                             f"labels across phrasings spread as much or more"])
            else:
                rows.append([name, "mix across phrasings", "not computed (fewer than 2 phrasings or 1 approach)"])
            if asmp:
                rows.append([name, f"agreement within a phrasing: mean share of the phrasing's most frequent approach "
                                   f"({asmp['n_wordings']} phrasings)",
                             f"{asmp['mean_majority']:.2f}; {asmp['expected_iid']:.2f} if every sample were an independent "
                             f"draw from the pooled mix"])
                rows.append([name, "phrasings whose samples all land on the same approach", f"{asmp['single']}/{asmp['n_wordings']}"])
        out += ["### Variation of the neutral approach", "", md_table(["label", "", ""], rows), ""]

    allr = L + N
    if allr:
        how = Counter(r["final_how"] for r in allr)
        # rows written before 2026-10-09 carry no max_new_tokens; they came from the file's first run
        limits = {k: meta[k][0]["max_new_tokens"] for k in ["labeled", "neutral"] if meta.get(k)}
        trunc = sum(r["n_tokens"] >= (r.get("max_new_tokens") or limits.get("labeled" if "approach" in r else "neutral", 10 ** 9))
                    for r in allr)
        rows = [["final answer found by", " ".join(f"{k}:{v}" for k, v in how.most_common())],
                ["mentions the paradox / 'depends'", pct(sum(r["mentions_paradox"] for r in allr), len(allr))],
                ["answers that hit the token limit", pct(trunc, len(allr))],
                ["mean answer length (tokens)", f"{mean(r['n_tokens'] for r in allr):.0f}"]]
        out += ["### Scorer diagnostics", "", md_table(["", ""], rows), ""]
    return "\n".join(out)


def samples_file(tag, data):
    rng = random.Random(0)
    picks = []
    for kind in ["labeled", "neutral"]:
        rows = data[kind]
        picks += [(kind, r) for r in rng.sample(rows, min(15, len(rows)))]
    if not picks:
        return
    out = [f"# {tag}: {len(picks)} random answers for a manual read of the scorer", ""]
    for kind, r in picks:
        label = f"labeled {r['approach']} / {r['desc_id']}" if kind == "labeled" else f"neutral sample {r['sample']}"
        out += [f"## {r['id']} — {label}", "",
                f"scorer: number→**{r['approach_number']}** ({r['final_how']}, value {r['final_value']}), "
                f"stated→**{r['approach_text']}** (hits {r.get('method_hits')}), "
                f"paradox={r['mentions_paradox']}, {r['n_tokens']} tokens", "",
                "> " + r["prompt"].replace("\n", "\n> "), "", "```", r["answer"], "```", ""]
    (S1 / f"samples_{tag}.md").write_text("\n".join(out), encoding="utf-8")


def _read_entry(r, extra=""):
    v = "–" if r["final_value"] is None else r["final_value"]
    return [f"## {r['id']} — phrasing {r['wording_id']}, sample {r['sample']}{extra}", "",
            f"- number: **{r['approach_number']}** (value {v}, {r['final_how']})",
            f"- stated method: **{r['approach_text']}** (hits {r['method_hits']})",
            f"- {r['n_tokens']} tokens", "", "> " + r["prompt"].replace("\n", "\n> "), "", "```", r["answer"], "```", ""]


def read_files(tag, data):
    """Hand-reading files: every neutral answer, and N_READ_LABELED labeled answers spread evenly over approaches
    and their descriptions (phrasings drawn at random within a description)."""
    N = sorted(data["neutral"], key=lambda r: (r["wording_id"], r["sample"]))
    if N:
        out = [f"# {tag}: all {len(N)} neutral answers", "",
               "Sorted by phrasing, then sample. number = label from the final number (primary); stated method = label "
               "from the method markers (check).", ""]
        for r in N:
            out += _read_entry(r)
        (S1 / f"read_neutral_{tag}.md").write_text("\n".join(out), encoding="utf-8")
    L = data["labeled"]
    if L:
        rng = random.Random(0)
        per = N_READ_LABELED // len(APPROACHES)
        picks = []
        for a in APPROACHES:
            by = defaultdict(list)
            for r in L:
                if r["approach"] == a:
                    by[r["desc_id"]].append(r)
            for rs in by.values():
                rng.shuffle(rs)
            descs = sorted(by)
            for i in range(per):  # round-robin over descriptions
                d = descs[i % len(descs)]
                picks.append(by[d][i // len(descs)])
        picks.sort(key=lambda r: (r["approach"], r["desc_id"], r["wording_id"]))
        out = [f"# {tag}: {len(picks)} labeled answers spread across approaches and descriptions", "",
               f"{per} per approach, round-robin over its descriptions (seed 0). number = label from the final number "
               "(primary); stated method = label from the method markers (check).", ""]
        for r in picks:
            held = ", held-out desc" if r["heldout_desc"] else ""
            out += _read_entry(r, f" — labeled **{r['approach']}** / {r['desc_id']}{held}")
        (S1 / f"read_labeled_{tag}.md").write_text("\n".join(out), encoding="utf-8")


def main():
    utf8_stdout()
    parts = ["# Stage 1 summary", "", "Generated by `s1_summarize.py` from `results/s1/{labeled,neutral}_*.jsonl`. "
             "Final number (1/3, 1/2, 1/4) is the primary label; the stated method is kept as a check next to it.", ""]
    for tag in tags():
        meta, data = load(tag)
        parts.append(section(tag, meta, data))
        samples_file(tag, data)
        if tag in READ_TAGS:
            read_files(tag, data)
    text = "\n".join(parts)
    (S1 / "summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

"""Stage 2, 7B: binary branch-word probe (final number 1/3 vs not) on supported and unsupported answers (CPU/sklearn).

Supported = the judge's steps lead to the boxed number (data key derived_or_recalled == "derived"); unsupported = they
do not ("recalled"). Reads results/s2/acts_word_{tag}.npz (supported) and acts_word_{tag}_unsupported.npz, both from
s2_word_acts.py: residual stream at t - k, t = first token of the first word naming the variable.

Per set x offset x layer: StandardScaler + LogisticRegression, GroupKFold(6) by phrasing outside, C by GroupKFold over
phrasings inside (outer_eval from s2_answer_probe.py); balanced accuracy, chance 50%. At LAYER (fixed in advance, the
layer of the earlier 3-class curve) both nulls with `--n_shuffles` shuffles: within-phrasing and global. Words-only
baselines per set x offset: TF-IDF on prompt + answer text up to t - k, and on the answer text alone. Size-matched
supported curve: `--n_subsets` random subsets of supported answers valid at every offset, with the unsupported class
counts, probed at LAYER.
Writes results/s2/word_probe_binary_{tag}.json and results/s2/summary_word_binary_{tag}.md.
"""
import argparse
import json
import sys

import numpy as np
from joblib import Parallel, delayed

from common import RESULTS, model_tag, read_jsonl, resolve_model, utf8_stdout
from s2_answer_probe import outer_eval, probe_with_nulls, scores
from s2_probe import lr_pipe, md_table, text_pipe

S2 = RESULTS / "s2"
LAYER = 22


def load(tag, suffix):
    Z = np.load(S2 / f"acts_word_{tag}{suffix}.npz")
    m = read_jsonl(S2 / f"acts_word_{tag}{suffix}_meta.jsonl")
    rows = m[1:]
    return dict(W=Z["word"], ok=Z["word_ok"], layers=[int(v) for v in Z["layers"]], offsets=[int(v) for v in Z["offsets"]],
                y=np.array([int(r["final_number"] == "1/3") for r in rows]), g=np.array([r["wording_id"] for r in rows]),
                rows=rows, meta=m[0])


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="7b")
    ap.add_argument("--Cs", type=float, nargs="+", default=[1e-3, 1e-2, 1e-1, 1.0])
    ap.add_argument("--Cs_text", type=float, nargs="+", default=[0.1, 1.0, 10.0, 100.0])
    ap.add_argument("--n_shuffles", type=int, default=50)
    ap.add_argument("--n_subsets", type=int, default=20)
    ap.add_argument("--n_jobs", type=int, default=-1)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    tag = model_tag(resolve_model(args.model))
    D = {"supported": load(tag, ""), "unsupported": load(tag, "_unsupported")}
    layers, offsets = D["supported"]["layers"], D["supported"]["offsets"]
    assert D["unsupported"]["layers"] == layers and D["unsupported"]["offsets"] == offsets
    Li = layers.index(LAYER)
    U = D["unsupported"]
    n_pos, n_neg = int(U["y"].sum()), int((1 - U["y"]).sum())
    for name, d in D.items():
        print(f"{name}: n={len(d['y'])}, 1/3 {int(d['y'].sum())} vs not {int((1 - d['y']).sum())}, "
              f"median anchor token {np.median([r['word_tok'] for r in d['rows']]):.0f}", file=sys.stderr)

    def light(X, y, g):
        pred, chosen = outer_eval(lr_pipe, X, y, g, args.Cs)
        return dict(n=int(len(y)), C=chosen, **scores(y, pred))

    jobs, keys = [], []
    for name, d in D.items():
        for j, k in enumerate(offsets):
            m = d["ok"][:, j]
            for l, L in enumerate(layers):
                jobs.append(delayed(light)(d["W"][m, j, l], d["y"][m], d["g"][m])); keys.append(("curve", name, k, L))
            jobs.append(delayed(probe_with_nulls)(d["W"][m, j, Li], d["y"][m], d["g"][m], args.Cs, args.n_shuffles,
                                                  args.seed + 100 * j + (0 if name == "supported" else 50)))
            keys.append(("nulls", name, k, LAYER))
    # size-matched supported subsets: supported answers valid at every offset, with the unsupported class counts
    S = D["supported"]
    pool = np.where(S["ok"].all(1))[0]
    pos, neg = pool[S["y"][pool] == 1], pool[S["y"][pool] == 0]
    subsets = []
    for s in range(args.n_subsets):
        rng = np.random.default_rng(1000 + s)
        idx = np.sort(np.r_[rng.choice(pos, n_pos, replace=False), rng.choice(neg, n_neg, replace=False)])
        subsets.append(idx.tolist())
        for j, k in enumerate(offsets):
            jobs.append(delayed(light)(S["W"][idx, j, Li], S["y"][idx], S["g"][idx])); keys.append(("matched", s, k, LAYER))
    print(f"running {len(jobs)} jobs ...", file=sys.stderr)
    res = Parallel(n_jobs=args.n_jobs, verbose=5)(jobs)
    curves, nulls, matched = {}, {}, {}
    for (kind, a, k, L), r in zip(keys, res):
        if kind == "curve":
            curves.setdefault(a, {}).setdefault(str(k), {})[L] = r
        elif kind == "nulls":
            nulls.setdefault(a, {})[str(k)] = r
        else:
            matched.setdefault(str(k), []).append(r["bal"])
    matched_sum = {k: dict(mean=float(np.mean(v)), p5=float(np.percentile(v, 5)), p95=float(np.percentile(v, 95)), runs=v)
                   for k, v in matched.items()}

    words = {}
    for name, d in D.items():
        words[name] = {}
        for j, k in enumerate(offsets):
            m = d["ok"][:, j]
            R = [r for r, ok in zip(d["rows"], m) if ok]
            for wname, T in (("prompt_plus_answer_text", [r["prompt"] + "\n\n" + r["text_upto"][str(k)] for r in R]),
                             ("answer_text", [r["text_upto"][str(k)] for r in R])):
                pred, chosen = outer_eval(text_pipe, np.array(T, dtype=object), d["y"][m], d["g"][m], args.Cs_text)
                words[name].setdefault(str(k), {})[wname] = dict(C=chosen, **scores(d["y"][m], pred))

    med = {name: float(np.median([r["word_tok"] for r in d["rows"]])) for name, d in D.items()}
    counts = {name: dict(n=int(len(d["y"])), one_third=int(d["y"].sum()), not_one_third=int((1 - d["y"]).sum()),
                         n_judged=d["meta"].get("n_judged", len(d["y"])), no_word=d["meta"].get("no_word", []),  # older recordings: none dropped
                         phrasings=int(len(set(d["g"].tolist())))) for name, d in D.items()}
    result = dict(tag=tag, layer=LAYER, layers=layers, offsets=offsets, counts=counts, median_anchor_token=med,
                  curves=curves, nulls=nulls, words=words, matched=matched_sum, matched_subsets=subsets,
                  n_shuffles=args.n_shuffles, n_subsets=args.n_subsets)
    (S2 / f"word_probe_binary_{tag}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    f2 = lambda v: f"{100 * v:.0f}%"
    md = [f"# Stage 2, 7B: binary branch-word probe (1/3 vs not), supported vs unsupported answers ({tag})", "",
          "Supported: the written steps lead to the boxed number; unsupported: they do not (hand judgment). Anchor t = first "
          "token of the first word naming the variable (perpendicular distance, distance (d) from the center, central angle, "
          "subtend, midpoint). Residual stream at t − k. Label: final number is 1/3 or not; balanced accuracy, chance 50%. "
          "Folds: GroupKFold(6) by phrasing.", "",
          "| set | answers judged | no variable word (dropped) | n | 1/3 / not | phrasings | median anchor token |",
          "|---|---|---|---|---|---|---|"]
    for name, c in counts.items():
        md.append(f"| {name} | {c['n_judged'] if c['n_judged'] is not None else '–'} | {len(c['no_word']) if c['no_word'] is not None else '–'} | "
                  f"{c['n']} | {c['one_third']} / {c['not_one_third']} | {c['phrasings']} | {med[name]:.0f} |")
    md += ["", f"## Layer {LAYER} (fixed in advance): probe, nulls ({args.n_shuffles} shuffles), words, size-matched supported", "",
           md_table(["k", "supported n", "supported bal", "within null p95", "global null p95", "words (prompt+text)",
                     "unsupported n", "unsupported bal", "within null p95", "global null p95", "words (prompt+text)",
                     f"supported, 56-answer subsets: mean (p5–p95)"],
                    [[k, curves["supported"][str(k)][LAYER]["n"], f2(curves["supported"][str(k)][LAYER]["bal"]),
                      f2(nulls["supported"][str(k)]["null_within"]["bal_p95"]), f2(nulls["supported"][str(k)]["null_global"]["bal_p95"]),
                      f2(words["supported"][str(k)]["prompt_plus_answer_text"]["bal"]),
                      curves["unsupported"][str(k)][LAYER]["n"], f2(curves["unsupported"][str(k)][LAYER]["bal"]),
                      f2(nulls["unsupported"][str(k)]["null_within"]["bal_p95"]), f2(nulls["unsupported"][str(k)]["null_global"]["bal_p95"]),
                      f2(words["unsupported"][str(k)]["prompt_plus_answer_text"]["bal"]),
                      f"{f2(matched_sum[str(k)]['mean'])} ({f2(matched_sum[str(k)]['p5'])}–{f2(matched_sum[str(k)]['p95'])})"]
                     for k in offsets]), "",
           "Words baseline on the answer text alone: " + "; ".join(
               f"{name}: " + ", ".join(f"k={k} {f2(words[name][str(k)]['answer_text']['bal'])}" for k in offsets) for name in D), "",
           f"Small n: the unsupported set has {counts['unsupported']['n']} answers over {counts['unsupported']['phrasings']} phrasings, "
           "so each test fold holds about 9; many phrasings have only a few unsupported answers, and the within-phrasing shuffle "
           "only moves labels in phrasings that have both classes. The size-matched supported subsets show how much a "
           "56-answer set alone lowers and spreads the supported curve.", ""]
    for name in D:
        md += [f"## {name}: balanced accuracy by offset (rows) and layer (columns), no nulls", "",
               md_table(["k"] + [str(L) for L in layers],
                        [[k] + [f2(curves[name][str(k)][L]["bal"]) for L in layers] for k in offsets]), ""]
    (S2 / f"summary_word_binary_{tag}.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:20]))


if __name__ == "__main__":
    main()

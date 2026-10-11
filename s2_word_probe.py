"""Stage 2, last 7B check: probe at fixed distances before the variable is first named in words (CPU/sklearn).

Reads results/s2/acts_word_{tag}.npz (+ meta) from s2_word_acts.py, and results/s2/acts_answers_{tag}.npz (+ meta)
for the first-10-token mean. Probe, folds and nulls as in s2_answer_probe.py: StandardScaler + multinomial LR,
GroupKFold(6) by phrasing outside, C by GroupKFold(5) over phrasings inside; nulls with C fixed to the real run's
most frequent choice: labels shuffled over all answers (global) and within each phrasing (within). Label = final number.

Per offset k (residual at t - k, t = first token of the variable word) x layer: probe + both nulls (`--n_shuffles`).
Words-only baselines per offset: TF-IDF on the answer text up to and including position t - k, and on prompt + that text.
Extra rows (no nulls): without the answers whose formula comes before the word; with the stricter anchor (answers first
naming "distance (d) from the center" re-anchored on a later perpendicular distance / central angle / subtend /
midpoint, or dropped). Best layer = highest balanced accuracy averaged over offsets; there both nulls are rerun with
`--n_shuffles_best` shuffles. Also: the within-phrasing null for the first-10-token mean (missing from the last run).
Writes results/s2/word_probe_{tag}.json and results/s2/summary_word_{tag}.md.
"""
import argparse
import json
import sys

import numpy as np
from joblib import Parallel, delayed

from common import APPROACHES, RESULTS, model_tag, read_jsonl, resolve_model, utf8_stdout
from s2_answer_probe import outer_eval, probe_with_nulls, scores
from s2_probe import lr_pipe, md_table, text_pipe

S2 = RESULTS / "s2"


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="7b")
    ap.add_argument("--Cs", type=float, nargs="+", default=[1e-3, 1e-2, 1e-1, 1.0])
    ap.add_argument("--Cs_text", type=float, nargs="+", default=[0.1, 1.0, 10.0, 100.0])
    ap.add_argument("--n_shuffles", type=int, default=20)
    ap.add_argument("--n_shuffles_best", type=int, default=50)
    ap.add_argument("--n_jobs", type=int, default=-1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--only_layers", type=int, nargs="+", default=None, help="smoke test on a few layers (must include 16)")
    args = ap.parse_args()
    tag = model_tag(resolve_model(args.model))

    Z = np.load(S2 / f"acts_word_{tag}.npz")
    zm = read_jsonl(S2 / f"acts_word_{tag}_meta.jsonl")
    zmeta, rows = zm[0], zm[1:]
    layers, offsets = [int(v) for v in Z["layers"]], [int(v) for v in Z["offsets"]]
    W, Wok, S, Sok = Z["word"], Z["word_ok"], Z["strict"], Z["strict_ok"]
    F10_all = None
    if args.only_layers:
        idx = [layers.index(L) for L in args.only_layers]
        W, S, layers = W[:, :, idx], S[:, :, idx], list(args.only_layers)
    y = np.array([APPROACHES.index(r["label"]) for r in rows])
    g = np.array([r["wording_id"] for r in rows])
    no_ff = np.array([not r["formula_before_word"] for r in rows])
    print(f"{tag}: {len(y)} answers, offsets {offsets}, layers {layers}", file=sys.stderr)

    A = np.load(S2 / f"acts_answers_{tag}.npz")
    am = read_jsonl(S2 / f"acts_answers_{tag}_meta.jsonl")[1:]
    akeep = np.array([not r["in_window"] for r in am])
    am = [r for r, k in zip(am, akeep) if k]
    ya = np.array([APPROACHES.index(r["label"]) for r in am])
    ga = np.array([r["wording_id"] for r in am])
    alayers = [int(v) for v in A["layers"]]
    F10 = A["first10"][akeep][:, [alayers.index(L) for L in layers]]

    def full(X, yy, gg, n_sh, seed):
        return probe_with_nulls(X, yy, gg, args.Cs, n_sh, seed)

    def light(X, yy, gg):
        pred, chosen = outer_eval(lr_pipe, X, yy, gg, args.Cs)
        return dict(n=int(len(yy)), C=chosen, **scores(yy, pred))

    jobs, keys = [], []
    for j, k in enumerate(offsets):
        m = Wok[:, j]
        ms = Sok[:, j]
        mf = m & no_ff
        for Li, L in enumerate(layers):
            jobs.append(delayed(full)(W[m, j, Li], y[m], g[m], args.n_shuffles, args.seed + 100 * j + Li)); keys.append(("main", k, L))
            jobs.append(delayed(light)(W[mf, j, Li], y[mf], g[mf])); keys.append(("no_formula_first", k, L))
            jobs.append(delayed(light)(S[ms, j, Li], y[ms], g[ms])); keys.append(("strict_anchor", k, L))
    for Li, L in enumerate(layers):
        jobs.append(delayed(full)(F10[:, Li], ya, ga, args.n_shuffles, args.seed + 5000 + Li)); keys.append(("first10", None, L))
    print(f"running {len(jobs)} jobs ...", file=sys.stderr)
    res = Parallel(n_jobs=args.n_jobs, verbose=5)(jobs)
    out = {}
    for (name, k, L), r in zip(keys, res):
        if name != "first10":
            r["n"] = r.get("n", None)
        out.setdefault(name, {}).setdefault(str(k), {})[L] = r
    for k in offsets:
        n = int(Wok[:, offsets.index(k)].sum())
        for L in layers:
            out["main"][str(k)][L]["n"] = n

    # best layer and the 50-shuffle rerun
    mean_bal = {L: float(np.mean([out["main"][str(k)][L]["bal"] for k in offsets])) for L in layers}
    best = max(mean_bal, key=mean_bal.get)
    Bi = layers.index(best)
    print(f"best layer {best} (mean bal {mean_bal[best]:.3f}); rerunning nulls with {args.n_shuffles_best} shuffles", file=sys.stderr)
    res_b = Parallel(n_jobs=args.n_jobs, verbose=5)(
        delayed(full)(W[Wok[:, j], j, Bi], y[Wok[:, j]], g[Wok[:, j]], args.n_shuffles_best, args.seed + 9000 + j)
        for j in range(len(offsets)))
    best_rerun = {str(k): r for k, r in zip(offsets, res_b)}

    # words-only baselines per offset
    words = {}
    for j, k in enumerate(offsets):
        m = Wok[:, j]
        T = np.array([r["text_upto"][str(k)] for r, ok in zip(rows, m) if ok], dtype=object)
        TP = np.array([r["prompt"] + "\n\n" + r["text_upto"][str(k)] for r, ok in zip(rows, m) if ok], dtype=object)
        words[str(k)] = {}
        for name, X in (("answer_text", T), ("prompt_plus_answer_text", TP)):
            pred, chosen = outer_eval(text_pipe, X, y[m], g[m], args.Cs_text)
            words[str(k)][name] = dict(C=chosen, **scores(y[m], pred))

    n_re, n_drop = zmeta["n_reanchored"], zmeta["n_no_strict"]
    result = dict(tag=tag, layers=layers, offsets=offsets, n=int(len(y)), n_formula_first=int((~no_ff).sum()),
                  n_reanchored=n_re, n_no_strict=n_drop, n_shuffles=args.n_shuffles, n_shuffles_best=args.n_shuffles_best,
                  best_layer=best, mean_bal_by_layer=mean_bal, curves=out, best_rerun=best_rerun, words=words,
                  majority=float(np.bincount(y).max() / len(y)), acts_meta=zmeta)
    (S2 / f"word_probe_{tag}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    # ---- markdown
    f2 = lambda v: f"{100 * v:.0f}%"
    M = out["main"]
    md = [f"# Stage 2, last 7B check: before the variable is named in words ({tag})", "",
          f"{len(y)} derived neutral answers; t = first token of the first variable word (perpendicular distance, distance (d) "
          f"from the center, central angle, subtend, midpoint). Residual at single positions t − k. Label = final number; "
          f"balanced accuracy, chance 33%; plain-accuracy majority {f2(result['majority'])}. Folds: GroupKFold(6) by phrasing. "
          f"Nulls: global = labels shuffled over all answers; within = shuffled inside each phrasing.", "",
          "## Balanced accuracy by offset (rows) and layer (columns)", "",
          md_table(["k (tokens before the word)", "n"] + [str(L) for L in layers],
                   [[k, M[str(k)][layers[0]]["n"]] + [f2(M[str(k)][L]["bal"]) for L in layers] for k in offsets]), ""]

    def curve(L, rerun=None):
        rows_ = []
        for k in offsets:
            r = rerun[str(k)] if rerun else M[str(k)][L]
            wk = words[str(k)]
            rows_.append([k, M[str(k)][L]["n"], f2(r["acc"]), f2(r["bal"]),
                          f"{f2(r['null_global']['bal_mean'])} / {f2(r['null_global']['bal_p95'])}",
                          f"{f2(r['null_within']['bal_mean'])} / {f2(r['null_within']['bal_p95'])}",
                          f2(wk["answer_text"]["bal"]), f2(wk["prompt_plus_answer_text"]["bal"]),
                          f2(out["no_formula_first"][str(k)][L]["bal"]), f2(out["strict_anchor"][str(k)][L]["bal"])])
        return md_table(["k", "n", "acc", "bal", "global null bal (mean / p95)", "within null bal (mean / p95)",
                         "words: answer text up to t−k", "words: prompt + that text",
                         f"without {result['n_formula_first']} formula-first", "stricter anchor"], rows_)

    md += [f"## Curve at the best layer ({best}; nulls with {args.n_shuffles_best} shuffles)", "",
           f"Best layer = highest balanced accuracy averaged over offsets (mean {f2(mean_bal[best])}). "
           f"'without formula-first' drops the {result['n_formula_first']} answers whose chord-length formula comes before the word; "
           f"'stricter anchor' re-anchors the answers first naming 'distance (d) from the center' on a later stricter word "
           f"({n_re} re-anchored, {n_drop} dropped). Those two rows have no nulls; the words columns use the same folds.", "",
           curve(best, best_rerun), "",
           f"## Curve at layer 16 (nulls with {args.n_shuffles} shuffles)", "", curve(16), ""]
    F = out["first10"]["None"]
    md += ["## First-10-token mean (the null missing from the last run)", "",
           f"Same {len(ya)} answers and folds as `summary_answer_{tag}.md`; {args.n_shuffles} shuffles.", "",
           md_table(["layer", "acc", "bal", "global null bal (mean / p95)", "within null bal (mean / p95)"],
                    [[L, f2(F[L]["acc"]), f2(F[L]["bal"]),
                      f"{f2(F[L]['null_global']['bal_mean'])} / {f2(F[L]['null_global']['bal_p95'])}",
                      f"{f2(F[L]['null_within']['bal_mean'])} / {f2(F[L]['null_within']['bal_p95'])}"] for L in layers]), ""]
    (S2 / f"summary_word_{tag}.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()

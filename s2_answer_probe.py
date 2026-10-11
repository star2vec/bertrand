"""Stage 2, answer direction probe and comparison with the reading direction (CPU/sklearn).

Reads results/s2/acts_answers_{tag}.npz (+ meta, from s2_answer_acts.py) and results/s2/acts_{tag}.npz (+ meta,
from s2_activations.py). Same layers in both.

Answer probe (per layer): StandardScaler + multinomial LogisticRegression on the mean residual over the early-answer
window, label = final number (A 1/3, B 1/2, C 1/4), derived answers whose first chord-length formula falls after the
window. Outer folds: GroupKFold(6) by phrasing (every test phrasing unseen in training); C picked inside each training
fold by GroupKFold(5) over phrasings. Nulls (same folds, C fixed to the real run's most frequent choice):
  global       : labels permuted over all answers
  within       : labels permuted within each phrasing (keeps the phrasing -> number link, removes sample-level signal)
Baselines on the same folds: TF-IDF on the prompt text, TF-IDF on the decoded window text, majority class.
The last-prompt-token probe is run the same way (its activation is the same for every sample of a phrasing).
Sensitivity: means over the first 10 / 20 / 30 / 60 answer tokens, with how many answers have the formula / the
variable named in words inside each span.

Comparison (per layer): reading probe = s2_probe's pipeline refit on the labeled train split (C by GroupKFold over
phrasings); answer probe = fit on all kept answers. Alignment: cosine between raw-space class weights (coef / scale)
and between difference-of-means directions, class by class and as 3x3 matrices; null = the same cosines with answer
probes fit on globally shuffled labels. Cross-prediction: reading probe -> answer window means and answer last prompt
token; answer probe -> labeled prompts (all, strict). Raw and with each set shifted onto the training set's mean.
Writes results/s2/answer_probe_{tag}.json and results/s2/summary_answer_{tag}.md.
"""
import argparse
import json
import sys
from collections import Counter

import numpy as np
from joblib import Parallel, delayed
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import GroupKFold

from common import APPROACHES, RESULTS, model_tag, read_jsonl, resolve_model, utf8_stdout
from s2_probe import cv_fit, lr_pipe, md_table, text_pipe

S2 = RESULTS / "s2"
N_OUTER = 6


def outer_eval(make, X, y, groups, Cs, C_fixed=None):
    """Predictions for every answer from models trained on the other phrasings. -> (pred, chosen Cs)"""
    pred, chosen = np.empty(len(y), dtype=int), []
    for tr, te in GroupKFold(N_OUTER).split(X, y, groups):
        assert not set(groups[tr]) & set(groups[te])
        if C_fixed is None:
            m, C, _ = cv_fit(make, X[tr], y[tr], groups[tr], Cs)
        else:
            m, C = make(C_fixed).fit(X[tr], y[tr]), C_fixed
        pred[te] = m.predict(X[te])
        chosen.append(C)
    return pred, chosen


def scores(y, pred):
    return dict(acc=float((pred == y).mean()), bal=float(balanced_accuracy_score(y, pred)))


def perm_within(y, groups, rng):
    yp = y.copy()
    for g in np.unique(groups):
        i = np.where(groups == g)[0]
        yp[i] = rng.permutation(y[i])
    return yp


def probe_with_nulls(X, y, groups, Cs, n_shuffles, seed):
    rng = np.random.default_rng(seed)
    pred, chosen = outer_eval(lr_pipe, X, y, groups, Cs)
    C0 = Counter(chosen).most_common(1)[0][0]
    out = dict(C=chosen, **scores(y, pred))
    for name, perm in [("global", lambda: rng.permutation(y)), ("within", lambda: perm_within(y, groups, rng))]:
        acc, bal = [], []
        for _ in range(n_shuffles):
            p, _ = outer_eval(lr_pipe, X, perm(), groups, Cs, C_fixed=C0)
            s = scores(y, p)  # scored against the true labels
            acc.append(s["acc"]); bal.append(s["bal"])
        out[f"null_{name}"] = dict(acc_mean=float(np.mean(acc)), acc_p95=float(np.percentile(acc, 95)),
                                   bal_mean=float(np.mean(bal)), bal_p95=float(np.percentile(bal, 95)))
    return out


def raw_weights(model):
    sc, lr = model[0], model[1]
    W = lr.coef_ / sc.scale_
    return W / np.linalg.norm(W, axis=1, keepdims=True)


def dm_dirs(X, y):
    mu = np.stack([X[y == k].mean(0) for k in range(3)])
    U = np.stack([mu[k] - np.delete(mu, k, 0).mean(0) for k in range(3)])
    return U / np.linalg.norm(U, axis=1, keepdims=True)


def compare_layer(Li, R, Ry, Rgroups, tr, strict, Xw, Xl, y, groups, Cs, n_shuffles, seed):
    rng = np.random.default_rng(seed + 1000 + Li)
    Xr = R[:, Li]
    rprobe, rC, _ = cv_fit(lr_pipe, Xr[tr], Ry[tr], Rgroups[tr], Cs)
    aprobe, aC, _ = cv_fit(lr_pipe, Xw[:, Li], y, groups, Cs)
    Wr, Wa = raw_weights(rprobe), raw_weights(aprobe)
    Dr, Da = dm_dirs(Xr[tr], Ry[tr]), dm_dirs(Xw[:, Li], y)
    cosW, cosD = Wr @ Wa.T, Dr @ Da.T
    nullW, nullD = [], []
    for _ in range(n_shuffles):
        yp = rng.permutation(y)
        Wn = raw_weights(lr_pipe(aC).fit(Xw[:, Li], yp))
        Dn = dm_dirs(Xw[:, Li], yp)
        nullW += list(np.abs(np.diag(Wr @ Wn.T)))
        nullD += list(np.abs(np.diag(Dr @ Dn.T)))
    mu_rtr, mu_w, mu_l, mu_lab = Xr[tr].mean(0), Xw[:, Li].mean(0), Xl[:, Li].mean(0), Xr.mean(0)
    cross = {}
    for name, X, shift in [("read_to_window", Xw[:, Li], mu_rtr - mu_w), ("read_to_last", Xl[:, Li], mu_rtr - mu_l)]:
        cross[name] = dict(raw=scores(y, rprobe.predict(X)), centered=scores(y, rprobe.predict(X + shift)))
    for name, m in [("answer_to_labeled", np.ones(len(Ry), bool)), ("answer_to_strict", strict)]:
        X = Xr[m]
        cross[name] = dict(raw=scores(Ry[m], aprobe.predict(X)),
                           centered=scores(Ry[m], aprobe.predict(X - mu_lab + mu_w)))
    return dict(read_C=rC, answer_C=aC, cos_w=cosW.tolist(), cos_dm=cosD.tolist(),
                null_w_p95=float(np.percentile(nullW, 95)), null_dm_p95=float(np.percentile(nullD, 95)), cross=cross)


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="7b")
    ap.add_argument("--Cs", type=float, nargs="+", default=[1e-3, 1e-2, 1e-1, 1.0])
    ap.add_argument("--Cs_text", type=float, nargs="+", default=[0.1, 1.0, 10.0, 100.0])
    ap.add_argument("--n_shuffles", type=int, default=20)
    ap.add_argument("--n_jobs", type=int, default=-1)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    tag = model_tag(resolve_model(args.model))

    A = np.load(S2 / f"acts_answers_{tag}.npz")
    am = read_jsonl(S2 / f"acts_answers_{tag}_meta.jsonl")
    ameta, arows = am[0], am[1:]
    layers = [int(v) for v in A["layers"]]
    keep = np.array([not r["in_window"] for r in arows])
    arows = [r for r, k in zip(arows, keep) if k]
    y = np.array([APPROACHES.index(r["label"]) for r in arows])
    groups = np.array([r["wording_id"] for r in arows])
    acts = {k: A[k][keep] for k in A.files if k != "layers"}
    w = ameta["window"]
    fpos = json.loads((S2 / f"formula_pos_{tag}.json").read_text(encoding="utf-8"))
    spans = ameta["spans"]
    inside = {s: dict(formula=sum(r["formula_tok"] is not None and r["formula_tok"] < s for r in arows),
                      word=sum(r["word_tok"] is not None and r["word_tok"] < s for r in arows)) for s in spans}
    print(f"{tag}: {len(y)} answers kept of {len(keep)} (window {w}), labels {Counter(y.tolist())}, "
          f"{len(set(groups))} phrasings, layers {layers}", file=sys.stderr)

    R = np.load(S2 / f"acts_{tag}.npz")
    assert [int(v) for v in R["layers"]] == layers, "reading and answer activations use different layers"
    rm = read_jsonl(S2 / f"acts_{tag}_meta.jsonl")[1:]
    lab = [i for i, r in enumerate(rm) if r["set"] == "labeled"]
    Rl = R["last"][lab]
    Ry = np.array([APPROACHES.index(rm[i]["approach"]) for i in lab])
    Rg = np.array([rm[i]["wording_id"] for i in lab])
    hw = np.array([rm[i]["heldout_wording"] for i in lab])
    hd = np.array([rm[i]["heldout_desc"] for i in lab])
    tr, strict = ~hw & ~hd, hw & hd

    majority = float(np.bincount(y).max() / len(y))
    jobs = []
    for Li in range(len(layers)):
        jobs.append(("window", Li, acts["window"][:, Li], True))
        jobs.append(("last", Li, acts["last"][:, Li], True))
        for s in spans:
            if s != w:  # the span equal to the window is the window row itself
                jobs.append((f"first{s}", Li, acts[f"first{s}"][:, Li], False))

    def run(job):
        name, Li, X, nulls = job
        if nulls:
            return name, Li, probe_with_nulls(X, y, groups, args.Cs, args.n_shuffles, args.seed + Li)
        pred, chosen = outer_eval(lr_pipe, X, y, groups, args.Cs)
        return name, Li, dict(C=chosen, **scores(y, pred))

    print(f"probing {len(jobs)} (position, layer) jobs ...", file=sys.stderr)
    res = Parallel(n_jobs=args.n_jobs, verbose=5)(delayed(run)(j) for j in jobs)
    curves = {}
    for name, Li, r in res:
        curves.setdefault(name, {})[layers[Li]] = r

    texts = {"prompt text": np.array([r["prompt"] for r in arows], dtype=object),
             "window text": np.array([r["window_text"] for r in arows], dtype=object)}
    text_base = {}
    for k, T in texts.items():
        pred, chosen = outer_eval(text_pipe, T, y, groups, args.Cs_text)
        text_base[k] = dict(C=chosen, **scores(y, pred))

    print("comparing directions ...", file=sys.stderr)
    comp = Parallel(n_jobs=args.n_jobs, verbose=5)(
        delayed(compare_layer)(Li, Rl, Ry, Rg, tr, strict, acts["window"], acts["last"], y, groups, args.Cs,
                               args.n_shuffles, args.seed) for Li in range(len(layers)))
    comp = {layers[Li]: c for Li, c in enumerate(comp)}

    result = dict(tag=tag, layers=layers, window=w, w_rule=ameta["w_rule"], n_kept=int(len(y)), n_total=int(len(keep)),
                  label_counts={a: int((y == k).sum()) for k, a in enumerate(APPROACHES)}, majority=majority,
                  inside_span=inside, formula_pos={k: v for k, v in fpos.items() if k != "rows"},
                  curves=curves, text_baselines=text_base, comparison=comp, n_shuffles=args.n_shuffles,
                  acts_meta=ameta)
    (S2 / f"answer_probe_{tag}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    # ---- markdown
    f2 = lambda v: f"{100 * v:.0f}%"
    fp = result["formula_pos"]
    out = [f"# Stage 2, answer direction: {tag}", "",
           f"Activations from {ameta['time']} ({ameta['device']}, {ameta['dtype']}). {len(y)} derived neutral answers "
           f"(of {len(keep)}; {len(keep) - len(y)} dropped because the formula starts inside the window), "
           f"labels by final number {result['label_counts']}, {len(set(groups))} phrasings. "
           f"Majority-class rate {f2(majority)}; balanced accuracy chance 33%. Folds: GroupKFold({N_OUTER}) by phrasing, "
           f"so every test phrasing is unseen in training.", "",
           "## Where the first chord-length formula starts (answer tokens)", "",
           f"Formula found in {fp['n_formula']}/{fp['n']} answers (the rest argue in words only). Percentiles of its first "
           f"token: {fp['formula_tok_percentiles']}. Variable named in words (distance / central angle / subtend / midpoint): "
           f"{fp['word_tok_percentiles']}. Rule: largest w with the formula at or after w in >= {f2(fp['cover'])} of answers "
           f"gives {fp['w_rule']}; clipped to [{fp['w_min']}, {fp['w_max']}] -> window = first {w} tokens.", ""]
    out += ["## Answer probe per layer (window mean) and last-prompt-token probe", "",
            "The last-prompt-token activation is the same for every sample of a phrasing, so its within-phrasing null equals the "
            "real run by construction and is shown only for completeness.", "",
            "acc / balanced acc. Nulls: mean and 95th percentile of balanced accuracy over "
            f"{args.n_shuffles} shuffles; global = labels shuffled over all answers, within = shuffled inside each phrasing.", "",
            md_table(["layer", "window acc", "window bal", "global null bal (mean / p95)", "within null bal (mean / p95)",
                      "last-prompt acc", "last-prompt bal", "last: global null p95", "last: within null p95"],
                     [[L, f2(curves["window"][L]["acc"]), f2(curves["window"][L]["bal"]),
                       f"{f2(curves['window'][L]['null_global']['bal_mean'])} / {f2(curves['window'][L]['null_global']['bal_p95'])}",
                       f"{f2(curves['window'][L]['null_within']['bal_mean'])} / {f2(curves['window'][L]['null_within']['bal_p95'])}",
                       f2(curves["last"][L]["acc"]), f2(curves["last"][L]["bal"]),
                       f2(curves["last"][L]["null_global"]["bal_p95"]), f2(curves["last"][L]["null_within"]["bal_p95"])]
                      for L in layers]), "",
            "Words-only baselines (same folds): " + "; ".join(f"{k}: acc {f2(v['acc'])}, bal {f2(v['bal'])}" for k, v in text_base.items())
            + f"; majority class: acc {f2(majority)}, bal 33%. Layer 0 of the window is the mean token embedding.", ""]
    sens_cols = [f"first{s}" if f"first{s}" in curves else "window" for s in spans]
    out += ["## Sensitivity: mean over the first N answer tokens (balanced accuracy)", "",
            "Answers with the formula inside the span: " + ", ".join(f"first {s}: {inside[s]['formula']}" for s in spans)
            + ". Answers naming the variable in words inside the span: " + ", ".join(f"first {s}: {inside[s]['word']}" for s in spans)
            + f" (of {len(y)}). A higher number for a longer span can come from the answer stating its approach, not from earlier commitment.", "",
            md_table(["layer"] + [f"first {s}" for s in spans],
                     [[L] + [f2(curves[c][L]["bal"]) for c in sens_cols] for L in layers]), ""]
    num = lambda v, f="{:.2f}": "–" if v is None or not np.isfinite(v) else f.format(v)
    cls = lambda M: " / ".join(num(M[k][k], "{:+.2f}") for k in range(3))
    out += ["## Reading direction vs answer direction", "",
            "cos: class-by-class cosine (A / B / C) between the reading probe's and the answer probe's raw-space weights, "
            "and between their difference-of-means directions; null = 95th percentile of |cos| with answer probes on shuffled "
            "labels; – where the reading activations do not vary (layer 0 at the last prompt token is the same token embedding for every "
            "prompt). Cross-prediction as balanced accuracy, raw / centered (each set shifted onto the training set's mean).", "",
            md_table(["layer", "cos weights A/B/C", "null p95", "cos diff-means A/B/C", "null p95",
                      "read -> answer window", "read -> answer last prompt", "answer -> labeled (all)", "answer -> labeled (strict)"],
                     [[L, cls(c["cos_w"]), num(c["null_w_p95"]), cls(c["cos_dm"]), num(c["null_dm_p95"])]
                      + [f"{f2(c['cross'][k]['raw']['bal'])} / {f2(c['cross'][k]['centered']['bal'])}"
                         for k in ["read_to_window", "read_to_last", "answer_to_labeled", "answer_to_strict"]]
                      for L, c in comp.items()]), "",
            "Full 3x3 cosine matrices are in the json (`comparison[layer].cos_w`, rows = reading classes, columns = answer classes).", ""]
    (S2 / f"summary_answer_{tag}.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()

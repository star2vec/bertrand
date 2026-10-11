"""Stage 2 probe (Mac, CPU/sklearn). Reads results/s2/acts_{tag}.npz + meta.

Per layer (primary position "last"): StandardScaler + multinomial LogisticRegression, C chosen by GroupKFold(5)
over training wordings. Splits of the 432 labeled prompts:
  train     = training wordings x training descriptions (13 x 5 x 3 = 195)
  strict    = held-out wordings x held-out descriptions (5 x 3 x 3 = 45)
  desc_only = training wordings x held-out descriptions (117)
  word_only = held-out wordings x training descriptions (75)
Layer chosen by the inner CV accuracy on train. Baselines at that layer: labels shuffled within train (n repeats)
and a TF-IDF word 1-2gram text classifier on the same splits. Also difference-of-means directions and a
nearest-centroid classifier. The chosen-layer probe is applied to the neutral prompts and set next to the stage-1
sampling frequencies when results/s1/neutral_{tag}.jsonl exists.
Writes results/s2/probe_{tag}.json, results/s2/direction_{tag}.npz (for stage 3), results/s2/summary_{tag}.md.
"""
import argparse
import json
import sys

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from common import APPROACHES, APPROACH_LABEL, RESULTS, model_tag, read_jsonl, resolve_model, utf8_stdout

S2 = RESULTS / "s2"
SPLITS = ["train", "strict", "desc_only", "word_only"]


def md_table(header, rows):
    out = ["| " + " | ".join(str(h) for h in header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def cv_fit(make, X, y, groups, Cs):
    """Pick C by GroupKFold(5) accuracy, refit on all of (X, y). -> (model, C, cv_acc)"""
    best = None
    for C in Cs:
        accs = []
        for tr, te in GroupKFold(5).split(X, y, groups):
            accs.append(make(C).fit(X[tr], y[tr]).score(X[te], y[te]))
        acc = float(np.mean(accs))
        if best is None or acc > best[1]:
            best = (C, acc)
    return make(best[0]).fit(X, y), best[0], best[1]


def lr_pipe(C):
    return make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=5000))


def text_pipe(C):
    return make_pipeline(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True), LogisticRegression(C=C, max_iter=5000))


def split_scores(model, X, y, masks):
    return {s: float(model.score(X[m], y[m])) for s, m in masks.items()}


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="1.5b")
    ap.add_argument("--position", default="last", choices=["last", "user_last", "user_mean"])
    ap.add_argument("--Cs", type=float, nargs="+", default=[1e-3, 1e-2, 1e-1, 1.0])
    ap.add_argument("--Cs_text", type=float, nargs="+", default=[0.1, 1.0, 10.0, 100.0])
    ap.add_argument("--n_shuffles", type=int, default=20)
    ap.add_argument("--layer", type=int, default=None, help="override the CV-chosen layer")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    tag = model_tag(resolve_model(args.model))
    rng = np.random.default_rng(args.seed)

    acts = np.load(S2 / f"acts_{tag}.npz")
    layer_ids = [int(v) for v in acts["layers"]] if "layers" in acts.files else list(range(acts["last"].shape[1]))
    meta_rows = read_jsonl(S2 / f"acts_{tag}_meta.jsonl")
    run_meta, meta = meta_rows[0], meta_rows[1:]
    lab = [i for i, r in enumerate(meta) if r["set"] == "labeled"]
    neu = [i for i, r in enumerate(meta) if r["set"] == "neutral"]
    y = np.array([APPROACHES.index(meta[i]["approach"]) for i in lab])
    hw = np.array([meta[i]["heldout_wording"] for i in lab])
    hd = np.array([meta[i]["heldout_desc"] for i in lab])
    groups = np.array([meta[i]["wording_id"] for i in lab])
    masks = {"train": ~hw & ~hd, "strict": hw & hd, "desc_only": ~hw & hd, "word_only": hw & ~hd}
    tr = masks["train"]
    # leakage asserts: no held-out wording or description id appears in train
    assert not (set(groups[tr]) & set(groups[hw])), "held-out wording in train"
    assert not ({meta[i]["desc_id"] for i in np.array(lab)[tr]} & {meta[i]["desc_id"] for i in np.array(lab)[hd]}), "held-out desc in train"
    sizes = {s: int(m.sum()) for s, m in masks.items()}
    print(f"{tag}: {len(lab)} labeled, {len(neu)} neutral; splits {sizes}; position {args.position}", file=sys.stderr)

    # ---- layer curve (all positions; model selection on the primary position)
    curves = {}
    for pos in ["last", "user_last", "user_mean"]:
        A = acts[pos][lab]  # (n_lab, n_layers+1, d)
        curve = []
        for L, lid in enumerate(layer_ids):
            X = A[:, L, :]
            model, C, cv = cv_fit(lr_pipe, X[tr], y[tr], groups[tr], args.Cs)
            sc = split_scores(model, X, y, masks)
            curve.append(dict(layer=lid, C=C, cv=cv, **sc))
            if pos == args.position:
                print(f"  L{lid:2d} C={C:<6g} cv={cv:.2f} train={sc['train']:.2f} strict={sc['strict']:.2f} "
                      f"desc_only={sc['desc_only']:.2f} word_only={sc['word_only']:.2f}", file=sys.stderr)
        curves[pos] = curve
    curve = curves[args.position]
    L = args.layer if args.layer is not None else layer_ids[int(np.argmax([c["cv"] for c in curve]))]
    Li = layer_ids.index(L)  # array index of the chosen layer
    X = acts[args.position][lab][:, Li, :]
    probe, C, cv = cv_fit(lr_pipe, X[tr], y[tr], groups[tr], args.Cs)
    chosen = dict(layer=L, C=C, cv=cv, **split_scores(probe, X, y, masks))

    # ---- shuffled-label null at the chosen layer (same pipeline incl. C selection)
    null = {s: [] for s in SPLITS}
    for _ in range(args.n_shuffles):
        yp = y.copy()
        yp[tr] = rng.permutation(y[tr])
        m, _, _ = cv_fit(lr_pipe, X[tr], yp[tr], groups[tr], args.Cs)
        for s, v in split_scores(m, X, y, masks).items():  # scored against the true labels
            null[s].append(v)
    null_summary = {s: dict(mean=float(np.mean(v)), p95=float(np.percentile(v, 95)), max=float(np.max(v))) for s, v in null.items()}

    # ---- text baseline on the same splits
    texts = np.array([meta[i]["text"] for i in lab], dtype=object)
    tmodel, tC, tcv = cv_fit(text_pipe, texts[tr], y[tr], groups[tr], args.Cs_text)
    text_scores = dict(C=tC, cv=tcv, **split_scores(tmodel, texts, y, masks))

    # ---- difference of means + nearest centroid at the chosen layer
    mu = np.stack([X[tr][y[tr] == k].mean(0) for k in range(3)])
    nc_pred = np.argmin(((X[:, None, :] - mu[None]) ** 2).sum(-1), axis=1)
    nc_scores = {s: float((nc_pred[m] == y[m]).mean()) for s, m in masks.items()}
    scaler = probe[0]
    Xs = scaler.transform(X)
    mus = np.stack([Xs[tr][y[tr] == k].mean(0) for k in range(3)])
    ncs_pred = np.argmin(((Xs[:, None, :] - mus[None]) ** 2).sum(-1), axis=1)
    ncs_scores = {s: float((ncs_pred[m] == y[m]).mean()) for s, m in masks.items()}

    # ---- directions for stage 3 (raw residual space, unit norm) and their class separations
    W = probe[1].coef_ / scaler.scale_  # (3, d): standardized-space weights mapped back to raw space
    u_clf = W / np.linalg.norm(W, axis=1, keepdims=True)
    u_dm = np.stack([mu[k] - np.delete(mu, k, 0).mean(0) for k in range(3)])
    u_dm /= np.linalg.norm(u_dm, axis=1, keepdims=True)

    def separation(U):
        out = []
        for k in range(3):
            p = X[tr] @ U[k]
            out.append(float(p[y[tr] == k].mean() - p[y[tr] != k].mean()))
        return out

    sep_clf, sep_dm = separation(u_clf), separation(u_dm)
    resid_norm = float(np.linalg.norm(X[tr], axis=1).mean())
    cos = [float(u_clf[k] @ u_dm[k]) for k in range(3)]
    np.savez(S2 / f"direction_{tag}.npz", layer=L, position=args.position, u_clf=u_clf, sep_clf=np.array(sep_clf),
             u_dm=u_dm, sep_dm=np.array(sep_dm), resid_norm=resid_norm, scaler_mean=scaler.mean_, scaler_scale=scaler.scale_)

    # ---- apply to neutral prompts, next to stage-1 sampling frequencies if present
    Xn = acts[args.position][neu][:, Li, :]
    P = probe.predict_proba(Xn)
    s1 = [r for r in read_jsonl(RESULTS / "s1" / f"neutral_{tag}.jsonl") if r.get("kind") == "answer"]
    neutral_rows, agree, n_cmp = [], 0, 0
    for i, idx in enumerate(neu):
        wid = meta[idx]["wording_id"]
        samp = [r for r in s1 if r["wording_id"] == wid]
        freq = {a: sum(r["approach_number"] == a for r in samp) / len(samp) for a in APPROACHES} if samp else None
        row = dict(wording_id=wid, heldout_wording=meta[idx]["heldout_wording"],
                   probe={a: round(float(P[i, k]), 3) for k, a in enumerate(APPROACHES)},
                   probe_argmax=APPROACHES[int(P[i].argmax())], sampled=freq, n_samples=len(samp))
        if freq and max(freq.values()) > 0:
            row["sampled_argmax"] = max(freq, key=freq.get)
            n_cmp += 1
            agree += row["probe_argmax"] == row["sampled_argmax"]
        neutral_rows.append(row)
    spearman = {}
    if n_cmp >= 3:
        from scipy.stats import spearmanr
        for a in APPROACHES:
            f = np.array([r["sampled"][a] for r in neutral_rows if r["sampled"]])
            p = np.array([r["probe"][a] for r in neutral_rows if r["sampled"]])
            spearman[a] = None if f.std() == 0 else float(spearmanr(f, p).statistic)

    result = dict(tag=tag, position=args.position, sizes=sizes, Cs=args.Cs, chosen=chosen, curves=curves,
                  null=null_summary, n_shuffles=args.n_shuffles, text_baseline=text_scores,
                  nearest_centroid_raw=nc_scores, nearest_centroid_standardized=ncs_scores,
                  direction=dict(sep_clf=sep_clf, sep_dm=sep_dm, cos_clf_dm=cos, resid_norm=resid_norm),
                  neutral=neutral_rows, neutral_argmax_agreement=(agree, n_cmp), spearman=spearman,
                  acts_meta=run_meta)
    (S2 / f"probe_{tag}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    # ---- markdown
    f2 = lambda v: f"{100 * v:.0f}%"
    out = [f"# Stage 2 probe: {tag}", "", f"Position `{args.position}`, activations from {run_meta['time']} ({run_meta['device']}, {run_meta['dtype']}). "
           f"Splits: {sizes}. Accuracies are 3-class (chance 33%); the strict set has {sizes['strict']} examples, so one example is {100 / sizes['strict']:.1f} points.", ""]
    out += [f"## Chosen layer {L} (by inner CV on train; C={C:g})", "",
            md_table(["", "cv (train)", "train", "strict", "desc_only", "word_only"],
                     [["probe (activations)", f2(cv), f2(chosen["train"]), f2(chosen["strict"]), f2(chosen["desc_only"]), f2(chosen["word_only"])],
                      [f"shuffled labels, mean of {args.n_shuffles}", "", f2(null_summary["train"]["mean"]), f2(null_summary["strict"]["mean"]), f2(null_summary["desc_only"]["mean"]), f2(null_summary["word_only"]["mean"])],
                      ["shuffled labels, 95th pct", "", f2(null_summary["train"]["p95"]), f2(null_summary["strict"]["p95"]), f2(null_summary["desc_only"]["p95"]), f2(null_summary["word_only"]["p95"])],
                      [f"text TF-IDF (C={tC:g})", f2(tcv), f2(text_scores["train"]), f2(text_scores["strict"]), f2(text_scores["desc_only"]), f2(text_scores["word_only"])],
                      ["nearest class mean, raw", "", f2(nc_scores["train"]), f2(nc_scores["strict"]), f2(nc_scores["desc_only"]), f2(nc_scores["word_only"])],
                      ["nearest class mean, standardized", "", f2(ncs_scores["train"]), f2(ncs_scores["strict"]), f2(ncs_scores["desc_only"]), f2(ncs_scores["word_only"])]]), ""]
    out += [f"## Layer curve (position `{args.position}`)", "", md_table(["layer", "C", "cv", "train", "strict", "desc_only", "word_only"],
            [[c["layer"], f"{c['C']:g}", f2(c["cv"]), f2(c["train"]), f2(c["strict"]), f2(c["desc_only"]), f2(c["word_only"])] for c in curve]), ""]
    best_alt = {p: max(curves[p], key=lambda c: c["cv"]) for p in curves}
    out += ["Other positions, layer with best inner CV: " + "; ".join(
        f"`{p}` L{c['layer']} cv {f2(c['cv'])}, strict {f2(c['strict'])}" for p, c in best_alt.items()), ""]
    out += ["## Directions saved for stage 3", "",
            md_table(["approach", "separation along classifier dir", "along diff-of-means dir", "cos(clf, dm)"],
                     [[APPROACH_LABEL[a], f"{sep_clf[k]:.2f}", f"{sep_dm[k]:.2f}", f"{cos[k]:.2f}"] for k, a in enumerate(APPROACHES)]),
            "", f"Mean residual norm at layer {L} on train: {resid_norm:.1f}. Separation = mean projection of the class minus mean projection of the other classes (raw units); stage 3 uses alpha x separation.", ""]
    out += ["## Neutral prompts: probe vs stage-1 sampling", "",
            md_table(["id", "", "probe P(A) P(B) P(C)", "probe argmax", "sampled freq A B C", "n", "sampled argmax"],
                     [[r["wording_id"], "H" if r["heldout_wording"] else "", " ".join(f"{r['probe'][a]:.2f}" for a in APPROACHES), r["probe_argmax"],
                       " ".join(f"{r['sampled'][a]:.2f}" for a in APPROACHES) if r["sampled"] else "–", r["n_samples"], r.get("sampled_argmax", "–")]
                      for r in neutral_rows]), "",
            f"Argmax agreement: {agree}/{n_cmp}. Spearman per approach (None = sampled frequency constant): {spearman or 'no stage-1 samples found'}.", "",
            "Caveat: the probe was trained where the approach is stated in the prompt; neutral prompts state none, so this is a distribution shift.", ""]
    (S2 / f"summary_{tag}.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out[:12]))
    print(f"wrote {S2 / f'summary_{tag}.md'}, probe_{tag}.json, direction_{tag}.npz", file=sys.stderr)


if __name__ == "__main__":
    main()

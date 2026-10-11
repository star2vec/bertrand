"""Stage 2, answer direction: where the first chord-length formula appears, and activations early in the answer.

Input: the derived neutral answers in results/s1/judge_qwen{tag}.jsonl (hand judgment), joined to
results/s1/neutral_{tag}.jsonl on (wording_id, sample). Label = final number (1/3 -> A, 1/2 -> B, 1/4 -> C).

Step 1 (always, tokenizer only): tokenize each answer on its own (as it was generated after the prompt) and find
  formula_tok : first answer token of the first chord-length formula, i.e. an expression tying the chord's length to
                the distance from the center (2*sqrt(r^2 - d^2) with any letter for d, (L/2)^2 + d^2 = r^2,
                d = sqrt(r^2 - (L/2)^2), or the words "Pythagorean theorem" that introduce it) or to the central angle
                (2r sin(theta/2), a cosine). The triangle side s = r*sqrt(3) does not count. Answers that argue in
                words only (e.g. "the side subtends 120 degrees") have no formula.
  word_tok    : first answer token that names the variable in words (perpendicular distance, distance from the
                center, central angle, subtend, midpoint).
  Window: tokens 0..w-1 with w the largest value such that formula_tok >= w in >= 95% of answers (answers with no
  formula count as later), then clipped to [15, 60]. Answers whose formula starts inside the window are marked
  `in_window` (dropped by the answer probe).
  Writes results/s2/formula_pos_{tag}.json. `--measure` stops here; `--show N` prints N answers with the marks.
Step 2 (GPU): one forward pass per answer over the chat-templated prompt + the first 60 answer tokens (causal, so
  later text cannot change these positions), recording the residual stream at `--layers` at: the last prompt token,
  the mean over the window, and the means over the first 10 / 20 / 30 / 60 answer tokens.
  Writes results/s2/acts_answers_{tag}.npz (fp32 [n, n_layers, d] per position, plus `layers`) and _meta.jsonl.
"""
import argparse
import json
import random
import re
import sys
import time

import numpy as np
import torch

from common import (RESULTS, ResidualRecorder, chat_prompt, load_model, model_tag, read_jsonl, resolve_model, run_meta,
                    utf8_stdout, write_jsonl)

N_TOK = 60
SPANS = [10, 20, 30, 60]
W_MIN, W_MAX, COVER = 15, 60, 0.95
NUM2LAB = {"1/3": "A", "1/2": "B", "1/4": "C"}

_D2 = r"d\s*\^\s*\{?\s*2"  # d^2, d^{2}
_HALF = r"\\frac\s*\{[^{}]*\}\s*\{\s*2\s*\}"  # \frac{x}{2}
FORMULA = re.compile("|".join([
    r"\\sqrt\s*\{[^{}]*?-\s*[A-Za-z]\s*\^\s*\{?\s*2",  # \sqrt{r^2 - d^2} (also a, x, L for the distance)
    r"Pythagorean",  # "by the Pythagorean theorem" (radius, half-chord, distance) comes right before the formula
    r"\\right\s*\)\s*\^\s*\{?\s*2\}?\s*\+\s*[A-Za-z]\s*\^",  # \left(\frac{L}{2}\right)^2 + d^2
    r"[A-Za-z]\s*\^\s*\{?\s*2\}?\s*\+\s*\\left\s*\(\s*\\frac",  # L^2 + \left(\frac{..}{2}\right)^2
    r"\\cos\s*\(",
    r"\\sqrt\s*\{[^{}]*?-\s*\\left\s*\(\s*" + _HALF,  # \sqrt{r^2 - \left(\frac{L}{2}\right)^2}
    r"\\sqrt\s*\{[^{}]*?-\s*\(\s*" + _HALF,
    r"\\sqrt\s*\{[^{}]*?-\s*\(?\s*[A-Za-z]\s*/\s*2",
    _D2 + r"\}?\s*\+",  # d^2 + (L/2)^2 = r^2
    r"\+\s*" + _D2,  # (L/2)^2 + d^2 = r^2
    r"\\sin\s*(\\left)?\s*\(?\s*" + _HALF,  # \sin\left(\frac{\theta}{2}\right)
    r"\\sin\s*\(\s*[^()]*?/\s*2\s*\)",  # \sin(\theta/2)
    r"\\sin\s*\\frac",
    r"sin\s*\(\s*[θα]\s*/\s*2\s*\)",
    r"\\cos\s*(\\left)?\s*\(?\s*\\(theta|alpha|phi)",  # law of cosines on the central angle
    r"√\s*\(?\s*[rR\d]\s*²\s*[-−]\s*d\s*²",
    r"sqrt\s*\(\s*[rR\d]+\s*\^\s*2\s*-\s*d\s*\^\s*2",
]))
VARWORD = re.compile(r"perpendicular distance|distance from the cent(?:er|re)|distance\s*\\?\(?\s*d\s*\\?\)?\s*from the cent"
                     r"|central angle|subtend|midpoint", re.I)


def char_to_tok(offsets, c):
    """index of the first token whose span ends after character c"""
    for i, (a, b) in enumerate(offsets):
        if b > c:
            return i
    return len(offsets)


def load_answers(tag, judged="derived"):  # judged: "derived" (supported) or "recalled" (unsupported)
    judge = read_jsonl(RESULTS / "s1" / f"judge_{tag}.jsonl")
    neutral = {(r["wording_id"], r["sample"]): r for r in read_jsonl(RESULTS / "s1" / f"neutral_{tag}.jsonl")
               if r.get("kind") == "answer"}
    rows = []
    for j in judge:
        if j["derived_or_recalled"] != judged:
            continue
        r = neutral[(j["wording_id"], j["sample"])]
        rows.append(dict(wording_id=j["wording_id"], sample=j["sample"], final_number=j["final_number"],
                         label=NUM2LAB[j["final_number"]], variable=j["variable"],
                         heldout_wording=r["heldout_wording"], prompt=r["prompt"], answer=r["answer"]))
    return rows


def measure(tok, rows):
    for r in rows:
        enc = tok(r["answer"], return_offsets_mapping=True, add_special_tokens=False)
        r["answer_ids"] = enc["input_ids"]
        m, v = FORMULA.search(r["answer"]), VARWORD.search(r["answer"])
        r["formula_char"] = m.start() if m else None
        r["formula_match"] = m.group(0) if m else None
        r["formula_tok"] = char_to_tok(enc["offset_mapping"], m.start()) if m else None
        r["word_tok"] = char_to_tok(enc["offset_mapping"], v.start()) if v else None
        r["word_match"] = v.group(0) if v else None
    pos = [r["formula_tok"] if r["formula_tok"] is not None else 10 ** 9 for r in rows]
    w_rule = max([w for w in range(1, W_MAX + 1) if np.mean([p >= w for p in pos]) >= COVER] or [1])
    w = min(max(w_rule, W_MIN), W_MAX)
    for r in rows:
        r["in_window"] = r["formula_tok"] is not None and r["formula_tok"] < w
        r["word_in_window"] = r["word_tok"] is not None and r["word_tok"] < w
    return w_rule, w


def report(rows, w_rule, w):
    ft = np.array([r["formula_tok"] for r in rows if r["formula_tok"] is not None])
    wt = np.array([r["word_tok"] for r in rows if r["word_tok"] is not None])
    q = lambda a: {p: int(np.percentile(a, p)) for p in (0, 5, 10, 25, 50, 75)} if len(a) else {}
    kept = [r for r in rows if not r["in_window"]]
    out = dict(n=len(rows), n_formula=int(len(ft)), formula_tok_percentiles=q(ft),
               n_word=int(len(wt)), word_tok_percentiles=q(wt), w_rule=w_rule, window=w, cover=COVER,
               w_min=W_MIN, w_max=W_MAX, n_in_window=sum(r["in_window"] for r in rows), n_kept=len(kept),
               n_word_in_window_kept=sum(r["word_in_window"] for r in kept),
               formula_inside_span={s: sum(r["formula_tok"] is not None and r["formula_tok"] < s for r in rows)
                                    for s in SPANS},
               word_inside_span={s: sum(r["word_tok"] is not None and r["word_tok"] < s for r in rows) for s in SPANS},
               by_label={lab: dict(n=sum(r["label"] == lab for r in rows),
                                   median_formula_tok=float(np.median([r["formula_tok"] for r in rows if r["label"] == lab and r["formula_tok"] is not None])),
                                   in_window=sum(r["in_window"] for r in rows if r["label"] == lab)) for lab in "ABC"},
               rows=[{k: r[k] for k in ("wording_id", "sample", "label", "formula_tok", "formula_match", "word_tok",
                                        "word_match", "in_window", "word_in_window")} for r in rows])
    return out


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="7b")
    ap.add_argument("--device", default=None)
    ap.add_argument("--layers", type=int, nargs="+", default=None, help="residual indices to keep (default: all)")
    ap.add_argument("--measure", action="store_true", help="only measure formula positions (no model)")
    ap.add_argument("--show", type=int, default=0, help="print N random answers with the formula mark")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    name = resolve_model(args.model)
    tag = model_tag(name)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(name)

    rows = load_answers(tag)
    w_rule, w = measure(tok, rows)
    rep = report(rows, w_rule, w)
    (RESULTS / "s2").mkdir(parents=True, exist_ok=True)
    (RESULTS / "s2" / f"formula_pos_{tag}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "rows"}, indent=1), file=sys.stderr)
    for r in random.Random(1).sample(rows, args.show):
        a, c = r["answer"], r["formula_char"]
        mark = a[:c] + "⟦" + a[c:c + 40] + "⟧" if c is not None else a[:1500] + " …[NO FORMULA]"
        print(f"\n=== w{r['wording_id']} s{r['sample']} {r['final_number']} formula_tok={r['formula_tok']} "
              f"word_tok={r['word_tok']} ({r['word_match']})\n{mark[:2500]}")
    if args.measure:
        return

    if args.limit:
        rows = rows[: args.limit]
    _, model, device = load_model(args.model, "forward", args.device)
    layers = args.layers if args.layers is not None else list(range(len(model.model.layers) + 1))
    names = ["last", "window"] + [f"first{s}" for s in SPANS]
    acts = {k: [] for k in names}
    t0 = time.time()
    with ResidualRecorder(model) as rec, torch.no_grad():
        for i, r in enumerate(rows):
            p_ids = tok(chat_prompt(tok, r["prompt"]), add_special_tokens=False).input_ids
            a_ids = r["answer_ids"][:N_TOK]
            assert len(a_ids) == N_TOK, (r["wording_id"], r["sample"], len(a_ids))
            ids = torch.tensor([p_ids + a_ids], device=device)
            model(ids)
            hs = rec.stack()[layers, 0].float()  # (n_kept_layers, T, d)
            P = len(p_ids)
            acts["last"].append(hs[:, P - 1].cpu().numpy())
            acts["window"].append(hs[:, P:P + w].mean(1).cpu().numpy())
            for s in SPANS:
                acts[f"first{s}"].append(hs[:, P:P + s].mean(1).cpu().numpy())
            r["prompt_tokens"] = P
            r["window_text"] = tok.decode(a_ids[:w])
            if (i + 1) % 50 == 0 or i + 1 == len(rows):
                print(f"  {i + 1}/{len(rows)}  {time.time() - t0:.0f}s", file=sys.stderr)

    arrays = {k: np.stack(v).astype(np.float32) for k, v in acts.items()}
    out = RESULTS / "s2" / f"acts_answers_{tag}.npz"
    np.savez(out, layers=np.array(layers), **arrays)
    keep = ("wording_id", "sample", "final_number", "label", "variable", "heldout_wording", "prompt", "formula_tok",
            "word_tok", "in_window", "word_in_window", "prompt_tokens", "window_text")
    meta = run_meta(name, device, "forward", n=len(rows), window=w, w_rule=w_rule, spans=SPANS, n_tok=N_TOK,
                    layers=layers, positions=names, shape=list(arrays["last"].shape))
    write_jsonl(RESULTS / "s2" / f"acts_answers_{tag}_meta.jsonl", [dict(kind="meta", **meta)] + [{k: r[k] for k in keep} for r in rows])
    print(f"wrote {out} {arrays['last'].shape} and meta ({len(rows)} answers, window {w})", file=sys.stderr)


if __name__ == "__main__":
    main()

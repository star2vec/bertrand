"""Stage 2, last 7B check: activations just before the variable is first named in words.

Same derived neutral answers as s2_answer_acts.py. Anchor t = first answer token of the first variable word
(VARWORD: perpendicular distance, distance (d) from the center, central angle, subtend, midpoint). A stricter anchor
t_strict uses only perpendicular distance / central angle / subtend / midpoint (STRICT); it differs from t for the
answers whose first naming is "distance (d) from the center", and is missing if no stricter word follows.

One forward pass per answer over the chat-templated prompt + answer tokens up to max(t, t_strict) (causal), recording
the residual stream at `--layers` at single positions t - k for k in OFFSETS (k = 0 is the word's first token).
A position before the first answer token is not used (mask False).
Writes results/s2/acts_word_{tag}.npz: `word` and `strict` fp32 [n, n_offsets, n_layers, d], masks `word_ok` and
`strict_ok` [n, n_offsets], `layers`, `offsets`; and _meta.jsonl (anchors, matched words, formula position,
decoded answer text up to each offset).
"""
import argparse
import re
import sys
import time

import numpy as np
import torch

from common import RESULTS, ResidualRecorder, chat_prompt, load_model, model_tag, resolve_model, run_meta, utf8_stdout, write_jsonl
from s2_answer_acts import char_to_tok, load_answers, measure

OFFSETS = [30, 20, 10, 5, 2, 1, 0]
STRICT = re.compile(r"perpendicular distance|central angle|subtend|midpoint", re.I)


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="7b")
    ap.add_argument("--device", default=None)
    ap.add_argument("--layers", type=int, nargs="+", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--set", default="supported", choices=["supported", "unsupported"],
                    help="judged answers to use: supported (steps lead to the boxed number) or unsupported")
    args = ap.parse_args()
    name = resolve_model(args.model)
    tag = model_tag(name)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(name)

    rows = load_answers(tag, "derived" if args.set == "supported" else "recalled")
    suffix = "" if args.set == "supported" else "_unsupported"
    measure(tok, rows)  # sets answer_ids, formula_tok, word_tok, word_match
    for r in rows:
        enc = tok(r["answer"], return_offsets_mapping=True, add_special_tokens=False)
        m = STRICT.search(r["answer"])
        r["strict_tok"] = char_to_tok(enc["offset_mapping"], m.start()) if m else None
        r["strict_match"] = m.group(0) if m else None
        r["formula_before_word"] = r["formula_tok"] is not None and r["word_tok"] is not None and r["formula_tok"] < r["word_tok"]
    n_judged = len(rows)
    no_word = [(r["wording_id"], r["sample"], r["final_number"]) for r in rows if r["word_tok"] is None]
    rows = [r for r in rows if r["word_tok"] is not None]
    print(f"{args.set}: {n_judged} answers, {len(no_word)} never name the variable in words (dropped): {no_word}", file=sys.stderr)
    if args.limit:
        rows = rows[: args.limit]
    n_re = sum(r["strict_tok"] is not None and r["strict_tok"] != r["word_tok"] for r in rows)
    n_drop = sum(r["strict_tok"] is None for r in rows)
    print(f"{len(rows)} answers; strict anchor differs for {n_re}, missing for {n_drop}; "
          f"formula before word in {sum(r['formula_before_word'] for r in rows)}", file=sys.stderr)

    _, model, device = load_model(args.model, "forward", args.device)
    layers = args.layers if args.layers is not None else list(range(len(model.model.layers) + 1))
    n, K, Ln, d = len(rows), len(OFFSETS), len(layers), model.config.hidden_size
    out = {k: np.zeros((n, K, Ln, d), np.float32) for k in ("word", "strict")}
    ok = {k: np.zeros((n, K), bool) for k in ("word", "strict")}
    t0 = time.time()
    with ResidualRecorder(model) as rec, torch.no_grad():
        for i, r in enumerate(rows):
            p_ids = tok(chat_prompt(tok, r["prompt"]), add_special_tokens=False).input_ids
            end = max(r["word_tok"], r["strict_tok"] or 0) + 1
            ids = torch.tensor([p_ids + r["answer_ids"][:end]], device=device)
            model(ids)
            hs = rec.stack()[layers, 0].float()  # (n_kept_layers, T, d)
            P = len(p_ids)
            for key, t in (("word", r["word_tok"]), ("strict", r["strict_tok"])):
                if t is None:
                    continue
                for j, k in enumerate(OFFSETS):
                    if t - k >= 0:
                        out[key][i, j] = hs[:, P + t - k].cpu().numpy()
                        ok[key][i, j] = True
            a = r["answer_ids"]
            t = r["word_tok"]
            r["text_upto"] = {str(k): tok.decode(a[: t - k + 1]) if t - k >= 0 else None for k in OFFSETS}
            r["token_at_t"] = tok.decode(a[t:t + 1])
            r["prompt_tokens"] = P
            if (i + 1) % 50 == 0 or i + 1 == n:
                print(f"  {i + 1}/{n}  {time.time() - t0:.0f}s", file=sys.stderr)

    path = RESULTS / "s2" / f"acts_word_{tag}{suffix}.npz"
    np.savez(path, layers=np.array(layers), offsets=np.array(OFFSETS), word=out["word"], strict=out["strict"],
             word_ok=ok["word"], strict_ok=ok["strict"])
    keep = ("wording_id", "sample", "final_number", "label", "variable", "heldout_wording", "prompt", "word_tok",
            "word_match", "strict_tok", "strict_match", "formula_tok", "formula_before_word", "token_at_t",
            "prompt_tokens", "text_upto")
    meta = run_meta(name, device, "forward", n=n, layers=layers, offsets=OFFSETS, n_reanchored=n_re, n_no_strict=n_drop,
                    set=args.set, n_judged=n_judged, no_word=no_word)
    write_jsonl(RESULTS / "s2" / f"acts_word_{tag}{suffix}_meta.jsonl", [dict(kind="meta", **meta)] + [{k: r[k] for k in keep} for r in rows])
    print(f"wrote {path} {out['word'].shape}; valid per offset {dict(zip(OFFSETS, ok['word'].sum(0).tolist()))}", file=sys.stderr)


if __name__ == "__main__":
    main()

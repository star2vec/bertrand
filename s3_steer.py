"""Stage 3 steering sweep (Windows GPU, half precision; --limit on the Mac for a smoke test).

Loads results/s2/direction_{tag}.npz from stage 2 (layer, unit direction per approach, class separation along it).
For each chosen neutral prompt x target approach x alpha in --alphas: greedy generation with
alpha * separation * u_target added to the residual stream at the chosen layer, at the last prompt token and at
every generated token. A plain (no hook) greedy run is done first; alpha = 0 goes through the hook and is checked
against it token for token. Writes results/s3/steer_{tag}.jsonl (resumable), rows carry the scorer's fields.
"""
import argparse
import sys
import time

import numpy as np
import torch

from common import (APPROACHES, RESULTS, Steer, add_common_args, append_jsonl, chat_prompt, generate, load_model,
                    load_prompts, model_tag, read_jsonl, resolve_model, run_meta, utf8_stdout)
from score import score

DEFAULT_WORDINGS = [0, 3, 7, 9, 11, 14]  # placeholder; choose from stage-1 behaviour with --wordings


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    add_common_args(ap)
    ap.add_argument("--wordings", type=int, nargs="+", default=DEFAULT_WORDINGS)
    ap.add_argument("--targets", nargs="+", default=APPROACHES, choices=APPROACHES)
    ap.add_argument("--alphas", type=float, nargs="+", default=[0, 1, 2, 4, 8])
    ap.add_argument("--direction", choices=["classifier", "diffmeans"], default="classifier")
    ap.add_argument("--layer", type=int, default=None, help="override the stage-2 layer")
    ap.add_argument("--max_new_tokens", type=int, default=768)
    ap.add_argument("--batch_size", type=int, default=None)
    args = ap.parse_args()

    name = resolve_model(args.model)
    tag = model_tag(name)
    d = np.load(RESULTS / "s2" / f"direction_{tag}.npz")
    layer = args.layer if args.layer is not None else int(d["layer"])
    U = d["u_clf"] if args.direction == "classifier" else d["u_dm"]
    SEP = d["sep_clf"] if args.direction == "classifier" else d["sep_dm"]
    neutral = {w["wording_id"]: w for w in load_prompts("neutral")}
    wids = args.wordings[: args.limit] if args.limit else args.wordings
    batch_size = args.batch_size or (4 if "3b" in tag else 8)

    out = RESULTS / "s3" / f"steer_{tag}.jsonl"
    prev = read_jsonl(out)
    done = {(r["wording_id"], r["target"], r["alpha"]) for r in prev if r.get("kind") == "answer"}
    plain = {r["wording_id"]: r["answer"] for r in prev if r.get("kind") == "answer" and r["target"] == "plain"}
    groups = [("plain", 0.0)] + [(t, float(a)) for t in args.targets for a in args.alphas]
    jobs = [(t, a, [w for w in wids if (w, t, a) not in done]) for t, a in groups]
    jobs = [(t, a, ws) for t, a, ws in jobs if ws]
    n_total = sum(len(ws) for _, _, ws in jobs)
    print(f"steer/{tag}: layer {layer}, {args.direction} direction, {len(wids)} wordings x {len(groups)} (target, alpha) "
          f"groups; {len(done)} done, {n_total} to go", file=sys.stderr)
    if not jobs:
        return

    tok, model, device = load_model(args.model, "generate", args.device)
    if not prev:
        append_jsonl(out, [dict(kind="meta", **run_meta(name, device, "generate", layer=layer, direction=args.direction,
                                                        alphas=args.alphas, wordings=wids, targets=args.targets,
                                                        sep={a: float(SEP[k]) for k, a in enumerate(APPROACHES)},
                                                        resid_norm=float(d["resid_norm"]), max_new_tokens=args.max_new_tokens,
                                                        repetition_penalty=model.generation_config.repetition_penalty))])
    t0, n_done = time.time(), 0
    for t, a, ws in jobs:
        k = None if t == "plain" else APPROACHES.index(t)
        for b in range(0, len(ws), batch_size):
            bw = ws[b:b + batch_size]
            strs = [chat_prompt(tok, neutral[w]["text"]) for w in bw]
            if k is None:
                texts, ntok = generate(tok, model, device, strs, max_new_tokens=args.max_new_tokens)
            else:
                with Steer(model, layer, torch.tensor(U[k], dtype=torch.float32), a * float(SEP[k])):
                    texts, ntok = generate(tok, model, device, strs, max_new_tokens=args.max_new_tokens)
            rows = []
            for w, text, n in zip(bw, texts, ntok):
                row = dict(kind="answer", wording_id=w, target=t, alpha=a,
                           alpha_abs=0.0 if k is None else a * float(SEP[k]), layer=layer, direction=args.direction,
                           prompt=neutral[w]["text"], answer=text, n_tokens=n)
                if k is None:
                    plain[w] = text
                elif a == 0 and w in plain:
                    row["matches_plain"] = text == plain[w]
                row.update(score(text))
                rows.append(row)
            append_jsonl(out, rows)
            n_done += len(bw)
            print(f"  {n_done}/{n_total}  {(time.time() - t0) / 60:.1f} min  target={t} alpha={a:g}: "
                  + " ".join(f"{r['wording_id']}:{r['approach_number']}" for r in rows), file=sys.stderr)
    print(f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()

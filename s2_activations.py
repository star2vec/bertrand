"""Stage 2 activation extraction (forward-only; Mac, fp32, batch 1).

One forward pass per labeled and neutral prompt (chat template, no prefill), recording the residual stream at every
layer (0 = embeddings, k = output of block k; `--layers` keeps a subset, saved as `layers`) at three positions:
  last      : last token of the templated prompt (the newline after <|im_start|>assistant)  <- primary
  user_last : last token of the user message
  user_mean : mean over the user-message tokens
Writes results/s2/acts_{tag}.npz (fp32 arrays [n_prompts, n_kept_layers, d] per position, labeled rows first)
and results/s2/acts_{tag}_meta.jsonl (first row run metadata, then one row per prompt in the same order).
"""
import argparse
import sys
import time

import numpy as np
import torch

from common import (RESULTS, ResidualRecorder, add_common_args, chat_prompt, load_model, load_prompts, model_tag,
                    resolve_model, run_meta, user_token_span, utf8_stdout, write_jsonl)

POSITIONS = ["last", "user_last", "user_mean"]


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    add_common_args(ap)
    ap.add_argument("--layers", type=int, nargs="+", default=None, help="residual indices to keep (default: all)")
    args = ap.parse_args()
    name = resolve_model(args.model)
    tag = model_tag(name)

    jobs = []
    for set_name in ["labeled", "neutral"]:
        rows = load_prompts(set_name)
        if args.limit:
            rows = rows[: args.limit]
        for r in rows:
            jobs.append(dict(set=set_name, id=r.get("id", f"w{r['wording_id']:02d}"), wording_id=r["wording_id"],
                             approach=r.get("approach"), desc_id=r.get("desc_id"), heldout_desc=r.get("heldout_desc"),
                             heldout_wording=r["heldout_wording"], frame=r.get("frame"), position=r.get("position"),
                             noun=r["noun"], text=r["text"]))

    tok, model, device = load_model(args.model, "forward", args.device)
    layers = args.layers if args.layers is not None else list(range(len(model.model.layers) + 1))
    acts = {p: [] for p in POSITIONS}
    t0 = time.time()
    with ResidualRecorder(model) as rec, torch.no_grad():
        for i, j in enumerate(jobs):
            prompt = chat_prompt(tok, j["text"])
            uf, ul = user_token_span(tok, prompt, j["text"])
            ids = tok(prompt, return_tensors="pt", add_special_tokens=False).input_ids.to(device)
            model(ids)
            hs = rec.stack()[layers, 0].float()  # (n_kept_layers, T, d)
            acts["last"].append(hs[:, -1].cpu().numpy())
            acts["user_last"].append(hs[:, ul].cpu().numpy())
            acts["user_mean"].append(hs[:, uf:ul + 1].mean(1).cpu().numpy())
            j["prompt_tokens"] = int(ids.shape[1])
            j["user_span"] = [uf, ul]
            if (i + 1) % 50 == 0 or i + 1 == len(jobs):
                print(f"  {i + 1}/{len(jobs)}  {time.time() - t0:.0f}s", file=sys.stderr)

    out = RESULTS / "s2" / f"acts_{tag}.npz"
    arrays = {p: np.stack(v).astype(np.float32) for p, v in acts.items()}
    np.savez(out, layers=np.array(layers), **arrays)
    meta = run_meta(name, device, "forward", n=len(jobs), positions=POSITIONS, shape=list(arrays["last"].shape), layers=layers,
                    n_labeled=sum(j["set"] == "labeled" for j in jobs), n_neutral=sum(j["set"] == "neutral" for j in jobs))
    write_jsonl(RESULTS / "s2" / f"acts_{tag}_meta.jsonl", [dict(kind="meta", **meta)] + jobs)
    print(f"wrote {out} {arrays['last'].shape} and meta ({len(jobs)} prompts)", file=sys.stderr)


if __name__ == "__main__":
    main()

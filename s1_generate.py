"""Stage 1 generation (Windows GPU, half precision, 7B in 4-bit; --limit for Mac smoke tests).

  --set labeled : all 432 labeled prompts, greedy, 1 answer each
  --set neutral : 18 neutral prompts, --n_samples answers each at --temperature / --top_p

repetition_penalty is 1.0 (common.generate); the batch size defaults to 8 / 4 / 2 for the 1.5B / 3B / 7B.

Resumable: appends to results/s1/{set}_{tag}.jsonl and skips (id, sample) pairs already present; raising --n_samples
adds the missing sample indices. Each run that generates writes a meta row, and each answer row stores its max_new_tokens.
Each row stores the answer and the scorer's fields (see score.py).
"""
import argparse
import sys
import time
import zlib

from common import (REPETITION_PENALTY, RESULTS, add_common_args, append_jsonl, chat_prompt, default_batch, generate,
                    load_model, load_prompts, model_tag, read_jsonl, resolve_model, run_meta, utf8_stdout)
from score import score


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    add_common_args(ap)
    ap.add_argument("--set", choices=["labeled", "neutral"], required=True)
    ap.add_argument("--n_samples", type=int, default=None, help="default: 1 for labeled, 10 for neutral")
    ap.add_argument("--temperature", type=float, default=None, help="default: 0 (greedy) for labeled, 0.7 for neutral")
    ap.add_argument("--top_p", type=float, default=0.95)
    ap.add_argument("--max_new_tokens", type=int, default=768, help="a full greedy 1.5B answer ran 535 tokens")
    ap.add_argument("--batch_size", type=int, default=None, help="default: 8 for 1.5b, 4 for 3b, 2 for 7b")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ids", default=None, help="comma-separated prompt ids (smoke tests), e.g. w00_a0,w03_b1 or w00,w07")
    args = ap.parse_args()

    name = resolve_model(args.model)
    tag = model_tag(name)
    n_samples = args.n_samples if args.n_samples is not None else (1 if args.set == "labeled" else 10)
    temperature = args.temperature if args.temperature is not None else (0.0 if args.set == "labeled" else 0.7)
    batch_size = args.batch_size or default_batch(name)

    prompts = load_prompts(args.set)
    for p in prompts:
        p.setdefault("id", f"w{p['wording_id']:02d}")
    if args.ids:
        want = set(args.ids.split(","))
        prompts = [p for p in prompts if p["id"] in want]
    if args.limit:
        prompts = prompts[: args.limit]

    out = RESULTS / "s1" / f"{args.set}_{tag}.jsonl"
    done = {(r["id"], r["sample"]) for r in read_jsonl(out) if r.get("kind") == "answer"}
    jobs = [(p, k) for p in prompts for k in range(n_samples) if (p["id"], k) not in done]
    print(f"{args.set}/{tag}: {len(prompts)} prompts x {n_samples} samples, {len(done)} done, {len(jobs)} to go, "
          f"temperature={temperature}, batch={batch_size}", file=sys.stderr)
    if not jobs:
        return

    tok, model, device = load_model(args.model, "generate", args.device)
    # one meta row per run that generates anything; a resumed run with new settings gets its own row
    append_jsonl(out, [dict(kind="meta", **run_meta(name, device, "generate", set=args.set, n_samples=n_samples,
                                                    temperature=temperature, top_p=args.top_p,
                                                    max_new_tokens=args.max_new_tokens, seed=args.seed,
                                                    repetition_penalty=REPETITION_PENALTY, batch_size=batch_size,
                                                    resumed_after=len(done)))])

    keep = ["wording_id", "approach", "desc_id", "heldout_desc", "heldout_wording", "frame", "position", "noun"]
    t0 = time.time()
    for b in range(0, len(jobs), batch_size):
        batch = jobs[b:b + batch_size]
        strs = [chat_prompt(tok, p["text"]) for p, _ in batch]
        key = "|".join(f"{p['id']}:{k}" for p, k in batch).encode()
        seed = args.seed * 1_000_000 + zlib.crc32(key) % 1_000_000 if temperature > 0 else None
        texts, n_tok = generate(tok, model, device, strs, max_new_tokens=args.max_new_tokens,
                                temperature=temperature, top_p=args.top_p, seed=seed)
        rows = []
        for (p, k), text, n in zip(batch, texts, n_tok):
            row = dict(kind="answer", id=p["id"], sample=k, **{f: p[f] for f in keep if f in p},
                       prompt=p["text"], answer=text, n_tokens=n, max_new_tokens=args.max_new_tokens, seed=seed)
            row.update(score(text))
            rows.append(row)
        append_jsonl(out, rows)
        dt = time.time() - t0
        print(f"  {b + len(batch)}/{len(jobs)}  {dt / 60:.1f} min  last: text={rows[-1]['approach_text']} "
              f"number={rows[-1]['approach_number']} ({rows[-1]['final_how']}, {rows[-1]['n_tokens']} tok)", file=sys.stderr)
    print(f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()

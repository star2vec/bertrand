"""Stage 1, next-word check (forward-only). Kept as a script; its numbers are not reported (2026-10-08).

For each neutral prompt the assistant turn is prefilled with "Solution: we choose the {noun} by" and we read
(a) the top-k next tokens with probabilities, and
(b) the total log-prob of 4 canonical continuations per approach; approach score = logsumexp over its
    continuations, softmaxed across the three approaches ("raw"). Longer continuations get lower totals, so a
    length-normalized variant is also reported: best mean log-prob per token per approach, softmaxed ("per token").
Writes results/s1/nextword_{tag}.jsonl (one row per prompt, first row is run metadata).
"""
import argparse
import json
import math

import torch

from common import (APPROACHES, PROMPTS, RESULTS, add_common_args, chat_prompt, load_model, load_prompts,
                    model_tag, resolve_model, run_meta, utf8_stdout, write_jsonl)


@torch.no_grad()
def continuation_logprob(model, ids, cont_ids):
    """Sum of log P(continuation tokens | prompt ids)."""
    full = torch.cat([ids, torch.tensor([cont_ids], device=ids.device)], dim=1)
    logits = model(full).logits[0].float()
    n = ids.shape[1]
    logp = torch.log_softmax(logits[n - 1:-1], dim=-1)
    return logp.gather(1, torch.tensor(cont_ids, device=ids.device)[:, None]).sum().item()


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    add_common_args(ap)
    ap.add_argument("--topk", type=int, default=20)
    args = ap.parse_args()

    tok, model, device = load_model(args.model, "forward", args.device)
    name = resolve_model(args.model)
    neutral = load_prompts("neutral")
    if args.limit:
        neutral = neutral[: args.limit]
    cont = json.load(open(PROMPTS / "continuations.json", encoding="utf-8"))

    rows = [dict(kind="meta", **run_meta(name, device, "forward", prefill=cont["prefill"], topk=args.topk))]
    print(f"{'id':>3} {'P(A)':>6} {'P(B)':>6} {'P(C)':>6} | {'tokA':>5} {'tokB':>5} {'tokC':>5}  top next tokens")
    for w in neutral:
        prefill = cont["prefill"].format(noun=w["noun"])
        prompt = chat_prompt(tok, w["text"], prefill)
        ids = tok(prompt, return_tensors="pt", add_special_tokens=False).input_ids.to(device)
        with torch.no_grad():
            logp = torch.log_softmax(model(ids).logits[0, -1].float(), dim=-1)
        top = torch.topk(logp, args.topk)
        topk = [{"token": tok.decode([i]), "p": round(math.exp(v), 5)}
                for v, i in zip(top.values.tolist(), top.indices.tolist())]

        per_cont, scores, best_per_tok = {}, {}, {}
        for a in APPROACHES:
            lps, per_tok = [], []
            for c in cont["continuations"][a]:
                cids = tok(c, add_special_tokens=False).input_ids
                lp = continuation_logprob(model, ids, cids)
                lps.append(lp)
                per_tok.append(lp / len(cids))
                per_cont[c] = {"approach": a, "logprob": round(lp, 3), "n_tokens": len(cids),
                               "logprob_per_token": round(lp / len(cids), 3), "first_token": tok.decode([cids[0]])}
            scores[a] = torch.logsumexp(torch.tensor(lps), 0).item()
            best_per_tok[a] = max(per_tok)
        probs = torch.softmax(torch.tensor([scores[a] for a in APPROACHES]), 0).tolist()
        approach_prob = {a: round(p, 4) for a, p in zip(APPROACHES, probs)}
        probs_tok = torch.softmax(torch.tensor([best_per_tok[a] for a in APPROACHES]), 0).tolist()
        approach_prob_pertoken = {a: round(p, 4) for a, p in zip(APPROACHES, probs_tok)}

        rows.append(dict(kind="prompt", wording_id=w["wording_id"], heldout_wording=w["heldout_wording"],
                         noun=w["noun"], prefill=prefill, approach_prob=approach_prob,
                         approach_prob_pertoken=approach_prob_pertoken,
                         approach_logsumexp={a: round(v, 3) for a, v in scores.items()},
                         best_logprob_per_token={a: round(v, 3) for a, v in best_per_tok.items()},
                         continuations=per_cont, topk=topk, prompt_tokens=int(ids.shape[1])))
        tops = " ".join(f"{t['token']!r}:{t['p']:.2f}" for t in topk[:6])
        pt = approach_prob_pertoken
        print(f"{w['wording_id']:>3} {approach_prob['A']:6.3f} {approach_prob['B']:6.3f} {approach_prob['C']:6.3f} | "
              f"{pt['A']:5.2f} {pt['B']:5.2f} {pt['C']:5.2f}  {tops}")

    out = RESULTS / "s1" / f"nextword_{model_tag(name)}.jsonl"
    write_jsonl(out, rows)
    print(f"wrote {out} ({len(rows) - 1} prompts)")


if __name__ == "__main__":
    main()

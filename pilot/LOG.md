# Pilot log

Light running log, newest entry last. Numbers go here after each stage; decisions are the researcher's.

## 2026-10-08 — setup

- Models: Qwen2.5-1.5B-Instruct and Qwen2.5-3B-Instruct, both already in the Mac's HF cache. They match the brief's sizes.
- Mac runs forward-only work (next-word check, activations, probe) in fp32. The Windows RTX 2000 Ada runs generation in bf16, batch ≤ 4 for the 3B.
- Env: uv + Python 3.11, `pyproject.toml` in pilot/. Windows resolves CUDA torch from the cu124 index through a platform marker, so `uv sync` works on both machines.
- No gates or thresholds. After each stage the numbers go in this log with a sentence or two, then work stops until the researcher decides.

## 2026-10-08 — stage 1 prepared; next-word check run for the 1.5B

(Several points in this entry were changed the same day on the researcher's instructions; see the next entry.)

- Prompts (`prompts/build_prompts.py`, seed 7): 18 neutral wordings from object × threshold × radius × order × verb, each value 3–7 times, canonical Bertrand text included. 5 wordings held out (ids 1, 2, 4, 5, 17); they share no (object, threshold, radius) triple with a training wording and cover all three objects and thresholds. 8 descriptions per approach, 3 held out and written without the training ones' keywords; 3 clause frames × 2 positions (clause before or after the problem). Labeled = 18 × 3 × 8 = 432. For the probe later: train 195, strict held-out 45 (one example = 2.2 points), description-only 117, wording-only 75.
- Scorer (`score.py`): the final number gives the approach; a boxed answer always wins; bare 0 and 1 count as numbers (a 1.5B greedy answer ended in `\boxed{0}`, and the first scorer version mislabeled it as B from a 1/2 in a formula). 25 self-test cases pass. Keyword label from the solution text is kept as a secondary column.
- Generation settings: greedy for labeled prompts; neutral sampling at T = 0.7, top_p 0.95, Qwen's top_k off; Qwen's shipped repetition_penalty 1.1 kept in both; max_new_tokens 768 because one full greedy 1.5B answer ran 535 tokens.
- Next-word check: the 1.5B numbers and the 3B fp32 failure that were logged here were removed when the check was dropped from reporting (next entry); `s1_nextword.py` stays in the repo.
- Hand-off to Windows: `s1_generate.py --set labeled` and `--set neutral` for both models (commands in README; resumable), push `results/s1/*.jsonl`, then `s1_summarize.py`. Stage-2 and stage-3 scripts are written and compile; they get smoke-tested once stage 1 is in. Waiting for the researcher.

## 2026-10-08 — changes before the Windows runs (researcher's), one line on why each

- Prompts: every wording says "chord"; the two "segment with endpoints" objects are gone. Why: those phrasings change what the model is asked about, not how the chord problem is worded, and the variation should stay inside the chord problem. Regenerated with the same seed and constraints minus the object axis: 18 wordings, held out ids 2, 4, 10, 14, 15. The strict held-out rule still held (no (threshold, radius) pair shared with a training wording; held-out covers all three threshold phrasings), so nothing was relaxed. Labeled still 432; splits 195 / 45 / 117 / 75 unchanged.
- Scorer: the method stated in the text is the primary label, the final number the secondary one; their agreement is reported. Why: the number can be the textbook value for a method the text never used, or a slip for the method it did use, and the stated method is what stage 2 will label neutral samples by. "none" and "multiple" kept. Keyword markers per approach are matched sentence by sentence (lists in `score.py`); a "distance uniform" sentence that also mentions the midpoint or the disk's area is not counted for B, since that is C's derivation. The two cross-vocabulary descriptions (b4, c3) will often read as "multiple" when the model restates them. 36 self-test cases pass.
- Generation: repetition_penalty 1.0 everywhere (Qwen ships 1.1). Why: the penalty bends the token distribution the samples are meant to reflect, including on repeated numbers and method words.
- Precision: half precision on every machine, bf16 on CUDA, fp16 on MPS; the fp32 rule is dropped. Why: fp32 did not fit the 3B on the Mac, and one precision on both machines keeps Mac forward passes comparable with Windows generations.
- Next-word check dropped from the summary and this log; `s1_nextword.py` stays. Why: the prefilled continuation scores are length-sensitive and the top next tokens fix no approach; stage 1 is read from full answers. The earlier numbers were removed from the entry above and the stale `results/s1/nextword_qwen1.5b.jsonl` (old prompts) deleted.
- Third model: Qwen2.5-7B-Instruct in 4-bit (bitsandbytes nf4, bf16 compute, `--model 7b`), same stage-1 runs, default batch 2 (raise `--batch_size` if memory allows). Why: a more capable model that still fits the 8 GB GPU, to see whether the behaviour changes with scale. bitsandbytes is a Windows-only dependency (no MPS build); the 4-bit path could not be exercised on the Mac.
- Stage-1 report, per model: labeled accuracy on non-canonical wordings (and on the other splits), text/number agreement, the neutral stated-method distribution per wording, and whether it varies across wordings (chi-square on wording × approach counts, permutation p-value) and across samples (within-wording majority share next to what iid draws from the pooled mix would give). Why: these are the questions stage 2 depends on: does the model follow a stated approach on rewordings, do the two readings of an answer agree, and is the neutral choice a property of the wording or of the sample.
- Stage 2 will change: the probe trains on neutral samples labeled by their own stated method, at the last prompt token and at each of the first ~30 generated tokens. The current s2 scripts were left as they are and not smoke-tested.
- Smoke test on the Mac (1.5B, fp16 on MPS, repetition_penalty 1.0): 8 labeled greedy answers on mixed prompts and 3 neutral wordings × 3 samples, 5.6–6.5 min per batch of 8 at 768 max tokens; the files were deleted afterwards so the Windows runs regenerate them. Labeled: stated method = labeled method in 3/8 (a0, b1, b7); B stated for a6 (an A prompt) and for c0 and c3 (C prompts); no method stated for b4 and c5. Final number = labeled value in 1/8; 4/8 ended in 1/2. Text and number agreed in all 3 answers where both were readable. Neutral: 3/9 samples stated a method (A, A, C), 6/9 none; 6/9 ended in a non-canonical number (2√3/3, 1/8, 1/6, 1, …); 2/17 answers hit the token limit. The 1.5B mostly reasons from the chord-length formula 2√(r²−d²) without saying how d is drawn, hence the many "none". The markers were tuned on these answers: a generic "defined by two points on the circle" and "the length of the diameter" no longer count as methods, and "the central angle is uniformly distributed" counts as A. `s1_summarize.py` re-scores answers from their text, so later scorer fixes need no regeneration.
- Hand-off: Windows runs the six `s1_generate.py` commands in the README (labeled and neutral for 1.5b, 3b, 7b; resumable), pushes `results/s1/*.jsonl`; then `s1_summarize.py` and the stage-1 numbers go here. Waiting for the researcher.

## 2026-10-09 — stage 1 run on Windows (1.5B, 3B); 7B not run

- Runs: RTX 2000 Ada, bf16, default batch sizes (8 for the 1.5B, 4 for the 3B, 6.4 GB in use), no out-of-memory errors. Per model, 432 labeled greedy answers and 18 phrasings × 10 neutral samples at T = 0.7. Wall time: 1.5B about 21 + 10 min, 3B about 52 + 26 min. The machine's stored HF token is rejected, so the runs used `HF_HUB_DISABLE_IMPLICIT_TOKEN=1` (the Qwen models are public).
- Scoring change (researcher's): the final number (1/3 A, 1/2 B, 1/4 C) is now the primary label and the stated method is a check next to it. The keyword markers were not retuned. The per-problem-statement table has a new column for samples that end in a canonical number but state no method, split by number. `s1_summarize.py` also writes `read_neutral_qwen3b.md` (all 180 3B neutral answers) and `read_labeled_qwen3b.md` (60 labeled 3B answers, 20 per approach, 2–3 per description) for reading by hand.
- How the two variation readings work. Across phrasings: count A/B/C per phrasing, measure how unevenly the mix is spread over the phrasings, and compare that spread with what you get after shuffling the labels among phrasings (5000 shuffles). A large share of shuffles that spread at least as much means the phrasings differ no more than chance. Within a phrasing: the average share of samples that land on the phrasing's most common approach, next to the share that independent draws from the pooled mix would give.

Final number (primary), with the stated method as a check:

| | 1.5B | 3B |
|---|---|---|
| labeled, number = labeled approach (all 432) | 25% | 46% |
| ... non-canonical phrasings / held-out phrasing and description | 26% / 20% | 46% / 42% |
| ... per approach A / B / C | 16% / 46% / 14% | 26% / 57% / 56% |
| labeled, stated method = labeled approach (check) | 33% | 43% |
| labeled, number ends in something other than 1/3, 1/2 or 1/4 | 54% | 25% |
| number and stated method agree, where both are A/B/C (labeled) | 83% of 109 | 92% of 194 |
| neutral, number A / B / C / other (of 180) | 28 / 39 / 6 / 100 | 40 / 49 / 28 / 62 |
| neutral samples with a canonical number but no stated method | 57 of 73 | 61 of 117 |
| neutral, stated method A / B / C / none (check) | 11 / 13 / 7 / 146 | 20 / 13 / 42 / 100 |
| across phrasings: shuffles spreading as much or more (number; stated) | 41%; 52% | 82%; 28% |
| within a phrasing: mean majority share vs independent draws (number) | 0.68 vs 0.66 | 0.53 vs 0.55 |
| answers that hit the 768-token limit (all) | 9% | 7% |

The 3B follows a stated approach about twice as often as the 1.5B, mostly for B and C (A is followed in about a quarter of answers and often ends in 1/2 or 1/4). The 1.5B ends in a non-canonical number in about half its answers. In neither model does the neutral choice look like a property of the problem statement: the mix across phrasings is no more uneven than shuffled labels, and samples of one phrasing agree no more often than independent draws from the pooled mix would. Most neutral answers that end in 1/3, 1/2 or 1/4 do not state a method. Full tables are in `results/s1/summary.md`. Waiting for the researcher.

## 2026-10-09 — 3B neutral resampled to 30 per problem statement

- `s1_generate.py --model 3b --set neutral --n_samples 30 --max_new_tokens 1024` (T = 0.7) resumed from the existing file. It kept samples 0–9 (768 tokens) and added samples 10–29 (1024 tokens) to `neutral_qwen3b.jsonl`, which now holds 540 samples. Each run now writes its own meta row, and new answer rows store their `max_new_tokens`. Hitting the token limit dropped from 17/180 at 768 tokens to 4/360 at 1024.
- 3B neutral, 540 samples: final number A 121, B 159, C 81, other 177, multiple 2. 191 of the 361 that end in 1/3, 1/2 or 1/4 state no method. Stated-method check: A 49, B 34, C 123, multiple 23, none 311. Across phrasings, 10% of label shuffles spread as much or more on the number (1.2% on the stated method). Within a phrasing the mean majority share is 0.49, against 0.48 for independent draws. So with 30 samples per problem statement, the number-based choice still looks like a per-sample draw. Only the stated method, which is read from fewer samples, hints at some dependence on the phrasing.

## 2026-10-09 — hand judgment of the 3B neutral answers ending in 1/3, 1/2 or 1/4

- What was judged: the 361 of 540 samples in `neutral_qwen3b.jsonl` whose final number is 1/3, 1/2 or 1/4. I read each answer; no script or API did the judging. For each answer I recorded three things. First, the variable treated as evenly spread. Second, whether it was derived (the written steps produce the boxed number) or recalled (a computation that gives something else, wrong ranges or thresholds that happen to land on it, or the number just stated). Third, whether it mentions the paradox. Slips that the number does not depend on were let pass. Using the 120° threshold angle itself as the favourable fraction (threshold/360°), without a model of which arc is favourable, was counted as recalled. Results are in `results/s1/judge_qwen3b.jsonl`; 30 judged answers with full text (10 per number, seed 0) are in `results/s1/judge_check.md`.
- Overall: 200 derived, 161 recalled. No answer mentions the paradox or that the answer depends on how the chord is chosen (0/361).
- By number: 1/3 → 30 derived, 91 recalled. 1/2 → 95 derived, 64 recalled. 1/4 → 75 derived, 6 recalled.
- By variable: angle at the center 30 derived / 109 recalled; distance from the center 95 / 6; midpoint in the disk 75 / 33; none 0 / 10; other 0 / 3 (a band of chords, half the disk area, a segment area).
- Number × variable: every derived 1/3 uses the angle, every derived 1/2 the distance, every derived 1/4 the midpoint. Recalled 1/2s come from the angle (22), the midpoint (23; the area ratio is computed as 1/4, then 1/2 is boxed), none (10), the distance (6) and other (3). Recalled 1/3s come from the angle (87) and the midpoint with a wrong threshold R/√3 (4).
- By problem statement (derived / recalled):

| phrasing | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| derived | 6 | 12 | 14 | 4 | 11 | 12 | 6 | 17 | 9 | 8 | 18 | 10 | 9 | 11 | 17 | 6 | 14 | 16 |
| recalled | 14 | 12 | 3 | 16 | 9 | 6 | 14 | 6 | 6 | 11 | 6 | 11 | 9 | 13 | 5 | 11 | 4 | 5 |

The 1/4s are almost always worked out. Most 1/3s are not: the answer finds the 120° angle and divides it by 360°, or computes 1/6 or 2/3 and boxes 1/3. The 1/2s split between a real computation from the distance and a box that contradicts the working.

Next stage tests: we test whether steering the stated reading and steering the final number give different kinds of answers.

## 2026-10-09 — stage 1 on the 7B

- Runs: `s1_generate.py --model 7b --set labeled` (greedy, 768 tokens, 432 answers) and `--set neutral --n_samples 30 --max_new_tokens 1024` (T = 0.7, 18 phrasings × 30 = 540). The 7B loads in 4-bit nf4 (bitsandbytes) with bf16 compute at batch 2, so these numbers are for the quantized model.
- Labeled, final number follows the labeled approach: 71% (307/432); A 63%, B 94%, C 56%. Non-canonical phrasings 73%, canonical problem statement 42% (10/24), held-out phrasings 68%, held-out descriptions 67%, held-out phrasing and description 64% (29/45). Stated-method check: 57%. 15% of labeled answers end in a non-canonical number (1.5B 54%, 3B 25%). Number and stated method agree in 96% of the 233 labeled answers where both are readable. Most misses: C prompts ending in 1/2 (40/144), and A prompts ending in a non-canonical number (46/144). One C description (c3) is followed in 2/18.
- Neutral, 540 samples: final number A 182, B 159, C 59, other 139, multiple 1. 280 of the 400 that end in 1/3, 1/2 or 1/4 state no method. Stated-method check: A 73, B 30, C 39, multiple 13, none 385.
- Variation across phrasings: none of 5000 label shuffles spread as much as the real mix (spread 131.7, df 34); on the stated method, 1.9% did. Within a phrasing, the mean majority share is 0.61, against 0.51 for independent draws. Unlike the 1.5B and 3B, the 7B's choice depends on the problem statement. For example, phrasing 6 gives 18 A of 20 canonical, phrasing 17 gives 20 B of 27, and phrasing 12 gives 18 A of 22.
- 2% of answers hit the token limit (15/972). Full tables are in `results/s1/summary.md`.

## 2026-10-09 — hand judgment of the 7B neutral answers ending in 1/3, 1/2 or 1/4

- What was judged: the 400 of 540 samples in `neutral_qwen7b.jsonl` whose final number is 1/3, 1/2 or 1/4. Same rubric and rules as for the 3B: I read each answer myself, with no script or API, and recorded the variable, derived or recalled, mentions of the paradox, and a reason. Results are in `results/s1/judge_qwen7b.jsonl`. 30 judged answers with full text (10 per number, seed 0) are in `results/s1/judge_check_qwen7b.md`.
- Overall: 342 derived, 58 recalled (3B: 200 / 161). No answer mentions the paradox or says the answer depends on how the chord is chosen (0/400).
- By number: 1/3 → 142 derived, 40 recalled. 1/2 → 143 derived, 16 recalled. 1/4 → 57 derived, 2 recalled.
- By variable: angle at the center 142 derived / 45 recalled; distance from the center 143 / 1; midpoint in the disk 57 / 9; none 0 / 1; other 0 / 2 (a segment-area ratio cut off at the token limit, where the scorer read the 1/3 inside 1/3 − √3/(4π)).
- Number × variable: as with the 3B, every derived 1/3 uses the angle, every derived 1/2 the distance, and every derived 1/4 the midpoint.
  - Recalled 1/3s come from the angle (37), none (1) and the segment area (2). The angle ones mostly compute 1/6 or 2/3 and box 1/3, take the 120° threshold over 360° as the probability, or use wrong ranges that happen to land on 1/3.
  - Recalled 1/2s come from the angle (8: wrong ranges summed to 180°), the midpoint (7: wrong thresholds or area ratios that give 1/2), and the distance (1: reversed condition).
  - Recalled 1/4s come from the midpoint (2: false reasons for the r/2 threshold).
- By phrasing (derived / recalled):

| phrasing | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| derived | 7 | 20 | 20 | 19 | 21 | 18 | 17 | 24 | 22 | 17 | 19 | 16 | 15 | 24 | 19 | 12 | 25 | 27 |
| recalled | 8 | 4 | 5 | 3 | 1 | 3 | 3 | 3 | 0 | 1 | 4 | 7 | 7 | 2 | 4 | 2 | 1 | 0 |

- Derived share by threshold phrasing:

| threshold phrasing | phrasings | derived share | by number (derived / recalled) |
|---|---|---|---|
| triangle | 0, 1, 3, 6, 9, 11, 15 | 79% (108/136) | 1/3 70 / 20; 1/2 19 / 7; 1/4 19 / 1 |
| r√3 | 2, 4, 7, 12, 13, 14, 17 | 87% (150/172) | 1/3 47 / 15; 1/2 78 / 6; 1/4 25 / 1 |
| numeric | 5, 8, 10, 16 | 91% (84/92) | 1/3 25 / 5; 1/2 46 / 3; 1/4 13 / 0 |

The 7B works out its number far more often than the 3B (86% against 55%). The 1/3s are still the weakest: 22% of them are recalled, against 10% of 1/2s and 3% of 1/4s. Triangle phrasings get the lowest derived share. They lead to 1/3 more often (90 of 136, against 30 of 92 for numeric thresholds), and the triangle's 120° angle invites the threshold-over-360° shortcut. The canonical problem statement (phrasing 0) is the only one where recalled answers outnumber derived ones (8 to 7).

## 2026-10-09 — stage 2 on the 7B: reading direction, answer direction, comparison

Every second layer: residual indices 0, 2, …, 28; 0 is the embeddings. The 7B is the 4-bit model, as in stage 1. No steering. Tables are in `results/s2/summary_qwen7b.md` (reading) and `results/s2/summary_answer_qwen7b.md` (answer and comparison).

**Reading direction**: labeled prompts, last prompt token, the existing `s2_probe.py`.
- The probe trains on 195 prompts: training phrasings × training descriptions. It is tested on three held-out sets:
  - phrasing and description both unseen (45);
  - description unseen (117);
  - phrasing unseen (75).
- Inner cross-validation picks layer 20. There it is right on 96% of the 45 fully unseen prompts. It also gets 87% on unseen descriptions and 100% on unseen phrasings.
- Shuffled labels give 33% (95th percentile 45%). A words-only classifier on the prompt text gets 76% / 80% / 100%.
- Layers 2–18 already get 87–100% on unseen phrasings, but only 51–68% on unseen descriptions. From layer 20 on, both are high. So the early layers mostly key on the description's words, and the later layers carry something that transfers to descriptions written without the training keywords.
- On the 18 neutral prompts, the layer-20 probe puts all its weight on A for every phrasing. That is not what the model then samples, which is A for 8 phrasings and B for 10. Neutral prompts state no approach, so this is outside what the probe was trained on.

**Answer direction: where the formula starts.**
- Input: the 342 derived neutral answers from `judge_qwen7b.jsonl`. The label is the final number: 1/3 for 142 answers, 1/2 for 143, 1/4 for 57.
- What I searched for: the first chord-length formula in each answer. That is an expression tying the chord's length to the distance from the center (2√(r²−d²) and its variants, including the words "Pythagorean theorem" that introduce it) or to the central angle (2r sin(θ/2), a cosine).
- What was found: 307 answers have one. The other 35 argue in words only ("the side subtends 120°").
- How early it starts: answer token 53 at the earliest, 92 at the 5th percentile, 162 at the median.
- Detector check: I read 30 random answers against the detector's mark. In all 30 it sat on the first formula, or correctly found none.
- Window: by the rule (the formula comes after the window in at least 95% of answers), it would be about 92 tokens (the 5th percentile). It was capped at 60, so the floor of 15 did not apply. One answer has its formula inside the first 60 tokens and is dropped, leaving 341 answers.
- Words before formulas: the variable is often named in words before any formula. The median first mention of "perpendicular distance", "central angle", "subtend" or "midpoint" is token 110. 29 of the 341 kept answers name it inside the window: 9 within the first 20 tokens, 14 within 30. So a probe on the first 60 tokens can partly be reading words that state the approach.

**Answer direction: probe.**
- Setup:
  - Activations: the prompt plus the first 60 answer tokens were run through the model.
  - Probe input: the mean over the window, per layer.
  - Folds: six groups of phrasings. Every test phrasing is unseen in training.
  - Score: balanced accuracy, where 33% is chance. The plain-accuracy majority rate is 42%.
- Results:
  - It peaks at 53% balanced (63% plain) at layers 10–16. Most layers are 48–50%.
  - **Global null:** labels shuffled over all answers give 33% (95th percentile 36–40%).
  - **Within-phrasing null:** labels shuffled only inside each phrasing give 43–45% (95th percentile 45–48%). This shuffle keeps how often each phrasing leads to each number and removes everything specific to one sample.
  - **Words-only baselines:**
    - TF-IDF on the window's own text gets 48% balanced.
    - The mean token embedding (layer 0) gets 47%.
    - TF-IDF on the prompt text gets 40%.
- Reading of these numbers: most of what the window probe gets is already in the phrasing and in the window's words. At layers 10–16, the activations add about 5 points over the words and over the within-phrasing null's 95th percentile.

**Answer direction: other positions.**
- **Last prompt token on its own:** 50% balanced at layer 8, 34–47% at the other layers, and 27% at layer 0, against a global null 95th percentile of 37–46%. This activation is the same for every sample of a phrasing (18 distinct points), so all of it is phrasing-level information that carries over to unseen phrasings. Its within-phrasing null equals the real run by construction.
- **Sensitivity (mean over the first 10 / 20 / 30 / 60 tokens, balanced):** best 53% / 51% / 48% / 53%. No kept answer has its formula inside any of these spans. The variable is named in words in 0 / 9 / 14 / 29 answers. The first-10 mean already reaches 50–53% at layers 10–20, but those tokens mostly restate the problem ("To determine the probability that a randomly drawn chord…"). Whether that is more than the phrasing is not tested here: the within-phrasing null was run only on the 60-token window.

**Comparison of the two directions.**
- **Alignment:** the class-by-class cosines between the reading probe's weights and the answer probe's weights are all between −0.03 and +0.06. The 95th percentile with shuffled answer labels is 0.03–0.06. Difference-of-means directions agree no better: within ±0.08 at layers 2–26, and +0.17 for A at layer 28 against a null of 0.22.
- **Cross-prediction:**
  - Raw, each probe puts nearly everything in one class on the other set (balanced 33%).
  - With each set shifted onto the other's mean, the reading probe on the answer windows gets 22–47% balanced; the two highest are 47% at layer 26 and 44% at layer 28.
  - The reading probe on the answers' last prompt token gets 21–39%.
  - The answer probe on the labeled prompts gets 27–36% (strict set 22–42%).
- **Overall:** at these layers and positions, the direction that reads a stated approach in the prompt and the direction that predicts the final number early in the model's own answer are not the same direction. Neither transfers to the other's data.

**Phrasing caveat.** The 7B's neutral choice depends on the phrasing (stage 1). So the answer probe may partly read the phrasing rather than a choice the model makes in each sample.
- **What the folds control for:** each test phrasing is unseen in training, so the probe cannot score by recognising a phrasing it was trained on.
- **What they do not control for:** features shared across phrasings still predict the number on unseen ones: threshold type (triangle / r√3 / numeric), radius, verb, sentence order. Triangle phrasings, for example, lead to 1/3 more often.
- **How much that could explain:**
  - Phrasing-level information alone gets 41–50% balanced (last-prompt-token probe) and 40% (prompt-text TF-IDF).
  - Keeping the phrasing → number link but shuffling within phrasings gives 43–45%, with a 95th percentile up to 48%.
  - The window probe's 53% is only a little above these.

## 2026-10-10 — stage 2, last 7B check: how far before the variable is named can the number be read

- **Disk:** I deleted the 1.5B and 3B weights from the Hugging Face cache (8.7 GB). C: went from 5.3 GB free to 14 GB. The 7B weights and all results files are kept.
- **Setup:**
  - **Answers:** the same 342 derived neutral answers. For each one, `t` is the first token of the first word that names the variable: "perpendicular distance" (140), "subtend" (89), "central angle" (52), "distance (d) from the center" (53) or "midpoint" (8). Every answer names one, so none were dropped.
  - **Positions:** the residual stream at layers 0, 2, …, 28, at single positions 30, 20, 10, 5, 2 and 1 tokens before `t`, and at `t` itself. 14 answers name the variable within their first 30 tokens and 9 within 20, so they are missing at those offsets (n = 328 and 333).
  - **Probe:** same probe and phrasing folds as before; label = final number.
  - **Nulls:** labels shuffled over all answers, and shuffled only inside each phrasing (20 shuffles). At the best layer, 22, both nulls were rerun with 50 shuffles.
  - **Words-only baseline:** TF-IDF on the answer text up to the probed position, with and without the prompt in front. The probed position is the last token that residual has read.
  - **Scores:** balanced accuracy, where chance is 33%. The within-phrasing null, which keeps what the phrasing alone predicts, sits at 37–47% on average, with a 95th percentile of 41–52%.
- **Curve against offset at layer 22** (probe / within-phrasing null 95th percentile / best words baseline):

| tokens before the word | probe | within-phrasing null 95th percentile | best words baseline |
|---|---|---|---|
| 30 | 40% | 41% | 42% |
| 20 | 48% | 41% | 49% |
| 10 | 53% | 46% | 49% |
| 5 | 57% | 47% | 48% |
| 2 | 70% | 49% | 58% |
| 1 | 75% | 48% | 59% |
| 0 (the word) | 79% | 52% | 72% |

  Layer 16 looks the same within a few points.
- **In words:**
  - 30 tokens before the variable is named, the final number cannot be read beyond what the phrasing and the visible words already give.
  - From about 20 to 5 tokens before, the probe rises from 48% to 57%. That is above the within-phrasing shuffle, and at 5 tokens it is 9 points above the words.
  - The big step comes in the last two tokens before the word: 70% at 2 tokens and 75% at 1, against 58–59% for the words. The residual one token before the word is the one that predicts the next token. So much of this is the model about to write "perpendicular distance" or "central angle", and that word nearly fixes the method and so the number.
  - At the word itself, the probe gets 79% and the words 68–72%.
  - Overall, the number becomes readable shortly before the answer names its variable, mostly in the last few tokens, not at the start of the answer.
- **Extra rows (layer 22, no nulls):**
  - **Without the 23 answers whose formula comes before the word:** 40 / 46 / 56 / 58 / 68 / 73 / 80% across the seven offsets, close to the main curve.
  - **Stricter anchor:** the 53 "distance (d) from the center" answers were re-anchored on a later stricter word (27) or dropped when none followed (26). The curve is 45 / 47 / 59 / 58 / 70 / 73 / 80%. Neither group changes the picture.
- **First-10-token mean, with the within-phrasing null that was missing last time:** 42–53% balanced across layers. Shuffling only within phrasings gives 42–47% on average, with a 95th percentile of 47–52%. Only layer 20 is at all above it (53% against 50%). So the 50–53% that the first 10 tokens reached in the last run is phrasing-level information, not an early per-sample choice.
- **Caveat:** as in the last entry, the phrasing folds keep test phrasings unseen but do not remove features shared across phrasings. The within-phrasing shuffle and the prompt + answer-text baseline are the bar for "more than the phrasing".
- Tables: `results/s2/summary_word_qwen7b.md`.

## 2026-10-10 — figures for the write-up

- `figures.py` regenerates all seven figures from the results files: `uv run python figures.py`. matplotlib was added to the project.
- Output: `results/figures/{header,phrasings,which,how,famous_number,where_we_look,when}.{png,svg}`; every PNG is 1600 px wide.
- Style: one palette (1/3 blue, 1/2 orange, 1/4 green, other grey); derived bars solid, recalled bars hatched; no titles inside the figures.
- The header shows no numbers, and its shaded regions use a neutral accent color, so it does not give away the answers.
- Captions are in `results/figures/captions.md`. The where-we-look example was chosen for fit: its branch word comes at token 68, while it usually comes around token 110. Its caption says so.
- Below are the exact numbers each figure draws (also in `results/figures/numbers.md`).

### header

(a) endpoints at 90° and 237°; shaded arc 210°–330° (one third)
(b) radius at 85°, point at 0.39 r; shaded inner half of the radius
(c) midpoint at 0.36 r, angle 34°; shaded inner disk radius r/2
No numbers drawn; favourable regions in one accent color (not a number color).

### phrasings

canonical id 0; rephrasings ids 13, 14 (random.Random(0)); labeled prompt w00_c4 (approach C, description c4, clause after the problem)
highlighted clause: "The chord is obtained by sampling the chord's midpoint uniformly over the whole disk."

### which

x order (threshold, radius, id): 0(triangle,r), 6(triangle,r), 1(triangle,r=1), 11(triangle,r=1), 3(triangle,r=2), 9(triangle,r=2), 15(triangle,r=5), 12(r√3,r), 7(r√3,r=1), 13(r√3,r=1), 17(r√3,r=1), 4(r√3,r=2), 2(r√3,r=5), 14(r√3,r=5), 10(numeric,r=1), 5(numeric,r=2), 8(numeric,r=5), 16(numeric,r=5)
3B per phrasing (1/3, 1/2, 1/4, other): 0: 9,10,1,10; 6: 8,8,4,10; 1: 5,13,6,6; 11: 6,9,6,9; 3: 11,5,4,10; 9: 8,6,5,11; 15: 8,8,1,13; 12: 8,3,7,12; 7: 8,9,6,7; 13: 9,9,6,6; 17: 10,8,3,9; 4: 9,6,5,10; 2: 3,11,3,13; 14: 5,13,4,8; 10: 3,16,5,6; 5: 4,7,7,12; 8: 5,6,4,15; 16: 2,12,4,12
7B per phrasing (1/3, 1/2, 1/4, other): 0: 11,4,0,15; 6: 18,2,0,10; 1: 17,3,4,6; 11: 17,1,5,7; 3: 12,5,5,8; 9: 9,3,6,12; 15: 6,8,0,16; 12: 18,1,3,8; 7: 12,14,1,3; 13: 7,17,2,4; 17: 5,20,2,3; 4: 6,7,9,8; 2: 6,12,7,5; 14: 8,13,2,7; 10: 7,16,0,7; 5: 9,9,3,9; 8: 8,12,2,8; 16: 6,12,8,4

### how

3B 1/3: derived 30 (angle 30); recalled 91 (angle 87, midpoint 4)
7B 1/3: derived 142 (angle 142); recalled 40 (angle 37, other: area of a circular segment 2, none 1)
3B 1/2: derived 95 (distance 95); recalled 64 (midpoint 23, angle 22, none 10, distance 6, other: area of a band of chords 1, other: half of the disk area 1, other: segment area, then 'half the circle' 1)
7B 1/2: derived 143 (distance 143); recalled 16 (angle 8, midpoint 7, distance 1)
3B 1/4: derived 75 (midpoint 75); recalled 6 (midpoint 6)
7B 1/4: derived 57 (midpoint 57); recalled 2 (midpoint 2)

### famous number

3B triangle: derived 52/141 = 37%
3B r√3: derived 95/145 = 66%
3B numeric: derived 53/75 = 71%
7B triangle: derived 108/136 = 79%
7B r√3: derived 150/172 = 87%
7B numeric: derived 84/92 = 91%
right panel: 7B phrasing 12 sample 26, answer lines [0, 10, 18, 22, 26, 28, 29, 31]; highlighted line 26 (computes 2/3) and line 29 (boxed 1/3)

### where we look

7B phrasing 2 sample 7 (final number 1/2, derived); prompt 56 tokens, last 4 shown; answer tokens 0–72 shown; branch word "perpendicular distance" at answer token 68 (tokens 68–69); ticks at answer tokens 38, 58, 63, 67; first-60 bracket over tokens 0–59
median branch-word position over the 342 answers: token 110

### when

x (tokens before the branch word): [30, 20, 10, 5, 2, 1, 0]
probe, layer 22, balanced accuracy (%): 40.1, 47.9, 52.6, 57.2, 69.7, 74.6, 79.2
words only, prompt + answer text up to that point (%): 40.1, 48.8, 47.3, 46.1, 58.1, 59.2, 71.6
within-phrasing shuffle, 95th percentile, 50 shuffles (%): 40.6, 40.5, 46.4, 46.9, 48.5, 47.8, 51.9
chance: 33.3%
n per offset: 328, 333, 342, 342, 342, 342, 342


## 2026-10-10 — figures revised

- **header:** redrawn in a thin geometry style. All strokes are 1.2 pt, with the circle and chords in one dark blue and the triangle in light grey. Points are small dots with a white edge, and the center is marked.
  - (a) The favourable arc is shaded in the 1/3 color.
  - (b) The full radius is drawn, with its inner half shaded in the 1/2 color.
  - (c) The inner circle is filled in the 1/4 color.
  - Each panel has its number under it.
  - The robot is redrawn in the same thin stroke. It has no tilt; its puzzled look comes from one raised eyebrow and a short flat mouth, with a light "?".
- **which:** the group with no radius given is labeled "no r".
- **famous number:** the math in the excerpt is rendered with mathtext. Both highlights are kept: the step that computes 2/3, and the boxed 1/3.
- **where we look:** the brackets are gone. The first 60 answer tokens are shaded grey, labeled once. Dots with labels sit above the tokens 30, 10, 5 and 1 before the branch word, and the rows are spaced further apart.
- **when:** the seven x positions are now equally spaced.
- **phrasings:** the two rephrasings are now id 16 (numeric threshold) and id 6 (no radius in the text). The labeled prompt is now labeled "canonical statement plus a clause for 1/4".
- Numbers for the changed figures, from `results/figures/numbers.md`:

### header

(a) endpoints at 90° and 237°; shaded arc 210°–330° (one third), 1/3 color
(b) radius at 20°, point at 0.26 r; inner half of the radius shaded, 1/2 color
(c) midpoint at 0.41 r, angle 210°; inner disk of radius r/2 filled, 1/4 color
numbers under the panels: (a) 1/3, (b) 1/2, (c) 1/4

### phrasings

canonical id 0; rephrasings id 16 (numeric threshold) and id 6 (no radius), picked with random.Random(0) within those groups; labeled prompt w00_c0 (approach C, description c0, clause after the problem)
highlighted clause: "In this problem, "at random" means choosing a point uniformly at random inside the disk and taking the chord whose midpoint is that point."

### famous number

3B triangle: derived 52/141 = 37%
3B r√3: derived 95/145 = 66%
3B numeric: derived 53/75 = 71%
7B triangle: derived 108/136 = 79%
7B r√3: derived 150/172 = 87%
7B numeric: derived 84/92 = 91%
right panel: 7B phrasing 12 sample 26, answer lines [0, 10, 18, 22, 26, 28, 29, 31], math rendered with mathtext; highlighted line 26 (computes 2/3) and line 29 (boxed 1/3)

### where we look

7B phrasing 2 sample 7 (final number 1/2, derived); prompt 56 tokens, last 4 shown; answer tokens 0–72 shown; first 60 answer tokens (0–59) shaded grey; branch word "perpendicular distance" (tokens 68–69); dots at answer tokens 38, 58, 63, 67
for the caption: branch word of this answer at answer token 68; median branch-word position over the 342 answers: token 110

### when

x (tokens before the branch word, equally spaced): [30, 20, 10, 5, 2, 1, 0]
probe, layer 22, balanced accuracy (%): 40.1, 47.9, 52.6, 57.2, 69.7, 74.6, 79.2
words only, prompt + answer text up to that point (%): 40.1, 48.8, 47.3, 46.1, 58.1, 59.2, 71.6
within-phrasing shuffle, 95th percentile, 50 shuffles (%): 40.6, 40.5, 46.4, 46.9, 48.5, 47.8, 51.9
chance: 33.3%
n per offset: 328, 333, 342, 342, 342, 342, 342


## 2026-10-10 — figures: header, which, famous number touched up

- **header:**
  - (b) The radius is at 100°, with the point at 0.30 r. The chord ends at 173° and 27°, at least 37° from every vertex. The shaded part is exactly the segment from 0 to 0.5 r of the radius.
  - (c) The midpoint is at 0.30 r.
  - The numbers are half the previous size, just under each circle.
  - The robot has both eyebrows (one raised, one flat) and a margin below its head.
- **which:** wider gaps between the threshold groups, and smaller radius sublabels.
- **famous number:** the math is set at the prose size, with full-size fractions. Lines are spaced by their rendered height. The data drawn is unchanged.

## 2026-10-10 — figures: header (b), panel labels, two captions

- **header:**
  - The (a)/(b)/(c) labels are removed.
  - In (b), the radius points away from all three vertices: 270°, 60° from each. The point is at 0.20 r. The inner half of the radius, from the center to its midpoint at 0.5 r, is drawn as a thicker line in the 1/2 color. With the radius between two vertices and the point in the inner half, the chord ends cannot stay 30° from every vertex; here they are 18° from the nearest one.
- **where we look:** the grey label and the caption now say "the first 60 answer tokens, used by the earlier probe".
- **when:** the caption now ends with "a probe above this line reads more than the phrasing."
- **header (b), adjusted:** the radius is now at 262°, tilted 8° off straight down so it is not perpendicular to the triangle's base. The point is at 0.15 r, and the chord ends are 13° from the nearest vertex. The inner-half line is drawn at 55% opacity.
- **header (b):** the inner-half band now matches the arc band in (a): 0.1 r wide (about 7.7 pt), 35% opacity, drawn under the radius line.
- **header (b):** the inner-half band is now wider: 0.2 r (about 15 pt), at 45% opacity.

## 2026-10-11 — branch-word probe on unsupported 7B answers (1/3 vs not), next to supported

- **Cache check:** Qwen2.5-3B-Instruct is not in the Hugging Face cache. It was deleted on 2026-10-10 as asked; nothing was downloaded.
- **Naming:** from here on, the judge's categories are called **supported** (the written steps lead to the boxed number) and **unsupported** (they do not). The data keys stay `derived_or_recalled` = `derived` / `recalled`.
- **Answers:**
  - **Unsupported:** 58 answers (1/3 40, 1/2 16, 1/4 2). Two never name the variable in words and were dropped: phrasing 0 sample 5, and phrasing 12 sample 1, both 1/3. That leaves 56: 38 end in 1/3 and 18 do not, over 16 phrasings.
  - **Supported:** 342 answers, 142 1/3 and 200 not. None was dropped.
  - **Branch word, median token:** 110 for supported, 142 for unsupported.
- **Setup:**
  - **Recording:** the residual stream at layers 0, 2, …, 28, at 30, 20, 10, 5, 2, 1 and 0 tokens before the branch word.
  - **Probe:** binary, final number 1/3 or not; same probe and phrasing folds as before.
  - **Score:** balanced accuracy, where chance is 50%.
  - **Plotted layer:** 22, fixed in advance as the layer of the earlier curve. There, both nulls were run with 50 shuffles.
  - **Words-only baseline:** TF-IDF on prompt + answer text up to that point.
  - **Size-matched curve:** the supported probe rerun on 20 random subsets of 56 supported answers, with the same 38 / 18 split.
  - **Figure:** `results/figures/when_supported_vs_unsupported.png`; tables in `results/s2/summary_word_binary_qwen7b.md`.

| tokens before | supported | within null p95 | global null p95 | words | supported, 56-answer subsets: mean (5th–95th) | unsupported | within null p95 | global null p95 | words |
|---|---|---|---|---|---|---|---|---|---|
| 30 | 63% | 61% | 54% | 57% | 50% (45–56%) | 41% | 49% | 54% | 49% |
| 20 | 68% | 62% | 56% | 63% | 53% (42–63%) | 38% | 54% | 56% | 47% |
| 10 | 74% | 64% | 56% | 69% | 60% (46–73%) | 53% | 54% | 56% | 45% |
| 5 | 79% | 65% | 57% | 66% | 63% (46–75%) | 48% | 53% | 56% | 47% |
| 2 | 87% | 72% | 59% | 73% | 74% (61–86%) | 45% | 54% | 56% | 47% |
| 1 | 92% | 67% | 56% | 76% | 87% (78–93%) | 38% | 53% | 56% | 47% |
| 0 | 98% | 76% | 60% | 94% | 97% (90–100%) | 56% | 57% | 58% | 47% |

- **Supported:** whether the boxed number will be 1/3 is barely above the within-phrasing shuffle 30 tokens before the branch word (63% against 61%). It rises steadily to 87–92% in the last two tokens and 98% at the word, above both the shuffle and the words.
- **Supported, 56-answer subsets:** with only 56 answers the supported probe sits near chance until about 5 tokens before the word (50–63%). It still climbs to 87–97% in the last two tokens. So a set this small can show the late rise.
- **Unsupported:** the probe stays at or below its within-phrasing shuffle at every offset (38–56%), even at the branch word itself. Before and at the point where an unsupported answer names its variable, the residual stream does not tell whether its boxed number will be 1/3. The words do no better (45–49%).
- **Small n:** the unsupported set is small. Each test fold holds about 9 answers, and many phrasings have only a few unsupported answers, so the within-phrasing shuffle only moves labels where a phrasing has both classes.
- **Why the unsupported curve stays flat:** in these answers the branch word is mostly an angle word (subtend 24, central angle 12), whether the box ends up 1/3 or not. So the variable the answer names does not fix its final number, unlike in supported answers.

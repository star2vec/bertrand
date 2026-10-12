<img width="1600" height="551" alt="header" src="https://github.com/user-attachments/assets/237a6dec-62f4-4055-af98-4273db2f6aa9" />

[LessWrong article](https://www.lesswrong.com/posts/GymxEweup4GyNbpRE/a-problem-with-three-correct-answers-which-how-and-when-does)

A look at how models (3 sizes of the Qwen 2.5 model family) behave when posed with Bertrand's paradox. 18 phrasings, up to 30 answers each. For each, we check which of the three famous responses it outputs, whether it explains the method or recalls it, and when the method choice shows up in the model's internals. 
When models are posed with an ambiguous question, it is very useful to know whether we can identify their choice through the chain of thought transcript alone. We asked whether the method choice is represented in the model's activation before it is written down, and when.

Findings:
* 0/761 answers state that the problem is ambiguous. The model settles on an approach and provides the final answer as if it were the only possibility.
* For the 7B, the phrasing nudges towards a final number (no radius given: ⅓, radius given: ½). For the smaller models, the distribution of final numbers remains consistent across phrasings. 
* Most answers explain their reasoning (85% for 7B, 55% for 3B). The famous ⅓ is the one that gets recalled (plainly stated) most often, and the reasoning builds up to it while the model knows what it is supposed to reach (75% of ⅓s for 3B, 22% for 7B) 
* The approach the model settles on becomes distinguishable only 5-10 tokens before the pivotal word (the one that nails the method down: "central angle", "perpendicular distance", and other similar ones). The reading at 30 tokens before it does not add anything else that the phrasing and the text up until that point didn't already provide, but a probe detects a 5-10 token build-up (from 53-57% to 79% at the exact position of the pivotal token).

## Setup

Needs [uv](https://docs.astral.sh/uv/); `uv sync` installs everything. The 7B runs in 4-bit and needs a CUDA GPU.
Full options, machines and smoke-test flags are in [`RUNNING.md`](RUNNING.md); the running log of every run and
decision is [`LOG.md`](LOG.md).

## Stages, in order

**Stage 1: behavior** (what each model answers)

    uv run python s1_generate.py --model 7b --set labeled      # also --model 1.5b / 3b
    uv run python s1_generate.py --model 7b --set neutral --n_samples 30 --max_new_tokens 1024
    uv run python s1_summarize.py

**Stage 2: probes** (7B)

    uv run python s2_activations.py --model 7b --layers 0 2 4 6 8 10 12 14 16 18 20 22 24 26 28
    uv run python s2_probe.py --model 7b
    uv run python s2_answer_acts.py --model 7b --layers 0 2 4 6 8 10 12 14 16 18 20 22 24 26 28
    uv run python s2_answer_probe.py --model 7b
    uv run python s2_word_acts.py --model 7b --layers 0 2 4 6 8 10 12 14 16 18 20 22 24 26 28
    uv run python s2_word_acts.py --model 7b --set unsupported --layers 0 2 4 6 8 10 12 14 16 18 20 22 24 26 28
    uv run python s2_word_probe.py --model 7b
    uv run python s2_word_probe_binary.py --model 7b

**Stage 3: steering** (scripts in place, not run yet)

    uv run python s3_steer.py --model 7b
    uv run python s3_summarize.py

Figures: `uv run python figures.py`.

## Where things are

- `prompts/` — the 18 neutral phrasings and 432 specified prompts, rebuilt by `prompts/build_prompts.py`.
- `results/s1/` — every stage-1 answer (`labeled_*.jsonl`, `neutral_*.jsonl`), `summary.md`, and samples to read.
- `results/s1/judge_qwen3b.jsonl`, `results/s1/judge_qwen7b.jsonl` — the hand judgments (explained / unexplained,
  variable used, paradox mentioned) of every 3B and 7B neutral answer ending in 1/3, 1/2 or 1/4;
  `judge_check.md` (3B) and `judge_check_qwen7b.md` hold 30 judged answers each with full text, for checking.
  In the data the judgment key is `derived_or_recalled`: `derived` = explained, `recalled` = unexplained.
- `results/s2/` — probe results and summaries (`summary_*.md`, `*.json`).
- `results/figures/` — the figures (PNG and SVG), `captions.md`, and `numbers.md` with every number they draw.

## What is reproducible from this repo

The stage-1 summaries for all three models and all figures regenerate from the committed files
(`s1_summarize.py`, `figures.py`; one figure loads the 7B tokenizer from the Hugging Face hub). The hand judgments of
the 3B and 7B answers are committed as made; they were done by reading each answer, not by a script, and there is no
1.5B judgment. The activation arrays (`results/s2/*.npz`, several hundred MB) are not committed: regenerating them, and
the stage-2 numbers that depend on them, needs the stage-2 commands above on a GPU.

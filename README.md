# bertrand

Bertrand's chord paradox has three textbook answers — 1/3, 1/2 and 1/4 — depending on how "a random chord" is drawn,
and this repo asks whether a small language model's choice among them can be read from its activations. On Qwen2.5
1.5B, 3B and 7B-Instruct we record which number each model gives across 18 phrasings of the problem, judge by hand
whether the written steps actually explain the boxed number, and probe the 7B's residual stream for the stated and
the chosen approach. The approach stated in a prompt is easy to read, but the 7B's own choice becomes readable only a
few tokens before the answer names its variable, and not at all for answers whose steps do not explain the number.

Post: [link to the post](https://example.com/TODO) (placeholder).

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

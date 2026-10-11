# Running the code

Bertrand pilot: can a small model's choice of approach (endpoints 1/3, radial 1/2, midpoint 1/4) be read from its
activations before it writes, and can that direction steer what it writes? Running log in `LOG.md`.

## Setup (both machines)

Needs [uv](https://docs.astral.sh/uv/). From this folder:

    uv sync

Windows resolves CUDA torch from the cu124 index automatically (needs an NVIDIA driver >= 550) and also installs
bitsandbytes for the 4-bit 7B. Check with `uv run python -c "import torch; print(torch.cuda.is_available())"`.
Models download from the HF hub on first use (the 7B is about 15 GB of bf16 safetensors, quantized at load time).

Precision: half precision everywhere, bf16 on CUDA, fp16 on MPS. The 7B (`--model 7b`) loads in 4-bit nf4 with bf16
compute and needs CUDA. Generation uses repetition_penalty 1.0 (Qwen ships 1.1).

Any script takes `--limit N` for a smoke test (`--max_new_tokens 60` shortens generation). Generation scripts are
resumable: re-run the same command after an interruption. `--device cpu|mps|cuda` overrides auto-detection.

## Stage 1: behavior

Windows (generation; default batch 8 / 4 / 2 for the 1.5B / 3B / 7B, raise `--batch_size` if memory allows):

    uv run python s1_generate.py --model 1.5b --set labeled
    uv run python s1_generate.py --model 1.5b --set neutral
    uv run python s1_generate.py --model 3b --set labeled
    uv run python s1_generate.py --model 3b --set neutral
    uv run python s1_generate.py --model 7b --set labeled
    uv run python s1_generate.py --model 7b --set neutral

Then `git add results/s1 && git commit && git push`. Summary on any machine: `uv run python s1_summarize.py`
(writes `results/s1/summary.md` and `results/s1/samples_{tag}.md`). `--ids w00_a0,w03_b1` runs chosen prompts
(smoke test).

`s1_nextword.py` (prefilled next-word check) is kept as a script but its numbers are not reported.

## Stage 2: probe (reading direction on labeled prompts; answer direction on derived neutral answers)

    uv run python s2_activations.py --model 1.5b
    uv run python s2_probe.py --model 1.5b

Writes `results/s2/summary_{tag}.md`, `probe_{tag}.json` and `direction_{tag}.npz` (the activations `.npz` is
gitignored; the direction file is small and committed for stage 3). `--layers 0 2 4 …` keeps a subset of layers.

Answer direction (Windows, after the stage-1 hand judgment `results/s1/judge_{tag}.jsonl` exists):

    uv run python s2_activations.py --model 7b --layers 0 2 4 6 8 10 12 14 16 18 20 22 24 26 28
    uv run python s2_probe.py --model 7b
    uv run python s2_answer_acts.py --model 7b --measure --show 30   # formula positions + window, no GPU
    uv run python s2_answer_acts.py --model 7b --layers 0 2 4 6 8 10 12 14 16 18 20 22 24 26 28
    uv run python s2_answer_probe.py --model 7b

Writes `results/s2/formula_pos_{tag}.json`, `answer_probe_{tag}.json` and `summary_answer_{tag}.md`.

Before the variable is named in words (probe at 30, 20, 10, 5, 2, 1 and 0 tokens before the first "perpendicular
distance" / "central angle" / "subtend" / "midpoint" / "distance (d) from the center"):

    uv run python s2_word_acts.py --model 7b --layers 0 2 4 6 8 10 12 14 16 18 20 22 24 26 28
    uv run python s2_word_probe.py --model 7b

Writes `results/s2/word_probe_{tag}.json` and `summary_word_{tag}.md`.

## Stage 3: steering sweep (Windows)

    uv run python s3_steer.py --model 1.5b --wordings 0 3 7 9 11 14
    uv run python s3_summarize.py

Pick the six `--wordings` from the stage-1 behaviour. `--alphas 0 1 2 4 8` and `--direction classifier|diffmeans`
are the knobs.

## Files

- `prompts/build_prompts.py` regenerates `prompts/*.jsonl` deterministically (18 neutral, 432 labeled; every wording says "chord").
- `score.py` labels an answer by its final number (primary) and by the method stated in its text (kept as a check); run it to self-test.
- `common.py` holds model loading, the chat template, residual-stream recording and the steering hook.

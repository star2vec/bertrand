"""Shared helpers: paths, model loading, chat formatting, generation, residual-stream capture and steering.

Layer indexing used everywhere in the pilot: 0 = embedding output, k = output of decoder block k (1..n_layers).
Precision (since 2026-10-08): half precision on every machine, bf16 on CUDA, fp16 on MPS (fp32 only on CPU, which
is not a target). The 7B loads in 4-bit (bitsandbytes nf4, bf16 compute) and needs CUDA. The `mode` argument of
load_model/run_meta is kept for the callers but no longer changes the dtype.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
PROMPTS = HERE / "prompts"
RESULTS = HERE / "results"

MODELS = {"1.5b": "Qwen/Qwen2.5-1.5B-Instruct", "3b": "Qwen/Qwen2.5-3B-Instruct", "7b": "Qwen/Qwen2.5-7B-Instruct"}
TAGS = {"Qwen/Qwen2.5-1.5B-Instruct": "qwen1.5b", "Qwen/Qwen2.5-3B-Instruct": "qwen3b",
        "Qwen/Qwen2.5-7B-Instruct": "qwen7b"}
QUANT4 = {"Qwen/Qwen2.5-7B-Instruct"}  # loaded in 4-bit nf4 (bitsandbytes); the 8 GB GPU cannot hold it in bf16
DEFAULT_BATCH = {"qwen1.5b": 8, "qwen3b": 4, "qwen7b": 2}  # generation batch sizes for the 8 GB GPU; raise if memory allows
APPROACHES = ["A", "B", "C"]
APPROACH_LABEL = {"A": "A endpoints 1/3", "B": "B radial 1/2", "C": "C midpoint 1/4"}


def utf8_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def resolve_model(key: str) -> str:
    return MODELS.get(key.lower(), key)


def model_tag(name: str) -> str:
    return TAGS.get(name, name.split("/")[-1].lower())


def pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def pick_dtype(device: str, mode: str | None = None) -> torch.dtype:
    """Half precision everywhere (bf16 CUDA, fp16 MPS); fp32 only on CPU. `mode` is ignored (kept for callers)."""
    return {"cuda": torch.bfloat16, "mps": torch.float16, "cpu": torch.float32}[device]


def dtype_label(name: str, device: str) -> str:
    if name in QUANT4:
        return "4bit-nf4/bf16"
    return str(pick_dtype(device)).replace("torch.", "")


def default_batch(name: str) -> int:
    return DEFAULT_BATCH.get(model_tag(name), 4)


def load_model(key: str, mode: str | None = None, device: str | None = None):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    name = resolve_model(key)
    device = device or pick_device()
    tok = AutoTokenizer.from_pretrained(name)
    tok.padding_side = "left"
    t0 = time.time()
    if name in QUANT4:
        if device != "cuda":
            raise SystemExit(f"{name} is run in 4-bit (bitsandbytes), which needs CUDA; got device={device}")
        from transformers import BitsAndBytesConfig
        q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                               bnb_4bit_compute_dtype=torch.bfloat16)
        model = AutoModelForCausalLM.from_pretrained(name, quantization_config=q, device_map={"": 0},
                                                     dtype=torch.bfloat16)
        model.eval()
    else:
        dtype = pick_dtype(device)
        model = AutoModelForCausalLM.from_pretrained(name, dtype=dtype)
        model.to(device).eval()
        got = next(model.parameters()).dtype
        assert got == dtype, f"wanted {dtype}, loaded {got}"
    print(f"[common] {name} on {device} as {dtype_label(name, device)} ({time.time() - t0:.0f}s)", file=sys.stderr)
    return tok, model, device


def chat_prompt(tok, user_text: str, prefill: str = "") -> str:
    s = tok.apply_chat_template([{"role": "user", "content": user_text}], tokenize=False, add_generation_prompt=True)
    return s + prefill


def encode(tok, strings, device):
    enc = tok(strings, return_tensors="pt", padding=True, add_special_tokens=False)
    return {k: v.to(device) for k, v in enc.items()}


def user_token_span(tok, prompt_str: str, user_text: str):
    """(first, last) token indices covering the user message inside the templated prompt."""
    enc = tok(prompt_str, return_offsets_mapping=True, add_special_tokens=False)
    start = prompt_str.index(user_text)
    end = start + len(user_text)
    idx = [i for i, (a, b) in enumerate(enc["offset_mapping"]) if b > start and a < end]
    return idx[0], idx[-1]


def n_layers(model) -> int:
    return len(model.model.layers)


def _out_tensor(output):
    return output[0] if isinstance(output, tuple) else output


class ResidualRecorder:
    """Records the residual stream during a forward pass: acts[0] = embeddings, acts[k] = output of block k."""

    def __init__(self, model):
        self.acts = {}
        self.handles = [model.model.embed_tokens.register_forward_hook(self._hook(0))]
        for i, layer in enumerate(model.model.layers):
            self.handles.append(layer.register_forward_hook(self._hook(i + 1)))

    def _hook(self, idx):
        def fn(module, inputs, output):
            self.acts[idx] = _out_tensor(output).detach()
        return fn

    def stack(self):
        """(n_layers + 1, batch, seq, d_model)"""
        return torch.stack([self.acts[i] for i in range(len(self.acts))], 0)

    def remove(self):
        for h in self.handles:
            h.remove()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.remove()


class Steer:
    """Adds alpha * u to the residual stream at the output of block `layer` (1-based, as in ResidualRecorder).

    During the prompt pass (seq > 1) only the last prompt token is changed; during generation every new token
    (seq == 1, with KV cache) is changed. alpha = 0 leaves the model untouched.
    """

    def __init__(self, model, layer: int, u: torch.Tensor, alpha: float):
        assert 1 <= layer <= n_layers(model), layer
        self.u = u.detach().flatten()
        self.alpha = float(alpha)
        self.handle = model.model.layers[layer - 1].register_forward_hook(self._hook)

    def _hook(self, module, inputs, output):
        o = _out_tensor(output)  # alpha = 0 still runs through here (adds a zero vector) as a sanity check
        delta = (self.alpha * self.u).to(device=o.device, dtype=o.dtype)
        o = o.clone()
        if o.shape[1] > 1:
            o[:, -1, :] += delta
        else:
            o[:, :, :] += delta
        return (o,) + tuple(output[1:]) if isinstance(output, tuple) else o

    def remove(self):
        self.handle.remove()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.remove()


REPETITION_PENALTY = 1.0


@torch.no_grad()
def generate(tok, model, device, prompt_strs, max_new_tokens=400, temperature=0.0, top_p=0.95, seed=None):
    """Batched generation. temperature <= 0 -> greedy. Returns (texts, n_new_tokens). Qwen's shipped
    repetition_penalty (1.1) is overridden to 1.0 (no penalty); its top_k=20 is disabled when sampling."""
    enc = encode(tok, prompt_strs, device)
    if seed is not None:
        torch.manual_seed(seed)
    kw = dict(max_new_tokens=max_new_tokens, pad_token_id=tok.pad_token_id, repetition_penalty=REPETITION_PENALTY)
    if temperature and temperature > 0:
        kw.update(do_sample=True, temperature=float(temperature), top_p=float(top_p), top_k=0)
    else:
        kw.update(do_sample=False, temperature=None, top_p=None, top_k=None)
    out = model.generate(**enc, **kw)
    gen = out[:, enc["input_ids"].shape[1]:]
    texts = [tok.decode(g, skip_special_tokens=True) for g in gen]
    n_tokens = [int((g != tok.pad_token_id).sum()) for g in gen]
    return texts, n_tokens


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def append_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_prompts(name: str):
    return read_jsonl(PROMPTS / f"{name}.jsonl")


def add_common_args(ap: argparse.ArgumentParser):
    ap.add_argument("--model", default="1.5b", help="1.5b | 3b | 7b (4-bit, CUDA only) | HF model id")
    ap.add_argument("--device", default=None, help="cuda | mps | cpu (default: auto)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N prompts (smoke test)")


def run_meta(model_name, device, mode=None, **extra):
    import transformers
    return dict(model=model_name, tag=model_tag(model_name), device=device, dtype=dtype_label(model_name, device),
                torch=torch.__version__, transformers=transformers.__version__,
                time=time.strftime("%Y-%m-%d %H:%M:%S"), **extra)

# Stage 2, answer direction: qwen7b

Activations from 2026-10-09 23:24:06 (cuda, 4bit-nf4/bf16). 341 derived neutral answers (of 342; 1 dropped because the formula starts inside the window), labels by final number {'A': 142, 'B': 142, 'C': 57}, 18 phrasings. Majority-class rate 42%; balanced accuracy chance 33%. Folds: GroupKFold(6) by phrasing, so every test phrasing is unseen in training.

## Where the first chord-length formula starts (answer tokens)

Formula found in 307/342 answers (the rest argue in words only). Percentiles of its first token: {'0': 53, '5': 92, '10': 108, '25': 126, '50': 162, '75': 213}. Variable named in words (distance / central angle / subtend / midpoint): {'0': 18, '5': 42, '10': 65, '25': 78, '50': 110, '75': 166}. Rule: largest w with the formula at or after w in >= 95% of answers gives 60; clipped to [15, 60] -> window = first 60 tokens.

## Answer probe per layer (window mean) and last-prompt-token probe

The last-prompt-token activation is the same for every sample of a phrasing, so its within-phrasing null equals the real run by construction and is shown only for completeness.

acc / balanced acc. Nulls: mean and 95th percentile of balanced accuracy over 20 shuffles; global = labels shuffled over all answers, within = shuffled inside each phrasing.

| layer | window acc | window bal | global null bal (mean / p95) | within null bal (mean / p95) | last-prompt acc | last-prompt bal | last: global null p95 | last: within null p95 |
|---|---|---|---|---|---|---|---|---|
| 0 | 58% | 47% | 33% / 39% | 42% / 44% | 34% | 27% | 37% | 27% |
| 2 | 58% | 48% | 33% / 38% | 43% / 46% | 50% | 41% | 44% | 41% |
| 4 | 60% | 48% | 32% / 36% | 44% / 46% | 54% | 47% | 46% | 47% |
| 6 | 59% | 49% | 34% / 38% | 44% / 47% | 57% | 46% | 39% | 46% |
| 8 | 59% | 49% | 34% / 40% | 45% / 47% | 57% | 50% | 40% | 50% |
| 10 | 62% | 53% | 33% / 37% | 44% / 46% | 42% | 34% | 39% | 37% |
| 12 | 63% | 53% | 32% / 37% | 43% / 45% | 49% | 39% | 38% | 39% |
| 14 | 63% | 53% | 33% / 37% | 44% / 46% | 51% | 42% | 40% | 43% |
| 16 | 63% | 53% | 32% / 39% | 45% / 48% | 52% | 43% | 40% | 38% |
| 18 | 59% | 48% | 33% / 38% | 43% / 46% | 51% | 42% | 45% | 46% |
| 20 | 60% | 50% | 35% / 38% | 44% / 47% | 52% | 43% | 40% | 43% |
| 22 | 59% | 48% | 33% / 37% | 44% / 47% | 52% | 43% | 41% | 43% |
| 24 | 60% | 49% | 32% / 36% | 43% / 47% | 52% | 43% | 40% | 44% |
| 26 | 60% | 50% | 33% / 38% | 43% / 46% | 52% | 43% | 40% | 44% |
| 28 | 59% | 48% | 33% / 38% | 43% / 46% | 51% | 44% | 39% | 43% |

Words-only baselines (same folds): prompt text: acc 50%, bal 40%; window text: acc 60%, bal 48%; majority class: acc 42%, bal 33%. Layer 0 of the window is the mean token embedding.

## Sensitivity: mean over the first N answer tokens (balanced accuracy)

Answers with the formula inside the span: first 10: 0, first 20: 0, first 30: 0, first 60: 0. Answers naming the variable in words inside the span: first 10: 0, first 20: 9, first 30: 14, first 60: 29 (of 341). A higher number for a longer span can come from the answer stating its approach, not from earlier commitment.

| layer | first 10 | first 20 | first 30 | first 60 |
|---|---|---|---|---|
| 0 | 29% | 39% | 40% | 47% |
| 2 | 42% | 43% | 43% | 48% |
| 4 | 43% | 48% | 48% | 48% |
| 6 | 48% | 51% | 46% | 49% |
| 8 | 49% | 49% | 45% | 49% |
| 10 | 50% | 44% | 39% | 53% |
| 12 | 51% | 44% | 45% | 53% |
| 14 | 49% | 41% | 46% | 53% |
| 16 | 51% | 47% | 48% | 53% |
| 18 | 51% | 45% | 47% | 48% |
| 20 | 53% | 46% | 47% | 50% |
| 22 | 47% | 46% | 45% | 48% |
| 24 | 42% | 46% | 43% | 49% |
| 26 | 40% | 45% | 40% | 50% |
| 28 | 41% | 43% | 39% | 48% |

## Reading direction vs answer direction

cos: class-by-class cosine (A / B / C) between the reading probe's and the answer probe's raw-space weights, and between their difference-of-means directions; null = 95th percentile of |cos| with answer probes on shuffled labels; – where the reading activations do not vary (layer 0 at the last prompt token is the same token embedding for every prompt). Cross-prediction as balanced accuracy, raw / centered (each set shifted onto the training set's mean).

| layer | cos weights A/B/C | null p95 | cos diff-means A/B/C | null p95 | read -> answer window | read -> answer last prompt | answer -> labeled (all) | answer -> labeled (strict) |
|---|---|---|---|---|---|---|---|---|
| 0 | – / – / – | – | – / – / – | – | 33% / 33% | 33% / 33% | 33% / 33% | 33% / 33% |
| 2 | -0.03 / -0.01 / -0.02 | 0.04 | +0.02 / +0.03 / +0.02 | 0.08 | 33% / 40% | 33% / 26% | 33% / 33% | 42% / 27% |
| 4 | -0.03 / +0.02 / -0.02 | 0.04 | -0.04 / +0.00 / +0.01 | 0.05 | 29% / 29% | 33% / 39% | 33% / 34% | 33% / 33% |
| 6 | -0.01 / -0.00 / -0.02 | 0.04 | -0.04 / -0.02 / -0.02 | 0.06 | 30% / 22% | 33% / 23% | 33% / 30% | 33% / 27% |
| 8 | -0.02 / -0.01 / +0.00 | 0.03 | -0.02 / -0.01 / +0.02 | 0.06 | 33% / 39% | 33% / 21% | 33% / 32% | 33% / 31% |
| 10 | -0.00 / +0.01 / -0.01 | 0.03 | -0.03 / -0.04 / -0.04 | 0.05 | 33% / 30% | 33% / 25% | 35% / 32% | 33% / 36% |
| 12 | +0.01 / +0.00 / +0.03 | 0.04 | -0.01 / -0.02 / -0.08 | 0.08 | 33% / 29% | 33% / 22% | 33% / 33% | 33% / 31% |
| 14 | -0.01 / +0.01 / -0.01 | 0.04 | -0.02 / -0.04 / -0.01 | 0.05 | 33% / 32% | 33% / 30% | 33% / 31% | 33% / 31% |
| 16 | +0.06 / +0.01 / +0.01 | 0.04 | +0.01 / -0.01 / +0.00 | 0.09 | 33% / 38% | 33% / 26% | 33% / 36% | 33% / 27% |
| 18 | +0.02 / +0.01 / +0.03 | 0.04 | +0.03 / +0.02 / +0.02 | 0.07 | 34% / 38% | 33% / 31% | 33% / 36% | 33% / 31% |
| 20 | +0.04 / -0.01 / +0.01 | 0.04 | +0.04 / +0.03 / +0.03 | 0.07 | 33% / 36% | 33% / 23% | 33% / 36% | 33% / 42% |
| 22 | +0.05 / +0.01 / +0.02 | 0.04 | +0.02 / +0.01 / -0.03 | 0.13 | 33% / 33% | 33% / 29% | 33% / 32% | 33% / 38% |
| 24 | +0.03 / +0.00 / +0.02 | 0.04 | +0.03 / +0.02 / -0.03 | 0.14 | 33% / 35% | 33% / 26% | 33% / 33% | 33% / 29% |
| 26 | +0.03 / +0.03 / +0.04 | 0.04 | -0.00 / +0.01 / -0.02 | 0.09 | 33% / 47% | 33% / 33% | 33% / 33% | 33% / 29% |
| 28 | -0.01 / +0.01 / +0.02 | 0.06 | +0.17 / +0.06 / +0.03 | 0.22 | 33% / 44% | 33% / 31% | 33% / 27% | 33% / 22% |

Full 3x3 cosine matrices are in the json (`comparison[layer].cos_w`, rows = reading classes, columns = answer classes).

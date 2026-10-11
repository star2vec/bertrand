# Stage 2, 7B: binary branch-word probe (1/3 vs not), supported vs unsupported answers (qwen7b)

Supported: the written steps lead to the boxed number; unsupported: they do not (hand judgment). Anchor t = first token of the first word naming the variable (perpendicular distance, distance (d) from the center, central angle, subtend, midpoint). Residual stream at t − k. Label: final number is 1/3 or not; balanced accuracy, chance 50%. Folds: GroupKFold(6) by phrasing.

| set | answers judged | no variable word (dropped) | n | 1/3 / not | phrasings | median anchor token |
|---|---|---|---|---|---|---|
| supported | 342 | 0 | 342 | 142 / 200 | 18 | 110 |
| unsupported | 58 | 2 | 56 | 38 / 18 | 16 | 142 |

## Layer 22 (fixed in advance): probe, nulls (50 shuffles), words, size-matched supported

| k | supported n | supported bal | within null p95 | global null p95 | words (prompt+text) | unsupported n | unsupported bal | within null p95 | global null p95 | words (prompt+text) | supported, 56-answer subsets: mean (p5–p95) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 328 | 63% | 61% | 54% | 57% | 56 | 41% | 49% | 54% | 49% | 50% (45%–56%) |
| 20 | 333 | 68% | 62% | 56% | 63% | 56 | 38% | 54% | 56% | 47% | 53% (42%–63%) |
| 10 | 342 | 74% | 64% | 56% | 69% | 56 | 53% | 54% | 56% | 45% | 60% (46%–73%) |
| 5 | 342 | 79% | 65% | 57% | 66% | 56 | 48% | 53% | 56% | 47% | 63% (46%–75%) |
| 2 | 342 | 87% | 72% | 59% | 73% | 56 | 45% | 54% | 56% | 47% | 74% (61%–86%) |
| 1 | 342 | 92% | 67% | 56% | 76% | 56 | 38% | 53% | 56% | 47% | 87% (78%–93%) |
| 0 | 342 | 98% | 76% | 60% | 94% | 56 | 56% | 57% | 58% | 47% | 97% (90%–100%) |

Words baseline on the answer text alone: supported: k=30 56%, k=20 63%, k=10 70%, k=5 71%, k=2 75%, k=1 79%, k=0 94%; unsupported: k=30 50%, k=20 47%, k=10 47%, k=5 47%, k=2 47%, k=1 47%, k=0 47%

Small n: the unsupported set has 56 answers over 16 phrasings, so each test fold holds about 9; many phrasings have only a few unsupported answers, and the within-phrasing shuffle only moves labels in phrasings that have both classes. The size-matched supported subsets show how much a 56-answer set alone lowers and spreads the supported curve.

## supported: balanced accuracy by offset (rows) and layer (columns), no nulls

| k | 0 | 2 | 4 | 6 | 8 | 10 | 12 | 14 | 16 | 18 | 20 | 22 | 24 | 26 | 28 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 57% | 60% | 61% | 61% | 61% | 60% | 58% | 61% | 61% | 60% | 63% | 63% | 60% | 61% | 59% |
| 20 | 56% | 60% | 62% | 64% | 64% | 66% | 68% | 68% | 67% | 65% | 68% | 68% | 65% | 62% | 61% |
| 10 | 64% | 68% | 68% | 68% | 71% | 71% | 72% | 72% | 73% | 73% | 74% | 74% | 71% | 70% | 73% |
| 5 | 74% | 75% | 74% | 74% | 74% | 76% | 76% | 75% | 73% | 76% | 78% | 79% | 78% | 79% | 77% |
| 2 | 82% | 83% | 83% | 81% | 83% | 83% | 83% | 84% | 83% | 84% | 86% | 87% | 87% | 89% | 87% |
| 1 | 81% | 84% | 86% | 85% | 87% | 89% | 88% | 89% | 89% | 90% | 90% | 92% | 92% | 92% | 92% |
| 0 | 98% | 98% | 98% | 98% | 98% | 98% | 98% | 98% | 98% | 98% | 98% | 98% | 98% | 98% | 98% |

## unsupported: balanced accuracy by offset (rows) and layer (columns), no nulls

| k | 0 | 2 | 4 | 6 | 8 | 10 | 12 | 14 | 16 | 18 | 20 | 22 | 24 | 26 | 28 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 41% | 46% | 47% | 46% | 46% | 41% | 43% | 46% | 43% | 45% | 42% | 41% | 42% | 43% | 42% |
| 20 | 45% | 39% | 41% | 37% | 43% | 42% | 43% | 37% | 38% | 41% | 39% | 38% | 42% | 45% | 44% |
| 10 | 38% | 56% | 54% | 54% | 52% | 53% | 45% | 49% | 52% | 46% | 52% | 53% | 50% | 59% | 60% |
| 5 | 46% | 48% | 52% | 49% | 46% | 39% | 43% | 43% | 41% | 41% | 42% | 48% | 42% | 41% | 45% |
| 2 | 42% | 43% | 42% | 45% | 42% | 42% | 42% | 45% | 45% | 46% | 43% | 45% | 42% | 42% | 40% |
| 1 | 39% | 40% | 38% | 36% | 41% | 36% | 39% | 42% | 42% | 39% | 36% | 38% | 49% | 45% | 44% |
| 0 | 56% | 53% | 53% | 52% | 56% | 55% | 55% | 56% | 55% | 55% | 53% | 56% | 53% | 57% | 56% |

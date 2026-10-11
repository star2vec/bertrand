# Stage 2, last 7B check: before the variable is named in words (qwen7b)

342 derived neutral answers; t = first token of the first variable word (perpendicular distance, distance (d) from the center, central angle, subtend, midpoint). Residual at single positions t − k. Label = final number; balanced accuracy, chance 33%; plain-accuracy majority 42%. Folds: GroupKFold(6) by phrasing. Nulls: global = labels shuffled over all answers; within = shuffled inside each phrasing.

## Balanced accuracy by offset (rows) and layer (columns)

| k (tokens before the word) | n | 0 | 2 | 4 | 6 | 8 | 10 | 12 | 14 | 16 | 18 | 20 | 22 | 24 | 26 | 28 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 328 | 34% | 40% | 41% | 41% | 41% | 38% | 40% | 42% | 42% | 41% | 38% | 40% | 39% | 41% | 41% |
| 20 | 333 | 39% | 40% | 42% | 46% | 49% | 47% | 49% | 50% | 47% | 44% | 45% | 48% | 45% | 42% | 41% |
| 10 | 342 | 46% | 49% | 49% | 53% | 52% | 55% | 52% | 53% | 55% | 57% | 55% | 53% | 53% | 50% | 50% |
| 5 | 342 | 55% | 54% | 53% | 53% | 54% | 55% | 56% | 54% | 57% | 57% | 57% | 57% | 59% | 59% | 58% |
| 2 | 342 | 68% | 61% | 63% | 62% | 60% | 62% | 64% | 66% | 64% | 65% | 67% | 70% | 67% | 68% | 68% |
| 1 | 342 | 54% | 64% | 70% | 67% | 68% | 69% | 69% | 69% | 69% | 68% | 69% | 75% | 75% | 75% | 74% |
| 0 | 342 | 68% | 77% | 77% | 77% | 75% | 73% | 73% | 75% | 75% | 76% | 79% | 79% | 80% | 81% | 79% |

## Curve at the best layer (22; nulls with 50 shuffles)

Best layer = highest balanced accuracy averaged over offsets (mean 60%). 'without formula-first' drops the 23 answers whose chord-length formula comes before the word; 'stricter anchor' re-anchors the answers first naming 'distance (d) from the center' on a later stricter word (27 re-anchored, 26 dropped). Those two rows have no nulls; the words columns use the same folds.

| k | n | acc | bal | global null bal (mean / p95) | within null bal (mean / p95) | words: answer text up to t−k | words: prompt + that text | without 23 formula-first | stricter anchor |
|---|---|---|---|---|---|---|---|---|---|
| 30 | 328 | 46% | 40% | 33% / 37% | 38% / 41% | 42% | 40% | 40% | 45% |
| 20 | 333 | 54% | 48% | 34% / 37% | 37% / 41% | 43% | 49% | 46% | 47% |
| 10 | 342 | 60% | 53% | 33% / 37% | 41% / 46% | 49% | 47% | 56% | 59% |
| 5 | 342 | 65% | 57% | 33% / 37% | 43% / 47% | 48% | 46% | 58% | 58% |
| 2 | 342 | 75% | 70% | 34% / 40% | 44% / 49% | 58% | 58% | 68% | 70% |
| 1 | 342 | 79% | 75% | 32% / 39% | 44% / 48% | 58% | 59% | 73% | 73% |
| 0 | 342 | 85% | 79% | 33% / 39% | 47% / 52% | 68% | 72% | 80% | 80% |

## Curve at layer 16 (nulls with 20 shuffles)

| k | n | acc | bal | global null bal (mean / p95) | within null bal (mean / p95) | words: answer text up to t−k | words: prompt + that text | without 23 formula-first | stricter anchor |
|---|---|---|---|---|---|---|---|---|---|
| 30 | 328 | 49% | 42% | 34% / 38% | 39% / 43% | 42% | 40% | 38% | 43% |
| 20 | 333 | 54% | 47% | 34% / 37% | 38% / 42% | 43% | 49% | 46% | 49% |
| 10 | 342 | 61% | 55% | 33% / 39% | 42% / 45% | 49% | 47% | 54% | 55% |
| 5 | 342 | 64% | 57% | 34% / 41% | 43% / 47% | 48% | 46% | 52% | 53% |
| 2 | 342 | 70% | 64% | 33% / 40% | 43% / 47% | 58% | 58% | 65% | 62% |
| 1 | 342 | 75% | 69% | 34% / 40% | 45% / 50% | 58% | 59% | 68% | 70% |
| 0 | 342 | 83% | 75% | 32% / 42% | 49% / 58% | 68% | 72% | 76% | 78% |

## First-10-token mean (the null missing from the last run)

Same 341 answers and folds as `summary_answer_qwen7b.md`; 20 shuffles.

| layer | acc | bal | global null bal (mean / p95) | within null bal (mean / p95) |
|---|---|---|---|---|
| 0 | 34% | 29% | 32% / 34% | 30% / 33% |
| 2 | 51% | 42% | 34% / 40% | 43% / 49% |
| 4 | 51% | 43% | 34% / 40% | 45% / 51% |
| 6 | 51% | 48% | 34% / 42% | 44% / 52% |
| 8 | 53% | 49% | 34% / 39% | 45% / 52% |
| 10 | 54% | 50% | 32% / 35% | 43% / 50% |
| 12 | 56% | 51% | 34% / 39% | 46% / 51% |
| 14 | 54% | 49% | 33% / 39% | 44% / 52% |
| 16 | 55% | 51% | 33% / 37% | 45% / 51% |
| 18 | 55% | 51% | 33% / 36% | 46% / 49% |
| 20 | 59% | 53% | 33% / 37% | 47% / 50% |
| 22 | 53% | 47% | 33% / 37% | 44% / 49% |
| 24 | 50% | 42% | 33% / 38% | 42% / 47% |
| 26 | 48% | 40% | 33% / 39% | 44% / 49% |
| 28 | 48% | 41% | 33% / 38% | 42% / 50% |

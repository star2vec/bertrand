# Stage 2 probe: qwen7b

Position `last`, activations from 2026-10-09 23:17:36 (cuda, 4bit-nf4/bf16). Splits: {'train': 195, 'strict': 45, 'desc_only': 117, 'word_only': 75}. Accuracies are 3-class (chance 33%); the strict set has 45 examples, so one example is 2.2 points.

## Chosen layer 20 (by inner CV on train; C=0.1)

|  | cv (train) | train | strict | desc_only | word_only |
|---|---|---|---|---|---|
| probe (activations) | 99% | 100% | 96% | 87% | 100% |
| shuffled labels, mean of 20 |  | 33% | 33% | 34% | 34% |
| shuffled labels, 95th pct |  | 39% | 45% | 43% | 42% |
| text TF-IDF (C=0.1) | 100% | 100% | 76% | 80% | 100% |
| nearest class mean, raw |  | 90% | 87% | 78% | 92% |
| nearest class mean, standardized |  | 92% | 89% | 82% | 92% |

## Layer curve (position `last`)

| layer | C | cv | train | strict | desc_only | word_only |
|---|---|---|---|---|---|---|
| 0 | 0.001 | 33% | 33% | 33% | 33% | 33% |
| 2 | 0.01 | 96% | 100% | 47% | 51% | 100% |
| 4 | 0.1 | 96% | 100% | 56% | 57% | 100% |
| 6 | 1 | 98% | 100% | 51% | 56% | 100% |
| 8 | 1 | 97% | 100% | 64% | 68% | 97% |
| 10 | 0.1 | 97% | 100% | 67% | 58% | 95% |
| 12 | 0.1 | 98% | 100% | 49% | 63% | 92% |
| 14 | 1 | 97% | 100% | 56% | 59% | 87% |
| 16 | 1 | 98% | 100% | 56% | 67% | 95% |
| 18 | 1 | 96% | 100% | 69% | 68% | 95% |
| 20 | 0.1 | 99% | 100% | 96% | 87% | 100% |
| 22 | 0.1 | 98% | 100% | 100% | 87% | 100% |
| 24 | 1 | 96% | 100% | 98% | 83% | 100% |
| 26 | 1 | 96% | 100% | 98% | 85% | 100% |
| 28 | 1 | 96% | 100% | 96% | 84% | 100% |

Other positions, layer with best inner CV: `last` L20 cv 99%, strict 96%; `user_last` L14 cv 98%, strict 98%; `user_mean` L0 cv 100%, strict 80%

## Directions saved for stage 3

| approach | separation along classifier dir | along diff-of-means dir | cos(clf, dm) |
|---|---|---|---|
| A endpoints 1/3 | 4.50 | 5.96 | 0.76 |
| B radial 1/2 | 2.67 | 4.28 | 0.62 |
| C midpoint 1/4 | 2.27 | 3.54 | 0.64 |

Mean residual norm at layer 20 on train: 98.2. Separation = mean projection of the class minus mean projection of the other classes (raw units); stage 3 uses alpha x separation.

## Neutral prompts: probe vs stage-1 sampling

| id |  | probe P(A) P(B) P(C) | probe argmax | sampled freq A B C | n | sampled argmax |
|---|---|---|---|---|---|---|
| 0 |  | 1.00 0.00 0.00 | A | 0.37 0.13 0.00 | 30 | A |
| 1 |  | 0.99 0.00 0.01 | A | 0.57 0.10 0.13 | 30 | A |
| 2 | H | 1.00 0.00 0.00 | A | 0.20 0.40 0.23 | 30 | B |
| 3 |  | 0.99 0.00 0.01 | A | 0.40 0.17 0.17 | 30 | A |
| 4 | H | 1.00 0.00 0.00 | A | 0.20 0.23 0.30 | 30 | C |
| 5 |  | 1.00 0.00 0.00 | A | 0.30 0.30 0.10 | 30 | A |
| 6 |  | 1.00 0.00 0.00 | A | 0.60 0.07 0.00 | 30 | A |
| 7 |  | 1.00 0.00 0.00 | A | 0.40 0.47 0.03 | 30 | B |
| 8 |  | 1.00 0.00 0.00 | A | 0.27 0.40 0.07 | 30 | B |
| 9 |  | 1.00 0.00 0.00 | A | 0.30 0.10 0.20 | 30 | A |
| 10 | H | 1.00 0.00 0.00 | A | 0.23 0.53 0.00 | 30 | B |
| 11 |  | 1.00 0.00 0.00 | A | 0.57 0.03 0.17 | 30 | A |
| 12 |  | 1.00 0.00 0.00 | A | 0.60 0.03 0.10 | 30 | A |
| 13 |  | 1.00 0.00 0.00 | A | 0.23 0.57 0.07 | 30 | B |
| 14 | H | 1.00 0.00 0.00 | A | 0.27 0.43 0.07 | 30 | B |
| 15 | H | 1.00 0.00 0.00 | A | 0.20 0.27 0.00 | 30 | B |
| 16 |  | 1.00 0.00 0.00 | A | 0.20 0.40 0.27 | 30 | B |
| 17 |  | 1.00 0.00 0.00 | A | 0.17 0.67 0.07 | 30 | B |

Argmax agreement: 8/18. Spearman per approach (None = sampled frequency constant): {'A': -0.03246529590014007, 'B': -0.25116193097754985, 'C': 0.15110979828193302}.

Caveat: the probe was trained where the approach is stated in the prompt; neutral prompts state none, so this is a distribution shift.

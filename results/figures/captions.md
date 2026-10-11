# Figure captions

**header.** Three ways to draw a chord at random in the same circle, with the inscribed equilateral triangle: (a) two random points on the circle, (b) a random point on a random radius, with the chord at right angles to it, (c) a random midpoint in the disk. Shaded: where the chord comes out longer than the triangle's side. Each way gives a different probability.

**phrasings.** Prompts as the model sees them. Top: the canonical Bertrand problem statement and two of the 17 rephrasings, one stating the comparison length as a number and one giving no radius. Bottom: the canonical statement plus a clause that states the approach for 1/4 (highlighted).

**which.** Which number each model gives on each phrasing of the neutral problem (30 samples per phrasing, temperature 0.7, label = final number). Phrasings are grouped by how the comparison length is stated (triangle side, r√3, or a number) and by radius ("no r": radius not given).

**how.** How the neutral answers ending in 1/3, 1/2 or 1/4 got there, by hand judgment. Solid: explained (the written steps produce the number), colored by the variable treated as evenly spread; every explained 1/3 uses the angle, every explained 1/2 the distance, every explained 1/4 the midpoint, so the colors match the numbers. Hatched: unexplained (the working gives something else, or the number is just stated). 3B: 361 answers; 7B: 400.

**famous_number.** Left: share of hand-judged answers whose steps actually produce their number, by how the comparison length is stated. Right: an unexplained 1/3 from the 7B (real answer, lines removed where marked …): the working gives 2/3, the boxed answer is the famous 1/3.

**where_we_look.** Where the probes look, on one real 7B answer (phrasing 2, sample 7). Dashed: the end of the prompt; the last prompt token is the reading probe's position. Grey: the first 60 answer tokens, used by the earlier probe. Highlighted: the first word that names the variable (the branch word, here at token 68); dots mark positions 30, 10, 5 and 1 tokens before it. This answer was chosen for fit; the branch word usually comes around token 110.

**when.** When the final number becomes readable in the 7B's answer. x: position, in tokens before the first word that names the variable (positions equally spaced); y: balanced accuracy of a linear probe for the final number (1/3, 1/2, 1/4), test phrasings unseen in training. Black: probe on the residual stream at layer 22. Red: a classifier on the words alone. Grey: what shuffling labels within each phrasing reaches (95th percentile of 50 shuffles); a probe above this line reads more than the phrasing.

**when_supported_vs_unsupported.** Whether the 7B's final number is 1/3 can be read from the residual stream (layer 22) at positions before the first word that names the variable, for answers whose steps produce the boxed number (explained, n = 342) and answers whose steps do not (unexplained, n = 56). Light blue: the explained probe on random subsets the size and class mix of the unexplained set (mean of 20, band 5th–95th percentile). Dashed: 95th percentile of labels shuffled within phrasing; a probe above its line reads more than the phrasing. The unexplained curve rests on 56 answers. Median position of the branch word: token 110 (explained), 142 (unexplained).

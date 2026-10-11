"""Score a model answer to a Bertrand prompt.

Primary label (approach_number) = the final number: 1/3 -> A (endpoints), 1/2 -> B (radial), 1/4 -> C
  (midpoint), anything else -> "other", no number -> "none", several canonical numbers with no clear final ->
  "multiple".
Check label (approach_text) = the method stated in the text, read with keyword markers per approach:
  exactly one approach's markers fire -> that approach; two or more -> "multiple"; none -> "none".
`agree` says whether the two labels match when both are in A/B/C. Run this file to self-test.

Markers are matched sentence by sentence; a B "distance uniform" sentence that also talks about the midpoint or
the disk's area is not counted for B (that is C's derivation). Descriptions that mix vocabularies on purpose
(b4 "midpoint along a radius", c3 "perpendicular to the radius through a point of the disk") will often read as
"multiple" when the model restates them.
"""
import re

CANON = {"A": 1 / 3, "B": 1 / 2, "C": 1 / 4}
TOL = 0.011
WORDS = {"one third": 1 / 3, "one-third": 1 / 3, "a third": 1 / 3,
         "one half": 1 / 2, "one-half": 1 / 2, "a half": 1 / 2,
         "one quarter": 1 / 4, "one-quarter": 1 / 4, "a quarter": 1 / 4, "one fourth": 1 / 4, "one-fourth": 1 / 4}

NUM_RE = re.compile(
    r"\\[dt]?frac\{(?P<fn>\d+)\}\{(?P<fd>\d+)\}"
    r"|(?P<n>\d+)\s*/\s*(?P<d>\d+)"
    r"|(?P<pct>\d+(?:\.\d+)?)\s*%"
    r"|(?P<dec>\d*\.\d+)"
    r"|(?P<word>" + "|".join(re.escape(w) for w in WORDS) + r")"
    r"|(?<![\d.])(?P<int>[01])(?!\d|\.\d|/)",  # bare 0 or 1 (a probability can be exactly these)
    re.IGNORECASE)
BOXED_RE = re.compile(r"\\boxed\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}")
CUE_WORD = re.compile(r"probab|chance|answer|likelihood|odds|\bP\s*[=(]", re.I)
CONNECTOR = re.compile(r"(?:\bis|=|equals|\bbe|:|≈|approximately|about|roughly|\bof|probability|chance|answer|therefore|thus|so|get|gives|obtain)\s*$", re.I)
WRAP = re.compile(r"[\s$\\()\[\]{},]+$")
SENTENCE_END = re.compile(r"[.!?](?:\s|$)|\n")
PARADOX_RE = re.compile(r"bertrand|depends on (?:how|the|which|what)|ambiguous|ill[- ]posed|not well[- ]defined|different (?:answers|methods|interpretations)|paradox", re.I)

# --- method markers -------------------------------------------------------------------------------------------
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
DISK = r"(?:disk|disc|interior|area|inside (?:of )?the circle|within the circle|inside the circle)"
ADJ = r"(?:(?:fixed|given|chosen|random|particular|arbitrary|randomly (?:chosen|selected|picked|oriented|drawn)|uniformly random) )?"
METHOD_RE = {
    "A": [
        r"two (?:\w+ ){0,3}points?\b(?! (?:in|inside|within|from) the (?:disk|disc|interior))",
        r"(?:two|both|each|the other|the second|one) (?:random |uniform(?:ly)? )?end-?points?",
        r"two (?:random |uniform(?:ly)? (?:random )?)?(?:angles|directions|spots|locations|positions)",
        r"fix(?:ing|ed|es)? (?:one|an|the first) (?:end)?point",
        r"\barcs?\b",
        r"angle[^.;]{0,60}uniform|uniform[^.;]{0,60}angle",
    ],
    "B": [
        r"random (?:radius|radii|diameter)|(?:radius|diameter) (?:\w+ ){0,2}at random",
        r"(?:along|on) (?:a|the|this|that|one|any|some|its|an) " + ADJ + r"(?:radius|diameter)\b",
        r"perpendicular to (?:the|a|this|that|one|its|some|an) " + ADJ + r"(?:radius|diameter)",
        r"distance[^.;]{0,60}uniform(?:ly)?[^.;]{0,40}(?:\[\s*0|\(\s*0|between 0|from 0|0 (?:and|to) )",
        r"uniform(?:ly)?[^.;]{0,40}distance (?:from|to|of) the cent(?:er|re)",
        r"distance (?:from|to|of) the cent(?:er|re)[^.;]{0,40}uniform(?:ly)?",
        r"\b[dx]\s*(?:~|\\sim|∈|\\in)\s*(?:U|\\mathcal\{U\}|\\text\{U(?:niform)?\}|Uniform)?\s*[\[(]\s*0\s*,\s*(?:r|R|1)\b",
    ],
    "C": [
        r"mid-?point[^.;]{0,80}(?:uniform|random)[^.;]{0,60}" + DISK,
        r"(?:uniform|random)[^.;]{0,60}" + DISK + r"[^.;]{0,80}mid-?point",
        r"(?:random |arbitrary )?point (?:\w+ )?(?:chosen |picked |selected |taken |thrown )?(?:uniformly )?(?:at random )?(?:in|inside|within|from) the (?:disk|disc|interior)",
        r"uniform(?:ly)?(?: distributed| at random| random)? (?:in|over|inside|within|throughout|across|on) the (?:disk|disc|area|interior|whole circle|entire circle|whole disk)",
        r"uniform(?:ly)? (?:in|over|with respect to|by) area",
        r"area of the (?:smaller|inner|concentric|small) (?:circle|disk|disc)",
        r"(?:smaller|inner|concentric) (?:circle|disk|disc) of radius",
        r"ratio of (?:the )?(?:two )?areas",
        r"bisect",
        r"\(\s*[rR]\s*/\s*2\s*\)\s*\^\s*2|\\left\(\s*\\[dt]?frac\{[rR]\}\{2\}\s*\\right\)\s*\^\s*2|\\[dt]?frac\{[rR]\^2\}\{4\}|\\[dt]?frac\{\\pi [rR]\^2\}\{4\}|\\pi\s*\(\s*[rR]\s*/\s*2\s*\)\s*\^\s*2",
    ],
}
METHOD_RE = {a: [re.compile(p, re.I) for p in ps] for a, ps in METHOD_RE.items()}
# Sentence conditions for single markers. A#0 ("two points") must sit in a sentence about choosing them, not in a
# definition ("a chord is defined by two points on the circle"). B's "distance uniform" markers (#3-#6) must not be
# about the midpoint / disk area, which is C's derivation.
REQUIRE = {("A", 0): re.compile(r"random|uniform|cho(?:o|)s|pick|select|independ|draw|place|fix|generat|take|taking", re.I)}
EXCLUDE = {("B", i): re.compile(r"mid-?point|disk|disc|area", re.I) for i in (3, 4, 5, 6)}


def _val(m):
    if m.group("fn"):
        return int(m.group("fn")) / int(m.group("fd")) if int(m.group("fd")) else None
    if m.group("n"):
        return int(m.group("n")) / int(m.group("d")) if int(m.group("d")) else None
    if m.group("pct"):
        return float(m.group("pct")) / 100
    if m.group("dec"):
        return float(m.group("dec"))
    if m.group("int"):
        return float(m.group("int"))
    return WORDS[m.group("word").lower()]


def numbers(text):
    out = []
    for m in NUM_RE.finditer(text):
        v = _val(m)
        if v is not None:
            out.append((v, m.start(), m.end()))
    return out


def to_approach(v):
    if v is None:
        return "none"
    for a, c in CANON.items():
        if abs(v - c) <= TOL:
            return a
    return "other"


def _cued(text, start):
    pre = text[max(0, start - 120):start]
    return bool(CUE_WORD.search(pre)) and bool(CONNECTOR.search(WRAP.sub("", pre)[-40:]))


def _canonical_set(nums):
    return {to_approach(v) for v, _, _ in nums} & set(CANON)


def final_number(text):
    """-> (value or None, how) with how in boxed / boxed_other / cued / fallback / none / multiple.
    A boxed answer is always taken as the final answer, even when it is not a parseable number."""
    boxed = BOXED_RE.findall(text)
    if boxed:
        nums = numbers(boxed[-1])
        if len(_canonical_set(nums)) >= 2:
            return None, "multiple"
        if nums:
            return nums[-1][0], "boxed"
        return None, "boxed_other"
    nums = numbers(text)
    cued = [n for n in nums if _cued(text, n[1])]
    if cued:
        v, _, end = cued[-1]
        m = SENTENCE_END.search(text, end)
        rest = text[end:m.start() if m else len(text)]
        others = _canonical_set(numbers(rest)) - {to_approach(v)}
        return (None, "multiple") if others else (v, "cued")
    if nums:
        canon = _canonical_set(nums)
        if len(canon) >= 2:
            return None, "multiple"
        return nums[-1][0], "fallback"
    return None, "none"


def method_hits(text):
    """{approach: number of marker hits}, counted sentence by sentence."""
    hits = {a: 0 for a in CANON}
    for sent in SENT_SPLIT.split(text):
        if not sent.strip():
            continue
        for a, rxs in METHOD_RE.items():
            for i, rx in enumerate(rxs):
                if (a, i) in REQUIRE and not REQUIRE[a, i].search(sent):
                    continue
                if (a, i) in EXCLUDE and EXCLUDE[a, i].search(sent):
                    continue
                hits[a] += len(rx.findall(sent))
    return hits


def method_from_text(text):
    """-> (label, mentioned): label in A/B/C/multiple/none; mentioned = sorted approaches with >= 1 hit."""
    hits = method_hits(text)
    mentioned = sorted(a for a, n in hits.items() if n)
    if not mentioned:
        return "none", mentioned, hits
    if len(mentioned) == 1:
        return mentioned[0], mentioned, hits
    return "multiple", mentioned, hits


def score(text):
    v, how = final_number(text)
    by_number = {"multiple": "multiple", "boxed_other": "other"}.get(how) or to_approach(v)
    by_text, mentioned, hits = method_from_text(text)
    return {
        "approach_text": by_text,
        "approach_number": by_number,
        "agree": by_number == by_text if by_number in CANON and by_text in CANON else None,
        "methods_mentioned": mentioned,
        "method_hits": hits,
        "final_value": None if v is None else round(v, 4),
        "final_how": how,
        "mentions_paradox": bool(PARADOX_RE.search(text)),
        "n_canonical_mentioned": len(_canonical_set(numbers(text))),
    }


# (text, wanted number label[-how], wanted text label or None to skip)
TESTS = [
    ("The probability is 1/3.", "A", "none"),
    ("Therefore the answer is \\boxed{\\frac{1}{2}}.", "B", "none"),
    ("Therefore P = 0.25.", "C", "none"),
    ("It could be 1/3 or 1/2 under other conventions. With our method the answer is 1/4.", "C", "none"),
    ("So the probability is 33.3%.", "A", None),
    ("The probability is approximately 0.333.", "A", None),
    ("The chance is one third.", "A", None),
    ("The probability is 2/3.", "other", None),
    ("This is Bertrand's paradox; the answer depends on the method: 1/2, 1/3 or 1/4.", "multiple", "none"),
    ("We cannot say without more information.", "none", "none"),
    ("\\[ P = \\dfrac{1}{4} \\]", "C", None),
    ("so the answer is 1/3 for a circle of radius 2.", "A", None),
    ("The probability that the chord is longer is 50%.", "B", None),
    ("P(L > s) = 1 - 1/2 = 1/2", "B", None),
    ("Thus the probability is $\\frac{1}{3}$.", "A", None),
    ("The desired probability is \\( \\frac{1}{4} \\).", "C", None),
    ("The side is 2√3 ≈ 3.46. Hence the probability equals 1/3.", "A", None),
    ("The chord is longer when the midpoint is within r/2 of the center, so the probability is (1/2)^2 = 1/4.", "C", None),
    ("Pick two random points on the circle. The arc condition gives probability 1/3.", "A", "A"),
    ("we have 0.5 as the answer", "fallback-B", None),
    ("Using L = 2R sin(θ/2) with sin(30°) = \\frac{1}{2}, no chord is longer, so P = 0. Thus the answer is \\(\\boxed{0}\\).", "other", None),
    ("The probability is 1.", "other", None),
    ("So the answer is \\boxed{\\frac{\\sqrt{3}}{2}}.", "other", None),
    ("Hence P = \\boxed{\\dfrac{1}{3}}.", "A", None),
    ("The distance is uniform on [0, r]. The chord is longer when d < r/2, so the probability is 1/2.", "B", "B"),
    # text label
    ("Choose two points independently and uniformly on the circle. Fix one endpoint at the top; the other endpoint "
     "lands on the far arc with probability 1/3.", "A", "A"),
    ("Let the central angle θ be uniformly distributed on [0, π]. The chord exceeds r√3 when θ > 2π/3, so P = 1/3.", "A", "A"),
    ("Pick a random radius and a point uniformly along it; draw the chord perpendicular to the radius at that point. "
     "The chord is longer iff the point is within r/2 of the center: probability 1/2.", "B", "B"),
    ("Let d be the distance from the center to the chord, uniformly distributed between 0 and r. Then P(d < r/2) = 1/2.", "B", "B"),
    ("Choose the midpoint uniformly at random inside the disk. The chord is longer when the midpoint lies in the "
     "concentric circle of radius r/2, whose area is a quarter of the disk: 1/4.", "C", "C"),
    ("The midpoint M is uniformly distributed over the disk. The favourable region is the inner disk of radius r/2, "
     "so the probability is π(r/2)^2 / πr^2 = 1/4.", "C", "C"),
    ("Throw a point P uniformly into the disk and take the chord bisected by P. The probability is 1/4.", "C", "C"),
    ("Method 1: two random endpoints give 1/3. Method 2: a random radius and a random point on it give 1/2. "
     "Method 3: a random midpoint in the disk gives 1/4. This is Bertrand's paradox.", "multiple", "multiple"),
    ("The chord length is 2√(r² − d²), where d is the distance from the center. Therefore the answer is \\boxed{\\frac{1}{2}}.", "B", "none"),
    ("Choose the chord's midpoint uniformly along a randomly chosen radius. Since the midpoint is uniform in distance "
     "from the center, P = 1/2.", "B", "B"),
    ("Pick a point uniformly at random in the disk and draw the chord perpendicular to the radius through it. "
     "The chord is longer when the point is in the inner disk of radius r/2, so P = 1/4.", "C", "multiple"),
    ("A chord in a circle is defined by two points on the circle. The total length of the diameter is 2. "
     "Therefore the answer is \\boxed{\\frac{1}{2}}.", "B", "none"),
    ("A chord is drawn by selecting a diameter at random and then choosing a point on that diameter at random. "
     "The probability is 1/2.", "B", "B"),
    ("Since the angle subtended by any chord at the center is uniformly distributed between 0 and 360°, the "
     "probability that this angle is greater than 120° is 2/3.", "other", "A"),
]


def self_test():
    bad = 0
    for text, want, want_text in TESTS:
        s = score(text)
        got = s["approach_number"]
        want_how = None
        if "-" in want:
            want_how, want = want.split("-")
        ok = got == want and (want_how is None or s["final_how"] == want_how)
        ok = ok and (want_text is None or s["approach_text"] == want_text)
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} number want={want:8s} got={got:8s} how={s['final_how']:8s} "
              f"text want={str(want_text):8s} got={s['approach_text']:8s} hits={s['method_hits']} | {text[:60]}")
    print(f"{len(TESTS) - bad}/{len(TESTS)} passed")
    return bad == 0


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)

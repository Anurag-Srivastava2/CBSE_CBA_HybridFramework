"""English paraphrase probe, to pair with the Maths one (set IS1336).

Takes the English baseline already in the bank (IS1340, CH-5: A Farm) and
rewords every question while holding EVERYTHING else identical - same names,
same answers, same options, same typology, chapter, competency, LO, Bloom's
and marks. Only the phrasing moves, so each of the 16 items is the same
question asked differently and all 16 should be flagged as duplicates.

Names are deliberately NOT swapped here. The name-swap case was measured
separately (IS1341, 16/16 blocked); changing names as well would confound the
two variables.

Tiers are crossed with typology rather than assigned in blocks, so a tier
effect cannot be a typology effect:
  tier 1 near-copy      : items 1, 5, 9, 13
  tier 2 moderate       : items 2, 6, 10, 14
  tier 3 heavy          : items 3, 7, 11, 15
  tier 4 semantic-only  : items 4, 8, 12, 16
"""
import json
from pathlib import Path

from tools.build_english_names_v2 import CURRICULUM, NAME_MAP, ROWS, TEMPLATE
from tools.name_swap_sheet_builder import build_sheet

OUTPUT_DIR = Path("data/qar_semantic")

TIER = {"1": 1, "5": 1, "9": 1, "13": 1, "13.1": 1, "13.2": 1,
        "2": 2, "6": 2, "10": 2, "14": 2, "14.1": 2, "14.2": 2,
        "3": 3, "7": 3, "11": 3, "15": 3, "15.1": 3, "15.2": 3,
        "4": 4, "8": 4, "12": 4, "16": 4, "16.1": 4, "16.2": 4}

PARAPHRASE = {
    "1": "Nisha is matching farm words. Each animal must be matched with the sound it makes.",
    "2": "Farhan is sorting farm pictures. Link every animal to the thing we get from it.",
    "3": "According to Deepa, hens and cows are among the animals the farmer looks after.",
    "4": "Manoj noted down the animal that gives us milk: a ____.",
    "5": "Assertion (A): Leela said that hens live on the farm. Reason (R): Eggs are given to us by hens.",
    "6": "Assertion (A): Aarav claimed wool is grown as a crop on the farm. Reason (R): Wool comes from sheep.",
    "7": "Nisha would like to put on a farm play. Prepare masks of the animals and demonstrate the way each one walks.",
    "8": "Farhan is preparing a poster about the farm. Sketch three creatures found there and write the name beside each.",
    "9": "Deepa asks which farm animal is your favourite. Write two or three sentences.",
    "10": "Manoj would like to hear how you would spend a whole day on a farm. Write a few sentences about it.",
    "11": "Leela must give a talk to her classmates about farms. Write about the things a visitor would notice there.",
    "12": "Aarav is preparing a piece on how a farmer spends his time. Set out his routine from the moment he rises until nightfall.",
    "13": "Nisha and her brother went to a farm. They stopped beside the shed where the cows were being milked.",
    "13.1": "In the shed that Nisha visited, what were the cows producing?",
    "13.2": "Nisha wanted to know why the cows are milked each morning. Give one reason.",
    "14": "Farhan saw a farm play at school. During one scene the hens escaped from their coop.",
    "14.1": "During the play Farhan saw, the hens got out of their coop.",
    "14.2": "In the play Farhan saw, what is the home of the hens?",
    "15": "Deepa read the following: Many animals are kept on a farm. Milk comes from cows, eggs from hens and wool from sheep. From dawn until dusk the farmer toils.",
    "15.1": "According to the text Deepa read, what comes from sheep?",
    "15.2": "According to the text Deepa read, for what length of time does the farmer labour?",
    "16": "Manoj read the following lines: Rising at dawn, the farmer first gives the animals their food before setting off for the field.",
    "16.1": "In the lines Manoj read, before setting off for the field the farmer gives food to the ____.",
    "16.2": "In the lines Manoj read, once the animals have been fed, where does the farmer head?",
}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, spec = [], []
    for base in ROWS:
        sno = base["sno"]
        reworded = dict(base)
        reworded["question"] = PARAPHRASE[sno]
        rows.append(reworded)
        spec.append({"sno": sno, "tier": TIER[sno], "typology": base["typology"],
                     "A": base["question"], "B": PARAPHRASE[sno],
                     "answer": base["answer"], "expect": "FLAG"})

    # Nothing but the wording may move.
    bad = [s["sno"] for s in spec if s["A"] == s["B"]]
    names = set(NAME_MAP) | set(NAME_MAP.values())
    moved = [s["sno"] for s in spec
             if {n for n in names if n in s["A"]} != {n for n in names if n in s["B"]}]

    target = build_sheet(rows, "A", OUTPUT_DIR / "sheet_B_english_paraphrase.xlsx",
                         TEMPLATE, CURRICULUM, {})
    (OUTPUT_DIR / "spec_english_paraphrase.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"English paraphrases: {target} ({len(rows)} rows -> 16 items)")
    print("unchanged questions :", bad or "none")
    print("rows whose NAMES moved (must be none):", moved or "none")


if __name__ == "__main__":
    main()

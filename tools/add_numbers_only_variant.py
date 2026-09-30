"""Add a "C" side to each pair: Sheet A with ONLY the numbers changed.

Sheet C isolates one variable the A/B pairs cannot: wording held fixed while
the arithmetic changes. These are legitimately DIFFERENT items - an item bank
is supposed to hold 8+5 and 9+6 as separate practice questions - so a duplicate
verdict here is a false positive, not a catch.

Every C question is its A question with digits (and number words) substituted
and nothing else touched; answers and explanations follow the new arithmetic
because they must.
"""
import json
import re
from pathlib import Path

PAIRS_FILE = Path("data/qar_semantic/semantic_duplicate_pairs.json")

# seq -> the numbers-only rewrite of Sheet A's question.
VARIANTS = {
    1:  {"question": "A basket holds 8 carrots and 5 more carrots are put into it. The basket now holds 13 carrots.",
         "answer": "TRUE",
         "explanation": "8 carrots and 5 more carrots make 13 carrots, so the statement is true."},
    2:  {"question": "Meera picks 6 tomatoes and her brother picks 9 tomatoes. How many tomatoes do they have altogether?",
         "options": ["13", "14", "15", "16"], "answer": "15",
         "explanation": "6 tomatoes and 9 tomatoes together make 15 tomatoes."},
    3:  {"question": "There were 18 onions in a sack and 5 were taken out. ____ onions are left in the sack.",
         "answer": "13", "explanation": "18 take away 5 leaves 13 onions."},
    4:  {"question": "A farmer plants 6 rows of spinach and then plants 7 more rows. How many rows are there now?",
         "answer": "13", "explanation": "6 rows and 7 more rows make 13 rows."},
    5:  {"question": "A crate had 19 potatoes. The cook used 4 of them. Explain how you would find how many potatoes are left.",
         "answer": "Take 4 away from 19, because the potatoes used are removed from the crate; 19 - 4 = 15 potatoes.",
         "explanation": "Recognising the situation as a subtraction is the point; the arithmetic follows from it."},
    6:  {"question": "Lina picks 6 beans in the morning and 9 beans in the evening, so she picks 14 beans in all.",
         "answer": "FALSE",
         "explanation": "6 beans and 9 beans make 15 beans, not 14, so the statement is false."},
    7:  {"question": "A vegetable seller had 20 cucumbers and sold 9 of them. How many cucumbers are left with him?",
         "options": ["9", "10", "11", "12"], "answer": "11",
         "explanation": "20 take away 9 leaves 11 cucumbers."},
    8:  {"question": "Ravi had 8 pumpkins and his neighbour gave him 4 more. Ravi now has ____ pumpkins.",
         "answer": "12", "explanation": "8 pumpkins and 4 more make 12 pumpkins."},
    9:  {"question": "There are 15 brinjals in one basket and 9 in another. How many more brinjals does the first basket have?",
         "answer": "6", "explanation": "15 take away 9 leaves 6, so the first basket has 6 more."},
    10: {"question": "A farmer had 18 cabbages and sold 9 at the market. Describe how to work out how many cabbages he brought home.",
         "answer": "Subtract the 9 sold from the 18 he started with; 18 - 9 = 9 cabbages came home.",
         "explanation": "The cabbages sold leave the group, so the situation is a subtraction."},
    11: {"question": "A farmer pulls out 16 radishes and sells 7 of them, so 9 radishes are left with the farmer.",
         "answer": "TRUE", "explanation": "16 take away 7 leaves 9, so the statement is true."},
    12: {"question": "Start with 15 peas in a bowl and take away 6. How many peas remain?",
         "options": ["7", "8", "9", "10"], "answer": "9",
         "explanation": "15 take away 6 leaves 9 peas."},
    13: {"question": "Complete the number sentence: 7 + ____ = 18",
         "answer": "11", "explanation": "7 and 11 make 18, so the missing addend is 11."},
    14: {"question": "Which number must be added to 14 to make 20?",
         "answer": "6", "explanation": "14 and 6 make 20, so 6 must be added."},
    15: {"question": "Write a story problem about a vegetable farm for the number sentence 12 + 6 = 18.",
         "answer": "A farmer picked 12 lady fingers and then picked 6 more. How many lady fingers did she pick in all? She picked 18.",
         "explanation": "Any story that joins a group of 12 and a group of 6 to make 18 is acceptable."},
    16: {"question": "The sum of 8 and 5 is the same as the sum of 5 and 8.",
         "answer": "TRUE",
         "explanation": "Changing the order of the two numbers being added does not change the total; both make 13."},
    17: {"question": "Which number sentence has the same answer as 16 - 7?",
         "options": ["6 + 3", "16 + 7", "9 + 16", "7 - 16"], "answer": "6 + 3",
         "explanation": "16 - 7 = 9, and 6 + 3 = 9, so the two sentences share an answer."},
    18: {"question": "Three more than 14 is ____.",
         "answer": "17", "explanation": "Counting on 3 from 14 reaches 17."},
    19: {"question": "What must be taken away from 20 to leave 12?",
         "answer": "8", "explanation": "20 take away 8 leaves 12, so 8 must be removed."},
    20: {"question": "Write the two subtraction sentences that belong to the addition fact 5 + 8 = 13.",
         "answer": "13 - 5 = 8 and 13 - 8 = 5",
         "explanation": "Every addition fact has two matching subtraction facts using the same three numbers."},
}

WORDS = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)"


def skeleton(text):
    """The question with every numeral and number word blanked out.

    Two questions that differ only in their numbers share a skeleton. This is
    what proves Sheet C is a numbers-only rewrite rather than a paraphrase.
    """
    text = re.sub(r"\d+", "#", text)
    text = re.sub(WORDS, "#", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip().casefold()


def main():
    data = json.loads(PAIRS_FILE.read_text(encoding="utf-8"))
    mismatched = []
    for pair in data["pairs"]:
        variant = VARIANTS[pair["seq"]]
        pair["C"] = variant
        if skeleton(pair["A"]["question"]) != skeleton(variant["question"]):
            mismatched.append(pair["seq"])

    data["sheet_c_note"] = (
        "Sheet C is Sheet A with ONLY the numbers changed - same wording, same "
        "entities, same typology/chapter/competency/LO/Bloom's/Marks. These are "
        "legitimately different items, so a duplicate verdict on Sheet C is a "
        "FALSE POSITIVE rather than a catch."
    )
    PAIRS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Added C variants for {len(VARIANTS)} pairs.")
    if mismatched:
        print("WORDING CHANGED (not numbers-only) on seq:", mismatched)
    else:
        print("Verified: every C question is its A question with numbers substituted and nothing else.")


if __name__ == "__main__":
    main()

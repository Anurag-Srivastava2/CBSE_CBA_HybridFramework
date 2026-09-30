"""Build the Grade 1 English A/C sheets for the QAR duplicate probe.

Sheet A: 24 rows covering all 12 typologies twice, all in one chapter (the
importer rejects a mixed-chapter upload). Case Based and Source Based need a
parent row plus sub-rows, so the 24 breaks down as 12 standalone leaf rows +
4 parents + 8 sub-rows - the sub-rows carry the leaf typologies, which is what
lets every typology appear twice inside exactly 24 rows.

Sheet C: Sheet A with ONLY the character names swapped. Numbers, wording,
structure and metadata are untouched. It is generated from A by substitution
rather than typed out, so "only the names changed" is guaranteed by
construction and then re-verified by blanking names out of both and comparing.

Names stay in the same cultural register across the swap on purpose: a swap
that also changed register would confound the duplicate result with a possible
Bias Detection difference.
"""
import json
import re
from pathlib import Path
from shutil import copy2

from openpyxl import load_workbook

from utilities.item_template_columns import (
    clear_rows_from,
    copy_item_row,
    resolve_columns,
    trim_helper_columns,
    write_row_fields,
)

OUTPUT_DIR = Path("data/qar_semantic")
TEMPLATE = Path("data/upload_templates/sme_sheet.xlsx")

CURRICULUM = {
    "grade": "Grade 1",
    "subject": "English",
    "book": "Book 1",
    # Unit is optional and left blank: a blank Unit falls back to the book's
    # full chapter list, which avoids depending on the chapter->unit mapping.
    "unit": None,
    "chapter": "CH-4: The Cap-seller and the Monkeys",
}

NAME_MAP = {
    "Meena": "Latha", "Arun": "Vikram", "Ravi": "Suresh",
    "Sita": "Radha", "Kabir": "Nikhil", "Anita": "Priya",
}

C_STORY = "Comprehends narrated/ read-out stories and identifies characters,storyline, and what the author wants to say"
LO_STORY = "Comprehends narrated / readout stories, identifies characters and interacts in English"
C_VOCAB = "Knows and uses enough words to carry out day-to-day interactions effectively and can guess the meaning of new words by using existing vocabulary"
LO_VOCAB = "Begins to use known and acquired vocabulary in classroom conversations and to ask/tell"
C_CONV = "Converses fluently and can hold a meaningful conversation"
LO_CONV = "Engages in short meaningful conversations (structured conversations)"
C_NARR = "Narrates short stories with clear plot and characters"
LO_NARR = "Narrates short stories"
C_INSTR = "Understands oral instructions for a complex task and gives clear oral instructions for the same to others"
LO_INSTR = "Follows step-wise instructions and responds accordingly"


def row(sno, typology, comp, lo, blooms, blooms_exp, marks, question,
        answer=None, explanation=None, options=None):
    return {
        "sno": sno, "typology": typology, "competency": comp, "learning_outcome": lo,
        "blooms": blooms, "blooms_explanation": blooms_exp, "marks": marks,
        "question": question, "answer": answer, "explanation": explanation,
        "options": options,
    }


ROWS = [
    row("1", "Match the Following", C_VOCAB, LO_VOCAB, "Understanding",
        "The learner links each story word to the meaning it carries.", "2",
        "Meena is matching words from the story. Match each one with what it means.",
        answer="1-A, 2-B, 3-C",
        explanation="A cap is worn on the head, a monkey climbs trees and a basket holds the caps.",
        options=["Cap|Monkey|Basket", "Worn on the head|Climbs trees|Holds the caps"]),
    row("2", "Match the Following", C_VOCAB, LO_VOCAB, "Understanding",
        "The learner links each character to the action the story gives them.", "2",
        "Arun is matching the story characters. Match each one with what they did.",
        answer="1-A, 2-B, 3-C",
        explanation="The cap-seller slept, the monkeys took the caps and the tree gave shade.",
        options=["Cap-seller|Monkeys|Tree", "Slept under it|Took the caps|Gave shade"]),
    row("3", "True or False", C_STORY, LO_STORY, "Remembering",
        "The learner recalls a stated event from the story.", "1",
        "Ravi told his friend that the cap-seller fell asleep under a tree.",
        answer="TRUE",
        explanation="The story says the cap-seller sat under a tree to rest and fell asleep."),
    row("4", "Fill in the Blank", C_STORY, LO_STORY, "Remembering",
        "The learner recalls what the monkeys threw down.", "1",
        "Sita read that the monkeys copied the cap-seller and threw down their ____.",
        answer="caps",
        explanation="The monkeys imitated the cap-seller, so they threw down the caps."),
    row("5", "Assertion and Reasoning", C_STORY, LO_STORY, "Analysing",
        "The learner judges whether the reason explains the assertion.", "1",
        "Assertion (A): Kabir said the cap-seller got all his caps back. "
        "Reason (R): The monkeys copied whatever the cap-seller did.",
        answer="A",
        explanation="Both statements are true, and the copying is exactly why the caps came back."),
    row("6", "Assertion and Reasoning", C_STORY, LO_STORY, "Analysing",
        "The learner separates a false assertion from a true reason.", "1",
        "Assertion (A): Anita said the monkeys climbed down and handed the caps back politely. "
        "Reason (R): Monkeys like to imitate people.",
        answer="D",
        explanation="The monkeys threw the caps down rather than handing them back, so A is false while R is true."),
    row("7", "FA Activity", C_INSTR, LO_INSTR, "Applying",
        "The learner follows step-wise instructions to act out a scene.", "2",
        "Meena wants to act out the story. Make a paper cap and show how the cap-seller called out to the monkeys.",
        answer="A paper cap is made, and the child calls out and waves a hand like the cap-seller did.",
        explanation="The activity is done correctly if the cap is made and the calling action is shown."),
    row("8", "FA Activity", C_INSTR, LO_INSTR, "Applying",
        "The learner follows instructions to draw and label a scene.", "2",
        "Arun is drawing the story. Draw the tree with the monkeys holding the caps, and label your picture.",
        answer="A tree is drawn with monkeys holding caps, labelled with the words tree, monkey and cap.",
        explanation="The activity is done correctly if the drawing shows the scene and carries the three labels."),
    row("9", "Free Response", C_CONV, LO_CONV, "Creating",
        "The learner composes an original response to an imagined situation.", "3",
        "Ravi asks what you would do if a monkey took your cap. Write two or three sentences.",
        answer="I would not shout at the monkey. I would copy the cap-seller and throw my own cap down so the monkey copies me.",
        explanation="Any sensible answer in two or three sentences is acceptable."),
    row("10", "Free Response", C_CONV, LO_CONV, "Evaluating",
        "The learner states a preference about the story and supports it.", "3",
        "Sita wants to know which part of the story you liked best. Write about it in a few sentences.",
        answer="I liked the part where the monkeys threw the caps down, because the cap-seller was clever.",
        explanation="Any part of the story is acceptable if the learner gives a reason."),
    row("11", "Long Answer Question", C_NARR, LO_NARR, "Understanding",
        "The learner retells the whole story in the right order.", "4",
        "Kabir has to retell the story to his class. Describe what happened from the time the cap-seller sat under the tree until he got his caps back.",
        answer="The cap-seller sat under a tree and fell asleep. Monkeys took his caps and climbed the tree. When he woke up he shouted and waved, and the monkeys copied him. He threw his own cap down, the monkeys threw theirs down too, and he collected them all.",
        explanation="The retelling should cover sleeping, the caps being taken, the copying and the caps being recovered."),
    row("12", "Long Answer Question", C_NARR, LO_NARR, "Understanding",
        "The learner describes a character's feelings and actions.", "4",
        "Anita is writing about the cap-seller. Describe how the cap-seller felt when he woke up and what he did next.",
        answer="He felt shocked and angry when he saw the monkeys wearing his caps. He shouted at them, shook his fist and stamped his foot, and then threw his own cap down, which made the monkeys throw theirs down too.",
        explanation="The answer should name the feeling and follow it with the actions the story gives."),

    # --- Case Based #1: parent + two sub-rows ---
    row("13", "Case Based Question", C_STORY, LO_STORY, "Understanding",
        "The learner reads a short case and answers questions from it.", "3",
        "Meena and her sister were reading the story together. They stopped at the page where the cap-seller wakes up and sees all the monkeys sitting in the tree wearing his caps.",
        explanation="The case sets up two questions about the moment the cap-seller wakes."),
    row("13.1", "Multiple Choice Question", C_STORY, LO_STORY, "Remembering",
        "The learner recalls where the monkeys were.", "1",
        "In the picture Meena was looking at, where were the monkeys when the cap-seller woke up?",
        answer="In the tree",
        explanation="The monkeys had climbed back up into the tree with the caps.",
        options=["In the tree", "In the basket", "On the road", "In the market"]),
    row("13.2", "Short Answer Question", C_STORY, LO_STORY, "Understanding",
        "The learner explains why the caps could not simply be taken back.", "2",
        "Meena asked why the cap-seller could not climb up and take his caps back. What is the reason?",
        answer="The monkeys were high up in the tree and he could not reach them.",
        explanation="The height of the monkeys in the tree is the reason given by the story."),

    # --- Case Based #2: parent + two sub-rows ---
    row("14", "Case Based Question", C_STORY, LO_STORY, "Understanding",
        "The learner reads a short case and answers questions from it.", "3",
        "Arun watched a play of the story at school. In the last scene the cap-seller throws his own cap on the ground in anger.",
        explanation="The case sets up two questions about the ending of the story."),
    row("14.1", "True or False", C_STORY, LO_STORY, "Understanding",
        "The learner checks an event against the story's ending.", "1",
        "In the play Arun watched, the monkeys threw their caps down after the cap-seller threw his.",
        answer="TRUE",
        explanation="The monkeys copied him, so they threw their caps down too."),
    row("14.2", "Very Short Answer Question", C_STORY, LO_STORY, "Remembering",
        "The learner recalls the closing action of the story.", "2",
        "In the play Arun watched, what did the cap-seller do with the caps after the monkeys threw them down?",
        answer="He picked them up and put them back in his basket.",
        explanation="Collecting the caps into his basket is how the story ends."),

    # --- Source Based #1: parent + two sub-rows ---
    row("15", "Source Based Question", C_STORY, LO_STORY, "Understanding",
        "The learner reads a passage and answers questions from it.", "3",
        "Sita read this passage aloud: A cap-seller carried a basket of caps on his head. The day was hot, so he sat under a big tree to rest. He soon fell fast asleep. Some monkeys came down, took the caps and climbed back up the tree.",
        explanation="The passage supplies both the reason for resting and the monkeys' actions."),
    row("15.1", "Multiple Choice Question", C_STORY, LO_STORY, "Remembering",
        "The learner locates a stated reason in the passage.", "1",
        "In the passage Sita read, why did the cap-seller sit under the tree?",
        answer="Because the day was hot",
        explanation="The passage says the day was hot, so he sat under a tree to rest.",
        options=["Because the day was hot", "Because he was hungry",
                 "Because it was raining", "Because he lost his basket"]),
    row("15.2", "Short Answer Question", C_STORY, LO_STORY, "Understanding",
        "The learner reports what the passage says the monkeys did.", "2",
        "In the passage Sita read, what did the monkeys do while the cap-seller was asleep?",
        answer="They took the caps from his basket and climbed back up the tree.",
        explanation="Both actions are stated directly in the passage."),

    # --- Source Based #2: parent + two sub-rows ---
    row("16", "Source Based Question", C_STORY, LO_STORY, "Analysing",
        "The learner reads a passage and examines the pattern in it.", "3",
        "Read the passage: Ravi read aloud, \"The cap-seller shook his fist at the monkeys. The monkeys shook their fists back at him. He stamped his foot. The monkeys stamped their feet too.\"",
        explanation="The passage shows the copying pattern that drives the ending."),
    row("16.1", "Fill in the Blank", C_STORY, LO_STORY, "Understanding",
        "The learner names the pattern the passage describes.", "1",
        "In the lines Ravi read, whatever the cap-seller did, the monkeys ____ him.",
        answer="copied",
        explanation="Every action in the passage is repeated by the monkeys, which is copying."),
    row("16.2", "Very Short Answer Question", C_STORY, LO_STORY, "Remembering",
        "The learner picks one repeated action out of the passage.", "2",
        "In the lines Ravi read, name one action the cap-seller did that the monkeys repeated.",
        answer="He shook his fist.",
        explanation="Shaking a fist and stamping a foot are both in the passage."),
]

NAME_RE = re.compile("|".join(sorted(NAME_MAP, key=len, reverse=True)))


def swap_names(value):
    if not isinstance(value, str):
        return value
    return NAME_RE.sub(lambda m: NAME_MAP[m.group(0)], value)


def blank_names(value):
    """Replace every name from either set with a placeholder, for comparison."""
    if not isinstance(value, str):
        return value
    every = sorted(set(NAME_MAP) | set(NAME_MAP.values()), key=len, reverse=True)
    return re.sub("|".join(every), "@", value)


def build_sheet(rows, side, target):
    copy2(TEMPLATE, target)
    workbook = load_workbook(target)
    worksheet = workbook["Items"]
    width = trim_helper_columns(worksheet)
    columns = resolve_columns(worksheet)

    for offset, item in enumerate(rows):
        excel_row = offset + 2
        if excel_row != 2:
            copy_item_row(worksheet, 2, excel_row, width)
        pick = (lambda v: swap_names(v)) if side == "C" else (lambda v: v)
        fields = {
            **CURRICULUM,
            "sequence": item["sno"],
            "competency": item["competency"],
            "learning_outcome": item["learning_outcome"],
            "blooms": item["blooms"],
            "blooms_explanation": item["blooms_explanation"],
            "typology": item["typology"],
            "question": pick(item["question"]),
            "answer": pick(item["answer"]),
            "explanation": pick(item["explanation"]),
            "marks": item["marks"],
            "option_1": None, "option_2": None, "option_3": None, "option_4": None,
        }
        for index, option in enumerate(item["options"] or [], start=1):
            fields[f"option_{index}"] = pick(option)
        write_row_fields(worksheet, excel_row, columns, fields)

    clear_rows_from(worksheet, len(rows) + 2, width)
    workbook.save(target)
    workbook.close()
    return target


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    a = build_sheet(ROWS, "A", OUTPUT_DIR / "sheet_A_english.xlsx")
    c = build_sheet(ROWS, "C", OUTPUT_DIR / "sheet_C_english_names.xlsx")

    payload = {"curriculum": CURRICULUM, "name_map": NAME_MAP, "rows": []}
    problems = []
    for item in ROWS:
        aq, cq = item["question"], swap_names(item["question"])
        payload["rows"].append({**item, "question_A": aq, "question_C": cq})
        if blank_names(aq) != blank_names(cq):
            problems.append(f"{item['sno']}: more than names changed")
        if aq == cq and any(n in aq for n in NAME_MAP):
            problems.append(f"{item['sno']}: name present but not swapped")
    (OUTPUT_DIR / "english_name_pairs.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Sheet A: {a}  ({len(ROWS)} rows)")
    print(f"Sheet C: {c}  ({len(ROWS)} rows)")
    print("Name-swap integrity:", "OK - only names differ" if not problems else problems)


if __name__ == "__main__":
    main()

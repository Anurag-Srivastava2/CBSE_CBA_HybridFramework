from uuid import UUID, uuid4
from random import Random


OPERATIONS = ("addition", "subtraction", "multiplication", "division")
MIN_MIXED_QUESTION_COUNT = 3
MAX_MIXED_QUESTION_COUNT = 5


def _base36(value):
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    value = abs(value)
    characters = []
    while value:
        value, remainder = divmod(value, 36)
        characters.append(alphabet[remainder])
    return "".join(reversed(characters or ["0"]))


def _run_code(run_token):
    return _base36(run_token)[-8:].rjust(8, "0")


def _seed_to_int(seed):
    if seed is None:
        return uuid4().int
    if isinstance(seed, int):
        return seed
    try:
        return UUID(str(seed)).int
    except ValueError:
        return int.from_bytes(str(seed).encode("utf-8"), "big")


def _build_operands(operation, salt):
    if operation == "addition":
        left = 100 + salt % 99_900
        right = 10 + (salt // 997) % 9_990
        return left, right, left + right, "+"

    if operation == "subtraction":
        right = 10 + salt % 9_990
        difference = 10 + (salt // 991) % 89_990
        left = right + difference
        return left, right, difference, "-"

    if operation == "multiplication":
        left = 12 + salt % 988
        right = 12 + (salt // 983) % 9_988
        return left, right, left * right, "*"

    divisor = 2 + salt % 998
    quotient = 2 + (salt // 977) % 99_998
    dividend = divisor * quotient
    return dividend, divisor, quotient, "/"


def generate_unique_arithmetic_questions(count=4, seed=None):
    """Generate unique, internally correct True/False arithmetic questions."""
    if count < 1:
        raise ValueError("Question count must be at least 1.")

    run_token = _seed_to_int(seed)
    questions = []
    seen = set()
    for index in range(count):
        operation = OPERATIONS[index % len(OPERATIONS)]
        attempt = 0
        while True:
            salt = run_token + index * 1_000_003 + attempt * 10_000_019
            left, right, correct_result, symbol = _build_operands(operation, salt)
            is_true = (index + run_token) % 2 == 0
            if is_true:
                displayed_result = correct_result
            else:
                delta = 1 + (salt // 971) % 9
                displayed_result = correct_result + delta

            question_text = f"Is {left} {symbol} {right} = {displayed_result}?"
            if question_text not in seen:
                seen.add(question_text)
                break
            attempt += 1

        answer = "True" if is_true else "False"
        if is_true:
            explanation = f"True. {left} {symbol} {right} = {correct_result}."
        else:
            explanation = (
                f"False. {left} {symbol} {right} = {correct_result}, "
                f"not {displayed_result}."
            )
        questions.append(
            {
                "operation": operation,
                "left_operand": left,
                "right_operand": right,
                "correct_result": correct_result,
                "displayed_result": displayed_result,
                "question": question_text,
                "answer": answer,
                "explanation": explanation,
            }
        )

    return questions


def generate_unique_comparison_questions(count=4, seed=None):
    """Generate structurally varied, unique True/False comparison questions."""
    if count < 1:
        raise ValueError("Question count must be at least 1.")

    run_token = _seed_to_int(seed)
    randomizer = Random(run_token)
    questions = []
    seen = set()
    run_code = _run_code(run_token)
    contexts = (
        ("attendance board", "Class Blue", "Class Green", "learners"),
        ("library record", "story shelf", "picture shelf", "books"),
        ("garden chart", "sunflower row", "marigold row", "flowers"),
        ("games scoreboard", "Red team", "Yellow team", "points"),
        ("art-room inventory", "blue tray", "green tray", "crayons"),
        ("fruit counter", "apple basket", "orange basket", "fruits"),
        ("math-kit checklist", "first box", "second box", "beads"),
        ("class reward chart", "Team Star", "Team Moon", "stickers"),
        ("nature collection", "shell group", "stone group", "objects"),
        ("sports cupboard", "top shelf", "bottom shelf", "balls"),
        ("school shop list", "pencil pack", "eraser pack", "items"),
        ("festival display", "red line", "yellow line", "flags"),
        ("canteen tally", "milk counter", "juice counter", "cartons"),
        ("bus register", "morning route", "afternoon route", "riders"),
        ("weather log", "sunny-day tally", "rainy-day tally", "days"),
        ("toy corner audit", "blocks bin", "puzzles bin", "toys"),
        ("music room count", "drum shelf", "tambourine shelf", "instruments"),
        ("kitchen-garden log", "tomato patch", "chilli patch", "plants"),
        ("stationery drive", "notebook stack", "crayon-box stack", "packs"),
        ("playground roster", "swing queue", "slide queue", "children"),
        ("birthday chart", "January list", "February list", "names"),
        ("recycling drive", "paper bin", "plastic bin", "kilograms"),
        ("field-trip count", "front-row seats", "back-row seats", "seats"),
        ("assembly tally", "left wing", "right wing", "students"),
    )
    structures = (
        (
            "recorded_while",
            "During the {context} activity {code} {detail}, {left_label} recorded "
            "{left} {unit}, while {right_label} recorded {right} {unit}. "
            "Is {left} > {right}?",
        ),
        (
            "chart_claim",
            "A Grade 1 chart {code}, {detail}, lists {left_label} with {left} "
            "{unit} and {right_label} with {right} {unit}. The chart claims that "
            "{left} > {right}. Is the claim true or false?",
        ),
        (
            "student_comparison",
            "For task {code} {detail}, a student compares {left_label} ({left} "
            "{unit}) with {right_label} ({right} {unit}). The student writes "
            "{left} > {right}. Is the student correct?",
        ),
        (
            "counting_question",
            "After counting the {context} {detail} for card {code}, there are "
            "{left} {unit} for {left_label} and {right} {unit} for {right_label}. "
            "Does {left_label} have more {unit} than {right_label}?",
        ),
        (
            "spoken_statement",
            "In the {context} check {code}, {detail}, {left_label} has {left} "
            "{unit}; {right_label} has {right} {unit}. Ravi says the first "
            "number is greater than the second. Is Ravi's statement true?",
        ),
        (
            "comparison_card",
            "Comparison card {code} ({detail}): {left_label} = {left} {unit} "
            "and {right_label} = {right} {unit}. Should the card show "
            "{left} > {right}?",
        ),
        (
            "teacher_prompt",
            "The teacher reads the {context} entry {code}, {detail}: {left} "
            "{unit} for {left_label} and {right} {unit} for {right_label}. Is "
            "the first quantity greater than the second quantity?",
        ),
        (
            "verification_task",
            "Verify entry {code} from the {context}, {detail}. It gives "
            "{left_label} {left} {unit} and {right_label} {right} {unit}. Is "
            "the comparison {left} > {right} correct?",
        ),
        (
            "friend_note",
            "A note about card {code} says {detail}: {left_label} has {left} "
            "{unit} and {right_label} has {right} {unit}. Is it correct to say "
            "{left_label} has more {unit} than {right_label}?",
        ),
        (
            "quiz_line",
            "Quiz line {code} ({detail}) shows {left_label} at {left} {unit} "
            "against {right_label} at {right} {unit}. True or false: "
            "{left} > {right}?",
        ),
        (
            "helper_check",
            "The class helper checks card {code} {detail} and counts {left} "
            "{unit} for {left_label} plus {right} {unit} for {right_label}. Is "
            "{left_label}'s count greater than {right_label}'s?",
        ),
        (
            "board_update",
            "Board update {code}, {detail}: {left_label} now shows {left} "
            "{unit} and {right_label} now shows {right} {unit}. Does "
            "{left_label} show a bigger number than {right_label}?",
        ),
    )
    details = (
        "noted on Monday morning",
        "checked just before lunch",
        "written up after the morning bell",
        "shared during the weekly review",
        "updated for this term",
        "seen on the classroom notice board",
        "confirmed by the class monitor",
        "logged before the assembly",
        "double-checked after recess",
        "recorded for the Friday review",
        "taken from today's count",
        "spotted during the walk-around",
    )
    context_pool = list(contexts)
    structure_pool = list(structures)
    randomizer.shuffle(context_pool)
    randomizer.shuffle(structure_pool)
    selected_contexts = randomizer.sample(
        context_pool, k=min(count, len(context_pool))
    )
    selected_structures = randomizer.sample(
        structure_pool, k=min(count, len(structure_pool))
    )
    true_first = bool(randomizer.getrandbits(1))

    for index in range(count):
        large_number = randomizer.randint(30, 99)
        small_number = randomizer.randint(1, 28)
        is_true = true_first if index % 2 == 0 else not true_first
        left_number, right_number = (
            (large_number, small_number)
            if is_true
            else (small_number, large_number)
        )
        context, left_label, right_label, unit = selected_contexts[
            index % len(selected_contexts)
        ]
        structure_name, structure_template = selected_structures[
            index % len(selected_structures)
        ]
        detail = randomizer.choice(details)
        item_code = f"{run_code}-{index + 1}"
        question_text = structure_template.format(
            context=context,
            code=item_code,
            detail=detail,
            left_label=left_label,
            right_label=right_label,
            left=left_number,
            right=right_number,
            unit=unit,
        )
        attempt = 0
        while question_text in seen:
            attempt += 1
            large_number = min(99, large_number + index + attempt)
            left_number, right_number = (
                (large_number, small_number)
                if is_true
                else (small_number, large_number)
            )
            detail = details[(details.index(detail) + attempt) % len(details)]
            question_text = structure_template.format(
                context=context,
                code=item_code,
                detail=detail,
                left_label=left_label,
                right_label=right_label,
                left=left_number,
                right=right_number,
                unit=unit,
            )
        seen.add(question_text)

        answer = "True" if is_true else "False"
        comparison = "is greater than" if is_true else "is not greater than"
        questions.append(
            {
                "left_operand": left_number,
                "right_operand": right_number,
                "context": context,
                "structure": structure_name,
                "question": question_text,
                "answer": answer,
                "explanation": (
                    f"{answer}. {left_number} {comparison} {right_number}."
                ),
            }
        )
    return questions


def generate_qar_ready_mixed_questions(count=4, seed=None):
    """Generate 3-5 distinct, Grade 1 time-themed items for an Excel upload.

    The activity-card code makes every run exactly traceable while the different
    contexts and typologies avoid relying on changed numbers for uniqueness.
    """
    if not MIN_MIXED_QUESTION_COUNT <= count <= MAX_MIXED_QUESTION_COUNT:
        raise ValueError(
            "Mixed item sheets must contain between "
            f"{MIN_MIXED_QUESTION_COUNT} and {MAX_MIXED_QUESTION_COUNT} questions."
        )

    run_token = _seed_to_int(seed)
    code = _run_code(run_token)
    names = ("Aarav", "Diya", "Kabir", "Meera", "Riya", "Vihaan")
    name = names[run_token % len(names)]
    start_hour = 7 + run_token % 3
    duration = 1 + (run_token // 7) % 2
    finish_hour = start_hour + duration
    clock_hour = 1 + (run_token // 11) % 11
    is_true = run_token % 2 == 0
    stated_duration = duration if is_true else (2 if duration == 1 else 1)

    items = [
        {
            "typology": "True or False",
            "question": (
                f"Activity card {code}: {name} starts reading at {start_hour}:00 "
                f"and stops at {finish_hour}:00. The reading time is "
                f"{stated_duration} hour{'s' if stated_duration != 1 else ''}. "
                "Is this statement true or false?"
            ),
            "options": [],
            "answer": "True" if is_true else "False",
            "explanation": (
                f"The time from {start_hour}:00 to {finish_hour}:00 is "
                f"{duration} hour{'s' if duration != 1 else ''}."
            ),
            "marks": "1",
        },
        {
            "typology": "Short Answer Question",
            "question": (
                f"School timetable {code}: Assembly begins at {start_hour}:00 "
                f"and the next activity begins at {finish_hour}:00. State the "
                "elapsed time in hours."
            ),
            "options": [],
            "answer": f"{duration} hour{'s' if duration != 1 else ''}",
            "explanation": (
                f"Counting from {start_hour}:00 to {finish_hour}:00 gives "
                f"{duration} complete hour{'s' if duration != 1 else ''}."
            ),
            "marks": "1",
        },
        {
            "typology": "Fill in the Blank",
            "question": (
                f"Journey note {code}: A bus leaves at {start_hour}:00 and "
                f"arrives at {finish_hour}:00. The journey lasts ___ "
                f"hour{'s' if duration != 1 else ''}."
            ),
            "options": [],
            "answer": str(duration),
            "explanation": (
                f"There are {duration} complete hour{'s' if duration != 1 else ''} "
                f"between {start_hour}:00 and {finish_hour}:00."
            ),
            "marks": "1",
        },
        {
            "typology": "Very Short Answer Question",
            "question": (
                f"Daily routine card {code}: {name} begins an activity at "
                f"{start_hour}:00 and finishes at {finish_hour}:00. How many "
                "complete hours does the activity take?"
            ),
            "options": [],
            "answer": str(duration),
            "explanation": (
                f"The activity lasts {duration} complete "
                f"hour{'s' if duration != 1 else ''}."
            ),
            "marks": "1",
        },
        {
            "typology": "MCQ",
            "question": (
                f"Clock check {code}: An activity starts at {start_hour}:00 and "
                f"ends at {finish_hour}:00. Which option gives the elapsed time?"
            ),
            "options": [
                f"{duration} hour{'s' if duration != 1 else ''}",
                "15 minutes",
                "30 minutes",
                f"{duration + 2} hours",
            ],
            "answer": "A",
            "explanation": (
                f"The elapsed time is {duration} "
                f"hour{'s' if duration != 1 else ''}, which is option A."
            ),
            "marks": "1",
        },
    ]

    return items[:count]

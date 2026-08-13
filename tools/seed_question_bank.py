"""One-off/rerunnable authoring script for the AI question bank seed batch.

Run with: python tools/seed_question_bank.py
Writes data/question_bank/questions.json (overwrites). Grows RAW_QUESTIONS below to
scale from this ~100-question seed batch toward the full ~1000-question target -
each new batch should stay typology-balanced and get run through validate_record
(this script already does that before writing).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utilities.question_bank_manager import content_hash, validate_record  # noqa: E402


# Each entry: (typology, grade, subject, chapter, competency, blooms_level, question,
#              options, answer, explanation, marks)
RAW_QUESTIONS = [
    # ---------------- MCQ ----------------
    ("Multiple Choice Question", "3", "Mathematics", "Addition and Subtraction", "Number Sense", "Applying",
     "What is the sum of 245 and 178?",
     ["423", "413", "433", "403"], "423",
     "245 + 178 = 423, adding ones, tens, and hundreds with carry-over.", 1),
    ("Multiple Choice Question", "4", "Mathematics", "Fractions", "Number Sense", "Understanding",
     "Which fraction is equivalent to 1/2?",
     ["2/5", "3/6", "4/9", "5/8"], "3/6",
     "3/6 simplifies to 1/2 since both numerator and denominator share a common factor of 3.", 1),
    ("Multiple Choice Question", "5", "Science", "Food and Nutrition", "Scientific Understanding", "Remembering",
     "Which nutrient mainly helps in building and repairing body tissues?",
     ["Carbohydrates", "Proteins", "Vitamins", "Fats"], "Proteins",
     "Proteins are the body-building nutrients responsible for tissue growth and repair.", 1),
    ("Multiple Choice Question", "6", "Science", "Electricity and Circuits", "Scientific Understanding", "Applying",
     "In a simple circuit, a bulb does not light up if the switch is:",
     ["Closed", "Open", "Made of metal", "Connected to a battery"], "Open",
     "An open switch breaks the circuit path, so current cannot flow to the bulb.", 1),
    ("Multiple Choice Question", "7", "Social Science", "The French Revolution", "Historical Understanding", "Remembering",
     "In which year did the storming of the Bastille take place?",
     ["1789", "1799", "1804", "1776"], "1789",
     "The Bastille was stormed by the people of Paris on 14 July 1789, marking the start of the revolution.", 1),
    ("Multiple Choice Question", "8", "Social Science", "Resources and Development", "Conceptual Understanding", "Understanding",
     "Which of the following is a renewable resource?",
     ["Coal", "Natural gas", "Solar energy", "Petroleum"], "Solar energy",
     "Solar energy is continuously replenished by nature and does not get depleted with use.", 1),
    ("Multiple Choice Question", "3", "English", "Nouns and Pronouns", "Grammatical Awareness", "Remembering",
     "Choose the correct pronoun: '___ is my best friend.'",
     ["Him", "She", "Her", "Them"], "She",
     "'She' is a subject pronoun correctly used before the verb 'is'.", 1),
    ("Multiple Choice Question", "4", "English", "Reading Comprehension", "Comprehension", "Analyzing",
     "In the passage, why did the boy return the lost wallet?",
     ["To get a reward", "Because he was honest", "Because his mother saw him", "Because it was empty"], "Because he was honest",
     "The passage states the boy returned the wallet purely because of his honest nature.", 2),
    ("Multiple Choice Question", "6", "Mathematics", "Integers", "Number Sense", "Applying",
     "What is the value of (-8) + 5?",
     ["-3", "3", "-13", "13"], "-3",
     "Adding a positive number to a negative number moves it towards zero: -8 + 5 = -3.", 1),

    # ---------------- Fill in the Blank ----------------
    ("Fill in the Blank", "3", "Mathematics", "Multiplication", "Number Sense", "Remembering",
     "7 multiplied by 6 is ______.",
     [], "42",
     "7 x 6 = 42, recalled from the multiplication table of 7.", 1),
    ("Fill in the Blank", "4", "Science", "States of Matter", "Scientific Understanding", "Understanding",
     "Water changes into water vapour through a process called ______.",
     [], "evaporation",
     "Evaporation is the process by which a liquid changes into vapour on absorbing heat.", 1),
    ("Fill in the Blank", "5", "English", "Vocabulary", "Language Awareness", "Remembering",
     "The opposite of the word 'brave' is ______.",
     [], "coward",
     "'Coward' (or 'cowardly') is the antonym of 'brave', describing a lack of courage.", 1),
    ("Fill in the Blank", "6", "Social Science", "The Earth in the Solar System", "Conceptual Understanding", "Remembering",
     "The planet closest to the Sun is ______.",
     [], "Mercury",
     "Mercury is the first planet from the Sun in our solar system.", 1),
    ("Fill in the Blank", "7", "Mathematics", "Simple Interest", "Application", "Applying",
     "The simple interest on Rs. 1000 at 5% per annum for 2 years is Rs. ______.",
     [], "100",
     "SI = (P x R x T)/100 = (1000 x 5 x 2)/100 = 100.", 2),
    ("Fill in the Blank", "8", "Science", "Cell Structure and Functions", "Scientific Understanding", "Remembering",
     "The powerhouse of the cell is the ______.",
     [], "mitochondria",
     "Mitochondria generate the energy (ATP) needed for cellular activities, earning this nickname.", 1),
    ("Fill in the Blank", "3", "English", "Verbs", "Grammatical Awareness", "Understanding",
     "She ______ (go) to school every day.",
     [], "goes",
     "Present tense, third person singular subject 'she' takes the verb form 'goes'.", 1),
    ("Fill in the Blank", "5", "Social Science", "Our Environment", "Conceptual Understanding", "Understanding",
     "The layer of gases surrounding the Earth is called the ______.",
     [], "atmosphere",
     "The atmosphere is the blanket of air that surrounds the Earth and supports life.", 1),

    # ---------------- Match the Following ----------------
    ("Match the Following", "4", "Science", "Animal Adaptations", "Conceptual Understanding", "Understanding",
     "Match the animal in Column A with its habitat in Column B.",
     ["A-Camel : B-Desert", "A-Fish : B-Water", "A-Polar Bear : B-Ice regions", "A-Monkey : B-Trees"],
     "A-Camel : B-Desert, A-Fish : B-Water, A-Polar Bear : B-Ice regions, A-Monkey : B-Trees",
     "Each animal is matched to the habitat it is naturally adapted to survive in.", 2),
    ("Match the Following", "6", "Mathematics", "Basic Geometrical Ideas", "Conceptual Understanding", "Remembering",
     "Match the shape in Column A with the number of sides in Column B.",
     ["A-Triangle : B-3", "A-Square : B-4", "A-Pentagon : B-5", "A-Hexagon : B-6"],
     "A-Triangle : B-3, A-Square : B-4, A-Pentagon : B-5, A-Hexagon : B-6",
     "Each polygon name corresponds directly to its defining number of sides.", 2),
    ("Match the Following", "7", "Social Science", "Indian Freedom Struggle", "Historical Understanding", "Remembering",
     "Match the leader in Column A with the movement in Column B.",
     ["A-Mahatma Gandhi : B-Dandi March", "A-Bhagat Singh : B-HSRA", "A-Subhas Chandra Bose : B-INA", "A-Lal Bahadur Shastri : B-Jai Jawan Jai Kisan"],
     "A-Mahatma Gandhi : B-Dandi March, A-Bhagat Singh : B-HSRA, A-Subhas Chandra Bose : B-INA, A-Lal Bahadur Shastri : B-Jai Jawan Jai Kisan",
     "Each freedom fighter is matched to the movement or slogan they are best known for.", 2),
    ("Match the Following", "5", "English", "Parts of Speech", "Grammatical Awareness", "Understanding",
     "Match the word in Column A with its part of speech in Column B.",
     ["A-Quickly : B-Adverb", "A-Happy : B-Adjective", "A-Run : B-Verb", "A-Table : B-Noun"],
     "A-Quickly : B-Adverb, A-Happy : B-Adjective, A-Run : B-Verb, A-Table : B-Noun",
     "Each word is matched with the grammatical category it belongs to.", 2),
    ("Match the Following", "8", "Science", "Force and Pressure", "Scientific Understanding", "Understanding",
     "Match the force in Column A with its example in Column B.",
     ["A-Gravitational force : B-Object falling down", "A-Frictional force : B-Stopping a rolling ball",
      "A-Muscular force : B-Lifting a bag", "A-Magnetic force : B-Attracting iron nails"],
     "A-Gravitational force : B-Object falling down, A-Frictional force : B-Stopping a rolling ball, A-Muscular force : B-Lifting a bag, A-Magnetic force : B-Attracting iron nails",
     "Each force type is matched with a real-life example illustrating it.", 2),
    ("Match the Following", "3", "Social Science", "Our Country India", "Conceptual Understanding", "Remembering",
     "Match the state in Column A with its capital in Column B.",
     ["A-Kerala : B-Thiruvananthapuram", "A-Punjab : B-Chandigarh", "A-Gujarat : B-Gandhinagar", "A-Assam : B-Dispur"],
     "A-Kerala : B-Thiruvananthapuram, A-Punjab : B-Chandigarh, A-Gujarat : B-Gandhinagar, A-Assam : B-Dispur",
     "Each state is matched with its correct administrative capital.", 2),

    # ---------------- True/False ----------------
    ("True or False", "3", "Mathematics", "Shapes and Patterns", "Conceptual Understanding", "Remembering",
     "A triangle has four sides.",
     [], "False",
     "A triangle has exactly three sides, not four.", 1),
    ("True or False", "4", "Science", "Plants Around Us", "Scientific Understanding", "Remembering",
     "Photosynthesis occurs in the roots of a plant.",
     [], "False",
     "Photosynthesis mainly occurs in the leaves, which contain chlorophyll, not in the roots.", 1),
    ("True or False", "5", "Social Science", "Maps and Directions", "Conceptual Understanding", "Understanding",
     "On a map, the top always represents the North direction.",
     [], "True",
     "By convention, maps are drawn with North at the top unless a direction indicator states otherwise.", 1),
    ("True or False", "6", "English", "Sentence Structure", "Grammatical Awareness", "Understanding",
     "A sentence must contain both a subject and a verb.",
     [], "True",
     "A grammatically complete sentence requires at least a subject and a verb to express a full thought.", 1),
    ("True or False", "7", "Mathematics", "Rational Numbers", "Number Sense", "Understanding",
     "Every whole number is a rational number.",
     [], "True",
     "Any whole number n can be written as n/1, satisfying the definition of a rational number.", 1),
    ("True or False", "8", "Science", "Chemical Effects of Electric Current", "Scientific Understanding", "Understanding",
     "Distilled water is a good conductor of electricity.",
     [], "False",
     "Distilled water lacks free ions, so it is a poor conductor unlike water with dissolved salts.", 1),

    # ---------------- VSA (Very Short Answer) ----------------
    ("Very Short Answer Question", "3", "Mathematics", "Measurement", "Application", "Applying",
     "Convert 3 metres into centimetres.",
     [], "300 cm",
     "1 metre = 100 cm, so 3 metres = 3 x 100 = 300 cm.", 1),
    ("Very Short Answer Question", "4", "Science", "Air Around Us", "Scientific Understanding", "Remembering",
     "Name the gas that plants absorb from the air during photosynthesis.",
     [], "Carbon dioxide",
     "Plants take in carbon dioxide from the air to carry out photosynthesis.", 1),
    ("Very Short Answer Question", "5", "Social Science", "Local Self Government", "Conceptual Understanding", "Remembering",
     "Name the elected head of a village Panchayat.",
     [], "Sarpanch",
     "The Sarpanch is the elected head who presides over the Gram Panchayat.", 1),
    ("Very Short Answer Question", "6", "English", "Tenses", "Grammatical Awareness", "Applying",
     "Write the past tense of the verb 'write'.",
     [], "wrote",
     "'Wrote' is the correct simple past tense form of the irregular verb 'write'.", 1),
    ("Very Short Answer Question", "7", "Mathematics", "Lines and Angles", "Conceptual Understanding", "Understanding",
     "What is the sum of the two acute angles in a right-angled triangle?",
     [], "90 degrees",
     "Since the three angles of a triangle sum to 180 degrees and one angle is 90 degrees, the other two sum to 90 degrees.", 1),
    ("Very Short Answer Question", "8", "Science", "Reproduction in Animals", "Scientific Understanding", "Remembering",
     "Name the process by which a single fertilized egg develops into an embryo.",
     [], "Embryonic development",
     "After fertilization, the zygote undergoes cell division and growth, a process called embryonic development.", 1),

    # ---------------- SAQ (Short Answer) ----------------
    ("Short Answer Question", "4", "Mathematics", "Time", "Application", "Applying",
     "A movie starts at 3:45 PM and lasts for 2 hours 30 minutes. At what time does it end?",
     [], "6:15 PM",
     "Adding 2 hours 30 minutes to 3:45 PM gives 6:15 PM.", 2),
    ("Short Answer Question", "5", "Science", "Force and Motion", "Scientific Understanding", "Understanding",
     "Explain briefly why a ball rolling on the ground eventually stops.",
     [], "Friction between the ball and the ground opposes its motion, gradually slowing it down until it stops.",
     "Frictional force acts opposite to the direction of motion, dissipating the ball's kinetic energy as heat.", 2),
    ("Short Answer Question", "6", "Social Science", "Diversity in India", "Conceptual Understanding", "Understanding",
     "Give two reasons why India is called a land of diversity.",
     [], "India has diversity in languages, religions, festivals, and geography, with people of many cultures living together.",
     "India's vast size and long history have led to a wide variety of languages, religions, and traditions coexisting.", 2),
    ("Short Answer Question", "7", "English", "Figures of Speech", "Language Awareness", "Understanding",
     "Identify the figure of speech in: 'The stars danced in the night sky.' Explain briefly.",
     [], "Personification, because the stars are given the human quality of dancing.",
     "Personification attributes human actions or qualities to non-living things, as seen with the stars 'dancing'.", 2),
    ("Short Answer Question", "8", "Mathematics", "Linear Equations in One Variable", "Application", "Applying",
     "Solve for x: 3x + 7 = 22.",
     [], "x = 5",
     "Subtracting 7 from both sides gives 3x = 15, then dividing by 3 gives x = 5.", 2),
    ("Short Answer Question", "3", "Science", "Our Body", "Scientific Understanding", "Remembering",
     "Name any two sense organs and the sense each one is responsible for.",
     [], "Eyes are responsible for sight, and ears are responsible for hearing.",
     "Each sense organ is specialized to detect a particular type of stimulus from the environment.", 2),

    # ---------------- LAQ (Long Answer) ----------------
    ("Long Answer Question", "6", "Science", "Water: A Precious Resource", "Scientific Understanding", "Analyzing",
     "Explain the water cycle in your own words, mentioning at least four stages.",
     [], "The water cycle involves evaporation of water from oceans and rivers, condensation of vapour into clouds, precipitation as rain or snow, and collection of water back into rivers, lakes, and oceans, which then repeats continuously.",
     "The answer should describe evaporation, condensation, precipitation, and collection as a continuous natural cycle.", 3),
    ("Long Answer Question", "7", "Social Science", "Impact of the French Revolution", "Historical Understanding", "Analyzing",
     "Discuss the long-term effects of the French Revolution on Europe.",
     [], "The French Revolution spread ideas of liberty, equality, and fraternity across Europe, weakened the power of absolute monarchies, inspired future democratic and nationalist movements, and led to significant political reforms in many countries.",
     "A complete answer connects the revolution's ideals to later political change across Europe, not just within France.", 3),
    ("Long Answer Question", "8", "English", "Story Analysis", "Comprehension", "Analyzing",
     "Describe the character development of the protagonist across the story, citing at least two examples.",
     [], "The protagonist starts as timid and unsure but grows more confident through challenges faced, such as standing up to a bully and taking responsibility for a mistake, showing clear growth by the story's end.",
     "A strong answer traces change over time and supports it with specific incidents from the story.", 3),
    ("Long Answer Question", "5", "Mathematics", "Perimeter and Area", "Application", "Analyzing",
     "A rectangular garden is 15 m long and 8 m wide. Find its perimeter and area, showing your working.",
     [], "Perimeter = 2(15+8) = 46 m; Area = 15 x 8 = 120 sq. m.",
     "Perimeter uses the formula 2(length+breadth); area uses length x breadth, both applied with the given dimensions.", 3),

    # ---------------- Case Based Question ----------------
    ("Case Based Question", "8", "Science", "Pollution of Air and Water", "Scientific Understanding", "Analyzing",
     "A factory near a river releases untreated waste directly into the water. Local fish populations have started declining, and villagers report a foul smell from the river. Based on this, what is the most likely cause of the declining fish population, and what should the factory do?",
     ["Natural fish migration; no action needed", "Water pollution from untreated waste; treat waste before release",
      "Excess fishing by villagers; ban fishing", "Seasonal temperature change; no action needed"],
     "Water pollution from untreated waste; treat waste before release",
     "The untreated waste is contaminating the river, harming aquatic life; treating waste before disposal would reduce pollution.", 3),
    ("Case Based Question", "7", "Social Science", "Agriculture in India", "Conceptual Understanding", "Analyzing",
     "A farmer in a low-rainfall region wants to grow a crop that requires very little water and matures quickly. Considering these constraints, which crop is most suitable, and why?",
     ["Rice, because it is widely grown in India", "Sugarcane, because it is profitable",
      "Millets (Bajra/Jowar), because they are drought-resistant and fast-growing", "Jute, because it grows in wet regions"],
     "Millets (Bajra/Jowar), because they are drought-resistant and fast-growing",
     "Millets are well suited to dry regions since they need less water and have a shorter growing season than crops like rice or sugarcane.", 3),
    ("Case Based Question", "6", "Mathematics", "Data Handling", "Application", "Analyzing",
     "A class recorded the number of books read by 5 students in a month: 4, 6, 3, 6, 6. The teacher wants to know which value appears most often. What is that value, and what is it called in statistics?",
     ["3, called the mean", "6, called the mode", "4, called the median", "6, called the range"],
     "6, called the mode",
     "6 occurs three times, more than any other value, making it the mode of the data set.", 3),

    # ---------------- Source Based Question ----------------
    ("Source Based Question", "7", "Social Science", "The Rise of Nationalism in Europe", "Historical Understanding", "Analyzing",
     "Read the extract: 'Napoleon introduced the Civil Code of 1804, abolishing privileges based on birth and establishing equality before the law.' Based on this extract, what change did the Civil Code bring to society?",
     ["It restored the monarchy", "It abolished birth-based privileges and ensured legal equality",
      "It banned all civil laws", "It gave more power to the clergy"],
     "It abolished birth-based privileges and ensured legal equality",
     "The extract directly states that the Civil Code removed birth-based privilege and established equality before the law.", 2),
    ("Source Based Question", "8", "Science", "Cell Structure and Functions", "Scientific Understanding", "Analyzing",
     "Read the extract: 'A cell wall is a rigid, non-living layer found outside the cell membrane in plant cells, providing shape and protection.' Based on this, which type of cell would you expect to lack a cell wall?",
     ["Plant cell", "Animal cell", "Bacterial cell", "Fungal cell"], "Animal cell",
     "Since the extract describes the cell wall as a plant-cell feature, animal cells (which lack this layer) would not have it.", 2),
    ("Source Based Question", "6", "English", "Biography Extract", "Comprehension", "Analyzing",
     "Read the extract: 'Despite losing his eyesight at a young age, he went on to become a celebrated musician, proving that determination can overcome great obstacles.' What quality of the person does this extract highlight?",
     ["Wealth", "Determination", "Luck", "Aggression"], "Determination",
     "The extract explicitly credits his success to determination despite his disability.", 2),

    # ---------------- Assertion and Reasoning ----------------
    ("Assertion and Reasoning", "8", "Science", "Force and Pressure", "Scientific Understanding", "Analyzing",
     "Assertion (A): A sharp knife cuts more effectively than a blunt one.\nReason (R): A sharp knife has a smaller area of contact, which increases the pressure exerted for the same force.\nChoose the correct option: (A) Both A and R are true and R correctly explains A. (B) Both A and R are true but R does not explain A. (C) A is true but R is false. (D) A is false but R is true.",
     [], "A",
     "Pressure = Force/Area; a sharper edge has a smaller contact area, producing higher pressure for the same force, which is why it cuts more effectively - this correctly explains the assertion.", 2),
    ("Assertion and Reasoning", "7", "Social Science", "Democracy and Diversity", "Conceptual Understanding", "Analyzing",
     "Assertion (A): Democracy accommodates social diversity better than other forms of government.\nReason (R): Democracy allows different groups to express disagreement and negotiate differences peacefully through elections and dialogue.\nChoose the correct option: (A) Both A and R are true and R correctly explains A. (B) Both A and R are true but R does not explain A. (C) A is true but R is false. (D) A is false but R is true.",
     [], "A",
     "Democratic processes like elections and open dialogue give diverse groups a peaceful means to express and resolve differences, which explains why democracy handles diversity well.", 2),
    ("Assertion and Reasoning", "6", "Mathematics", "Integers", "Number Sense", "Analyzing",
     "Assertion (A): The product of two negative integers is always positive.\nReason (R): Multiplying two negative signs gives a positive sign.\nChoose the correct option: (A) Both A and R are true and R correctly explains A. (B) Both A and R are true but R does not explain A. (C) A is true but R is false. (D) A is false but R is true.",
     [], "A",
     "By the sign rule for multiplication, a negative times a negative gives a positive, which is exactly why the product of two negative integers is positive.", 2),

    # ---------------- FA Activity ----------------
    ("FA Activity", "4", "Science", "Plants Around Us", "Application", "Applying",
     "Activity: Collect five different leaves from your surroundings. Sketch each leaf and note whether its margin is smooth or toothed.",
     [], "Students should present five leaf sketches with correctly identified margins (smooth or toothed) based on direct observation.",
     "This formative activity assesses observation and classification skills using a simple, visible leaf feature.", 2),
    ("FA Activity", "5", "Mathematics", "Shapes and Symmetry", "Application", "Applying",
     "Activity: Fold a square sheet of paper to show all its lines of symmetry, then draw and label each fold line.",
     [], "Students should identify and draw all 4 lines of symmetry of a square: two diagonals and two lines through the midpoints of opposite sides.",
     "This hands-on activity helps students discover symmetry lines experientially rather than by rote memorisation.", 2),
    ("FA Activity", "3", "English", "Storytelling", "Application", "Applying",
     "Activity: Narrate a short story (5-6 sentences) about a kind animal, using at least three describing words (adjectives).",
     [], "Students should produce a short original story using at least three adjectives describing the animal or its actions.",
     "This activity assesses creative use of descriptive vocabulary in a simple narrative context.", 2),

    # ---------------- Free Response ----------------
    ("Free Response", "6", "Social Science", "Understanding Diversity", "Conceptual Understanding", "Evaluating",
     "In your own words, describe one experience or example from daily life that shows India's cultural diversity, and explain what you learned from it.",
     [], "Answers will vary; a strong response describes a specific personal or observed example (e.g., a festival, food, or language difference) and reflects on what it revealed about India's diversity.",
     "Free response items are graded on relevance, personal reflection, and clarity rather than a single fixed answer.", 3),
    ("Free Response", "7", "Science", "Environmental Conservation", "Application", "Evaluating",
     "Suggest three practical steps your school could take to reduce plastic waste, and explain why each step would help.",
     [], "Answers will vary; strong responses propose concrete steps (e.g., banning single-use plastic, setting up recycling bins, promoting reusable bottles) with a clear explanation of their environmental benefit.",
     "Free response items are graded on the practicality of the suggestions and the clarity of the reasoning given.", 3),
    ("Free Response", "8", "English", "Personal Narrative", "Application", "Evaluating",
     "Write a short paragraph describing a time you helped someone, and reflect on how it made you feel.",
     [], "Answers will vary; a strong response includes a specific incident, clear sequence of events, and genuine reflection on the writer's feelings.",
     "Free response items are graded on coherence, specificity of the incident described, and depth of reflection.", 3),
]



# ---------------------------------------------------------------------------
# Parametrized generators: each produces many distinct, individually-correct
# questions from a real fact family (arithmetic, multiplication tables,
# number comparisons, unit conversions, number names, ...) so the bank can
# scale toward ~1000 items without hand-authoring every single one.
# All still flow through validate_record() before being written.
# ---------------------------------------------------------------------------

import random  # noqa: E402


def _mcq_distractors(rng, correct):
    offsets = [1, -1, 2, -2, 3, -3, 5, -5, 10, -10]
    rng.shuffle(offsets)
    distractors = []
    for offset in offsets:
        candidate = correct + offset
        if candidate != correct and candidate >= 0 and candidate not in distractors:
            distractors.append(candidate)
        if len(distractors) == 3:
            break
    return distractors


def generate_addition_subtraction_mcqs(count):
    rng = random.Random("addition-subtraction-mcq-seed")
    grade_configs = [("3", 10, 99), ("4", 100, 999), ("5", 200, 1999), ("6", 500, 4999)]
    seen = set()
    records = []
    while len(records) < count:
        grade, lo, hi = grade_configs[len(records) % len(grade_configs)]
        a, b = rng.randint(lo, hi), rng.randint(lo, hi)
        operation = "+" if len(records) % 2 == 0 else "-"
        if operation == "+":
            a, b = sorted((a, b), reverse=True)
        elif b > a:
            a, b = b, a
        key = (grade, operation, a, b)
        if key in seen:
            continue
        seen.add(key)
        correct = a + b if operation == "+" else a - b
        options = [str(correct)] + [str(value) for value in _mcq_distractors(rng, correct)]
        rng.shuffle(options)
        records.append((
            "Multiple Choice Question", grade, "Mathematics", "Addition and Subtraction",
            "Number Sense", "Applying", f"What is {a} {operation} {b}?", options, str(correct),
            f"{a} {operation} {b} = {correct}, computed by standard "
            f"{'addition' if operation == '+' else 'subtraction'}.", 1,
        ))
    return records


def generate_multiplication_fill_in_blanks(low=2, high=20):
    records = []
    for a in range(low, high + 1):
        for b in range(a, high + 1):
            correct = a * b
            records.append((
                "Fill in the Blank", "4", "Mathematics", "Multiplication", "Number Sense", "Remembering",
                f"{a} multiplied by {b} is ______.", [], str(correct),
                f"{a} x {b} = {correct}, recalled from the multiplication table of {a}.", 1,
            ))
    return records


def generate_number_comparison_true_false(count):
    rng = random.Random("true-false-comparison-seed")
    seen = set()
    records = []
    while len(records) < count:
        a, b = rng.randint(1, 500), rng.randint(1, 500)
        if a == b:
            continue
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        larger, smaller = max(a, b), min(a, b)
        statement_is_true = rng.choice([True, False])
        if statement_is_true:
            question, answer = f"{larger} is greater than {smaller}.", "True"
            explanation = f"{larger} is indeed greater than {smaller}, so the statement is true."
        else:
            question, answer = f"{smaller} is greater than {larger}.", "False"
            explanation = f"{smaller} is not greater than {larger}; the comparison is reversed, so the statement is false."
        records.append((
            "True or False", "3", "Mathematics", "Comparing Numbers", "Number Sense", "Understanding",
            question, [], answer, explanation, 1,
        ))
    return records


def generate_unit_conversion_vsa(count):
    rng = random.Random("unit-conversion-vsa-seed")
    conversions = [
        ("metres", "centimetres", 100), ("kilometres", "metres", 1000),
        ("kilograms", "grams", 1000), ("litres", "millilitres", 1000),
        ("hours", "minutes", 60), ("minutes", "seconds", 60),
    ]
    seen = set()
    records = []
    while len(records) < count:
        unit_from, unit_to, factor = rng.choice(conversions)
        value = rng.randint(2, 50)
        key = (unit_from, unit_to, value)
        if key in seen or key == ("metres", "centimetres", 3):
            # (metres, centimetres, 3) already exists as a hand-authored RAW_QUESTIONS entry.
            continue
        seen.add(key)
        result = value * factor
        records.append((
            "Very Short Answer Question", "4", "Mathematics", "Measurement", "Application", "Applying",
            f"Convert {value} {unit_from} into {unit_to}.", [], f"{result} {unit_to}",
            f"1 {unit_from} = {factor} {unit_to}, so {value} {unit_from} = {value} x {factor} = {result} {unit_to}.", 1,
        ))
    return records


def generate_simple_interest_saq(count):
    rng = random.Random("simple-interest-saq-seed")
    seen = set()
    records = []
    while len(records) < count:
        principal = rng.choice(range(500, 10001, 100))
        rate = rng.choice([2, 3, 4, 5, 6, 7, 8, 10, 12])
        time = rng.choice([1, 2, 3, 4, 5])
        key = (principal, rate, time)
        if key in seen:
            continue
        seen.add(key)
        interest = principal * rate * time // 100
        records.append((
            "Short Answer Question", "7", "Mathematics", "Simple Interest", "Application", "Applying",
            f"Find the simple interest on Rs. {principal} at {rate}% per annum for {time} years.",
            [], f"Rs. {interest}",
            f"SI = (P x R x T)/100 = ({principal} x {rate} x {time})/100 = {interest}.", 2,
        ))
    return records


def generate_perimeter_area_laq(count):
    rng = random.Random("perimeter-area-laq-seed")
    seen = set()
    records = []
    while len(records) < count:
        length, width = rng.randint(6, 60), rng.randint(3, 59)
        if width >= length:
            continue
        key = (length, width)
        if key in seen:
            continue
        seen.add(key)
        perimeter, area = 2 * (length + width), length * width
        records.append((
            "Long Answer Question", "5", "Mathematics", "Perimeter and Area", "Application", "Analyzing",
            f"A rectangular garden is {length} m long and {width} m wide. Find its perimeter and "
            "area, showing your working.", [], f"Perimeter = {perimeter} m; Area = {area} sq. m.",
            f"Perimeter = 2(length+breadth) = 2({length}+{width}) = {perimeter} m; "
            f"Area = length x breadth = {length} x {width} = {area} sq. m.", 3,
        ))
    return records


_ONES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _number_name(n):
    if n < 20:
        return _ONES[n].capitalize()
    tens, ones = divmod(n, 10)
    name = _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")
    return name.capitalize()


def generate_number_name_match_sets(count):
    rng = random.Random("number-name-match-seed")
    seen = set()
    records = []
    while len(records) < count:
        numbers = tuple(sorted(rng.sample(range(11, 99), 4)))
        if numbers in seen:
            continue
        seen.add(numbers)
        pairs = [f"A-{n} : B-{_number_name(n)}" for n in numbers]
        records.append((
            "Match the Following", "3", "Mathematics", "Number Names", "Number Sense", "Remembering",
            f"Match each number in Column A with its number name in Column B: "
            f"{', '.join(str(n) for n in numbers)}.", pairs, ", ".join(pairs),
            "Each numeral is matched to its correct English number name.", 2,
        ))
    return records


_CASE_NAMES = (
    "Riya", "Aman", "Sara", "Vikram", "Neha", "Karan", "Priya", "Rohan", "Ishaan", "Meera",
    "Aditi", "Farhan", "Kabir", "Simran", "Tara", "Yusuf", "Diya", "Arjun", "Lakshmi", "Omar",
)
_CASE_ITEMS = (
    "pencils", "marbles", "stickers", "stamps", "balloons", "books", "toys", "coins", "shells", "buttons",
)


def generate_case_based_word_problems(count):
    rng = random.Random("case-based-word-problem-seed")
    seen = set()
    records = []
    while len(records) < count:
        name, item = rng.choice(_CASE_NAMES), rng.choice(_CASE_ITEMS)
        first, second = rng.randint(5, 40), rng.randint(3, 40)
        key = (name, item, first, second)
        if key in seen:
            continue
        seen.add(key)
        total = first + second
        options = [str(total)] + [str(value) for value in _mcq_distractors(rng, total)]
        rng.shuffle(options)
        records.append((
            "Case Based Question", "4", "Mathematics", "Word Problems", "Application", "Analyzing",
            f"{name} had {first} {item}. A friend gave {name} {second} more {item}. {name} then "
            f"counted all the {item}. How many {item} does {name} have now?", options, str(total),
            f"{first} plus {second} equals {total}, so {name} has {total} {item}.", 2,
        ))
    return records


def generate_source_based_word_problems(count):
    rng = random.Random("source-based-word-problem-seed")
    seen = set()
    records = []
    while len(records) < count:
        name, item = rng.choice(_CASE_NAMES), rng.choice(_CASE_ITEMS)
        day1, day2 = rng.randint(5, 40), rng.randint(5, 40)
        key = (name, item, day1, day2)
        if key in seen:
            continue
        seen.add(key)
        total = day1 + day2
        options = [str(total)] + [str(value) for value in _mcq_distractors(rng, total)]
        rng.shuffle(options)
        records.append((
            "Source Based Question", "5", "Mathematics", "Word Problems", "Application", "Analyzing",
            f"Read the extract: '{name} collected {day1} {item} on Monday and {day2} {item} on "
            f"Tuesday.' Based on this extract, how many {item} did {name} collect in total?",
            options, str(total),
            f"{day1} plus {day2} equals {total}, so {name} collected {total} {item} in total.", 2,
        ))
    return records


def generate_number_comparison_assertion_reasoning(count):
    rng = random.Random("assertion-reasoning-comparison-seed")
    seen = set()
    records = []
    while len(records) < count:
        a, b = rng.randint(1, 200), rng.randint(1, 200)
        if a == b:
            continue
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        larger, smaller = max(a, b), min(a, b)
        records.append((
            "Assertion and Reasoning", "6", "Mathematics", "Comparing Numbers", "Number Sense", "Analyzing",
            f"Assertion (A): {larger} is greater than {smaller}.\n"
            f"Reason (R): {larger} comes after {smaller} when counting upward.\n"
            "Choose the correct option: (A) Both A and R are true and R correctly explains A. "
            "(B) Both A and R are true but R does not explain A. (C) A is true but R is false. "
            "(D) A is false but R is true.", [], "A",
            f"Since {larger} comes after {smaller} when counting upward, {larger} is greater than "
            f"{smaller}; the reason correctly explains the assertion.", 2,
        ))
    return records


def build_generated_questions():
    return (
        generate_addition_subtraction_mcqs(200)
        + generate_multiplication_fill_in_blanks(2, 20)
        + generate_number_comparison_true_false(150)
        + generate_unit_conversion_vsa(100)
        + generate_simple_interest_saq(100)
        + generate_perimeter_area_laq(60)
        + generate_number_name_match_sets(60)
        + generate_case_based_word_problems(60)
        + generate_source_based_word_problems(60)
        + generate_number_comparison_assertion_reasoning(60)
    )


def build_records():
    all_questions = RAW_QUESTIONS + build_generated_questions()
    records = []
    for index, (
        typology, grade, subject, chapter, competency, blooms_level,
        question, options, answer, explanation, marks,
    ) in enumerate(all_questions, start=1):
        record = {
            "id": f"QB-{index:06d}",
            "typology": typology,
            "grade": grade,
            "subject": subject,
            "chapter": chapter,
            "competency": competency,
            "blooms_level": blooms_level,
            "question": question,
            "options": options,
            "answer": answer,
            "explanation": explanation,
            "marks": marks,
            "content_hash": content_hash(question),
            "usage": {},
        }
        problems = validate_record(record)
        if problems:
            raise ValueError(f"Seed record {record['id']} failed validation: {problems}")
        records.append(record)

    hashes = [record["content_hash"] for record in records]
    duplicate_hashes = {h for h in hashes if hashes.count(h) > 1}
    if duplicate_hashes:
        raise ValueError(f"Seed batch contains duplicate question content: {duplicate_hashes}")

    return records


def main():
    import json

    records = build_records()
    output_path = Path(__file__).resolve().parents[1] / "data" / "question_bank" / "questions.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"Wrote {len(records)} questions to {output_path}")


if __name__ == "__main__":
    main()

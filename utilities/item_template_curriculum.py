"""Read the curriculum chain the item-upload template carries with it.

The template's dropdowns are backed by defined names holding the uploader's own
master data, laid out as a cascade:

    Grades
    G<g>_Subjects
    G<g>_S<s>_Books
    G<g>_S<s>_B<b>_Units              (absent for a subject with no unit data)
    G<g>_S<s>_B<b>_U<u>_Chapters      (chapters narrowed to one unit)
    G<g>_S<s>_B<b>_Chapters           (chapters for the whole book)
    G<g>_S<s>_Competencies
    G<g>_S<s>_C<c>_LOs

Tests read the chain from here rather than carrying an environment's master
data as literals - the tester-pack README has always warned that grade,
subject, chapter, competency and learning outcome have to be replaced when the
suite is pointed at a different environment, and Book and Unit are two more
values with the same problem.

Note the asymmetry this exists to make testable: `Unit` is optional. When it is
left blank the chapter list falls back to the book's full set, and a subject
with no units at all (Grade 1 Mathematics, at the time of writing) simply never
offers one - in the workbook or on the manual form.
"""

from openpyxl import load_workbook


class TemplateCurriculum:
    """The grade/subject/book/unit/chapter chain out of one template workbook."""

    def __init__(self, workbook):
        self._workbook = workbook

    @classmethod
    def from_path(cls, path):
        return cls(load_workbook(path))

    def close(self):
        self._workbook.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False

    # --- defined-name plumbing ------------------------------------------

    def values(self, name):
        """The non-empty values behind a defined name, or () if it has none.

        A missing name is a normal answer, not an error: `G1_S3_B1_Units` does
        not exist precisely because Grade 1 Mathematics has no units.
        """
        defined_name = self._workbook.defined_names.get(name)
        if defined_name is None:
            return ()
        collected = []
        for sheet_title, reference in defined_name.destinations:
            region = self._workbook[sheet_title][reference]
            if not isinstance(region, tuple):
                region = ((region,),)
            elif region and not isinstance(region[0], tuple):
                region = (region,)
            for row in region:
                for cell in row:
                    if cell.value not in (None, ""):
                        collected.append(str(cell.value))
        return tuple(collected)

    @staticmethod
    def _position(values, wanted):
        """The 1-based index the defined names use to refer to `wanted`."""
        for index, value in enumerate(values, start=1):
            if str(value).strip() == str(wanted).strip():
                return index
        raise LookupError(f"{wanted!r} is not one of {list(values)}")

    # --- the cascade ----------------------------------------------------

    def grades(self):
        return self.values("Grades")

    def subjects(self, grade):
        return self.values(f"G{self._position(self.grades(), grade)}_Subjects")

    def _grade_subject_prefix(self, grade, subject):
        grade_index = self._position(self.grades(), grade)
        subject_index = self._position(self.subjects(grade), subject)
        return f"G{grade_index}_S{subject_index}"

    def books(self, grade, subject):
        return self.values(f"{self._grade_subject_prefix(grade, subject)}_Books")

    def _book_prefix(self, grade, subject, book):
        prefix = self._grade_subject_prefix(grade, subject)
        return f"{prefix}_B{self._position(self.books(grade, subject), book)}"

    def units(self, grade, subject, book):
        """Units under a book - empty for a subject that has none."""
        return self.values(f"{self._book_prefix(grade, subject, book)}_Units")

    def chapters(self, grade, subject, book, unit=None):
        """Chapters for a book, or narrowed to one unit when `unit` is given."""
        book_prefix = self._book_prefix(grade, subject, book)
        if not unit:
            return self.values(f"{book_prefix}_Chapters")
        unit_index = self._position(self.units(grade, subject, book), unit)
        return self.values(f"{book_prefix}_U{unit_index}_Chapters")

    def competencies(self, grade, subject):
        return self.values(f"{self._grade_subject_prefix(grade, subject)}_Competencies")

    def learning_outcomes(self, grade, subject, competency):
        prefix = self._grade_subject_prefix(grade, subject)
        competency_index = self._position(self.competencies(grade, subject), competency)
        return self.values(f"{prefix}_C{competency_index}_LOs")

    def blooms_levels(self):
        return self.values("Blooms")

    # --- convenience ----------------------------------------------------

    def first_subject_with_units(self, grade, preferred=()):
        """(subject, book, units) for a subject offering unit data.

        `preferred` names subjects to try before the rest, in order. Callers use
        it when the choice matters for reasons outside the master data — a
        suite that creates item sets has to stay inside the scope other tests
        assert on, so it cannot simply take whichever subject happens to come
        first alphabetically.

        Returns (None, None, ()) when the grade has no such subject, which is
        the signal for a caller to skip a unit-specific scenario rather than
        invent a value the environment would reject.
        """
        available = self.subjects(grade)
        ordered = [subject for subject in preferred if subject in available]
        ordered += [subject for subject in available if subject not in ordered]
        for subject in ordered:
            for book in self.books(grade, subject):
                units = self.units(grade, subject, book)
                if units:
                    return subject, book, units
        return None, None, ()

    def row_for(self, grade, subject, book, unit=None):
        """A complete, internally consistent metadata row for one item.

        Chapter, competency and learning outcome are chosen from the ranges the
        template itself scopes to the choices above, so the row resolves against
        the environment's master data instead of relying on remembered values.
        """
        chapters = self.chapters(grade, subject, book, unit)
        competencies = self.competencies(grade, subject)
        competency = competencies[0] if competencies else ""
        outcomes = self.learning_outcomes(grade, subject, competency) if competency else ()
        blooms = self.blooms_levels()
        return {
            "grade": grade,
            "subject": subject,
            "book": book,
            "unit": unit or None,
            "chapter": chapters[0] if chapters else "",
            "competency": competency,
            "learning_outcome": outcomes[0] if outcomes else "",
            "blooms": blooms[0] if blooms else "Remembering",
        }

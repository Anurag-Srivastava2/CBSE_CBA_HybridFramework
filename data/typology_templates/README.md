# Item-Upload Templates — All 12 Typologies (Tester Pack)

One ready-to-upload Excel file per question typology. Every file uses the **25
canonical template columns** and is pre-filled with a **valid sample row** using
**real dev master data**. All 12 were verified on dev (`cba-api-dev-new`) on
2026-07-14: each uploads with `passedRows: 1, failedRows: 0`, and the review-grid
list projection (`GET /excel-import/:id/items`) renders every structured field
correctly.

| # | File | Typology | Sample marks |
|---|------|----------|------|
| 01 | `01_MCQ.xlsx`  | Multiple Choice Question | 1 |
| 02 | `02_TOF.xlsx`  | True or False | 1 |
| 03 | `03_MTF.xlsx`  | Match the Following | 1 |
| 04 | `04_FITB.xlsx` | Fill in the Blank | 1 |
| 05 | `05_AR.xlsx`   | Assertion and Reasoning | 1 |
| 06 | `06_VSAQ.xlsx` | Very Short Answer Question | 1 |
| 07 | `07_SAQ.xlsx`  | Short Answer Question | 2 |
| 08 | `08_LAQ.xlsx`  | Long Answer Question | 3 |
| 09 | `09_FAA.xlsx`  | FA Activity | 1 |
| 10 | `10_FR.xlsx`   | Free Response | 2 |
| 11 | `11_CABA.xlsx` | Case Based Question (parent + 2 sub-rows) | 2 |
| 12 | `12_SBQ.xlsx`  | Source Based Question (parent + 2 sub-rows) | 2 |

---

## ⚠️ Before you upload — account scope

The samples use this **real curriculum chain** (Grade 1 / Mathematics):

- **Grade:** `Grade 1`
- **Subject:** `Mathematics`
- **Book:** `Book 1`
- **Unit:** *(left empty — see below)*
- **Chapter No._Name:** `CH-1: Finding the Furry Cat! (Pre-number Concepts)`
- **Competency:** `Counts up to 99 both forwards and backwards and in groups of IOS and 20s`
- **Learning Outcome:** `Recognises quantities in groups of 2s`
- **Blooms Taxonomy:** `Remembering`

The importer resolves these **only within the uploader's scoped grade-subjects**.
So the SME/Teacher account you log in with **must be scoped to Grade 1 +
Mathematics**, otherwise the chapter/competency/LO won't resolve.

> On a **different environment (QA/UAT)** or a differently-scoped account, replace
> `Grade`, `Subject`, `Book`, `Unit`, `Chapter No._Name`, `Competency`,
> `Learning Outcome`, and `Blooms Taxonomy` with values that exist in **that**
> environment's master data.
> Competency must belong to the chapter's grade/subject, and the Learning Outcome
> must belong to that Competency, or the row will fail validation.

## How to upload

1. Log in as the scoped SME/Teacher.
2. Go to **Add Items → Upload File** (or `POST /excel-import/upload`, field
   `files`).
3. Pick one template file → the row is validated and, if clean, created as a
   **DRAFT** item.
4. Verify in the **Review & Tag** grid, then run QAR / send for review as usual.

Text-only samples need **no image zip**. Image columns (`Question Image`,
`Image 1-4`, `Answer Image`) are left blank — to test images you supply a
filename here and upload the matching zip in the 2-step staged flow.

---

## The 25 columns (fixed order)

```
Grade | Subject | Book | Unit | Chapter No._Name | S.No. | Competency |
Learning Outcome | Blooms Taxonomy | Explanation of Blooms Taxonomy |
Typology | Question | Question Image |
Option 1 | Option 2 | Option 3 | Option 4 |
Image 1 | Image 2 | Image 3 | Image 4 |
Answer | Answer Image | Explanation/Remarks | Marks
```

The single source of truth for this list is
`utilities/item_template_columns.CANONICAL_HEADERS`. Nothing in the suite writes
to a column by number: `resolve_columns(worksheet)` maps a field name to
whichever column the sheet in hand actually puts it in, which is what let Book
and Unit be inserted without renumbering nine sets of constants.

## Book and Unit

`Book` and `Unit` replaced the single `Unit/Theme` column that used to sit at
position 3, pushing `Chapter No._Name` and everything after it one column to the
right — `Marks` moved from X to **Y**.

- **`Book` is mandatory.** The manual authoring form renders it as `Book *`
  between `Subject *` and `Chapter *`, and the chapter list stays empty until a
  book is chosen.
- **`Unit` is optional**, and only exists where the master data has units for
  that subject. In this pack's Grade 1 / Mathematics chain there are none, so
  every sample leaves `Unit` empty and the chapter resolves against the book.
  Grade 1 / Hindi has five units; a row for it may fill `Unit`, and then the
  chapter has to be one that belongs to that unit.
- On multi-row **CABA / SBQ** samples, `Book` is filled on the parent row only.
  Sub-rows inherit it along with the rest of the metadata.

The dropdowns are backed by defined names inside the workbook
(`G<g>_S<s>_Books`, `G<g>_S<s>_B<b>_Units`,
`G<g>_S<s>_B<b>_U<u>_Chapters`, …). `utilities/item_template_curriculum.py`
reads that chain, so tests can pick a real book, unit and chapter for whatever
environment they are pointed at instead of hard-coding one.

## Refreshing these files

When the app's template changes again:

```bash
# the trimmed per-typology files, migrated in place
python tools/migrate_item_templates.py

# sme_sheet.xlsx, which keeps the lookup columns and so must be rebuilt
python tools/migrate_item_templates.py     --from-download ~/Downloads/item-set-template.xlsx     --sample-from data/upload_templates/sme_sheet.xlsx     data/upload_templates/sme_sheet.xlsx
```

## Per-typology format (how each maps the columns)

- **MCQ** — `Question` = stem; `Option 1-4` = choices A/B/C/D; `Answer` = the
  correct **letter** (`A`/`B`/`C`/`D`).
- **TOF** — `Question` = statement; `Answer` = `TRUE` or `FALSE`.
- **MTF** — `Question` = instruction line; `Option 1` = left-column **items**
  (`|`-separated); `Option 2` = right-column **matches** (`|`-separated, same
  count, may be scrambled); `Answer` = key `1-A, 2-B, 3-C` (number = item row,
  letter = match row). Option 3/4 unused.
- **FITB** — `Question` = text with blanks marked by **4+ underscores** `____`;
  `Answer` = the blank fills, **`|`-separated in order** (count must equal the
  number of `____`).
- **AR** — `Question` = one cell: `Assertion (A): … Reason (R): …` (split on
  `Reason (R):`); `Answer` = `A`/`B`/`C`/`D` (A: both true & R explains A · B:
  both true, R not the explanation · C: A true, R false · D: A false, R true).
  Option 1-4 are **ignored** (the 4 standard options are added by the backend).
- **VSAQ / SAQ / LAQ** — `Question` = question; `Answer` = model answer.
- **FR** — `Question` = question; `Answer` = sample answer.
- **FAA (FA Activity)** — `Question` = activity instructions. **NOTE:** an FA
  Activity has no answer key by design, but the importer **still requires the
  `Answer` column to be non-empty** — put the expected outcome / observation
  there (see "known quirk" below).
- **CABA / SBQ** — multi-row:
  - **Parent row** (`S.No.` = `1`): `Typology` = Case/Source Based Question;
    `Question` = the case passage / source; `Marks` = **sum of the sub-question
    marks**.
  - **Sub-rows** (`S.No.` = `1.1`, `1.2`, …): each has its own **leaf** typology
    (MCQ, VSAQ, TOF, …), its `Question` + options/answer, and its own `Marks`.
    Metadata columns (Grade/Subject/Chapter/etc.) can be left blank on sub-rows —
    they inherit from the parent. Sub-rows do **not** create their own items.

## Known quirk (flagged, not a template error)

**FAA requires the `Answer` column filled** even though FA Activity has no answer
key in the item schema. The sample works around it by putting the expected
outcome in `Answer`. If this is unintended, it's a small validator inconsistency
in the Excel import path (the generic "Answer required" rule + an
FAA-specific "Answer is required for FA Activity" config rule both fire on FAA).
Manual FAA creation via the form does not require an answer.

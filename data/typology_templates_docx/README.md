# Word item-upload templates

The `.docx` counterpart of `data/typology_templates/*.xlsx`. Same 25 canonical
fields, laid out down a two-column table (label left, value right) rather than
across a header row, one block per question.

| Files | What they cover |
|---|---|
| `01`–`12` | one text typology each, no images |
| `13`–`20` | image-bearing items (image in the question, or in the answer) |
| `images.zip` | the images `13`–`20` reference **by filename** |
| `img-src/` | the loose PNGs `images.zip` is built from |

Images are never embedded in the document. A document names an image in one of
its image fields and the file itself travels in `images.zip`, so uploading an
image-bearing item means staging **two** files, not one.

## Contract

`utilities/docx_item_template.py` reads and rewrites these without python-docx
(the framework does not ship it). `tests/M1_Item_Bank_Mgmt/test_docx_upload.py`
pins the contract in `TestDocxTemplateContract`, which needs no browser:

- all 20 documents carry the same 25 labels in the same order
- every image a document references exists in `images.zip`
- every declared `Typology` resolves to one the application offers

Run those three first after dropping in a new template revision — a drifted
template still opens and still looks valid, so without them a renamed label
surfaces much later as an unexplained row-validation failure.

Point `CBSE_DOCX_TEMPLATE_DIR` at a candidate drop to test it without a commit.

## Known differences from the application

`11_CaseBased.docx` and `12_SourceBased.docx` declare **"Case Based Questions"**
and **"Source Based Questions"** (plural). The application, the Excel typology
templates and the manual-item form all use the singular. An importer matching on
the exact string would reject both.

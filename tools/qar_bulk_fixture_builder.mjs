import fs from "node:fs/promises";
import path from "node:path";

import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";


const [templatePath, outputPath, scenarioJson] = process.argv.slice(2);
if (!templatePath || !outputPath || !scenarioJson) {
  throw new Error(
    "Usage: node qar_bulk_fixture_builder.mjs <template.xlsx> <output.xlsx> <scenario-json>",
  );
}

const scenario = JSON.parse(scenarioJson);
if (!String(scenario.prefix || "").startsWith("QAR_AUTO_")) {
  throw new Error(`Unsafe QAR fixture prefix: ${scenario.prefix}`);
}

const normalize = (value) => String(value || "")
  .trim()
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, "");

const input = await FileBlob.load(templatePath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheet = workbook.worksheets.getItemAt(0);
const outputDir = path.dirname(outputPath);
await fs.mkdir(outputDir, { recursive: true });

const baselinePreview = await workbook.render({
  sheetName: sheet.name,
  range: "A1:X8",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(outputDir, `${scenario.prefix} template before changes.png`),
  new Uint8Array(await baselinePreview.arrayBuffer()),
);

const templateValues = sheet.getRange("A1:X100").values;
const headers = templateValues[0];
const baseRow = templateValues[1];
const headerIndexes = new Map(headers.map((header, index) => [normalize(header), index]));

const findColumn = (aliases, required = true) => {
  for (const alias of aliases) {
    const normalizedAlias = normalize(alias);
    if (headerIndexes.has(normalizedAlias)) return headerIndexes.get(normalizedAlias);
  }
  for (const [header, index] of headerIndexes.entries()) {
    if (aliases.some(alias => header.includes(normalize(alias)))) return index;
  }
  if (required) {
    throw new Error(`Template is missing required header: ${aliases.join(" / ")}`);
  }
  return -1;
};

const columns = {
  grade: findColumn(["Grade"]),
  subject: findColumn(["Subject"]),
  chapter: findColumn(["Chapter"]),
  sequence: findColumn(["S No", "Serial Number", "Item Number"]),
  learningOutcome: findColumn(["Learning Outcome NCERT", "Learning Outcome", "LO"]),
  competency: findColumn(["Competency"]),
  questionType: findColumn(["Question Type", "Typology", "Item Type"]),
  question: findColumn(["Question Text", "Item Content", "Question", "Item"]),
  answer: findColumn(["Correct Answer", "Answer Key", "Answer"]),
  explanation: findColumn(["Explanation", "Rationale"]),
  marks: findColumn(["Marks", "Mark"]),
  optionA: findColumn(["Option A", "A"], false),
  optionB: findColumn(["Option B", "B"], false),
  optionC: findColumn(["Option C", "C"], false),
  optionD: findColumn(["Option D", "D"], false),
};

const validRow = (index, question) => {
  const row = [...baseRow];
  row[columns.sequence] = index + 1;
  row[columns.questionType] = "True or False";
  row[columns.question] = `${scenario.prefix} ${question}`;
  row[columns.answer] = "True";
  row[columns.explanation] = `${scenario.prefix} Valid automation explanation for item ${index + 1}.`;
  row[columns.marks] = 1;
  return row;
};

const buildRows = () => {
  const name = scenario.name;
  if (name === "positive") {
    return [
      validRow(0, "Is 15 minutes less than 30 minutes?"),
      validRow(1, "Does one hour contain sixty minutes?"),
    ];
  }
  if (name === "plagiarism_baseline") {
    return [validRow(0, "Does one hour contain sixty minutes?")];
  }
  if (name === "missing_question") {
    const row = validRow(0, "temporary question");
    row[columns.question] = null;
    return [row];
  }
  if (name === "missing_answer") {
    const row = validRow(0, "Does a clock show time?");
    row[columns.answer] = null;
    return [row];
  }
  if (name === "mcq_fewer_than_two_options") {
    if ([columns.optionA, columns.optionB].some(index => index < 0)) {
      throw new Error("MCQ scenario requires Option A and Option B headers.");
    }
    const row = validRow(0, "Which unit measures a short duration?");
    row[columns.questionType] = "MCQ";
    row[columns.optionA] = "Minute";
    row[columns.optionB] = null;
    if (columns.optionC >= 0) row[columns.optionC] = null;
    if (columns.optionD >= 0) row[columns.optionD] = null;
    row[columns.answer] = "A";
    return [row];
  }
  if (name === "missing_explanation") {
    const row = validRow(0, "Is noon later than morning?");
    row[columns.explanation] = null;
    return [row];
  }
  if (name === "invalid_question_type") {
    const row = validRow(0, "Is a minute a unit of time?");
    row[columns.questionType] = "Unsupported Automation Type";
    return [row];
  }
  if (name === "missing_marks") {
    const row = validRow(0, "Is an hour longer than a minute?");
    row[columns.marks] = null;
    return [row];
  }
  if (name === "wrong_chapter") {
    const row = validRow(0, "Does one day contain twenty four hours?");
    row[columns.chapter] = `${scenario.prefix} Shapes and Angles`;
    return [row];
  }
  if (name === "wrong_subject") {
    const row = validRow(0, "Is thirty minutes half an hour?");
    row[columns.subject] = "Environmental Science";
    return [row];
  }
  if (name === "invalid_learning_outcome") {
    const row = validRow(0, "Can a calendar measure days?");
    row[columns.learningOutcome] = `${scenario.prefix} NON EXISTING LEARNING OUTCOME`;
    return [row];
  }
  if (name === "bias") {
    return [validRow(0, "Are boys naturally better than girls at reading clocks?")];
  }
  if (name === "grammar") {
    return [validRow(0, "He go to school yesterday at eight clock is correct?")];
  }
  if (name === "clarity") {
    return [validRow(0, "What is it and when does that happen?")];
  }
  if (name === "duplicate") {
    return [
      validRow(0, "Does one hour contain sixty minutes?"),
      validRow(1, "Does one hour contain sixty minutes?"),
      validRow(2, "Is fifteen minutes one quarter of an hour?"),
    ];
  }
  if (name === "plagiarism_copy") {
    if (!scenario.sourceText) {
      throw new Error("plagiarism_copy requires sourceText.");
    }
    const row = validRow(0, "temporary copied question");
    row[columns.question] = scenario.sourceText;
    row[columns.explanation] = (
      `${scenario.prefix} Copied-item plagiarism automation evidence.`
    );
    return [row];
  }
  if (name === "blocker_precedence") {
    const row = validRow(0, "Are boys naturally better than girls at reading clocks?");
    row[columns.answer] = null;
    return [row];
  }
  throw new Error(`Unknown QAR fixture scenario: ${name}`);
};

const rows = buildRows();
sheet.getRange("A2:X100").clear({ applyTo: "contents" });
for (let index = 0; index < rows.length; index += 1) {
  const rowNumber = index + 2;
  if (index > 0) {
    sheet.getRange(`A${rowNumber}:X${rowNumber}`).copyFrom(
      sheet.getRange("A2:X2"),
      "all",
    );
  }
  sheet.getRange(`A${rowNumber}:X${rowNumber}`).values = [rows[index]];
}

const inspection = await workbook.inspect({
  kind: "table",
  range: `A1:X${rows.length + 1}`,
  include: "values,formulas",
  tableMaxRows: rows.length + 1,
  tableMaxCols: 24,
  maxChars: 8000,
});

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "QAR fixture formula error scan",
});

const preview = await workbook.render({
  sheetName: sheet.name,
  range: `A1:X${rows.length + 1}`,
  scale: 1,
  format: "png",
});
const previewPath = outputPath.replace(/\.xlsx$/i, " preview.png");
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

process.stdout.write(JSON.stringify({
  outputPath,
  previewPath,
  prefix: scenario.prefix,
  scenario: scenario.name,
  rowCount: rows.length,
  inspection: inspection.ndjson,
  formulaErrors: formulaErrors.ndjson,
}));

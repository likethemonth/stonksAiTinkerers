import fs from "node:fs";
import path from "node:path";
import XLSX from "xlsx";

const root = path.resolve(import.meta.dirname, "..");
const resultPath = path.join(root, "research", "backtest-results.json");
const payload = JSON.parse(fs.readFileSync(resultPath, "utf8"));

const targets = new Map([
  ["Home Depot", "HD-FY2026Q2.xlsx"],
  ["Analog Devices", "ADI-FY2026Q3.xlsx"],
  ["Hays plc", "HAS-FY2026.xlsx"],
  ["Deere & Company", "DE-FY2026Q3.xlsx"],
]);

fs.mkdirSync(path.join(root, "submission"), { recursive: true });
for (const [company, filename] of targets) {
  const source = path.join(root, "challenge", "templates", filename);
  const output = path.join(root, "submission", filename);
  const workbook = XLSX.readFile(source, { cellStyles: true });
  const sheet = workbook.Sheets.Summary;
  const forecasts = payload.forecasts.filter((item) => item.company === company);
  for (const item of forecasts) {
    let matched = false;
    for (let row = 7; row <= 9; row += 1) {
      if (sheet[`A${row}`]?.v === item.metric) {
        sheet[`C${row}`] = { t: "n", v: Number(item.forecast) };
        matched = true;
      }
    }
    if (!matched) throw new Error(`Template metric not found: ${company} / ${item.metric}`);
  }
  if (forecasts.length !== 3) throw new Error(`Expected 3 forecasts for ${company}, got ${forecasts.length}`);
  XLSX.writeFile(workbook, output, { cellStyles: true });
  console.log(`Wrote ${path.relative(root, output)}`);
}

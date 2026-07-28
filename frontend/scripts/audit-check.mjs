// Аудит прод-зависимостей с управляемым списком исключений (задача 41, 28.07).
//
// Зачем не голый `npm audit --audit-level=high`: он валит сборку на любую
// advisory в пакете, даже если уязвимая ФУНКЦИЯ у нас не используется. Выбор
// «уронить CI или отключить аудит целиком» плохой — нужен третий вариант:
// пропустить конкретную запись, записав причину и дату пересмотра.
//
// Запуск: node scripts/audit-check.mjs   (npm run audit)
// Исключения: audit-allowlist.json рядом с package.json.
import { execSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";

const allowlist = existsSync("audit-allowlist.json")
  ? JSON.parse(readFileSync("audit-allowlist.json", "utf8"))
  : { ignore: [] };

let report;
try {
  // npm audit возвращает ненулевой код при находках — вывод всё равно читаем
  report = execSync("npm audit --omit=dev --json", { encoding: "utf8" });
} catch (e) {
  report = e.stdout;
}

const { vulnerabilities = {} } = JSON.parse(report);
const SEVERITY = ["high", "critical"];   // low/moderate не блокируют

const blocking = [];
const ignored = [];

for (const [name, vuln] of Object.entries(vulnerabilities)) {
  if (!SEVERITY.includes(vuln.severity)) continue;
  for (const via of vuln.via) {
    if (typeof via !== "object") continue;          // строка = ссылка на другой пакет
    const rule = allowlist.ignore.find((i) => i.id === via.url || i.id === via.source);
    if (rule) {
      ignored.push(`${name}: ${via.title} — ${rule.reason}`);
    } else {
      blocking.push(`${vuln.severity.toUpperCase()} ${name}: ${via.title}\n    ${via.url}`);
    }
  }
}

for (const line of ignored) console.log("пропущено (в allowlist) →", line);

if (blocking.length) {
  console.error("\nНайдены уязвимости без обоснования:\n");
  for (const line of blocking) console.error("  " + line);
  console.error(
    "\nЛибо обновите пакет, либо добавьте запись в audit-allowlist.json " +
      "с причиной и датой пересмотра.",
  );
  process.exit(1);
}

console.log(`Аудит пройден: блокирующих уязвимостей нет (пропущено: ${ignored.length}).`);

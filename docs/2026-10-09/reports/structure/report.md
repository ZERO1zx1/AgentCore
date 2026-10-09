# AgentCore-ийн бүтцийн асуудлууд

Шалгасан огноо: 2026-10-09. Хамрах хүрээ: local Python source, TypeScript
package-ийн entry point/config, skill installer, үндсэн заавар, scan-ийн
файл сонголт. GitHub болон website-ийн шинэ судалгаа энэ шалгалтад хийгдээгүй.

## Юу олсон бэ?

7 асуудал/сайжруулах санал байна: HIGH 1, MEDIUM 4, LOW 2.
Хамгийн түрүүнд **TypeScript → Python bridge-ийн entry point** болон
**skill-ийн хоёр өөр жагсаалтыг** цэгцлэх хэрэгтэй. Шинээр нэмсэн
`deep_scan.py`-ийн бүтэц, scanner-ийн түр файл шүүх дүрэмд ч засвар шаардлагатай.

| № | Асуудал | Түвшин | Одоогийн төлөв |
|---|---|---|---|
| 1 | Bridge-ийн Python эхлүүлэх тохиргоо буруу | HIGH | Нэгтгэсэн аргументтай эхлүүлэлт алдааг дахин гаргасан |
| 2 | Skill файлууд ба installer-ийн жагсаалт зөрдөг | MEDIUM | Кодын урсгалаар баталсан |
| 3 | Deep scan-ийн өөр өөр үүрэг нэг файлд холилдсон | MEDIUM | Бүтцийн эрсдэл; энэ нь runtime failure биш |
| 4 | Тестийн runtime файлууд scan-д орж байна | MEDIUM | Файл сонголт ба AST шалгалтаар баталсан |
| 5 | Зааварт байхгүй тест, команд дурдагдсан | MEDIUM | Path болон parser-ийн кодоор баталсан |
| 6 | Ingestion-ийн SHA-256 код давхардсан | LOW | Function body ижил; нэгтгэх эсэхийг API тестээр шийднэ |
| 7 | Memory-ийн хоёр системийн ownership тодорхойгүй | LOW | Хоёр тусдаа үүрэгтэй; шууд устгах үндэслэлгүй |

## 1. Bridge-ийн entry point — HIGH

- Байршил: `packages/agentcore-assistant/src/config.ts:88`, `:187`;
  `packages/agentcore-types/src/bridge.ts:28`;
  `packages/agentcore-assistant/src/bridge.ts:73`.
- Баталсан шалтгаан: `engineModule` нь `'-m src.core.engine'` гэсэн нэг string.
  `spawn()` үүнийг нэг аргумент болгон өгдөг. Python нь `-m` болон module нэрийг
  тусдаа аргумент болгох шаардлагатай.
- Бодит үр дүн: ижил аргументтай Python эхлүүлэхэд
  `ModuleNotFoundError: No module named ' src'` гарсан.
- Нэмэлт хил: source-д bridge request dispatch бүхий Python entry point олдоогүй;
  `src/README.md:32` нь stdio bridge байгаа гэж бичсэн. Аргументыг салгах дан
  өөрчлөлтөөр JSON Lines протокол ажиллана гэж батлах боломжгүй.
- Нөлөө: анхдагч тохиргоогоор TypeScript assistant Python engine-тэй холбогдох
  эхний алхам дээр зогсох эрсдэлтэй. Бүрэн end-to-end холболт энэ удаад ажиллуулаагүй.
- Санал: тусдаа `src/bridge/` entry point үүсгэж, Python executable, `-m`, module,
  transport аргументыг тусад нь өгнө. Request/response dispatch болон stderr/stdout
  дүрмийг нэг contract-оор батална.
- Дахин шалгах: бодит child process-той health-check, initialize/status/cancel,
  алдаатай JSON ба процесс хаагдах integration тест.
- Итгэлцэл: 0.99 (аргументын алдаа); status: BLOCKED; proposed by: ai-agent;
  confirmed by: PENDING. Class: TEST FAILURE (тусгаарласан эхлүүлэлт).

## 2. Skill-ийн эх сурвалж хоёр болсон — MEDIUM

- Байршил: `plugin/agents.py:91`, `plugin/install.py:50`, `:54`, `:56`;
  `skills/full-scan/SKILL.md:1`, `skills/deep-research-scan/SKILL.md:1`.
- Баталсан шалтгаан: installer canonical `skills/`-ийг security scan хийдэг ч
  install хийхдээ `DEFAULT_SKILLS` доторх өөр inline текстийг ашигладаг.
- Бодит жагсаалт: canonical skill нь `code-engineer`, `credit-safe-agent`,
  `full-scan`, `deep-research-scan`. Installer-ийнх `adaptive-omni-agent`,
  `code-engineer`, `credit-safe-agent`.
- Нөлөө: шинэ хоёр scan skill install selection-д орсон ч registry-д байхгүй тул
  `continue` хийнэ. Security scan-д орсон текст ба суулгах текст өөр байх боломжтой.
- Санал: canonical `skills/<name>/SKILL.md`-ийг уншиж scan/install хоёуланд нь
  ижил bytes ашиглах. Internal adaptive routing-ийг public skill гэж суулгах эсэх
  бодлогыг `plugin/README.md:59`-тэй нийцүүлнэ.
- Дахин шалгах: temp target дээр scan skill-үүдийг сонгож суулгах тест; canonical
  болон суулгасан файлын hash ижил эсэх; unknown skill дээр ил тод алдаа.
- Итгэлцэл: 0.99. Status: STATIC-RISK; class: UNKNOWN (source-confirmed contract
  mismatch); proposed by: ai-agent; confirmed by: PENDING. Бодит agent руу install хийгээгүй.

## 3. `deep_scan.py` олон үүрэгтэй — MEDIUM

- Байршил: `src/deep_scan.py:26`, `:63`, `:130`, `:167`, `:207`, `:298`,
  `:326`, `:343`, `:365`; `src/deep_scan.py:18`; `src/full_scan.py:43`.
- Баталсан шалтгаан: 385 мөртэй нэг файлд HTTP client, upstream code/document
  collector, dependency inventory, AST architecture, orchestrator, Markdown,
  SVG, HTML, artifact persistence хамт байна. Мөн өөр module-ийн private
  `_files` helper-ийг import хийдэг.
- Таамагласан эрсдэл: тайлангийн жижиг өөрчлөлт collector-тэй нэг module-ийг
  өөрчилдөг тул ownership, regression scope, дахин ашиглалтыг хүндрүүлнэ.
- Санал: `src/scanning/` гэсэн нэг ownership-той package дотор discovery,
  static scan, dependencies, architecture, research client/sources, reporting,
  service гэсэн үүргээр салгана. Одоогийн public import-уудыг compatibility
  wrapper-аар хадгална.
- Нөлөө: CLI болон `tests/test_full_scan.py`, `tests/test_deep_scan.py` import-ууд.
- Дахин шалгах: scanner regression, CLI JSON contract, approval/request-limit,
  secret redaction, өмнөх artifact layout-ийн тест.
- Итгэлцэл: 0.97. Status: STATIC-RISK; class: UNKNOWN; proposed by: ai-agent;
  confirmed by: PENDING. Олон мөртэй байх нь дангаараа алдаа биш; үүргийн хольц нь үндэслэл.

## 4. Түр тестийн файлууд төслийн кодтой холилддог — MEDIUM

- Байршил: `src/full_scan.py:39`, `:43`, `:46`; `src/deep_scan.py:169`.
- Баталсан шалтгаан: skip жагсаалт `.test-temp`-ийг хасдаг ч
  `.test_private_artifacts`-ийг хасдаггүй.
- Бодит үр дүн: одоогийн walker энэ хавтсаас 586 файл сонгосон. AST шалгалтын
  6 parse boundary бүгд энд хадгалагдсан зориудаар malformed test fixture байсан.
- Нөлөө: түр fixture-ийн алдаа төслийн source-ийн алдаа мэт тайланд орж,
  файл/модуль тоо болон architecture-г бохирдуулж болно.
- Санал: source discovery-д runtime fixture directories-ийг хасах дүрмийг
  нэг газар төвлөрүүлэх. `tests/` доторх жинхэнэ regression тестийг хэвээр шалгана.
  Бүх dot-folder-ийг сохроор хасахгүй; `.github` зэрэг бодит config хэрэгтэй.
- Дахин шалгах: excluded runtime fixture scan-д орохгүй, tracked test/config
  файл орохыг батлах regression тест. Дараа нь local report дахин гаргах.
- Итгэлцэл: 1.00. Status: STATIC-RISK; class: UNKNOWN (source-selection defect);
  proposed by: ai-agent; confirmed by: PENDING. Fixture-г устгах шаардлагагүй.

## 5. Заавар бодит файлуудтай нийцэхгүй — MEDIUM

- Байршил: `AGENTS.md:3`, `:21`; `src/cli/README.md:9`;
  `src/cli/main.py:29`; `skills/README.md:6`; `src/README.md:8`.
- Баталсан шалтгаан: зааврын `skills/adaptive-local-memory/scripts/test_memory.py`
  файл байхгүй. `skill` CLI команд зааварт байна, parser-т бүртгээгүй.
  Skill index-д scan skill-үүд, source ownership хүснэгтэд `adaptive/` болон
  scan module-ууд тусгагдаагүй.
- Нөлөө: contributor байхгүй тест/команд ажиллуулах, module-ийн үүргийг буруу
  ойлгох, шаардлагатай validation-г алгасах боломжтой.
- Санал: хэрэгжсэн command/file-ээр index болон guide-уудыг нэг удаа нийцүүлэх.
  Хэрэгжээгүй bridge protocol-ийг implemented гэж бичихгүй. Шалгалтын command-ууд
  нь бодит байгаа тест рүү заана.
- Дахин шалгах: `python -m src.cli --help`, guide-ийн local path existence,
  CLI dispatch coverage; зааварт үлдсэн бүх test target байгаа эсэх.
- Итгэлцэл: 0.99. Status: STATIC-RISK; class: UNKNOWN; proposed by: ai-agent;
  confirmed by: PENDING. Энэ тайлангаар AGENTS.md-г өөрчлөөгүй.

## 6. SHA-256 implementation давхардсан — LOW

- Байршил: `src/ingestion/structured.py:14`, `src/ingestion/text.py:18`.
- Баталсан шалтгаан: `_sha256_file()` болон `compute_fingerprint()`-ийн body
  AST ижил: binary file нээж 8192-byte chunk-ээр SHA-256 тооцдог.
- Нөлөө: chunk/read/error handling шинэчлэл хоёр газар зөрөх боломжтой.
- Санал: shared helper-ийг `src/ingestion/fingerprints.py`-д гаргах; одоогийн
  `TextProcessor.compute_fingerprint` public method-ийг delegate хэлбэрээр хадгалах.
- Дахин шалгах: empty/binary/multi-chunk file дээр өмнөхтэй hash ижил, missing
  path exception contract хадгалагдсан эсэх; ingestion болон checkpoint тестүүд.
- Итгэлцэл: 1.00 (ижил body); хэрэгжүүлэх ач холбогдол: LOW. Status: STATIC-RISK;
  class: UNKNOWN; proposed by: ai-agent; confirmed by: PENDING.

## 7. Memory-ийн ownership-ийг тайлбарлах хэрэгтэй — LOW

- Байршил: `src/core/engine.py:29`, `:67`; `src/memory/store.py:18`;
  `src/adaptive/store.py:39`, `:46`; `src/memory/README.md:3`; `src/README.md:8`.
- Баталсан зүйл: engine нь `LocalMemoryStore` ашигладаг. `AdaptiveMemoryStore`
  тусдаа module ба тусдаа тесттэй; `src/` дотор түүн рүү import хийсэн код нь
  adaptive package дотроо байна. Хоёул `.agent-memory` дотор өөр файлууд хадгалдаг.
- Таамагласан эрсдэл: нэр болон storage root төстэй тул хоёр store-ийг нэг
  систем гэж андуурч магадгүй. Энэ нь ижил implementation эсвэл dead code гэдгийг
  нотлохгүй; гаднын хэрэглэгч байгаа эсэхийг local imports дангаар мэдэхгүй.
- Санал: `src/adaptive/README.md` нэмэх; runtime lesson memory ба optional adaptive
  memory/research subsystem-ийн owner, API, data file, integration boundary-г
  ялгаж тайлбарлах. Нэгтгэх/устгах шийдвэрийг тусдаа migration review-ээр гаргах.
- Дахин шалгах: `tests/test_adaptive_memory.py`, `tests/test_advanced_memory.py`,
  `tests/test_memory_governance.py`; хадгалалтын contract-уудыг харьцуулах.
- Итгэлцэл: 0.95 (ownership gap). Status: STATIC-RISK; class: UNKNOWN;
  proposed by: ai-agent; confirmed by: PENDING.

## Засах дараалал

1. Bridge-ийн startup + protocol contract-ийг засч integration тестээр батлах.
2. Canonical skill source-ийг scan/install-д нэг болгох.
3. Runtime fixture exclusion болон contributor guide-ийн зөрчлийг засах.
4. Scanner package-д үүргүүдийг салгах; хуучин public import-уудыг хадгалах.
5. Hash helper-ийг нэгтгэх, memory ownership-ийг баримтжуулах.

`feat/low_cost_skill/` тусдаа POC хэвээр, Python engine нь core хэвээр,
TypeScript нь supporting layer хэвээр байх саналтай. Budget-ийн Decimal,
15% reserve, checkpoint schema-г энэ бүтцийн санал өөрчлөхгүй.

Энэ удаад relocation/refactor хийгээгүй. Шалгалтын нотолгоо:
[evidence.md](evidence.md). Санал болгосон бүтэц:
[proposed-structure.md](proposed-structure.md).

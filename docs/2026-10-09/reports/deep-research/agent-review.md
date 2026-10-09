# Шинэ skill-ийн бодит туршилт

Огноо: 2026-10-09. Skill: `deep-research-scan`.
Хамрах хүрээ: AgentCore local source + public GitHub origin + **pypdf**.
Өмнөх зөвшөөрсөн scope-ийг ашигласан. Runtime код, dependency, installer болон
bridge-г энэ туршилтаар өөрчлөөгүй.

## Гол үр дүн

Шинэ skill-ийг ажиллуулж, collector-ийн үр дүн дээр agent review хийсэн.
**Local Python орчин dependency шаардлагатайгаа нийцэхгүй**, мөн
**суулгасан PDF parser security advisory-ийн affected range-д орж байна**.
17 focused тест тэнцсэн ч энэ нь malicious PDF-ийн эрсдэлгүй гэсэн баталгаа биш.

| Шалгасан зүйл | Бодит үр дүн | Утга |
|---|---|---|
| Local scan | 43 configured static findings, 330 dependency declarations | Батлагдсан 43 runtime bug гэсэн үг биш; declaration count нь unique package count биш |
| pypdf шаардлага | `requirements.txt:1` → `>=6.1.3` | Төслийн зарласан minimum |
| Энэ Python-д суулгасан | `6.1.1` | Minimum шаардлагыг хангахгүй |
| PyPI latest | `6.20.0`, Python `>=3.9` | Upgrade candidate; compatibility батлагдаагүй |
| GitHub main vs local committed HEAD | `identical`, ahead/behind 0 | Working-tree өөрчлөлтүүд remote comparison-д орохгүй |
| OSV exact-version query | 95 advisory records | Alias duplicates орсон; 95 тусдаа reachable vulnerability гэж үзэхгүй |
| Local focused tests | 17 passed | PDF/scanner-ийн сонгосон regression behavior ажилласан |

PyPI metadata-г [official registry](https://pypi.org/project/pypdf/6.20.0/)-оос,
security claim-ийг maintainer advisory ба exact installed version-оор шалгасан.
6.20.0-ийн license compatibility-г энэ удаад дүгнээгүй; collector-ийн legacy
license field null байсан.

## 1. Суулгасан хувилбар requirement-ээс бага — HIGH

- Location: `requirements.txt:1`; current interpreter-ийн package metadata.
- Баталсан шалтгаан: declaration нь `pypdf>=6.1.3`, `python` command-аар
  ажилласан Python 3.13.15-д `pypdf==6.1.1` байна.
- Reproduce: `python -c "import pypdf; print(pypdf.__version__)"`.
- Expected / actual: `>=6.1.3` / `6.1.1`.
- Impact: PDF боловсруулах dependency орчин төслийн шаардлагатай зөрсөн.
  Өөр virtualenv/deployment-ийн хувилбарыг энэ шалгалтаар тогтоогоогүй.
- Fix санал: project environment-ийг тодорхойлж, security/release review хийсэн
  хувилбараар dependency-г суулгах; environment reconciliation хийсний дараа PDF
  болон engine regression ажиллуулах. Энэ turn-д install хийгээгүй.
- Re-validate: `python -m pytest tests/test_pdf.py -q`, дараа нь engine suite.
- Confidence: 1.00. Class: ENV FAILURE. Status: BLOCKED (environment alignment
  pending). Proposed by: ai-agent. Confirmed by: PENDING.

## 2. PDF reader-ийн нөхцөл security advisory-тэй таарч байна — MEDIUM

- Location: `src/ingestion/router.py:46`, `:48`, `:55`;
  `src/ingestion/pdf.py:42`, `:73`, `:100`.
- Баталсан зүйл: project `PdfReader(path)` ашиглаж, `strict`-ийг өгөөгүй.
  Суулгасан 6.1.1 API-д default нь `False`.
- [GHSA-4xc4-762w-m6cg / CVE-2026-22690](https://github.com/py-pdf/pypdf/security/advisories/GHSA-4xc4-762w-m6cg)
  нь `<6.6.0` хувилбарын non-strict reader дээр missing `/Root`, том `/Size`
  бүхий PDF-ээс удаан processing үүсэхийг тайлбарлаж, `>=6.6.0`-д тухайн
  issue засагдсан гэж мэдээлсэн. Maintainer severity нь Moderate.
- Local → upstream холбоос: installed `_reader.py:199`-ийн recovery loop нь
  `/Size`-ийн тоогоор давтдаг. Commit-pinned upstream `_reader.py`-д recovery
  limit болон limit хүрэхэд exception байна.
- [Шалгасан upstream code](https://github.com/py-pdf/pypdf/blob/0309ab701a192fbd3228701a44dd009765a1629b/pypdf/_reader.py#L210),
  [fix PR](https://github.com/py-pdf/pypdf/pull/3594),
  [6.1.1 API](https://pypdf.readthedocs.io/en/6.1.1/modules/PdfReader.html).
- Impact: malformed/untrusted PDF-ийг боловсруулах local path байгаа тул энэ
  advisory-ийн code-path exposure үндэслэлтэй. Malicious PDF exploit ажиллуулж
  DoS-ийг бодитоор давтаж үзээгүй; deployment exposure тодорхойгүй.
- Fix санал: patched maintained version сонгон changelog/API compatibility-г
  шалгаж upgrade хийх. `6.6.0` нь зөвхөн энэ нэг advisory-ийн fix threshold;
  бусад advisory-г бүхэлд нь зассан хамгийн сүүлийн safe version гэж үзэхгүй.
  Strict mode нь workaround боловч зөв PDF-үүдэд compatibility tradeoff бий.
- Re-validate: normal, malformed, encrypted/blank PDF, dependency-missing
  behavior болон bounded processing-ийн regression.
- Confidence: 0.99 (affected version/default reader condition).
  Class: UNKNOWN (source-confirmed exposure, exploit untested).
  Status: STATIC-RISK. Proposed by: ai-agent. Confirmed by: PENDING.

## 3. Collector-ийн source selection хангалттай оновчтой биш — MEDIUM

- Location: `src/deep_scan.py:103` болон upstream sample selection.
- Evidence: auto-selected хоёр Python sample нь
  `.github/scripts/check_gh_pages_updates.py`, `.github/scripts/check_pr_title.py`.
- Root cause: жижиг Python файлуудыг path-аар эрэмбэлээд эхний хоёрыг авдаг;
  local project ашигладаг `PdfReader`/text-extraction runtime code-ийг
  relevance-аар сонгодоггүй.
- Impact: tree/doc fingerprint авч чадсан ч dependency code review-ийн
  гол асуултад тохирохгүй sample сонгож болно.
- Энэ skill run-д agent local caller-ийг уншаад relevant upstream
  `pypdf/_reader.py`-ийг commit-pinned URL-аар тусад нь шалгасан.
- Fix санал: local imports/API usage → upstream relevant source selection;
  `.github` tooling-ийг runtime sample-ээс ялгах; fallback selection-ийг тайлбарлах.
- Re-validate: fixture repo-д tooling + runtime source байхад runtime source
  сонгосон эсэх, request cap хадгалагдсан эсэх.
- Confidence: 1.00. Class: UNKNOWN. Status: STATIC-RISK.
  Proposed by: ai-agent. Confirmed by: PENDING. Collector код энэ turn-д өөрчлөгдөөгүй.

## 4. Installed-version мэдээлэл collector-д автоматаар орохгүй — MEDIUM

- Location: `src/deep_scan.py:130`, `:257` орчмын inventory/research logic.
- Evidence: declaration range тул collector `version=null`, advisory status
  `UNKNOWN` өгсөн. Agent `importlib.metadata`-аар actual installed version
  тогтоож, тусдаа exact-version OSV query хийсэн.
- Root cause: declared/locked inventory бий; current interpreter metadata
  reconciliation одоогоор collector-ийн өөрийн workflow-д байхгүй.
- Impact: range-based Python project дээр agent-ийн нэмэлт алхамгүйгээр installed
  package-ийн security exposure шалгагдахгүй.
- Fix санал: interpreter scope тодорхой provenance-тэй optional installed-version
  inventory нэмэх; version range-ийг installed гэж орлуулахгүй.
- Re-validate: declaration, lock, installed mismatch болон package-not-installed
  тохиолдлыг тусад нь шалгах.
- Confidence: 1.00. Class: UNKNOWN. Status: STATIC-RISK.
  Proposed by: ai-agent. Confirmed by: PENDING.

## Бүтцийн өмнөх findings

Runtime fixture contamination дахин гарсан: 6 parse boundary бүгд
`.test_private_artifacts` дотор байна. Давхардсан ingestion SHA-256 helper болон
bridge/installer ownership issues-ийн дэлгэрэнгүйг
[бүтцийн тайлан](../structure/report.md)-д үзнэ. Эдгээрийг энэ run-д зассан гэж
тэмдэглээгүй. `PDFProcessor.compute_fingerprint()` мөн төстэй hashing хийдэг;
өмнөх AST exact-body scan нь argument нэрийн ялгаатай тул түүнийг ижил group-д
оруулаагүй. Энэ нэмэлт candidate нь manual review шаардлагатай.

## Энгийн architecture тайлбар

```text
PDF файл
   ↓
InputRouter             src/ingestion/router.py
   ↓
PDFProcessor            src/ingestion/pdf.py
   ↓
pypdf.PdfReader         энэ Python орчинд 6.1.1
   ↓
Page text extraction
   ↓
Persisted chunk files   .agentcore/... эсвэл context_dir
```

Энэ жижиг зураглал нь source-д уншсан caller → consumer → persisted output
замыг тайлбарлаж байна. Хар-цагаан, диаграммын нэг холбоос нэг алхамтай.
Chunk path болон `state_dir/context_dir`-ийн сонголт нь дуудсан method-оос хамаарна.

## Шалгалт ба usage

- `python -m pytest tests/test_deep_scan.py tests/test_full_scan.py tests/test_pdf.py -q`:
  **17 passed in 2.28s**.
- Collector: 12 actual requests, 14 request cap.
- Stored exact-version OSV query: 1 additional request; persisted report count 13.
- OSV-ийн эхний diagnostic query тусдаа 1 request хийсэн. Website browsing,
  sandbox-д бүтэлгүйтсэн оролдлогууд persisted collector count-д орохгүй.
- `evidence/report.json` дотор installed version, 95 raw advisory record-ийн
  metadata/aliases/reference болон source fingerprint хадгалсан.
- Энэ нь account usage хувь эсвэл model tokens гэсэн хэмжүүр биш.
  Collector төлбөртэй model дуудаагүй. Энэ чат дахь agent-ийн account хэрэглээ
  болон provider billing-г дээрх request count-оос тооцоогүй.
- Full engine suite, exploit reproduction, upgrade compatibility, deployment
  behavior, бусад 329 dependency declaration энэ run-д шалгагдаагүй.

## Дараагийн хийх ажил

1. pypdf environment mismatch ба security upgrade review-г эхэлж шийдэх.
2. Collector-д relevant source selection, installed-version reconciliation нэмэх.
3. Өмнөх structure report-ийн bridge/installer/runtime fixture issues-г засах.
4. Өөрчлөлт тус бүрийг focused regression, дараа нь cross-boundary engine tests-ээр батлах.

# Санал болгож буй бүтэц

Доорх `scanning/`, `bridge/`, `fingerprints.py` нь **санал**;
одоогоор үүсгээгүй, implemented architecture гэж үзэхгүй.

```text
AgentCore/
├── src/                         Python core
│   ├── core/                    Engine, planner, executor
│   ├── budget/                  Decimal budget, reserve
│   ├── checkpoint/              Persist, resume
│   ├── scanning/                Full Scan + Deep Research
│   │   ├── discovery.py         File scope, excludes
│   │   ├── findings.py          Finding contract
│   │   ├── static.py            Local rules
│   │   ├── dependencies.py      Declared/locked inventory
│   │   ├── architecture.py      AST, structure, duplicates
│   │   ├── research/
│   │   │   ├── client.py        Request limits, source allowlist
│   │   │   └── sources.py       GitHub, PyPI, OSV evidence
│   │   ├── reporting.py         Markdown, JSON, optional HTML/SVG
│   │   └── service.py           Discovery → research → report
│   ├── bridge/                  TS ↔ Python protocol entry point
│   ├── ingestion/
│   │   └── fingerprints.py      Shared file hashing
│   ├── memory/                  Engine lesson memory
│   ├── adaptive/                Optional memory/research APIs
│   ├── full_scan.py             Compatibility wrapper
│   └── deep_scan.py             Compatibility wrapper
├── packages/                    TypeScript supporting layer
├── skills/                      Canonical skill instructions
├── plugin/                      Scan/install canonical skills
├── tests/                       Python regression + bridge tests
├── feat/                        Independent POCs
├── examples/                    Example applications
└── docs/YYYY-MM-DD/reports/
    ├── structure/               Бүтцийн асуудал, шилжилтийн санал
    └── deep-research/
        ├── report.md            Үндсэн тайлан
        ├── architecture/        Энгийн зураг ба тайлбар
        ├── evidence/            Нотолгоо
        └── optional/            HTML
```

Энэ бол folder/file-ийн ownership зураглал. Модуль хоорондын runtime flow гэж
үзэхгүй. Одоогийн import, consumer болон тестийг тайлангийн issue бүрт заасан.

## Шилжилтэд хадгалах зүйл

| Одоогийн API / consumer | Өөрчлөлтийн үед хадгалах contract |
|---|---|
| `src.full_scan.scan`, `render`, `write_report_bundle` | Хуучин import, default mode, Finding fields |
| `src.deep_scan.research`, `write_bundle` | Approval gate, request cap, unknown boundaries, artifact layout |
| `src.cli.main` | Existing commands, parseable JSON stdout, paths on stderr |
| `TextProcessor.compute_fingerprint` | Public static method, ижил hash/error behavior |
| TypeScript bridge schema | Request/response types; actual Python transport integration |
| Canonical skill source | Scan/install bytes ижил; сонгосон skill-г чимээгүй алгасахгүй |

Нэг migration-д бүгдийг зөөхгүй. Issue тус бүрийн хамгийн ойрын regression
шалгалт тэнцсэний дараа дараагийн module boundary-г өөрчилнө.

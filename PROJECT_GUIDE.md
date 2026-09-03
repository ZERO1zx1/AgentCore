# AgentCore — Ойлгох гарын авлага

> Энэхүү баримт бичиг нь AgentCore төслийг **хурдан ойлгоход** зориулагдсан. Гол 3 документын (README / AGENTS / SKILL) агуулгыг нэгтгэсэн хураангуй юм.

---

## 1. AgentCore гэж юу вэ?

**AgentCore** = *provider-агностик, төсөв-мэдрэмтгий, дахин эхлүүлэх боломжтой AI агент гүйцэтгэлийн хөдөлгүүр (execution engine)*.

Энгийнээр: та нэг **даалгавар (prompt)** өгөхөд AgentCore:

1. Үүнийг жижиг ажлын нэгжид (**WorkUnit**, P0–P4) задална.
2. Ажил бүрийг тохирох **model-д** хуваарилна (эхлээд чадвар, дараа нь үнэ).
3. **Төсвөө** хянаж байхдаа гүйцэтгэнэ.
4. Алхам бүрийг **checkpoint**-д хадгална → хагас замд зогссон ч дахин эхлүүлж болно.

### Гол 3 зарчим

| Зарчим | Тайлбар |
| --- | --- |
| **Provider-агностик** | OpenAI/Anthropic/Gemini-д хамаарахгүй. Жинхэнэ ажиллуулахын тулд өөрийн `OperationExecutor` adapter залгана. |
| **Төсөв-мэдрэмтгий** | `Decimal`-ээр тооцоо, сүүлийн **15% reserve**-ийг шаардлагагүй ажилд зарцуулахгүй. |
| **Дахин эхлүүлэх** | Checkpoint хадгалдаг тул давтдаггүй, үлдсэнээс нь үргэлжлүүлнэ. |

> ⚠️ **Анхаар:** `FakeExecutor` + fake model-ууд нь зөвхөн **demo** (интернетэд холбогддоггүй, billing биш). Жинхэнэ provider ажиллагаа нь таны adapter-аас хамаарна.

---

## 2. Ажиллах урсгал (pipeline)

```
TaskInput
  → InputRouter        (оролтыг таних: repo / text / pdf / structured / media)
  → TaskContext
  → AdaptiveOrchestrator
  → Planner → WorkUnit graph (P0–P4) → Scheduler
  → ModelRouter        (чадвар → үнэ)
  → OperationExecutor
  → ArtifactManager / CheckpointManager → report
        ↑
   BudgetManager       (төсөв байнга хянана)
```

---

## 3. Execution Mode (горим)

| Mode | Зорилго |
| --- | --- |
| `AUTO` | Анхдагч. Нарийн төвөгтэй байдал + үлдсэн төсөвөд дасан зохицно. |
| `FULL` | Чанар/бүрэн гүйцэтгэлд анхаарна — илүү хүчтэй model. |
| `CREDIT_SAFE` | Хамгийн хямд route, түргэн checkpoint, сонголтот ажлыг алгасна. |

---

## 4. Хавтасны бүтэц

### `src/` (гол код)

| Хавтас | Үүрэг |
| --- | --- |
| `core/` | **Engine, orchestrator, planner, executor, modes, task, policy** (гол зүрх) |
| `adapters/` | Provider adapter (`MultiProviderExecutor`) |
| `budget/` | Төсөв тооцоо (`estimator`, `state`) |
| `checkpoint/` | `TaskManifest` + `CheckpointManager` |
| `cli/` | Команд мөр (`run`, `list`, `resume`, `mcp`, `skill`, `observe`) |
| `ingestion/` | Оролтын routing (`router`, `repository`, `text`, `structured`, `pdf`, `assets`) |
| `mcp/` | Model Context Protocol stdio server |
| `memory/` | Локал memory (`governance`, `retrieval`, `safety`, `metrics`, ...) |
| `models/` | Model registry + routing |
| `observability/` | Хамтарсан read models |
| `output/` | Артефакт/гаралт (`artifact_manager`, `manager`) |

### Бусад

| Хавтас | Үүрэг |
| --- | --- |
| `tests/` | Гол тестүүд (~96) |
| `skills/` | 4 public skill (тус бүрдээ `SKILL.md`) |
| `plugin/` | Cross-agent installer + security scanner |
| `examples/` | Credit-accounting demo (FastAPI / Express / SQLite) |
| `feat/low_cost_skill/` | Тусдаа POC (engine-тэй холбоогүй) |
| `docs/` + `references/` | Баримт + бодлого (budget, checkpointing, routing...) |

---

## 5. Хэрхэн ажиллуулах / тестлэх

```bash
# Тест
python -m pytest tests -v

# Engine импорт шалгах
python -c "from src.core.engine import AgentCoreEngine; print('OK')"

# CLI тусламж
python -m src.cli --help

# Demo ажиллуулах (fake provider)
python -m src.cli run --prompt "Төслийг шинжилж дүгнэ" --provider fake
```

---

## 6. Үндсэн ойлголтууд

- **WorkUnit** — P0–P4 ажлын нэгж.
- **TaskManifest** — schema 3.0, ажлын төлөв (status, budget, outputs).
- **Checkpoint** — `.agentcore/checkpoints/` — дахин эхлүүлэх цэг.
- **Budget** — `used / remaining / reserved` (Decimal, 15% reserve).
- **Skill** — үйлдлийн бодлого: `adaptive-omni-agent`, `code-engineer`, `credit-safe-agent` (+ `adaptive-local-memory` дотоод).
- **Memory** — локал, *fallible* (одоогийн workspace evidence үргэлж давна).
- **MCP** — stdio-оор AgentCore-ийг гаднаас ашиглах боломж.

---

## 7. 3 үндсэн документ (хэзээ унших вэ)

| Документ | Юуны тухай | Хэзээ унших |
| --- | --- | --- |
| `README.md` | Setup, архитектур, adapter boundary | Эхлээд |
| `AGENTS.md` | Код өөрчлөх конвенци | Өөрчлөлт хийхээс өмнө |
| `SKILL.md` | Үйлдлийн журам (operating guide) | Ажил гүйцэтгэхдээ |

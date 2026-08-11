# CREDIT MANAGEMENT (DRAFT)

Энэхүү баримт нь AgentCore төслд AI провайдерийн кредит/коин зарцуулалтыг хэмжих, харуулах, дохиолох, мөн automatic policy-үүдээр зарцуулалтыг хянах ерөнхий архитектур, өгөгдлийн схем, болон жишээ кодыг агуулж байна.

Энд байгаа зүйлс нь DRAFT — та болон багийн гишүүд шалгаж, сайжруулж болно.

## Товч хураангуй

- Бүх AI хүсэлтийг серверээр proxy хийж, provider-ээс буцсан usage metadata-ийг бичнэ.
- Usage-аа local DB-д хадгалаад төслийн credit_balance-ийг шинэчилнэ.
- Policy engine-д threshold-уудыг тохируулж, авто-degrade эсвэл pause хийх боломжтой.
- Provider-ийн биллийн мэдээлэлтэй reconciliation хийх worker-ийг өдөр тутам ажиллуулна.

## Шаардлагатай таблианууд (жишээ)
- projects (credit_balance)
- usage_records (prompt_tokens, completion_tokens, estimated_cost, provider_request_id)
- policies

## Quick start
1. Branch: `docs/credit-management` дээр файлууд бэлэн болсон.
2. Local run: examples/backend/fastapi/usage_proxy.py ашиглан proxy серверыг тестлэх.
3. DB: examples/db/schema.sql скриптийг ажиллуулж эхний схемийг үүсгэх.

## Худалдан авалт, Auto-topup
- Auto-topup-г эхэндээ унтраасан байлга; зөвхөн админ ба проект эзний заавал зөвшөөрлөөр асаана.
- Agent-ууд нь зөвхөн авто-degrade хийх эрхтэй байж болно (хямд модел руу шилжих), харин төлбөр хийх боломжгүй.

## Next steps
- Unit tests (mock provider) нэмэх.
- Reconciliation worker-ийг хийнэ.
- Dashboard UI-тай холбох.

---

DRAFT: энэ файлд та засвар хийж, илүү нарийвчилсан заавар нэмнэ үү.

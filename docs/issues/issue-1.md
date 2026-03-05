# Issue #1

[Refactor] Kiến trúc lại repo giải pháp

## 1. Problem Statement
Refactor lại structure của dự án Tax Assistant nhằm target đến hướng xây dựng sản phẩm có scale lớn (1 triệu người dùng trở lên) và đảm bảo đầy đủ tính chất về tốc độ, độ chính xác của tư vấn, tối ưu chi phí LLM.
Có thể tham khảo một ví dụ về structure như sau:

core/
   tax_rules/
   calculators/
services/
   telegram/
   ai/
tests/
docker/

## 2. Acceptance Criteria
- Project structure phải tách được tax logic và LLM orchestration
-  Không còn tax logic nằm ngoài /core/tax_rules
- Không còn Telegram handler nằm ngoài /services/telegram
- Không còn prompt / LLM orchestration logic nằm ngoài /services/ai

Dependency Direction (Clean Architecture Constraint)
 - core/ không import bất kỳ module nào từ services/
 - core/ không phụ thuộc vào Telegram, OpenAI/Claude SDK hoặc framework bên ngoài
 - services/ được phép import core/, nhưng không ngược lại
 - Không có circular dependency giữa các module

Functional Integrity
 - 100% các test hiện tại vẫn pass sau refactor
 - Không thay đổi business logic (output trước và sau refactor phải giống nhau với cùng input)
 - Regression test được bổ sung cho ít nhất 3 flow chính:
 - Basic tax calculation
 - Premium reconciliation flow
 - AI Q&A tư vấn thuế

AI Cost Optimization Ready
 - AI prompt layer được tách riêng thành module có thể:
 - Inject model provider (Claude / OpenAI / local LLM)
 - Configurable temperature / max tokens
 - Có abstraction layer cho LLM provider (interface hoặc adapter pattern)
 - Có logging token usage

Scalability Readiness
 - Core logic có thể chạy độc lập không cần Telegram (CLI test được)
 - Có dockerfile chạy được production mode
 - Config được tách sang environment variables
 - Không còn hardcoded API key

## 3. Test Coverage
 - Coverage của core/ ≥ 80%
 - Có unit test riêng cho:
       - tax rules
       - calculators
  - Có integration test cho:
       - Telegram → Service → Core
       - AI prompt → Core logic


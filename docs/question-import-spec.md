# 本地题目导入规范 / Local question import

将 UTF-8 `.jsonl`（每行一个对象）或 `.json`（单对象或数组）提交到：

- `POST /api/questions/import/preview`：只校验，不写入。
- `POST /api/questions/import`：整批原子导入；任何错误都不会写入。

请求体为 `{ "filename": "my-bank.jsonl", "content": "..." }`。预览返回
`valid_count`、`invalid_count`、`duplicate_count` 和逐行 `errors`；提交额外返回
`imported_count`、`skipped_count`。已有 ID 且内容完全相同会跳过；同 ID 但内容不同返回
409，绝不覆盖历史题或作答记录。

每个新题必须为双语 `version: 2`，有 `id/domain/topic/concept/question_family_id/difficulty/type`
和 `content_i18n.zh-CN/en-US`。每个 locale 需要 `prompt`、`explanation`、`takeaway`、
`knowledge_card`；选择题必须各有 A-D 四个选项。`question_style` 只能是 `concept`、
`scenario`、`code_reasoning`、`debugging`、`system_design`、`tradeoff`、`calculation`。
候选题可上传 `verified:false, selection_status:"candidate"`；通过本地全量校验后会被提升为
`verified:true, selection_status:"active"`。

## 选择题质量门槛

不要把正确项写成唯一最长、唯一最具体或唯一带有因果机制的句子。四个选项必须都像一个认真但可能
错误的候选人会说的话：同一决策层级、相近信息密度、均回应题干约束。三个错误项要分别对应不同且
可解释的误区（例如把离线指标当线上目标、忽略时间泄漏、把吞吐优化误当正确性修复），而不是
`“明显错误”` 的凑数项。A–D 的正确答案位置须在一个导入包内大致均衡，不能把正确答案固定在 B。

导入校验会拒绝：非 A–D 四选项、重复选项、缺少逐个错误项解析、通用占位解析，以及明显通过长度
暴露正确项的选择题。双语内容必须是同一知识判断的自然表达；英语 locale 中不能遗留中文题干或
中文解析，中文 locale 也不能停留在英文句子的半翻译状态。

## 题目内容质量（比字段齐全更重要）

- 错误项必须是“有经验但在一个关键约束上判断错”的替代方案。每项都写清它忽略了什么，以及这会造成什么具体后果；禁止跨领域乱写、绝对化胡话或给错误项追加统一尾句凑长度。
- 正确项不能是唯一完整、最长、唯一包含因果解释的选项。四项应讨论同一个决策，措辞与信息密度自然接近；不能通过机械补字来满足长度门槛。
- 解析先回答本题情境下为什么选它，再讲机制、假设、代价/边界；不要把“面试要根据约束做选择”这种通用职业建议复制到知识卡。`takeaway` 应比题干多给一个可迁移判断，而不是重述答案；知识卡只保留本题确实新教的概念，允许简短。
- 一个 40 题包至少要混合概念判断、真实小段代码追踪/调试、系统或线上故障场景、trade-off、实验/评估设计。不要把 `question_style` 标签当成内容：名为 `scenario` 的题必须真的有场景约束。
- MLE 内容不局限于经典 ML 和 Transformer 基础。可按目标覆盖 RAG/检索、LLM 推理与服务、Agent/tool use、MCP/工具协议、多模态、模型评估、数据/训练配方、可靠性与安全等；题干要考机制、边界或工程取舍，而不是名词释义。新技术题必须在 `source_refs` 放官方文档或论文 URL，并写明核对日期/版本，避免用过时实现细节冒充通用事实。
- GPT 先产题，再用独立复核提示逐题问：“三个错误项分别为什么会吸引一个懂基础的人？题干中的哪个事实排除它？若去掉该事实，是否会变成第二个正确答案？”答不出来就重写，而非仅跑 JSON/schema validator。

给 ChatGPT 的生成提示：**“生成 UTF-8 JSONL。每题严格按 question_bank/schema.json v2；中英文
不是直译的碎片而是同一题；题干包含可判断约束；每个错误选项给出不同的、具体的误区解析；四个
选项同层级、长度相近且都貌似可行，正确项不能因最长/最具体/固定在 B 而被猜出；一题一个 family；
避免数字换皮计算和稻草人选项；L3 必须需要权衡两个以上约束；错误项必须是同一决策下看似合理、
但被题干某个具体条件排除的候选方案。解析解释正确机制与边界，takeaway 给可迁移知识，禁止通用
套话和为凑长度加尾句。题型混合概念、代码、debug、scenario、系统/评估设计、trade-off。MLE 额外覆盖
Agent/tool use、RAG、推理/服务、多模态、评估等目标方向；版本敏感内容用官方 `source_refs` 标注核对日期。
全包的正确选项 A/B/C/D 应接近均衡。”**

示例：

```json
{"id":"mle-import-rag-0001","domain":"mle","topic":"transformer_llm","concept":"rag-citation-grounding","question_family_id":"rag-grounding-choice","difficulty":"L3","type":"single_choice","content_i18n":{"zh-CN":{"prompt":"检索到的段落互相矛盾时，产品答案首先应？","options":[{"id":"A","text":"声明证据冲突并请求澄清"},{"id":"B","text":"选择最长段落"},{"id":"C","text":"忽略检索"},{"id":"D","text":"编造统一结论"}],"explanation":"可溯源性优先于流畅回答。","distractor_explanations":{"B":"长度不等于可信度","C":"丢弃证据","D":"制造幻觉"},"takeaway":"冲突证据应暴露而非掩盖。","knowledge_card":{"summary":"RAG grounding","why_it_matters":"减少高风险幻觉","interview_angle":"说明拒答路径","common_pitfall":"只看相似度"}},"en-US":{"prompt":"When retrieved passages conflict, the product should first?","options":[{"id":"A","text":"State the evidence conflict and request clarification"},{"id":"B","text":"Choose the longest passage"},{"id":"C","text":"Ignore retrieval"},{"id":"D","text":"Invent a combined conclusion"}],"explanation":"Traceability wins over fluent unsupported output.","distractor_explanations":{"B":"Length is not reliability","C":"Drops evidence","D":"Creates a hallucination"},"takeaway":"Expose conflicting evidence rather than hiding it.","knowledge_card":{"summary":"RAG grounding","why_it_matters":"Reduces high-risk hallucinations","interview_angle":"Explain the abstention path","common_pitfall":"Using similarity alone"}}},"answer":{"option_id":"A"},"accepted_answers":[],"regex_answers":[],"numeric_answer":null,"numeric_tolerance":null,"parameters":{},"verified":false,"verification":{"method":"stable_fact","solver":"","solver_version":"v3","evidence":"curated review"},"version":2,"schema_version":2,"source_kind":"imported","selection_status":"candidate","quality_tier":"candidate","question_style":"scenario","cognitive_skill":"evaluate","knowledge_points":["rag-grounding"],"tags":["rag","safety"],"source_refs":[]}
```

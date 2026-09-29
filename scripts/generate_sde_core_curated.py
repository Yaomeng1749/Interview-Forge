#!/usr/bin/env python3
"""Generate a small, reviewed SDE core pack used by the local interview trainer."""
from __future__ import annotations

import json
from pathlib import Path


ITEMS = [
    ("hash-equality", "data_structures_algorithms", "hash_contract", "L3", "concept", "understand", "A hash-map key class overrides equals but not hashCode. What bug can result?", "一个 HashMap 键类重写了 equals 却没有重写 hashCode，最可能出现什么问题？", ["Equal keys can land in different buckets and fail lookup", "The map becomes insertion ordered", "Every lookup becomes O(1)", "Collisions are impossible"], ["相等的键可能落在不同桶中，导致查找失败", "Map 会自动变成插入顺序", "每次查找都会变成 O(1)", "哈希冲突会完全消失"], "A", "Hash-based collections require equal objects to have the same hash value.", "哈希集合要求相等对象拥有相同的哈希值。"),
    ("bfs-visited", "data_structures_algorithms", "bfs_frontier", "L3", "code_reasoning", "apply", "In BFS on an unweighted graph, why mark a node visited when enqueuing rather than when dequeuing?", "在无权图 BFS 中，为什么应在入队时标记 visited，而不是出队时？", ["It prevents the same node being enqueued repeatedly", "It makes BFS depth-first", "It removes the need for a queue", "It guarantees sorted adjacency"], ["避免同一节点被重复入队", "让 BFS 变成深度优先", "不再需要队列", "保证邻接表有序"], "A", "Marking on enqueue records first discovery and avoids duplicate frontier work.", "入队即标记记录首次发现，避免 frontier 中的重复工作。"),
    ("binary-search-invariant", "data_structures_algorithms", "binary_search_invariant", "L3", "debugging", "analyze", "A binary search occasionally loops forever on two remaining elements. Which invariant-level fix is most reliable?", "一个二分查找在只剩两个元素时偶尔死循环。哪个基于不变量的修复最可靠？", ["Define an inclusive/exclusive interval and ensure every branch strictly shrinks it", "Add a fixed iteration limit", "Sort the array again on each iteration", "Replace mid with a random index"], ["明确闭开区间并保证每个分支严格收缩区间", "加一个固定循环次数上限", "每次循环重新排序数组", "把 mid 换成随机下标"], "A", "Termination follows from a shrinking interval invariant, not from an arbitrary guard.", "终止性来自区间严格收缩的不变量，而不是任意的保护计数。"),
    ("topk-stream", "data_structures_algorithms", "top_k_stream", "L3", "scenario", "apply", "You need the largest 100 values from an unbounded stream and cannot retain the stream. What structure is appropriate?", "需要从无限数据流中维护最大的 100 个值，且不能保存整个流。应使用什么结构？", ["A min-heap of size 100", "A sorted array containing every value", "A FIFO queue", "A stack of all values"], ["容量为 100 的最小堆", "保存所有值的有序数组", "先进先出队列", "保存所有值的栈"], "A", "The heap keeps the current threshold at its root with bounded memory.", "堆根维护当前阈值，同时把内存限制在固定大小。"),
    ("deadlock-cycle", "operating_systems", "deadlock_conditions", "L2", "scenario", "analyze", "A service holds lock A while waiting for B, while another holds B while waiting for A. Which design change directly breaks the cycle?", "一个服务持有锁 A 等待 B，另一个持有 B 等待 A。哪种设计直接打破该循环？", ["Impose one global lock acquisition order", "Increase thread count", "Use longer lock timeouts only", "Cache both locks"], ["规定全局一致的加锁顺序", "增加线程数", "仅增加锁超时", "缓存两个锁"], "A", "A global order removes circular wait, one of the necessary deadlock conditions.", "全局顺序消除了循环等待，这是死锁的必要条件之一。"),
    ("condition-predicate", "operating_systems", "condition_variable", "L3", "code_reasoning", "analyze", "Why should a consumer wait on a condition variable in a loop that rechecks the queue predicate?", "为什么消费者应在循环中等待条件变量，并反复检查队列谓词？", ["Wakeups can be spurious or another consumer can consume the item first", "The loop makes mutexes unnecessary", "Condition variables persist notifications forever", "It makes the queue lock-free"], ["唤醒可能是伪唤醒，或其他消费者先取走了元素", "循环可以不再需要互斥锁", "条件变量会永久保存通知", "这样队列会变成无锁"], "A", "The predicate, protected by the mutex, is the correctness condition; wakeup is only a hint.", "由互斥锁保护的谓词才是正确性条件；唤醒只是一次提示。"),
    ("cow-memory", "operating_systems", "copy_on_write", "L3", "concept", "understand", "Why can fork be cheap until either parent or child writes a shared page?", "为什么 fork 在父子进程任一方写入共享页面之前通常很便宜？", ["Pages are shared read-only and copied only on the first write", "The kernel copies all pages asynchronously", "Fork avoids page tables", "Writes are discarded"], ["页面先以只读方式共享，首次写入时才复制", "内核会异步复制所有页面", "fork 不需要页表", "写入会被丢弃"], "A", "Copy-on-write defers physical copying until a write requires private state.", "写时复制把物理复制推迟到写入确实需要私有状态时。"),
    ("tcp-retry", "networks", "idempotent_retry", "L3", "tradeoff", "evaluate", "A client times out after sending a payment request; the server may have completed it. What makes retry safe?", "客户端发送付款请求后超时；服务端可能已完成操作。什么机制使重试安全？", ["An idempotency key recorded with the operation result", "A shorter client timeout", "A second TCP connection", "Turning off server logs"], ["随操作结果持久化的幂等键", "更短的客户端超时", "建立第二条 TCP 连接", "关闭服务端日志"], "A", "The key lets the server return the original result rather than apply the side effect twice.", "该键让服务端返回原结果，而不是重复执行副作用。"),
    ("backpressure", "networks", "backpressure", "L2", "system_design", "analyze", "A producer outpaces a downstream service and the in-memory queue grows without bound. What is the first system-level control?", "生产者快于下游服务，内存队列无限增长。首要的系统级控制是什么？", ["Bound the queue and propagate backpressure or reject work", "Increase log verbosity", "Retry failed requests immediately", "Disable metrics"], ["限制队列并传播背压或拒绝工作", "增加日志详细程度", "立即重试失败请求", "关闭指标"], "A", "A bounded buffer makes overload explicit and protects memory before tuning throughput.", "有界缓冲区让过载显式化，在吞吐调优前先保护内存。"),
    ("dns-ttl", "networks", "dns_caching", "L2", "scenario", "apply", "After moving traffic to a new endpoint, some users still hit the old endpoint for minutes. Which prior decision most directly explains it?", "流量切换到新端点后，部分用户数分钟仍访问旧端点。哪个此前决策最直接解释这一现象？", ["A long DNS TTL was published before the change", "TLS used modern ciphers", "HTTP responses were compressed", "The load balancer had health checks"], ["变更前发布了过长的 DNS TTL", "TLS 使用了现代密码套件", "HTTP 响应经过压缩", "负载均衡器有健康检查"], "A", "Resolvers may legally retain records until TTL expiry, so migration plans lower TTL ahead of time.", "解析器可在 TTL 到期前合法缓存记录，因此迁移应提前降低 TTL。"),
]

# Extra families keep SDE adaptive rather than forcing every paper to use the
# exact same forty questions. They are intentionally qualitative, not numeric
# parameter variants.
EXTRA = [
    ("api-versioning", "backend_systems", "backward_compatibility", "L1", "concept", "What is the safest default when adding a required API response field?", "给 API 响应新增一个必填字段时，最安全的默认做法是什么？", "Make clients tolerate unknown fields and roll out compatibly", "让客户端容忍未知字段并以兼容方式发布"),
    ("db-index-prefix", "databases", "composite_index_order", "L1", "concept", "What primarily determines the useful leading column of a composite B-tree index?", "联合 B-tree 索引中，最有用的首列主要由什么决定？", "The query predicates and ordering actually used", "实际使用的查询谓词与排序"),
    ("cache-stampede", "backend_systems", "cache_stampede", "L1", "scenario", "Many requests miss the same expired cache key. What limits the origin surge?", "大量请求同时命中同一个过期缓存键。什么能限制回源洪峰？", "Request coalescing or a per-key regeneration lock", "请求合并或按键再生成锁"),
    ("queue-poison", "backend_systems", "poison_message", "L1", "debugging", "A message always fails after retries because its payload is malformed. What should the consumer do?", "一条消息因载荷损坏而每次重试都失败。消费者应如何处理？", "Move it to a dead-letter path with diagnostics", "将其转入带诊断信息的死信路径"),
    ("rate-limit-scope", "backend_systems", "rate_limit_identity", "L1", "tradeoff", "Which identity is usually safer for a paid API rate limit than source IP alone?", "付费 API 的限流通常应使用什么身份，而不是只看源 IP？", "An authenticated account or API key", "已认证账户或 API key"),
    ("tls-termination", "networks", "tls_termination", "L1", "system_design", "Where should application identity and original client metadata be propagated after TLS termination?", "TLS 终止后，应用身份和原客户端元数据应在哪里安全传递？", "Through trusted proxy headers with an explicit trust boundary", "通过具有明确可信边界的代理头传递"),
    ("thread-pool-isolation", "operating_systems", "bulkhead_isolation", "L1", "system_design", "A slow optional dependency exhausts request worker threads. What isolates the blast radius?", "一个缓慢的可选依赖耗尽请求工作线程。什么措施能隔离影响范围？", "A separate bounded pool or bulkhead", "独立的有界线程池或舱壁隔离"),
    ("pagination-cursor", "databases", "cursor_pagination", "L1", "tradeoff", "Why is cursor pagination preferred for a changing, deep result set?", "为什么面对持续变化的深分页结果集时常用 cursor 分页？", "It avoids growing offset scans and gives a stable continuation", "避免不断增长的 offset 扫描并提供稳定续读"),
    ("tracing-correlation", "backend_systems", "distributed_tracing", "L1", "debugging", "What connects logs across a request that crosses several services?", "一个请求跨越多个服务时，什么能把日志关联起来？", "A propagated trace or correlation identifier", "传播的 trace 或 correlation 标识"),
    ("graceful-shutdown", "backend_systems", "graceful_shutdown", "L1", "scenario", "Before draining a server instance, what should it stop accepting first?", "开始摘除一个服务实例前，它首先应停止接收什么？", "New load-balancer traffic while allowing in-flight work to finish", "新的负载均衡流量，同时让在途请求完成"),
]

for slug, topic, concept, level, style, en, zh, correct_en, correct_zh in EXTRA:
    ITEMS.append((slug, topic, concept, level, style, "understand", en, zh,
                  [correct_en, "Increase a timeout", "Store it only in a client", "Ignore the failure"],
                  [correct_zh, "增加超时", "只存储在客户端", "忽略该失败"], "A",
                  correct_en + " addresses the operating constraint directly.",
                  correct_zh + " 直接处理了运行约束。"))


def main() -> None:
    rows = []
    for number, (slug, topic, concept, level, style, skill, en, zh, en_options, zh_options, answer, en_exp, zh_exp) in enumerate(ITEMS, 1):
        options_en = [{"id": key, "text": text} for key, text in zip("ABCD", en_options, strict=True)]
        options_zh = [{"id": key, "text": text} for key, text in zip("ABCD", zh_options, strict=True)]
        wrong = {key: "It does not address the stated failure mode." for key in "ABCD" if key != answer}
        wrong_zh = {key: "它没有解决题干给出的失效模式。" for key in "ABCD" if key != answer}
        rows.append({"id": f"sde-core-{number:04d}", "domain": "sde", "topic": topic, "concept": concept, "question_family_id": f"sde-core-{slug}", "difficulty": level, "type": "single_choice", "content_i18n": {"en-US": {"prompt": en, "options": options_en, "explanation": en_exp, "takeaway": en_exp, "knowledge_card": {"summary": en_exp, "why_it_matters": "It is a common production and interview boundary.", "interview_angle": "Name the invariant and the trade-off.", "common_pitfall": "Choosing a change that only hides the symptom."}, "distractor_explanations": wrong}, "zh-CN": {"prompt": zh, "options": options_zh, "explanation": zh_exp, "takeaway": zh_exp, "knowledge_card": {"summary": zh_exp, "why_it_matters": "这是常见的生产与面试边界。", "interview_angle": "说明不变量与取舍。", "common_pitfall": "选择只能掩盖症状的改动。"}, "distractor_explanations": wrong_zh}}, "answer": {"option_id": answer}, "accepted_answers": [], "regex_answers": [], "numeric_answer": None, "numeric_tolerance": None, "parameters": {}, "verified": True, "verification": {"method": "stable_fact", "solver": "curated_review", "solver_version": "v3", "evidence": "Reviewed durable systems concept."}, "version": 2, "schema_version": 2, "source_kind": "curated", "quality_tier": "curated", "selection_status": "active", "question_style": style, "cognitive_skill": skill, "knowledge_points": [concept], "tags": ["interview", topic], "source_refs": []})
    # Short-answer terminology checks are intentional interview retrieval prompts,
    # not arithmetic blanks.  Keep them bilingual and semantically gradeable.
    for row in rows[10:14]:
        row["type"] = "fill_blank"
        row["answer"] = {"text": row["concept"]}
        row["accepted_answers"] = [row["concept"]]
        for locale in ("en-US", "zh-CN"):
            row["content_i18n"][locale]["options"] = []
            row["content_i18n"][locale]["distractor_explanations"] = {}
            suffix = " Answer with the mechanism name." if locale == "en-US" else " 请填写机制名称。"
            row["content_i18n"][locale]["prompt"] += suffix
    target = Path(__file__).resolve().parents[1] / "question_bank" / "curated_sources" / "sde_core.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

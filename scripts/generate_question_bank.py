#!/usr/bin/env python3
"""Generate a deterministic, bilingual, solver-backed 1,000-question bank."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any


GENERATOR_VERSION = "bank-v1.0.0"
GENERATOR_SEED = "mle-sde-adaptive-exam|2026-09-21|v1"
LOCALES = ("zh-CN", "en-US")
QUOTA = {
    domain: {
        "single_choice": {"L1": 110, "L2": 185, "L3": 75},
        "fill_blank": {"L1": 40, "L2": 65, "L3": 25},
    }
    for domain in ("sde", "mle")
}


def spec(
    domain: str,
    topic: str,
    concept: str,
    difficulty: str,
    solver: str,
    zh: str,
    en: str,
    unit_zh: str = "",
    unit_en: str = "",
) -> dict[str, str]:
    return {
        "domain": domain,
        "topic": topic,
        "concept": concept,
        "difficulty": difficulty,
        "solver": solver,
        "zh": zh,
        "en": en,
        "unit_zh": unit_zh,
        "unit_en": unit_en,
    }


FAMILY_SPECS = [
    # SDE L1
    spec("sde", "data_structures_algorithms", "binary_search", "L1", "binary_comparisons", "对含 {n} 个互异元素的有序数组进行二分查找，最坏情况需要多少次元素比较？", "For a sorted array of {n} distinct elements, how many element comparisons are required in the worst case by binary search?", " 次", " comparisons"),
    spec("sde", "data_structures_algorithms", "perfect_binary_tree", "L1", "perfect_tree_nodes", "一棵完美二叉树共有 {levels} 层（根为第 1 层），节点总数是多少？", "A perfect binary tree has {levels} levels (the root is level 1). How many nodes does it contain?"),
    spec("sde", "data_structures_algorithms", "array_storage", "L1", "product", "一个数组含 {a} 个元素，每个元素占 {b} 字节；数组数据区共占多少字节？", "An array contains {a} elements and each element occupies {b} bytes. How many bytes does its data region occupy?", " 字节", " bytes"),
    spec("sde", "operating_systems", "page_offset", "L1", "power_of_two", "页大小为 2^{bits} 字节，页内偏移可表示多少个不同字节位置？", "A page size is 2^{bits} bytes. How many distinct byte positions can the page offset represent?", " 个", " positions"),
    spec("sde", "backend_systems", "request_count", "L1", "product", "服务以每秒 {a} 个请求的固定速率运行 {b} 秒，共处理多少个请求？", "A service runs for {b} seconds at a fixed rate of {a} requests per second. How many requests does it process?", " 个请求", " requests"),
    spec("sde", "databases", "replication_storage", "L1", "product", "一个 {a} GB 的不可压缩数据集保存 {b} 个完整副本，共需要多少 GB 原始存储？", "An incompressible {a} GB dataset is stored as {b} full copies. How many GB of raw storage are required?", " GB", " GB"),
    # SDE L2
    spec("sde", "operating_systems", "round_robin", "L2", "ceil_div", "一个 CPU burst 为 {total} ms 的进程在时间片 {chunk} ms 下独占 CPU 运行。完成该 burst 需要多少个时间片？", "A process with a {total} ms CPU burst runs alone with a {chunk} ms quantum. How many quanta are required to finish the burst?", " 个", " quanta"),
    spec("sde", "backend_systems", "cache_misses", "L2", "difference", "某缓存收到 {total} 次查找，其中 {hit} 次命中。未命中次数是多少？", "A cache receives {total} lookups, of which {hit} are hits. How many are misses?", " 次", " misses"),
    spec("sde", "operating_systems", "average_memory_access", "L2", "weighted_average", "缓存命中率为 {rate}%，命中耗时 {fast} ns，未命中耗时 {slow} ns。忽略其他开销，平均访问时间是多少 ns？", "A cache has a {rate}% hit rate, {fast} ns hit time, and {slow} ns miss time. Ignoring other overhead, what is the average access time in ns?", " ns", " ns"),
    spec("sde", "databases", "hash_bucket_capacity", "L2", "ceil_div", "哈希索引要容纳 {total} 条记录，且每个 bucket 最多放 {chunk} 条。至少需要多少个 bucket？", "A hash index must hold {total} records with at most {chunk} records per bucket. What is the minimum number of buckets?", " 个", " buckets"),
    spec("sde", "networks", "tcp_window_throughput", "L2", "window_throughput", "TCP 发送窗口为 {window} KB，RTT 为 {rtt} ms，且链路无丢包。仅按窗口限制计算，最大吞吐量是多少 KB/s？", "A TCP sender has a {window} KB window and {rtt} ms RTT with no loss. Considering only the window limit, what is the maximum throughput in KB/s?", " KB/s", " KB/s"),
    spec("sde", "databases", "query_selectivity", "L2", "percentage", "表中有 {total} 行，过滤条件精确匹配其中 {rate}%。结果集有多少行？", "A table has {total} rows and a predicate matches exactly {rate}% of them. How many rows are in the result?", " 行", " rows"),
    # SDE L3
    spec("sde", "backend_systems", "exponential_backoff", "L3", "backoff_sum", "重试等待从 {base} ms 开始，每次翻倍，共等待 {attempts} 次。累计等待时间是多少 ms？", "Retry delays start at {base} ms and double each time for {attempts} waits. What is the cumulative delay in ms?", " ms", " ms"),
    spec("sde", "data_structures_algorithms", "directed_graph_edges", "L3", "directed_edges", "一个无自环的简单有向图含 {n} 个顶点，最多可有多少条有向边？", "A simple directed graph with {n} vertices has no self-loops. What is its maximum number of directed edges?", " 条", " edges"),
    spec("sde", "data_structures_algorithms", "grid_dynamic_programming", "L3", "product", "一个网格动态规划为每个单元格保存一个状态。网格为 {a}×{b}，共保存多少个状态？", "A grid dynamic program stores one state per cell. For a {a} by {b} grid, how many states are stored?", " 个", " states"),
    spec("sde", "backend_systems", "littles_law", "L3", "little_law", "稳定服务的到达率为每秒 {rate} 个请求，平均响应时间为 {latency} ms。按 Little 定律，系统内平均并发请求数是多少？", "A stable service receives {rate} requests per second with {latency} ms mean response time. By Little's law, what is the mean number of concurrent requests?", " 个", " requests"),
    spec("sde", "databases", "read_write_quorum", "L3", "quorum_write", "复制因子 N={n}，读 quorum 为 R={read}。要保证 R+W>N，整数写 quorum W 的最小值是多少？", "Replication factor N={n} and read quorum R={read}. To guarantee R+W>N, what is the minimum integer write quorum W?"),
    spec("sde", "backend_systems", "two_tier_cache", "L3", "two_tier_average", "请求以 {l1_rate}% 的概率在 L1 命中，耗时 {l1} ms；否则以 {l2_rate}% 的条件概率在 L2 命中，额外耗时 {l2} ms；其余访问源站，额外耗时 {origin} ms。平均耗时是多少 ms？", "A request hits L1 with probability {l1_rate}% at {l1} ms. Otherwise it hits L2 with conditional probability {l2_rate}% at an additional {l2} ms; the rest reaches origin at an additional {origin} ms. What is the mean latency in ms?", " ms", " ms"),
    # MLE L1
    spec("mle", "deep_learning", "dense_layer_parameters", "L1", "dense_params", "全连接层输入维度为 {in_dim}，输出维度为 {out_dim}，并含 bias。可训练参数总数是多少？", "A dense layer has input dimension {in_dim}, output dimension {out_dim}, and a bias. How many trainable parameters does it have?"),
    spec("mle", "transformer_llm", "embedding_parameters", "L1", "product", "词表大小为 {a}，embedding 维度为 {b}。不考虑其他参数，embedding 表有多少个参数？", "The vocabulary size is {a} and the embedding dimension is {b}. Ignoring other parameters, how many parameters are in the embedding table?"),
    spec("mle", "pytorch_training", "tensor_elements", "L1", "tensor_elements", "一个张量 shape 为 ({x}, {y}, {z})，它包含多少个标量元素？", "A tensor has shape ({x}, {y}, {z}). How many scalar elements does it contain?"),
    spec("mle", "pytorch_training", "batches_per_epoch", "L1", "ceil_div", "数据集有 {total} 个样本，batch size 为 {chunk}，保留最后一个不完整 batch。每个 epoch 有多少个 batch？", "A dataset has {total} samples and batch size {chunk}; the final incomplete batch is kept. How many batches are in one epoch?", " 个", " batches"),
    spec("mle", "classical_ml", "train_split", "L1", "percentage", "数据集共有 {total} 个样本，精确取 {rate}% 作为训练集。训练样本数是多少？", "A dataset contains {total} samples and exactly {rate}% are used for training. How many training samples are there?", " 个", " samples"),
    spec("mle", "transformer_llm", "attention_head_dimension", "L1", "exact_div", "Transformer hidden size 为 {total}，attention head 数为 {chunk}，各 head 等宽。每个 head 的维度是多少？", "A Transformer has hidden size {total} and {chunk} equal-width attention heads. What is each head's dimension?"),
    # MLE L2
    spec("mle", "math_statistics", "precision", "L2", "precision", "二分类结果中 TP={tp}、FP={fp}。precision 是多少？请用小数表示。", "For a binary classifier, TP={tp} and FP={fp}. What is precision? Express it as a decimal."),
    spec("mle", "classical_ml", "recall", "L2", "recall", "二分类结果中 TP={tp}、FN={fn}。recall 是多少？请用小数表示。", "For a binary classifier, TP={tp} and FN={fn}. What is recall? Express it as a decimal."),
    spec("mle", "mlops_evaluation", "f1_score", "L2", "f1", "二分类结果中 TP={tp}、FP={fp}、FN={fn}。F1 分数是多少？请用小数表示。", "For a binary classifier, TP={tp}, FP={fp}, and FN={fn}. What is the F1 score? Express it as a decimal."),
    spec("mle", "deep_learning", "convolution_output", "L2", "conv_output", "一维输入长度 {n}，卷积核 {kernel}，padding {padding}，stride {stride}，dilation=1。输出长度是多少？", "A 1-D input has length {n}, kernel {kernel}, padding {padding}, stride {stride}, and dilation=1. What is the output length?"),
    spec("mle", "ml_systems_inference", "effective_batch_size", "L2", "triple_product", "每张 GPU 的 micro-batch 为 {a}，梯度累积 {b} 步，共 {c} 张数据并行 GPU。一次优化更新的有效 batch size 是多少？", "The micro-batch per GPU is {a}, gradients accumulate for {b} steps, and {c} data-parallel GPUs are used. What is the effective batch size per optimizer update?"),
    spec("mle", "pytorch_training", "training_steps", "L2", "training_steps", "训练集有 {samples} 个样本，batch size={batch}，保留尾 batch，训练 {epochs} 个 epoch。总 optimizer step 数是多少？", "A training set has {samples} samples, batch size {batch}, the tail batch is kept, and training runs for {epochs} epochs. How many optimizer steps are taken?", " 步", " steps"),
    # MLE L3
    spec("mle", "ml_systems_inference", "kv_cache_memory", "L3", "kv_cache_mib", "自回归推理使用 batch={batch}、层数={layers}、序列长度={seq}、KV heads={heads}、head dim={dim}，K/V 各一份，每元素 {bytes} 字节。KV cache 为多少 MiB？", "Autoregressive inference uses batch={batch}, {layers} layers, sequence length={seq}, {heads} KV heads, head dimension={dim}, one K and one V tensor, and {bytes} bytes per element. How many MiB does the KV cache occupy?", " MiB", " MiB"),
    spec("mle", "transformer_llm", "lora_parameters", "L3", "lora_params", "对一个 {out_dim}×{in_dim} 线性权重应用 rank={rank} 的 LoRA，忽略 bias。A、B 两矩阵共有多少个参数？", "Rank-{rank} LoRA is applied to a {out_dim} by {in_dim} linear weight, ignoring bias. How many parameters are in matrices A and B combined?"),
    spec("mle", "ml_systems_inference", "training_compute", "L3", "training_mflops", "用近似式 6NT 估算训练计算量：参数量 N={params} 百万，token 数 T={tokens}。结果是多少百万 FLOP？", "Estimate training compute using 6NT: parameter count N={params} million and token count T={tokens}. How many million FLOPs is that?", " MFLOP", " MFLOPs"),
    spec("mle", "math_statistics", "bayes_posterior", "L3", "bayes", "某事件先验概率为 {prevalence}%，检测灵敏度为 {sensitivity}%，特异度为 {specificity}%。检测阳性时事件的后验概率是多少？用小数表示。", "An event has {prevalence}% prior probability. A test has {sensitivity}% sensitivity and {specificity}% specificity. What is the posterior probability of the event given a positive result? Express it as a decimal."),
    spec("mle", "transformer_llm", "top_k_candidates", "L3", "product", "batch 中有 {a} 个序列，每个序列在一步解码中保留 top-{b} 候选。该步共保留多少个候选 token？", "A batch has {a} sequences and keeps top-{b} candidates per sequence for one decoding step. How many candidate tokens are retained in total?", " 个", " candidates"),
    spec("mle", "ml_systems_inference", "moe_active_parameters", "L3", "moe_active", "一个 MoE 层每个 token 激活 {selected} 个 expert，每个 expert 有 {expert} 百万参数，另有共享部分 {shared} 百万参数。每个 token 的激活参数量是多少百万？", "An MoE layer activates {selected} experts per token; each expert has {expert} million parameters and the shared part has {shared} million. How many million parameters are active per token?", " 百万", " million"),
]


def _draw(key: str, low: int, high: int, *, step: int = 1) -> int:
    if high < low or step <= 0:
        raise ValueError("invalid deterministic draw range")
    count = ((high - low) // step) + 1
    digest = hashlib.sha256(f"{GENERATOR_SEED}|{key}".encode()).digest()
    return low + (int.from_bytes(digest[:8], "big") % count) * step


def make_parameters(solver: str, family_id: str, variant: int, attempt: int = 0) -> dict[str, int]:
    key = f"{family_id}|{variant}|{attempt}"
    d = lambda name, lo, hi, step=1: _draw(f"{key}|{name}", lo, hi, step=step)
    if solver == "binary_comparisons":
        return {"n": d("n", 17, 4095)}
    if solver == "perfect_tree_nodes":
        return {"levels": d("levels", 3, 40)}
    if solver == "product":
        return {"a": d("a", 8, 500), "b": d("b", 2, 64)}
    if solver == "power_of_two":
        return {"bits": d("bits", 8, 45)}
    if solver == "ceil_div":
        chunk = d("chunk", 3, 64)
        return {"total": d("total", chunk + 1, chunk * 80), "chunk": chunk}
    if solver == "difference":
        total = d("total", 100, 5000)
        return {"total": total, "hit": d("hit", 1, total - 1)}
    if solver == "weighted_average":
        return {"rate": d("rate", 60, 95), "fast": d("fast", 1, 20), "slow": d("slow", 80, 400, 5)}
    if solver == "window_throughput":
        rtt = d("rtt", 10, 100, 10)
        return {"window": d("window", 8, 256, 8), "rtt": rtt}
    if solver == "percentage":
        return {"total": d("total", 100, 10000, 100), "rate": d("rate", 5, 95, 5)}
    if solver == "backoff_sum":
        return {"base": d("base", 10, 250, 10), "attempts": d("attempts", 3, 8)}
    if solver == "directed_edges":
        return {"n": d("n", 5, 80)}
    if solver == "little_law":
        return {"rate": d("rate", 20, 1000, 20), "latency": d("latency", 50, 900, 50)}
    if solver == "quorum_write":
        n = d("n", 3, 15)
        return {"n": n, "read": d("read", 1, n)}
    if solver == "two_tier_average":
        return {"l1_rate": d("l1_rate", 50, 90, 5), "l1": d("l1", 1, 5), "l2_rate": d("l2_rate", 40, 90, 5), "l2": d("l2", 4, 20), "origin": d("origin", 50, 250, 10)}
    if solver == "dense_params":
        return {"in_dim": d("in_dim", 16, 512, 8), "out_dim": d("out_dim", 8, 256, 8)}
    if solver == "tensor_elements":
        return {"x": d("x", 2, 32), "y": d("y", 2, 64), "z": d("z", 2, 128)}
    if solver == "exact_div":
        chunk = d("chunk", 2, 16)
        return {"chunk": chunk, "total": chunk * d("factor", 8, 128)}
    if solver == "precision":
        return {"tp": d("tp", 20, 200, 5), "fp": d("fp", 5, 80, 5)}
    if solver == "recall":
        return {"tp": d("tp", 20, 200, 5), "fn": d("fn", 5, 80, 5)}
    if solver == "f1":
        return {"tp": d("tp", 20, 200, 5), "fp": d("fp", 5, 80, 5), "fn": d("fn", 5, 80, 5)}
    if solver == "conv_output":
        kernel = d("kernel", 2, 7)
        padding = d("padding", 0, 3)
        stride = d("stride", 1, 4)
        return {"n": d("n", kernel + 4, 128), "kernel": kernel, "padding": padding, "stride": stride}
    if solver == "triple_product":
        return {"a": d("a", 1, 32), "b": d("b", 1, 16), "c": d("c", 1, 16)}
    if solver == "training_steps":
        return {"samples": d("samples", 100, 10000), "batch": d("batch", 8, 128, 8), "epochs": d("epochs", 2, 20)}
    if solver == "kv_cache_mib":
        return {"batch": d("batch", 1, 8), "layers": d("layers", 4, 48, 4), "seq": d("seq", 128, 4096, 128), "heads": d("heads", 1, 16), "dim": d("dim", 32, 128, 32), "bytes": d("bytes", 1, 4)}
    if solver == "lora_params":
        return {"in_dim": d("in_dim", 128, 4096, 128), "out_dim": d("out_dim", 128, 4096, 128), "rank": d("rank", 2, 64, 2)}
    if solver == "training_mflops":
        return {"params": d("params", 10, 500, 10), "tokens": d("tokens", 10, 1000, 10)}
    if solver == "bayes":
        return {"prevalence": d("prevalence", 5, 50, 5), "sensitivity": d("sensitivity", 60, 95, 5), "specificity": d("specificity", 60, 95, 5)}
    if solver == "moe_active":
        return {"selected": d("selected", 1, 4), "expert": d("expert", 5, 100, 5), "shared": d("shared", 1, 50)}
    raise KeyError(f"unknown solver: {solver}")


def solve(solver: str, p: dict[str, int]) -> Fraction:
    if solver == "binary_comparisons":
        return Fraction(p["n"].bit_length())
    if solver == "perfect_tree_nodes":
        return Fraction(2 ** p["levels"] - 1)
    if solver == "product":
        return Fraction(p["a"] * p["b"])
    if solver == "power_of_two":
        return Fraction(2 ** p["bits"])
    if solver == "ceil_div":
        return Fraction(math.ceil(p["total"] / p["chunk"]))
    if solver == "difference":
        return Fraction(p["total"] - p["hit"])
    if solver == "weighted_average":
        return Fraction(p["rate"] * p["fast"] + (100 - p["rate"]) * p["slow"], 100)
    if solver == "window_throughput":
        return Fraction(p["window"] * 1000, p["rtt"])
    if solver == "percentage":
        return Fraction(p["total"] * p["rate"], 100)
    if solver == "backoff_sum":
        return Fraction(p["base"] * (2 ** p["attempts"] - 1))
    if solver == "directed_edges":
        return Fraction(p["n"] * (p["n"] - 1))
    if solver == "little_law":
        return Fraction(p["rate"] * p["latency"], 1000)
    if solver == "quorum_write":
        return Fraction(p["n"] - p["read"] + 1)
    if solver == "two_tier_average":
        l1_miss = 100 - p["l1_rate"]
        return Fraction(p["l1_rate"] * p["l1"] * 100 + l1_miss * p["l2_rate"] * (p["l1"] + p["l2"]) + l1_miss * (100 - p["l2_rate"]) * (p["l1"] + p["l2"] + p["origin"]), 10000)
    if solver == "dense_params":
        return Fraction(p["in_dim"] * p["out_dim"] + p["out_dim"])
    if solver == "tensor_elements":
        return Fraction(p["x"] * p["y"] * p["z"])
    if solver == "exact_div":
        return Fraction(p["total"], p["chunk"])
    if solver == "precision":
        return Fraction(p["tp"], p["tp"] + p["fp"])
    if solver == "recall":
        return Fraction(p["tp"], p["tp"] + p["fn"])
    if solver == "f1":
        return Fraction(2 * p["tp"], 2 * p["tp"] + p["fp"] + p["fn"])
    if solver == "conv_output":
        return Fraction(math.floor((p["n"] + 2 * p["padding"] - p["kernel"]) / p["stride"]) + 1)
    if solver == "triple_product":
        return Fraction(p["a"] * p["b"] * p["c"])
    if solver == "training_steps":
        return Fraction(math.ceil(p["samples"] / p["batch"]) * p["epochs"])
    if solver == "kv_cache_mib":
        elements = p["batch"] * p["layers"] * p["seq"] * p["heads"] * p["dim"] * 2
        return Fraction(elements * p["bytes"], 1024 * 1024)
    if solver == "lora_params":
        return Fraction(p["rank"] * (p["in_dim"] + p["out_dim"]))
    if solver == "training_mflops":
        return Fraction(6 * p["params"] * p["tokens"])
    if solver == "bayes":
        true_positive = p["sensitivity"] * p["prevalence"]
        false_positive = (100 - p["specificity"]) * (100 - p["prevalence"])
        return Fraction(true_positive, true_positive + false_positive)
    if solver == "moe_active":
        return Fraction(p["selected"] * p["expert"] + p["shared"])
    raise KeyError(f"unknown solver: {solver}")


def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    rendered = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return "0" if rendered == "-0" else rendered


def solver_expression(solver: str, p: dict[str, int]) -> str:
    formulas = {
        "binary_comparisons": "floor(log2(n)) + 1",
        "perfect_tree_nodes": "2^levels - 1",
        "product": "a * b",
        "power_of_two": "2^bits",
        "ceil_div": "ceil(total / chunk)",
        "difference": "total - hit",
        "weighted_average": "(rate*fast + (100-rate)*slow) / 100",
        "window_throughput": "window * 1000 / rtt",
        "percentage": "total * rate / 100",
        "backoff_sum": "base * (2^attempts - 1)",
        "directed_edges": "n * (n - 1)",
        "little_law": "rate * latency / 1000",
        "quorum_write": "N - R + 1",
        "two_tier_average": "P(L1)*L1 + P(L1miss,L2)*(L1+L2) + P(origin)*(L1+L2+origin)",
        "dense_params": "in_dim * out_dim + out_dim",
        "tensor_elements": "x * y * z",
        "exact_div": "total / chunk",
        "precision": "TP / (TP + FP)",
        "recall": "TP / (TP + FN)",
        "f1": "2TP / (2TP + FP + FN)",
        "conv_output": "floor((n + 2*padding - kernel) / stride) + 1",
        "triple_product": "a * b * c",
        "training_steps": "epochs * ceil(samples / batch)",
        "kv_cache_mib": "batch*layers*seq*heads*dim*2*bytes / 2^20",
        "lora_params": "rank * (in_dim + out_dim)",
        "training_mflops": "6 * params * tokens",
        "bayes": "sensitivity*prior / (sensitivity*prior + false_positive_rate*(1-prior))",
        "moe_active": "selected * expert + shared",
    }
    return formulas[solver]


def wrong_values(answer: Fraction) -> list[Fraction]:
    if answer.denominator == 1:
        n = answer.numerator
        candidates = [Fraction(n + 1), Fraction(max(0, n - 1)), Fraction(n * 2), Fraction(n + 2), Fraction(max(1, n // 2))]
    else:
        candidates = [answer + Fraction(1, 100), max(Fraction(0), answer - Fraction(1, 100)), answer * 2, answer + Fraction(1, 10), answer / 2]
    result: list[Fraction] = []
    rendered = {format_fraction(answer)}
    for candidate in candidates:
        text = format_fraction(candidate)
        if text not in rendered:
            result.append(candidate)
            rendered.add(text)
        if len(result) == 3:
            return result
    raise RuntimeError(f"could not create three unique distractors for {answer}")


def _family_id(item: dict[str, str], question_type: str) -> str:
    suffix = "choice" if question_type == "single_choice" else "fill"
    return f"{item['domain']}-{item['concept'].replace('_', '-')}-{item['difficulty'].lower()}-{suffix}"


def _render_prompt(item: dict[str, str], locale: str, parameters: dict[str, int], question_type: str) -> str:
    base = item["zh" if locale == "zh-CN" else "en"].format(**parameters)
    if question_type == "fill_blank":
        return base + (" 仅填写数值，不填写单位。" if locale == "zh-CN" else " Enter the numeric value only, without the unit.")
    return base


def make_question(item: dict[str, str], question_type: str, serial: int, variant: int, used_parameters: set[str]) -> dict[str, Any]:
    family_id = _family_id(item, question_type)
    for attempt in range(100):
        parameters = make_parameters(item["solver"], family_id, variant, attempt)
        parameter_key = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
        if parameter_key not in used_parameters:
            used_parameters.add(parameter_key)
            break
    else:
        raise RuntimeError(f"unable to create unique parameters for {family_id}")

    answer_value = solve(item["solver"], parameters)
    canonical = format_fraction(answer_value)
    question_id = f"{item['domain']}-{item['concept'].replace('_', '-')}-{serial:04d}"
    expression = solver_expression(item["solver"], parameters)
    evidence = f"solver={item['solver']}; formula={expression}; parameters={parameter_key}; result={canonical}"
    content_i18n: dict[str, dict[str, Any]] = {}
    answer: dict[str, str]

    if question_type == "single_choice":
        values = [answer_value] + wrong_values(answer_value)
        rotation = _draw(f"{family_id}|{variant}|answer-position", 0, 3)
        values = values[-rotation:] + values[:-rotation] if rotation else values
        option_ids = ("A", "B", "C", "D")
        answer_id = option_ids[values.index(answer_value)]
        for locale in LOCALES:
            unit = item["unit_zh" if locale == "zh-CN" else "unit_en"]
            options = [
                {"id": option_id, "text": format_fraction(value) + unit}
                for option_id, value in zip(option_ids, values, strict=True)
            ]
            if locale == "zh-CN":
                explanation = f"使用 {expression}，代入题目参数得到 {canonical}{unit}。"
                distractors = {
                    option_id: (
                        f"{format_fraction(value)}{unit} 是该选项代入后的值，"
                        f"与 reference solver 按 {expression} 得到的 {canonical}{unit} 不同。"
                    )
                    for option_id, value in zip(option_ids, values, strict=True)
                    if value != answer_value
                }
            else:
                explanation = f"Using {expression}, substituting the given parameters yields {canonical}{unit}."
                distractors = {
                    option_id: (
                        f"{format_fraction(value)}{unit} is the value represented by this option; "
                        f"it differs from the reference result {canonical}{unit} obtained with {expression}."
                    )
                    for option_id, value in zip(option_ids, values, strict=True)
                    if value != answer_value
                }
            content_i18n[locale] = {
                "prompt": _render_prompt(item, locale, parameters, question_type),
                "options": options,
                "explanation": explanation,
                "distractor_explanations": distractors,
            }
        answer = {"option_id": answer_id}
        accepted_answers: list[str] = []
        regex_answers: list[str] = []
        numeric_answer: float | int | None = None
        numeric_tolerance: float | None = None
    else:
        for locale in LOCALES:
            unit = item["unit_zh" if locale == "zh-CN" else "unit_en"]
            explanation = (f"使用 {expression}，代入题目参数得到 {canonical}{unit}。" if locale == "zh-CN" else f"Using {expression}, substituting the given parameters yields {canonical}{unit}.")
            content_i18n[locale] = {
                "prompt": _render_prompt(item, locale, parameters, question_type),
                "explanation": explanation,
            }
        answer = {"canonical": canonical}
        accepted_answers = [canonical]
        if canonical.startswith("0."):
            accepted_answers.append(canonical[1:])
        regex_answers = [f"^{re.escape(canonical)}$"]
        numeric_answer = int(answer_value) if answer_value.denominator == 1 else float(answer_value)
        numeric_tolerance = 0 if answer_value.denominator == 1 else 0.000001

    return {
        "id": question_id,
        "domain": item["domain"],
        "topic": item["topic"],
        "concept": item["concept"],
        "question_family_id": family_id,
        "difficulty": item["difficulty"],
        "type": question_type,
        "content_i18n": content_i18n,
        "answer": answer,
        "accepted_answers": accepted_answers,
        "regex_answers": regex_answers,
        "numeric_answer": numeric_answer,
        "numeric_tolerance": numeric_tolerance,
        "parameters": parameters,
        "verified": True,
        "verification": {
            "method": "reference_solver",
            "solver": item["solver"],
            "solver_version": "1",
            "evidence": evidence,
        },
        "version": 1,
    }


def generate_questions() -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    serials = Counter()
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for item in FAMILY_SPECS:
        for question_type in ("single_choice", "fill_blank"):
            grouped[(item["domain"], question_type, item["difficulty"])].append(item)

    for domain in ("sde", "mle"):
        for question_type in ("single_choice", "fill_blank"):
            for difficulty in ("L1", "L2", "L3"):
                families = grouped[(domain, question_type, difficulty)]
                target = QUOTA[domain][question_type][difficulty]
                family_counts = [target // len(families)] * len(families)
                for index in range(target % len(families)):
                    family_counts[index] += 1
                for item, count in zip(families, family_counts, strict=True):
                    used_parameters: set[str] = set()
                    for variant in range(1, count + 1):
                        serials[domain] += 1
                        questions.append(
                            make_question(
                                item,
                                question_type,
                                serials[domain],
                                variant,
                                used_parameters,
                            )
                        )
    questions.sort(key=lambda question: question["id"])
    return questions


SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://local.invalid/schemas/question-bank-v1.json",
    "title": "Bilingual verified question",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "id", "domain", "topic", "concept", "question_family_id", "difficulty",
        "type", "content_i18n", "answer", "accepted_answers", "regex_answers",
        "numeric_answer", "numeric_tolerance", "parameters", "verified",
        "verification", "version"
    ],
    "properties": {
        "id": {"type": "string", "pattern": "^(sde|mle)-[a-z0-9]+(-[a-z0-9]+)*-[0-9]{4}$"},
        "domain": {"enum": ["sde", "mle"]},
        "topic": {"type": "string", "minLength": 1},
        "concept": {"type": "string", "minLength": 1},
        "question_family_id": {"type": "string", "minLength": 1},
        "difficulty": {"enum": ["L1", "L2", "L3"]},
        "type": {"enum": ["single_choice", "fill_blank"]},
        "content_i18n": {
            "type": "object",
            "additionalProperties": False,
            "required": ["zh-CN", "en-US"],
            "properties": {
                "zh-CN": {"$ref": "#/$defs/content"},
                "en-US": {"$ref": "#/$defs/content"}
            }
        },
        "answer": {"type": "object"},
        "accepted_answers": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "regex_answers": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "numeric_answer": {"type": ["number", "null"]},
        "numeric_tolerance": {"type": ["number", "null"], "minimum": 0},
        "parameters": {"type": "object"},
        "verified": {"const": True},
        "verification": {
            "type": "object",
            "additionalProperties": False,
            "required": ["method", "solver", "solver_version", "evidence"],
            "properties": {
                "method": {"enum": ["reference_solver", "stable_fact"]},
                "solver": {"type": "string"},
                "solver_version": {"type": "string"},
                "evidence": {"type": "string", "minLength": 1}
            }
        },
        "version": {"const": 1}
    },
    "$defs": {
        "content": {
            "type": "object",
            "additionalProperties": False,
            "required": ["prompt", "explanation"],
            "properties": {
                "prompt": {"type": "string", "minLength": 1},
                "explanation": {"type": "string", "minLength": 1},
                "options": {
                    "type": "array", "minItems": 4, "maxItems": 4,
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["id", "text"],
                        "properties": {"id": {"enum": ["A", "B", "C", "D"]}, "text": {"type": "string", "minLength": 1}}
                    }
                },
                "distractor_explanations": {"type": "object"}
            }
        }
    }
}


README = """# Bilingual MLE/SDE question bank

This directory contains **1,000 logical questions**. Each JSONL record has one
locale-neutral ID and complete `zh-CN` plus `en-US` content. The bank is split
50/50 between SDE and MLE, contains 740 single-choice and 260 fill-in questions,
and has the exact L1/L2/L3 distribution 300/500/200.

## Reproduce and validate

From the repository root:

```bash
python3 scripts/generate_question_bank.py --output question_bank
python3 scripts/validate_question_bank.py --root question_bank
python3 -m unittest discover -s question_bank/tests -v
```

Generation does not use wall-clock time, Python `hash()`, an LLM, or global
random state. Parameters are derived from SHA-256 of the generator seed,
family ID, variant index, and parameter name. Every stored answer is produced
by a pure reference solver. `seed_manifest.json` records the generator version,
family inventory, quota, and protected file hashes; `seed_checksums.sha256`
duplicates the protected hashes in standard checksum form.

## Verification boundary

`verified=true` means the record passed deterministic structural checks and its
answer came from the named reference solver. It does **not** mean that 1,000
questions were independently reviewed by a subject-matter expert. The shipped
validation report therefore keeps `algorithmically_verified` and
`human_reviewed` separate; the latter is zero until a real review is recorded.

Choice distractors are numeric alternatives and every wrong option has a
bilingual explanation. Fill-in grading includes a canonical answer, accepted
aliases, an anchored regular expression, and numeric tolerance. Runtime grading
should normalize Unicode, trim whitespace, case-fold aliases, then apply regex
and numeric tolerance. During an in-progress exam, applications must project
away answers, explanations, verification evidence, and grading rules as required
by `docs/contracts.md`.
"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_bank(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    questions = generate_questions()
    questions_path = output / "questions.jsonl"
    questions_path.write_text(
        "".join(json.dumps(question, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for question in questions),
        encoding="utf-8",
    )
    schema_path = output / "schema.json"
    schema_path.write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "README.md").write_text(README, encoding="utf-8")

    protected = ("questions.jsonl", "schema.json")
    file_metadata = {name: {"sha256": sha256_file(output / name), "bytes": (output / name).stat().st_size} for name in protected}
    family_counts = Counter(question["question_family_id"] for question in questions)
    manifest = {
        "format_version": 1,
        "generator": "scripts/generate_question_bank.py",
        "generator_version": GENERATOR_VERSION,
        "seed": GENERATOR_SEED,
        "logical_question_count": len(questions),
        "locale_count": 2,
        "locales": list(LOCALES),
        "family_count": len(family_counts),
        "family_variant_counts": dict(sorted(family_counts.items())),
        "quota": QUOTA,
        "files": file_metadata,
        "review_status": {"algorithmically_verified": len(questions), "human_reviewed": 0},
    }
    (output / "seed_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "seed_checksums.sha256").write_text("".join(f"{file_metadata[name]['sha256']}  {name}\n" for name in protected), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "question_bank")
    args = parser.parse_args()
    write_bank(args.output)
    print(f"generated {len(generate_questions())} deterministic bilingual questions in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

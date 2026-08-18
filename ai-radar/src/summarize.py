"""
唯一一次 LLM 调用 —— 把配额选出的候选压缩成中文标题 + 两句话摘要。

规格来源：daimonia-trends-radar 改造计划 §四 5

关键的省 token 设计：一次调用处理全部候选，不是每条一次。

三层降级路径，任何一层触发都不能让邮件发不出去（改造计划第一原则：
"邮件必须发出去"）：
  1. 无 API key（或 provider: none）—— 跳过调用
  2. 调用失败 / 超时                 —— 同上
  3. 返回内容不是合法 JSON            —— 同上
降级时直接用原标题（截断）+ summary_raw 截断前 70 字符，不阻塞管道。
"""
from __future__ import annotations

import json
import logging
import os
import re

import requests

logger = logging.getLogger("summarize")

SYSTEM_PROMPT = """你是一份中文 AI 日报的编辑。输入是今天的候选资讯（中英文混合），
为每条输出中文摘要。

规则：
1. 标题：不超过 22 个汉字，陈述事实，不用"重磅""震撼""炸裂"等词。
   英文来源必须译成中文。
2. 正文：恰好两句话，不超过 70 个汉字。
   第一句说发生了什么（谁、做了什么、关键数字）。
   第二句说来源如何表述、或对读者意味着什么。
3. 传闻必须标注："据XX报道""XX援引XX称"。不要把传闻写成既成事实。
4. 输入信息不足以写满两句话时，写一句即可。禁止编造数字、日期、人名。
5. 禁用形容词：革命性、颠覆、重磅、史诗级、王炸、遥遥领先。

严格输出 JSON 数组，顺序与输入一致，不要任何额外文字：
[{"i": 0, "title": "...", "body": "..."}]"""


def _fallback_summary(item: dict) -> tuple[str, str]:
    title = (item.get("title") or "")[:40]
    body = (item.get("summary_raw") or "")[:70]
    return title, body


def _build_user_prompt(items: list[dict]) -> str:
    lines = []
    for i, it in enumerate(items):
        lines.append(
            json.dumps(
                {
                    "i": i,
                    "title": it.get("title", ""),
                    "summary": (it.get("summary_raw") or "")[:200],
                    "source": it.get("source", ""),
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def _call_deepseek(items: list[dict], llm_cfg: dict, api_key: str) -> list[dict] | None:
    url = f"{llm_cfg['base_url'].rstrip('/')}/chat/completions"
    payload = {
        "model": llm_cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(items)},
        ],
        "max_tokens": llm_cfg.get("max_output_tokens", 4000),
        "temperature": 0.3,
    }
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=llm_cfg.get("timeout_s", 60),
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("DeepSeek 调用失败: %s，降级为原文摘要", exc)
        return None

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning("DeepSeek 响应结构异常: %s，降级为原文摘要", exc)
        return None

    # 部分模型会把 JSON 包在 ```json ... ``` 代码块里，先剥掉再解析
    content = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", content.strip())
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("DeepSeek 返回内容不是合法 JSON: %s，降级为原文摘要", exc)
        return None

    if not isinstance(parsed, list):
        logger.warning("DeepSeek 返回内容不是 JSON 数组，降级为原文摘要")
        return None
    return parsed


def summarize(items: list[dict], llm_cfg: dict) -> tuple[list[dict], bool]:
    """就地在每个 item 上补 title_zh / body_zh，返回 (items, llm_used)。
    llm_used=False 时邮件 footer 要标注"已降级"，方便一眼看出管道是否健康
    ——特别是"LLM 调用失败"持续多天意味着 key 过期或 DeepSeek 侧出了问题。
    """
    provider = llm_cfg.get("provider", "none")
    api_key = os.environ.get(llm_cfg.get("api_key_env", ""), "")

    if provider == "none" or not api_key:
        logger.info("LLM 未启用或缺少 API key，跳过摘要，使用原文降级")
        for it in items:
            it["title_zh"], it["body_zh"] = _fallback_summary(it)
        return items, False

    result = _call_deepseek(items, llm_cfg, api_key)
    if result is None:
        for it in items:
            it["title_zh"], it["body_zh"] = _fallback_summary(it)
        return items, False

    by_index: dict[int, dict] = {}
    for entry in result:
        try:
            by_index[int(entry["i"])] = entry
        except (KeyError, TypeError, ValueError):
            continue

    for i, it in enumerate(items):
        entry = by_index.get(i)
        if entry and entry.get("title") and entry.get("body"):
            it["title_zh"] = entry["title"]
            it["body_zh"] = entry["body"]
        else:
            it["title_zh"], it["body_zh"] = _fallback_summary(it)

    return items, True

"""信源探活 —— 逐个拉取 config/sources.yaml 里的源，打印可用性。

规格来源：daimonia-trends-radar 改造计划 v2 §三 §六

在改动信源配置之后先跑这个脚本：RSS/API 地址会变，跑不通就先修
config/sources.yaml，不要往下写占用了失效地址的代码。

门槛（改造计划 v2 §五）：blogs 至少 8/11 通过、HF 三个端点全通、
HN 与 V2EX 通。只读网络请求，不写任何仓库文件。
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import feedparser
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UA = "Mozilla/5.0 (compatible; ai-radar-smoke/1.0)"
TIMEOUT_S = 20


def _probe_rss(name: str, url: str) -> tuple[str, str, int, str]:
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT_S)
    except requests.RequestException as exc:
        return (name, type(exc).__name__, 0, str(exc)[:60])
    if resp.status_code != 200:
        return (name, f"HTTP {resp.status_code}", 0, "")
    parsed = feedparser.parse(resp.content)
    n = len(parsed.entries)
    first = (parsed.entries[0].get("title", "") if n else "")[:50]
    return (name, "HTTP 200", n, first)


def _probe_json(name: str, url: str) -> tuple[str, str, int, str]:
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT_S)
    except requests.RequestException as exc:
        return (name, type(exc).__name__, 0, str(exc)[:60])
    if resp.status_code != 200:
        return (name, f"HTTP {resp.status_code}", 0, "")
    try:
        data = resp.json()
    except ValueError:
        return (name, "解析失败", 0, "")
    n = len(data) if isinstance(data, list) else 0
    first = ""
    if n:
        d0 = data[0]
        first = str(d0.get("id") or d0.get("title") or "")[:50]
    return (name, "HTTP 200", n, first)


def _probe_hackernews(cfg: dict) -> tuple[str, str, int, str]:
    try:
        resp = requests.get(cfg["url"], headers={"User-Agent": UA}, timeout=TIMEOUT_S)
    except requests.RequestException as exc:
        return ("Hacker News", type(exc).__name__, 0, str(exc)[:60])
    if resp.status_code != 200:
        return ("Hacker News", f"HTTP {resp.status_code}", 0, "")
    hits = resp.json().get("hits", [])
    first = (hits[0].get("title", "") if hits else "")[:50]
    return ("Hacker News", "HTTP 200", len(hits), first)


def build_rss_jobs(cfg: dict) -> list[tuple[str, str]]:
    jobs: list[tuple[str, str]] = []

    for src in cfg.get("blogs", []):
        jobs.append((f"blog:{src['name']}", src["url"]))

    v2 = cfg.get("v2ex", {})
    if v2.get("url"):
        jobs.append(("V2EX", v2["url"]))

    gh = cfg.get("github_releases", {})
    for repo in gh.get("watch", [])[:4]:  # 只抽 4 个验证 Atom 端点通不通
        jobs.append((f"gh-release:{repo}", f"https://github.com/{repo}/releases.atom"))

    return jobs


def build_hf_jobs(cfg: dict) -> list[tuple[str, str]]:
    hf = cfg.get("huggingface_api", {})
    jobs = []
    if hf.get("trending_models_url"):
        jobs.append(("hf:trending_models", hf["trending_models_url"]))
    if hf.get("daily_papers_url"):
        jobs.append(("hf:daily_papers", hf["daily_papers_url"]))
    if hf.get("trending_datasets_url"):
        jobs.append(("hf:trending_datasets", hf["trending_datasets_url"]))
    return jobs


def main() -> int:
    sources_path = ROOT / "config" / "sources.yaml"
    with sources_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    rss_jobs = build_rss_jobs(cfg)
    hf_jobs = build_hf_jobs(cfg)

    with ThreadPoolExecutor(max_workers=8) as ex:
        rss_results = list(ex.map(lambda j: _probe_rss(*j), rss_jobs))
        hf_results = list(ex.map(lambda j: _probe_json(*j), hf_jobs))
    results = rss_results + hf_results + [_probe_hackernews(cfg["hackernews"])]

    print(f"{'源':<28} {'状态':<16} {'条目':>4}  第一条样例")
    print("-" * 110)
    ok = 0
    blog_ok = 0
    hf_ok = 0
    blog_total = len(cfg.get("blogs", []))
    for name, status, n, first in results:
        good = status == "HTTP 200" and n > 0
        flag = "OK " if good else "BAD"
        if good:
            ok += 1
            if name.startswith("blog:"):
                blog_ok += 1
            if name.startswith("hf:"):
                hf_ok += 1
        print(f"{flag} {name:<25} {status:<16} {n:>4}  {first}")
    print("-" * 110)
    hn_ok = any(name == "Hacker News" and status == "HTTP 200" and n > 0 for name, status, n, _ in results)
    v2ex_ok = any(name == "V2EX" and status == "HTTP 200" and n > 0 for name, status, n, _ in results)
    print(f"可用 {ok}/{len(results)} · blogs {blog_ok}/{blog_total} · HF {hf_ok}/3 · HN {'OK' if hn_ok else 'BAD'} · V2EX {'OK' if v2ex_ok else 'BAD'}")
    print("门槛：blogs 至少 8/11 通过、HF 三个端点全通、HN 与 V2EX 通")

    if blog_ok < 8 or hf_ok < 3 or not hn_ok or not v2ex_ok:
        print("\n未达到门槛 —— 先修 config/sources.yaml 再继续开发。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

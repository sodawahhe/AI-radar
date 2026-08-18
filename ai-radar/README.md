# AI Radar

个人 AI 资讯简报：每天固定 10–12 条中文摘要，Gmail 送达。5 个分档——
GitHub（自建 star 时间序列 + Release 事件）、模型生态（HuggingFace
trending/papers）、社区（HN/V2EX）、一线视角（从业者/实验室博客）、行业
动向（硬上限 2 条）。完整设计见 [`PROJECT_SPEC_V2.md`](../PROJECT_SPEC_V2.md)，
本轮改造背景见 `daimonia-trends-radar` 改造计划（2026-08-18，v1+v2 两版）。

当前进度：v2 已上线。v1 曾用 Google News + 36氪等二手转载媒体，实测导致要闻区
被泛财经淹没、工程区被同仓库连续补丁版本号刷屏；v2 换成一手数据 API + 一线
从业者博客 + 社区原帖，不再订阅任何新闻媒体，GitHub 技能雷达重新升级为
GitHub 分档的正文内容（不再是邮件底部附属区块）。

## 每日运行入口

```powershell
cd ai-radar
pip install -r requirements.txt

# 强烈建议设置，未认证请求限速更低：
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"        # 技能雷达管道用
$env:DEEPSEEK_API_KEY = "sk-xxxxxxxxxxxx"      # 摘要用，缺失时自动降级为原文
$env:GMAIL_USER = "you@gmail.com"
$env:GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"

# 先跑一遍信源探活，确认 RSS 地址都还活着（地址会变）：
python scripts/smoke_feeds.py

# 预览邮件而不真的发送——写到 out/preview.html / out/preview.txt：
$env:DRY_RUN = "1"; python run_daily.py

# 真发一封：
Remove-Item Env:\DRY_RUN
python run_daily.py
```

产出：
- 邮件本体 —— 分「🔧 GitHub / 🤗 模型生态 / 💬 社区 / 📝 一线视角 / 📌 行业动向」五档
- `reports/daily/{今天日期}-news.md` —— 当天全部候选资讯（含未入选条目），供偶尔翻阅
- `reports/daily/{今天日期}.md` —— 技能雷达完整排序榜单（原 Phase 0 产出，格式不变）
- `data/snapshots/{今天日期}.jsonl` —— 技能雷达当日快照，用于计算 7 日增速
- `data/seen/{今天日期}.jsonl` —— 当天已推送资讯的标题指纹，保留 7 天，供跨天去重

## 运行测试

```powershell
pip install pytest
pytest tests/ -v
```

`test_score.py` 直接使用 `PROJECT_SPEC_V2.md` §3.5 中的真实仓库数据做断言。
`test_summarize.py` 用 mock 验证 LLM 调用失败/超时/JSON 解析失败三层降级路径
都不会阻塞发信——这是本系统的第一原则："邮件必须发出去"。
`test_gh_events.py` 验证 release 实质性过滤（版本号+changelog 长度）。
`test_collect_hf.py` mock HuggingFace 三个 API 响应验证字段归一化。

## 目录结构

```
config/
  sources.yaml         资讯信源清单（博客 / HN / V2EX / GitHub Release / HF API）
  news_scoring.yaml    资讯打分权重、关键词表、去重阈值、配额、多样性上限
  llm.yaml              摘要 LLM 配置（provider: none 时零 LLM 降级）
  watchlist.yaml        技能雷达种子仓库
  scoring.yaml           技能雷达打分权重、完整性闸门阈值
src/
  collect_feeds.py       一线博客 / Hacker News / V2EX 采集
  collect_gh_events.py   GitHub Release 采集，release 实质性过滤
  collect_hf.py           HuggingFace trending models/papers/datasets 采集
  normalize.py             清洗 + URL 规范化 + 跨源去重 + 跨天去重
  rank_news.py             零 LLM 打分 + 行业重打标 + 5 分档配额选取
  summarize.py             唯一一次 LLM 调用（三层降级）
  render_brief.py          HTML + 纯文本邮件渲染（5 分档）
  collect_github.py / score.py / render.py   技能雷达管道（不变）
  store.py                  快照 + seen 指纹读写
  send.py                   Gmail SMTP 发送（HTML + 纯文本双版本）
scripts/
  smoke_feeds.py       信源探活，改动信源配置后先跑这个
data/
  snapshots/           技能雷达快照（提交进 git，见 §7）
  seen/                资讯去重指纹，7 天滚动窗口
reports/daily/         每日报告（news 候选榜单 + 技能雷达完整榜单）
tests/
run_daily.py           唯一运行入口
run_phase0.py           技能雷达单独手动运行（不发邮件，调试打分公式用）
```

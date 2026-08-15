# AI Radar

个人 AI/DS 工具与 GitHub 技能雷达。完整设计见 [`PROJECT_SPEC_V2.md`](../PROJECT_SPEC_V2.md)。

当前进度：**Phase 0**（GitHub 技能雷达核心算法，零 LLM，本地手动运行）。

## Phase 0 快速开始（PowerShell）

```powershell
cd ai-radar
pip install -r requirements.txt

# 强烈建议设置 GITHUB_TOKEN —— 未认证请求限速 60 次/小时，
# watchlist 里约 50 个仓库会很快耗尽额度。
# 去 https://github.com/settings/tokens 创建一个 fine-grained token，
# 不需要任何写权限，public repositories 只读即可。
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"

python run_phase0.py
```

产出：
- `reports/daily/{今天日期}.md` —— 打开它，亲眼判断这份榜单是否比
  [github.com/trending](https://github.com/trending) 更有用。这是 Phase 0
  唯一的通过标准（`PROJECT_SPEC_V2.md` §10）。
- `data/snapshots/{今天日期}.jsonl` —— 当日快照，明天再跑一次即可开始
  看到真实的 7 日增速（momentum）。

## 运行测试

```powershell
pip install pytest
pytest tests/ -v
```

测试直接使用 `PROJECT_SPEC_V2.md` §3.5 中的真实仓库数据做断言 —— 改坏
完整性闸门的阈值会让测试立刻变红。

## 目录结构

```
config/       打分权重、完整性闸门阈值、关键词表、watchlist 种子仓库
src/          collect_github / store / score / render（Phase 0 全部内容）
data/         快照（提交进 git = 状态持久化 + cron 心跳，见 §7）
reports/      每日/每周报告
tests/        score.py 的完整性闸门测试
run_phase0.py Phase 0 唯一运行入口
```

## 本阶段明确不做的事

不发邮件、不调用任何 LLM、不做厂商变动监控、不抓 trending 页、不做
topic 查询。这些都是 Phase 1/2 的范围（`PROJECT_SPEC_V2.md` §10 §14）。

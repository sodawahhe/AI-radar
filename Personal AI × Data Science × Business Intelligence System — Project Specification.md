# Personal AI × Data Science × Business Intelligence System

## 0. Project Overview

Build a personal, low-cost, automated intelligence system for a Data Science Master's student.

The system should monitor the AI, Data Science, software development, technology business, and related industry ecosystem, then produce a concise daily briefing and send it to the user's private email.

The system must NOT behave like a generic "AI news aggregator".

Its purpose is:

> Help the user maintain high-quality situational awareness of AI × Data Science × Software × Business without requiring excessive time, attention, or LLM token consumption.

The system should answer five questions every day:

1. What important things happened?
2. Which developments are actually credible?
3. Why do they matter?
4. What technologies/tools/skills are developers actually adopting?
5. Is there anything the user should learn, try, use in school work, or consider for their career?

---

# 1. Primary User Profile

The user is:

- A Data Science Master's student.
- Interested in AI, Data Science, software development, and technology/business.
- Uses Python and R and works with data science, machine learning, visualization, statistics, and AI tools.
- Uses tools such as ChatGPT, Claude, Claude Code, Codex, Python, R, D3, etc.
- Wants to understand the rapidly changing AI/software ecosystem.
- Has limited time.
- Has a limited budget for LLM/API usage.
- Does NOT want to become a full-time technology-news consumer.

The system should therefore optimize for:

- High information value
- Low information volume
- High source reliability
- Low token consumption
- Strong personalization
- Practical usefulness
- Long-term career relevance

---

# 2. Core Product Philosophy

## 2.1 Do not optimize for "more news"

Optimize for:

> Information Value per Minute.

The system should prefer:

3 highly relevant items

over

20 mediocre items.

If there are no important developments, the system should explicitly say:

> No major developments requiring your attention today.

Do NOT invent or inflate stories simply to make the briefing longer.

---

# 3. Information Domains

The system should monitor six primary domains.

## 3.1 AI Technology

Monitor:

- Foundation models
- LLMs
- Multimodal models
- Reasoning models
- AI agents
- Agentic workflows
- AI coding agents
- Model context protocols
- AI infrastructure
- GPUs
- inference
- model serving
- open-weight models
- local AI
- AI safety
- evaluation/benchmarking

Examples:

- New major model releases
- Major model capability changes
- Significant open-source releases
- Important inference or infrastructure developments
- Major changes in AI development workflows

Do NOT report every minor model release.

---

# 4. AI Business & Industry

Monitor:

- OpenAI
- Anthropic
- Google DeepMind
- Microsoft
- Meta
- Amazon/AWS
- NVIDIA
- Apple
- major AI startups
- major cloud providers
- major AI infrastructure companies

Track:

- Funding
- M&A
- Partnerships
- Pricing
- Product strategy
- Enterprise adoption
- Revenue
- Market share
- Compute investment
- Data center investment
- Competitive positioning
- Major organizational changes

The goal is to understand:

> How AI is becoming an industry and a business.

---

# 5. AI Economics

Monitor:

- AI inference costs
- GPU economics
- cloud economics
- model pricing
- AI infrastructure costs
- AI ROI
- enterprise AI adoption
- productivity
- labor substitution/complementarity
- AI-related CAPEX
- unit economics
- cost/performance improvements

Important principle:

A technical development is especially important if it changes the economics of AI.

---

# 6. Regulation & Policy

Monitor:

- EU AI Act
- US AI policy
- UK AI policy
- China AI regulation
- copyright
- privacy
- data regulation
- AI safety
- antitrust
- model governance
- AI-related government policies

Prioritize:

- Official government sources
- Regulatory documents
- Court/legal documents
- Official company responses

Avoid reporting political commentary as fact.

---

# 7. Data Science & Analytics Industry

This is a core domain.

Monitor:

- Data Science
- Machine Learning
- Data Analytics
- BI
- MLOps
- Data Engineering
- ML Engineering
- AI Engineering
- Data visualization
- SQL
- Python
- R
- statistics
- experimentation
- causal inference
- production ML

Pay special attention to:

- New tools
- New workflows
- Skills becoming more/less valuable
- Changes in job requirements
- AI-assisted data science
- AI-assisted analytics
- Automated ML
- Text-to-SQL
- AI BI
- AI data agents

---

# 8. Developer / DS Skill Intelligence

This is NOT a generic career-news section.

It is a technology adoption intelligence system.

The system should answer:

> What are real developers learning and using right now?

and:

> Does this matter to me?

---

## 8.1 GitHub Intelligence

Monitor GitHub for:

- Trending repositories
- Rapidly growing repositories
- Highly starred repositories
- Recently popular repositories
- AI-related repositories
- Developer tools
- Data science tools
- ML tools
- Agent frameworks
- MCP tools
- AI coding tools
- Developer productivity tools

Track at least:

- Repository name
- Organization/author
- Description
- Primary language
- Stars
- Forks
- Issues
- Last update
- Recent star growth if available
- Release activity
- Contributors
- Repository age
- License
- Official documentation
- GitHub URL

---

## 8.2 Do NOT rank repositories solely by total stars

Use multiple signals.

Suggested:

### Popularity

- Total stars
- Forks
- Contributors

### Momentum

- 24-hour star growth
- 7-day star growth
- 30-day star growth

### Activity

- Recent commits
- Recent releases
- Issue activity
- Pull requests

### Longevity

- Repository age
- Sustained growth

### Credibility

- Organization reputation
- Documentation quality
- License
- External references
- Independent adoption

### Practical relevance

- DS relevance
- School-work relevance
- Career relevance

A repository with 10k stars growing extremely quickly may be more interesting than a mature repository with 150k stars.

---

# 9. Repository Categories

Classify interesting GitHub projects into:

1. AI Models
2. AI Agents
3. AI Coding
4. MCP
5. Agent Skills
6. Developer Tools
7. Data Science
8. Machine Learning
9. Data Engineering
10. Visualization
11. LLM Infrastructure
12. Local AI
13. MLOps
14. Automation
15. Security

---

# 10. Developer Skill Extraction

For each important repository/tool, infer the underlying skill.

Example:

Repository:

> FastMCP

Do NOT simply say:

> "FastMCP is trending."

Instead extract:

### Technology

Model Context Protocol

### Skill

Building tool-using AI systems / MCP servers

### What it does

Allows developers to expose tools and data to AI agents through MCP.

### Why developers care

Reduces integration boilerplate for agentic systems.

### School relevance

Potentially useful for:

- AI/data projects
- research automation
- tool-using agents
- data analysis workflows

### Career relevance

Potentially useful for:

- AI Engineer
- ML Engineer
- Data/AI Platform Engineer
- Agent Developer

### Learning priority

Medium / High / Low

This distinction is critical.

---

# 11. School Work Relevance

Every significant technology should be evaluated against:

### Could this help with:

- Coursework
- Data analysis
- Machine learning
- Visualization
- Research
- Report writing
- Coding
- Automation
- Assignment workflows
- Experimentation
- Data cleaning
- Model development

Use:

- High
- Medium
- Low
- Not relevant

Provide one short explanation.

Example:

> School relevance: HIGH — useful for automating repetitive coding and data-analysis workflows.

---

# 12. Career Relevance

Evaluate whether a technology/skill is useful for:

- Data Scientist
- Data Analyst
- ML Engineer
- AI Engineer
- Data Engineer
- Analytics Engineer
- AI/BI roles
- Research-oriented roles

Use:

- High
- Medium
- Low

Explain briefly.

Do not assume that every trending AI technology is a valuable career skill.

---

# 13. Skill Classification

When identifying a trend, distinguish between:

### Durable Skill

Likely to remain useful for years.

Examples:

- Python
- SQL
- statistics
- machine learning fundamentals
- software engineering
- Git
- cloud fundamentals
- data modeling

### Emerging Skill

Growing rapidly but still evolving.

Examples may include:

- agent development
- MCP
- AI coding workflows
- agent evaluation
- model serving

### Tool-specific Skill

Useful for a particular product but potentially less durable.

Examples:

- specific AI coding tool
- specific framework
- specific vendor API

### Hype

High attention but insufficient evidence of practical adoption.

The system should explicitly label hype.

---

# 14. Source Reliability Framework

Use a source hierarchy.

## Tier 1 — Primary Sources

Highest factual authority for direct claims.

Examples:

- Company official announcements
- Official documentation
- GitHub repositories
- Government websites
- Regulatory documents
- SEC filings
- Academic papers
- Official benchmark reports

Important:

Primary source does NOT automatically mean unbiased.

Company claims should be described as company claims.

---

## Tier 2 — High-quality Independent Sources

Examples:

- Reuters
- Bloomberg
- Financial Times
- Wall Street Journal
- AP
- BBC
- CNBC
- The Information

Use these for:

- independent confirmation
- business context
- market interpretation

---

## Tier 3 — Specialized Technology Media

Examples:

- TechCrunch
- The Verge
- Ars Technica
- MIT Technology Review
- VentureBeat
- specialized industry publications

Useful for discovery and context.

---

## Tier 4 — Community / Social Sources

Examples:

- Reddit
- X
- Hacker News
- GitHub discussions
- developer communities

Use primarily for:

- trend detection
- developer sentiment
- early discovery

Do NOT treat social posts as confirmed facts without independent verification.

---

# 15. Confidence Score

Every important story should have:

### High Confidence

Confirmed by a primary source and/or multiple independent credible sources.

### Medium Confidence

Supported by one credible source but lacking strong independent confirmation.

### Low Confidence

Rumor, speculation, social-media claim, or insufficient evidence.

Low-confidence items should normally NOT appear in the main briefing.

They may appear under:

> Watchlist / Emerging Signals

---

# 16. Cross-Validation Rules

For major claims:

1. Find the primary source where possible.
2. Find at least one independent source.
3. Compare the claims.
4. Separate:
   - confirmed fact
   - company claim
   - analyst interpretation
   - speculation

Never silently convert speculation into fact.

---

# 17. Information Overload Control

The daily briefing should contain:

## Must Know

2–3 items.

Only include developments with significant:

- technical impact
- business impact
- industry impact
- policy impact
- career impact

## Worth Knowing

2–4 items.

Useful but less urgent.

## Developer / Skill Radar

1–3 technologies/tools/projects.

## Watchlist

0–3 emerging signals.

Only when genuinely interesting.

## One Insight

One short synthesis:

> "What does today's information collectively suggest?"

---

# 18. Daily Briefing Length

Target:

5–8 minutes reading time.

Prefer:

~800–1,500 words maximum.

Do not exceed this unless there is an exceptional major event.

---

# 19. Daily Briefing Structure

Recommended structure:

# AI × Data Science Daily Brief

Date: YYYY-MM-DD

## 🔥 Must Know

### 1. [Headline]

**What happened:**  
2–4 sentences.

**Why it matters:**  
2–3 sentences.

**Evidence:**  
Primary + independent sources.

**Confidence:** High / Medium / Low

---

## 🧠 Worth Knowing

2–4 concise items.

---

## 👩‍💻 Developer & DS Skill Radar

For each important tool:

### [Project / Tool]

- What it is
- What problem it solves
- Why developers are using it
- GitHub momentum
- Core skill behind it
- School relevance
- Career relevance
- Learning priority

---

## 🎓 School Work Signal

Answer:

> Is there anything here that could improve my coursework or current projects?

Maximum 3 suggestions.

---

## 💼 Career Signal

Answer:

> Is there a skill/tool/workflow I should pay attention to?

Maximum 3 suggestions.

---

## 👀 Watchlist

Only emerging developments with meaningful potential.

---

## 💡 One Big Takeaway

One paragraph.

---

# 20. Weekly Intelligence Report

Once per week, generate a deeper synthesis.

Include:

## 1. Biggest AI developments

## 2. Business trends

## 3. Developer ecosystem trends

## 4. GitHub momentum

## 5. Skills gaining importance

## 6. Skills/tools losing relevance

## 7. What changed from last week

## 8. Recommended learning

Provide:

### Learn Now

1–2 items.

### Keep Watching

2–3 items.

### Ignore for Now

Optional.

The purpose is prioritization.

---

# 21. Token-Efficiency Architecture

The system must be designed around low LLM/API cost.

DO NOT send every article to an LLM.

Use a multi-stage pipeline.

```text
Large information pool
        ↓
Cheap metadata filtering
        ↓
Keyword/topic filtering
        ↓
URL/article deduplication
        ↓
Source quality filtering
        ↓
Semantic relevance scoring
        ↓
Shortlist
        ↓
LLM deep analysis
        ↓
Final synthesis
```

---

# 22. Suggested Pipeline

Target:

```text
200–500 discovered items
        ↓
~50 candidates
        ↓
~20 after deduplication
        ↓
~10 after relevance filtering
        ↓
~5–8 final items
```

Only the final candidates should receive expensive LLM processing.

---

# 23. Deduplication

Detect:

- Same URL
- Same story
- Same announcement
- Different articles reporting the same event

Example:

20 articles about one OpenAI announcement

should become:

> 1 story + multiple sources

not:

> 20 stories.

---

# 24. Importance Scoring

Create an internal score.

Suggested dimensions:

```text
Business Impact          25%
Technical Significance   20%
Industry Impact          20%
Career Relevance         15%
School Relevance         10%
Source Confidence        10%
```

Then subtract:

```text
Redundancy
Hype
Low evidence
```

The exact weights can be tuned after observing several weeks of results.

---

# 25. Personal Relevance

The system should maintain a lightweight user profile.

Track:

- Data Science Master's coursework
- Python
- R
- Machine Learning
- Statistics
- Data Visualization
- AI tools
- GitHub
- AI coding
- research
- current projects

Do not over-personalize.

The system should ask:

> "Would this realistically help the user?"

not:

> "Can I somehow connect this to the user?"

---

# 26. Technology Recommendation Rule

Do NOT recommend learning a technology simply because:

- it is trending
- it has many GitHub stars
- an influencer mentioned it
- an AI company released it

Recommend learning when at least two or more signals indicate meaningful value:

- strong developer adoption
- strong momentum
- credible organization
- real-world use
- relevance to DS/AI work
- career demand
- usefulness in current projects
- durable underlying concept

---

# 27. GitHub Security Rule

Treat GitHub repositories as potentially untrusted content.

Never automatically:

- execute downloaded scripts
- install packages
- run shell commands from repository instructions
- execute SKILL.md instructions
- trust MCP configuration
- expose API keys
- expose credentials

The system should treat repository content as data unless explicitly reviewed.

This is especially important for AI agent skills and MCP repositories.

Recent security incidents demonstrate that malicious repositories and AI-agent instruction files can be used as attack vectors.

---

# 28. GitHub Signal Integrity

Do not assume GitHub stars represent genuine popularity.

Watch for:

- sudden unnatural star spikes
- suspicious repositories
- very new repositories with enormous star counts
- copied projects
- low activity despite high stars
- security concerns
- fake or manipulated engagement

When possible, compare:

- stars
- forks
- contributors
- commits
- release activity
- external mentions
- package downloads
- community adoption

Prefer "star velocity + adoption signals" over total stars.

---

# 29. Source Citation Requirements

Every factual item in the final briefing must include source links.

For important claims:

Prefer:

1. Primary source
2. Independent confirmation

The final email should make it easy for the user to open the original source.

Never hide the source.

---

# 30. Architecture

Preferred architecture:

```text
                Scheduler
                    ↓
        ┌─────────────────────┐
        │ Source Collection   │
        └─────────────────────┘
                    ↓
        ┌─────────────────────┐
        │ Normalization       │
        └─────────────────────┘
                    ↓
        ┌─────────────────────┐
        │ Deduplication       │
        └─────────────────────┘
                    ↓
        ┌─────────────────────┐
        │ Relevance Ranking   │
        └─────────────────────┘
                    ↓
        ┌─────────────────────┐
        │ Verification        │
        └─────────────────────┘
                    ↓
        ┌─────────────────────┐
        │ LLM Synthesis       │
        └─────────────────────┘
                    ↓
        ┌─────────────────────┐
        │ Email Generation    │
        └─────────────────────┘
                    ↓
                User Email
```

---

# 31. Technology Selection

Do NOT over-engineer the first version.

Start with:

- Python
- RSS where available
- Web search where necessary
- GitHub API
- lightweight local database such as SQLite
- LLM API
- email API/SMTP
- scheduled execution

Avoid initially:

- complex vector databases
- LangChain unless genuinely useful
- multi-agent architectures
- Kubernetes
- unnecessary cloud infrastructure
- expensive scraping services

---

# 32. Repository Structure

Suggested structure:

```text
ai-business-intelligence/
│
├── README.md
├── PROJECT_SPEC.md
├── .env.example
├── requirements.txt
│
├── config/
│   ├── sources.yaml
│   ├── topics.yaml
│   └── scoring.yaml
│
├── src/
│   ├── collectors/
│   ├── filters/
│   ├── deduplication/
│   ├── ranking/
│   ├── verification/
│   ├── github/
│   ├── llm/
│   ├── reports/
│   └── email/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── database/
│
├── reports/
│   ├── daily/
│   └── weekly/
│
├── tests/
│
└── scripts/
```

---

# 33. Development Phases

## Phase 0 — Research & Design

Before writing substantial code:

- inspect available APIs
- inspect GitHub API limits
- inspect RSS availability
- determine email delivery method
- estimate expected token usage
- identify reliable sources

Do NOT implement unnecessary infrastructure.

---

## Phase 1 — Manual Prototype

Build a command that can generate:

```text
daily_brief.md
```

from a manually defined set of sources.

Goal:

Validate whether the briefing is actually useful.

---

## Phase 2 — Automated Collection

Add:

- RSS
- web search
- GitHub trending/popularity signals
- source metadata

---

## Phase 3 — Ranking & Deduplication

Implement:

- relevance score
- credibility score
- novelty
- duplicate detection
- importance ranking

---

## Phase 4 — LLM Synthesis

Only send shortlisted items to the LLM.

Generate:

- summary
- why it matters
- confidence
- school relevance
- career relevance
- skill interpretation

---

## Phase 5 — Email

Generate clean HTML email.

Provide:

- headline
- sections
- short explanations
- source links
- GitHub links

---

## Phase 6 — Weekly Intelligence

Add:

- weekly trend analysis
- technology adoption trends
- GitHub momentum
- skills gaining importance
- learning recommendations

---

## Phase 7 — Personal Memory

Track:

- previously seen stories
- previously recommended technologies
- technologies already learned
- recurring topics

Avoid repeatedly recommending the same thing.

---

# 34. Evaluation Metrics

The project should be evaluated based on usefulness, not technical complexity.

Track:

### Information Precision

What percentage of delivered items were actually useful?

### Redundancy

How many repeated stories appeared?

### False-positive rate

How often did hype/speculation enter the main briefing?

### Reading time

Target:

5–8 minutes/day.

### Token cost

Track:

- tokens/day
- tokens/week
- cost/month

### Actionability

How many recommendations led to:

- trying a tool
- learning a skill
- improving coursework
- improving a project

---

# 35. Feedback Loop

At the bottom of the daily briefing, optionally include:

> Was today's briefing useful?

Possible lightweight feedback:

- ⭐ Very useful
- 👍 Useful
- 😐 Too much
- 👎 Not relevant

Use this feedback to tune ranking weights.

---

# 36. Important Design Principle

The system should NOT try to predict the future.

It should distinguish:

### Fact

What happened.

### Signal

What appears to be gaining momentum.

### Interpretation

Why it may matter.

### Recommendation

What the user could consider doing.

Never mix these four levels.

---

# 37. Final Product Definition

The final system should feel like:

> "A technically literate friend who spends hours monitoring the AI/Data/Developer ecosystem, then gives me the five things I actually need to know."

It should NOT feel like:

> "Another AI-generated news newsletter."

The user's attention is the most valuable resource.

Optimize for:

> **Signal > Noise**
>
> **Evidence > Hype**
>
> **Relevance > Volume**
>
> **Actionability > Novelty**
>
> **Learning value > Entertainment**
>
> **Low cost > unnecessary complexity**

---

# 38. Initial Implementation Instruction for Claude Code / Codex

When starting implementation:

1. Read this entire `PROJECT_SPEC.md`.
2. Do not immediately write the full system.
3. First inspect the environment.
4. Determine available:
   - Python version
   - packages
   - GitHub API access
   - web/search capabilities
   - email configuration
   - LLM API configuration
5. Propose a minimal Phase 1 architecture.
6. Implement Phase 1 only.
7. Create tests.
8. Run the prototype.
9. Generate at least one sample daily briefing.
10. Evaluate the briefing against this specification.
11. Only then proceed to Phase 2.

Do not introduce unnecessary dependencies.

Do not create a multi-agent architecture unless there is a demonstrated need.

Do not spend significant API/LLM budget before the filtering pipeline is implemented.

---

# 39. Definition of Done — MVP

The MVP is complete when:

- [ ] Sources can be collected automatically.
- [ ] Duplicate stories are removed.
- [ ] Sources are ranked by reliability.
- [ ] Important stories are ranked.
- [ ] GitHub projects can be monitored.
- [ ] GitHub projects are evaluated using both popularity and momentum.
- [ ] Developer skills are extracted from projects.
- [ ] School relevance is evaluated.
- [ ] Career relevance is evaluated.
- [ ] Hype is separated from durable skills.
- [ ] Low-confidence claims are clearly marked.
- [ ] LLM calls happen only after filtering.
- [ ] Daily briefing is generated.
- [ ] Email can be sent automatically.
- [ ] Token/API cost is tracked.
- [ ] A weekly report can eventually be generated.
- [ ] The system does not execute untrusted GitHub code automatically.

---

# 40. Long-Term Vision

The long-term goal is not to build a news scraper.

The long-term goal is to build:

> **A personal technology radar for a Data Science Master's student.**

The system should gradually answer:

- What is happening?
- What is real?
- What is hype?
- What are developers adopting?
- What skills are becoming valuable?
- What skills are becoming commoditized?
- What tools should I learn?
- What tools should I ignore?
- What can improve my school work?
- What could improve my future career?
- What changed compared with last month?

The final output should help the user spend less time consuming information while becoming more aware of important changes in the AI, Data Science, software, and technology-business ecosystem.
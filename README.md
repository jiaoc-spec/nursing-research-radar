# Nursing Literature Digest Skill

A [Claude Code](https://claude.ai/code) skill for automated daily nursing and psychiatric nursing literature digests.

Monitors **PubMed/MEDLINE**, **Crossref**, **OpenAlex**, and **arXiv** for new papers, writes AI-powered summaries in your chosen language, saves local Markdown/DOCX archives, and sends daily email digests via the Gmail connector.

---

## What it does

- Fetches new papers every day at a scheduled time (default: 09:00)
- Covers core psychiatric nursing topics: therapeutic relationship, BPD, DBT, schizophrenia, bipolar, crisis intervention, trauma-informed care, forensic nursing, psychopharmacology
- Summarises title, abstract, MeSH terms, authors, journal, DOI, and research relevance
- Highlights high-impact psychiatric nursing journals (JPMHN, IJMHN, APN, IMHN, PPC)
- Saves archives to `nursing-literature-digests/YYYY-MM-DD.md`
- Sends digest by email through the Claude Code Gmail connector
- Works fully unattended via Claude Code's cron automation

## Who this is for

Nurses, nursing students, and researchers specialising in **psychiatric and mental health nursing** who want a daily, AI-curated literature overview without manually searching databases.

---

## Requirements

- [Claude Code](https://claude.ai/code) (CLI or desktop app)
- Python 3.9 or later
- Internet access (PubMed, Crossref, OpenAlex, arXiv APIs — all free, no API key required)
- Gmail connector (optional, for email delivery)

---

## Installation

1. Copy this skill folder into your Claude Code skills directory:
   ```bash
   cp -r nursing-literature-digest ~/.claude/skills/
   ```

2. In a Claude Code conversation, invoke the skill:
   ```
   /nursing-literature-digest
   ```
   Claude will guide you through setup interactively.

---

## Configuration

During setup, Claude creates a `nursing-literature-digest.config.json` in your workspace. Key fields:

| Field | Description | Default |
|---|---|---|
| `recipient_email` | Where the digest is sent | — |
| `language` | Digest language (`zh-CN`, `de`, `en`, …) | `zh-CN` |
| `timezone` | Your local timezone | ask |
| `schedule_time` | Daily run time | `09:00` |
| `output_dir` | Local archive folder | `nursing-literature-digests` |
| `keyword_groups` | Topics to monitor | psychiatric nursing defaults |
| `pubmed_rows` | Max PubMed results per run | `30` |
| `max_papers` | Max papers in digest | `40` |

See `references/default-config.md` for the full default keyword list.

---

## Keyword topics (defaults)

- Psychiatric nursing / mental health nursing
- Therapeutic relationship & communication
- Borderline personality disorder (BPD)
- Dialectical behaviour therapy (DBT)
- Schizophrenia / psychosis nursing
- Bipolar disorder nursing
- Psychiatric crisis & emergency nursing
- Trauma-informed care & PTSD nursing
- Forensic psychiatric nursing
- Psychopharmacology & medication management

---

## Project structure

```
nursing-literature-digest/
├── SKILL.md                         # Claude Code skill definition
├── README.md                        # This file
├── LICENSE                          # MIT License
├── scripts/
│   ├── daily_literature_digest.py   # Fetch script (PubMed, Crossref, OpenAlex, arXiv)
│   └── markdown_to_docx.py          # Optional DOCX export
├── agents/
│   └── openai.yaml                  # Agent configuration
└── references/
    └── default-config.md            # Default keyword groups & journal list
```

---

## License

MIT — see [LICENSE](LICENSE).

Based on [daily-literature-digest-skill](https://github.com/xuezheng627/daily-literature-digest-skill) by xuezheng627, licensed under MIT.
Adapted for psychiatric and mental health nursing by [jiaoc-spec](https://github.com/jiaoc-spec).

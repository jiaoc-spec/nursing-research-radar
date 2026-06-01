# Nursing Literature Digest Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A [Claude Code](https://claude.ai/code) skill for automated daily nursing and psychiatric nursing literature digests — with an integrated **Paper Vault** for building a searchable local research library.

Monitors **PubMed/MEDLINE**, **Crossref**, **OpenAlex**, and **arXiv** for new papers, writes AI-powered summaries in your chosen language, saves local Markdown archives, sends daily email digests via Gmail, and automatically imports high-priority papers into a browsable local web vault.

---

## What it does

**Daily Digest**
- Fetches new papers every day at a scheduled time (default: 09:00)
- Covers core psychiatric nursing topics: therapeutic relationship, BPD, DBT, schizophrenia, bipolar, crisis intervention, trauma-informed care, forensic nursing, psychopharmacology
- Supports 46 keyword groups mapped to 5 vault display categories via `vault_category`
- Summarises title, abstract, MeSH terms, authors, journal, DOI, and research relevance
- Highlights high-impact psychiatric nursing journals (JPMHN, IJMHN, APN, IMHN, PPC)
- Saves archives to `nursing-literature-digests/YYYY-MM-DD.md`
- Sends digest by email through Gmail (SMTP or Claude Code Gmail connector)
- Works fully unattended via launchd (macOS) or cron automation

**Paper Vault** *(integrated from [research-radar-paper-vault](https://github.com/xuezheng627/research-radar-paper-vault) by xuezheng627)*
- Imports High and Medium priority papers into a local static web dashboard
- Groups papers by Digest → Vault Category → Paper with tab navigation
- Can be combined with other digest skills in a shared vault
- Searchable card view with title, summary, method, result, and next-action fields
- Deduplicates by DOI/PMID across daily runs
- Auto-updates daily after each digest fetch (Step 5 in run scripts)
- Served locally via `python3 -m http.server 8766`, auto-started at login via launchd
- **German translation**: `--translate` flag auto-translates abstract fields (summary, objective, method, result) to German via Claude CLI on import; `translate-existing` command retroactively translates all cards already in the vault

---

## Who this is for

Nurses, nursing students, and researchers specialising in **psychiatric and mental health nursing** who want a daily, AI-curated literature overview and a persistent local research library — without manually searching databases.

---

## Requirements

- [Claude Code](https://claude.ai/code) (CLI or desktop app)
- Python 3.9 or later
- Internet access to PubMed/NCBI, Crossref, OpenAlex, and arXiv APIs. Some services may require contact information, API keys, or rate-limit compliance; for example, OpenAlex requires an API key for regular API use as of February 13, 2026.
- Gmail SMTP credentials or Claude Code Gmail connector (optional, for email delivery)

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
| `language` | Digest language (`auto`, `zh-CN`, `de`, `en`, …) | `auto` |
| `timezone` | Your local timezone | ask |
| `schedule_time` | Daily run time | `09:00` |
| `output_dir` | Local archive folder | `nursing-literature-digests` |
| `keyword_groups` | Topics to monitor, each with optional `vault_category` | psychiatric nursing defaults |
| `pubmed_rows` | Max PubMed results per run | `30` |
| `max_papers` | Max papers in digest | `40` |

Each keyword group can include a `vault_category` field to control how papers are displayed in the Paper Vault — separate from PubMed search granularity:

```json
{
  "label": "dialectical behavior therapy",
  "vault_category": "Behandlung und Therapieansätze",
  "terms": ["dialectical behavior therapy", "DBT skills training"],
  "pubmed_query": "\"Dialectical Behavior Therapy\"[MeSH Terms] OR ..."
}
```

See `references/default-config.md` for the full 46-group default configuration with 5 vault categories.

### Language auto-detection

Set `"language": "auto"` to let the fetch script detect the operating-system locale and write the resolved digest language into the JSON payload. Explicit values keep the old behavior: `"language": "de"`, `"language": "en"`, or `"language": "zh-CN"` are used as-is and do not trigger locale detection.

Common mappings:

| OS locale | Digest language |
|---|---|
| `de_DE`, `de-DE` | `de` |
| `en_US`, `en-GB` | `en` |
| `zh_CN`, `zh-Hans` | `zh-CN` |
| `zh_Hant`, `zh-TW` | `zh-TW` |
| `fr_FR` | `fr` |
| `ja_JP` | `ja` |

If locale detection fails or the locale is unsupported, the script falls back to `en`. The run log includes the selected mode, detected locale, and final digest language, for example:

```text
Language mode: auto
Detected locale: de_DE
Selected digest language: de
```

---

## Paper Vault quick start

```bash
# Initialise once
python3 scripts/paper_vault.py init --vault-dir my-vault

# Import after a fetch (with German translation)
python3 scripts/paper_vault.py import-high \
  --vault-dir my-vault \
  --digest-data-dir nursing-literature-digests/data \
  --config nursing-literature-digest.config.json \
  --priority Medium --digest-label "Nursing-Digest" --no-require-fulltext --translate

# Retroactively translate all existing vault cards to German
python3 scripts/paper_vault.py translate-existing --vault-dir my-vault

# Serve locally
cd my-vault && python3 -m http.server 8766 --bind 127.0.0.1
# Open: http://127.0.0.1:8766/index.html
```

---

## Project structure

```
nursing-literature-digest/
├── SKILL.md                          # Claude Code skill definition (digest + vault)
├── paper-vault-SKILL.md              # Standalone Paper Vault skill definition
├── README.md                         # This file
├── LICENSE                           # MIT License
├── scripts/
│   ├── daily_literature_digest.py    # Fetch script (PubMed, Crossref, OpenAlex, arXiv)
│   ├── paper_vault.py                # Paper Vault builder with German translation support
│   └── markdown_to_docx.py           # Optional DOCX export
├── assets/
│   └── frontend-template/            # HTML/CSS/JS vault template with digest-tab UI
│       ├── index.html
│       ├── styles.css
│       ├── app.js
│       └── data/
├── config/
│   └── nursing-literature-digest.config.json   # Psychiatric nursing digest config
├── run-scripts/
│   └── nursing-literature-digest-run.sh        # launchd run script — nursing digest
├── email-scripts/
│   └── nursing-literature-digest-email.py      # Gmail sender — nursing digest
├── launchd/
│   ├── com.nursing.literature.digest.plist     # launchd agent — nursing digest (09:00)
│   ├── com.nursing.paper-vault.server.plist    # launchd agent — vault HTTP server
│   └── com.obsidian.digest.sync.plist          # launchd agent — Obsidian sync
└── references/
    └── default-config.md             # Full 46-group keyword config with vault_category
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

Portions of this project are adapted from MIT-licensed open-source projects. See [NOTICE](NOTICE) for third-party copyright notices and attribution.

## Disclaimer

This project is a research and literature-awareness tool. It is not medical, nursing, diagnostic, therapeutic, legal, or professional advice. AI-generated summaries may be incomplete or inaccurate and must be checked against the original sources before being used for clinical, academic, or publication purposes.

The tool is designed to work with openly available metadata, abstracts, and user-provided or lawfully accessible full texts. It is not intended to bypass paywalls, publisher access controls, institutional login systems, or database terms of use.

Users are responsible for complying with the terms, rate limits, attribution requirements, and acceptable-use policies of all external services they configure or access, including PubMed/NCBI, Crossref, OpenAlex, arXiv, Gmail, and any publisher or institution.

This project is not affiliated with, endorsed by, or sponsored by Anthropic, Claude, PubMed/NCBI, Crossref, OpenAlex, arXiv, Google, Gmail, or any publisher mentioned in the documentation.

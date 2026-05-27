# Nursing Literature Digest Skill

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
- Supports multiple digests in one vault (nursing + psychiatry-medicine + AI nursing)
- Searchable card view with title, summary, method, result, and next-action fields
- Deduplicates by DOI/PMID across daily runs
- Auto-updates daily after each digest fetch (Step 5 in run scripts)
- Served locally via `python3 -m http.server 8766`, auto-started at login via launchd

---

## Who this is for

Nurses, nursing students, and researchers specialising in **psychiatric and mental health nursing** who want a daily, AI-curated literature overview and a persistent local research library — without manually searching databases.

---

## Requirements

- [Claude Code](https://claude.ai/code) (CLI or desktop app)
- Python 3.9 or later
- Internet access (PubMed, Crossref, OpenAlex, arXiv APIs — all free, no API key required)
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
| `language` | Digest language (`zh-CN`, `de`, `en`, …) | `zh-CN` |
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

---

## Paper Vault quick start

```bash
# Initialise once
python3 scripts/paper_vault.py init --vault-dir my-vault

# Import after a fetch
python3 scripts/paper_vault.py import-high \
  --vault-dir my-vault \
  --digest-data-dir nursing-literature-digests/data \
  --config nursing-literature-digest.config.json \
  --priority Medium --digest-label "Nursing-Digest" --no-require-fulltext

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
│   ├── paper_vault.py                # Paper Vault builder (adapted from xuezheng627)
│   └── markdown_to_docx.py           # Optional DOCX export
├── assets/
│   └── frontend-template/            # HTML/CSS/JS vault template with digest-tab UI
│       ├── index.html
│       ├── styles.css
│       ├── app.js
│       └── data/
├── agents/
│   └── openai.yaml
└── references/
    └── default-config.md             # Full 46-group keyword config with vault_category
```

---

## License

MIT — see [LICENSE](LICENSE).

**Upstream projects:**
- Digest fetch script based on [daily-literature-digest-skill](https://github.com/xuezheng627/daily-literature-digest-skill) by [xuezheng627](https://github.com/xuezheng627), licensed under MIT. Adapted for psychiatric and mental health nursing.
- Paper Vault (`scripts/paper_vault.py`, `assets/frontend-template/`) adapted from [research-radar-paper-vault](https://github.com/xuezheng627/research-radar-paper-vault) by [xuezheng627](https://github.com/xuezheng627). Adaptations: `vault_category` support, `digestSource` tagging, digest-tab UI, Python 3.9 compatibility, bidirectional keyword matching.

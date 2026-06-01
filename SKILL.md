---
name: nursing-literature-digest
description: Set up, run, modify, or troubleshoot a personal AI nursing and psychiatric nursing literature automation that monitors PubMed/MEDLINE, Crossref, OpenAlex, and arXiv for new papers by keyword groups, summarizes open metadata and abstracts, saves local Markdown archives, sends daily email digests through Gmail, and builds a searchable local Paper Vault of categorized research cards. Use when the user asks for daily nursing paper monitoring, psychiatric nursing literature alerts, evidence-based nursing digests, AI paper summary emails, Gmail nursing literature updates, a recurring 09:00 automation, a local visual paper library, or multi-digest vault setups with digest-tab navigation.
---

# Nursing Literature Digest

## Overview

Use this skill to create a personal daily nursing and psychiatric nursing literature digest. The bundled fetch script gathers open metadata and abstracts from PubMed/MEDLINE (primary source), Crossref, OpenAlex, and optionally arXiv. Claude writes the AI interpretation, saves the archive, sends email through Gmail when connected, and creates the recurring automation.

An integrated Paper Vault (`scripts/paper_vault.py`) turns High and Medium priority papers into a local static web dashboard — searchable, categorized, and persistent across daily runs.

PubMed/MEDLINE is the primary source for nursing literature. Crossref covers publisher-specific journals. OpenAlex enriches abstracts and open-access links. arXiv covers nursing informatics and health AI preprints.

Do not read paywalled full text or auto-login to university/publisher sites during the unattended daily run. Full-text follow-up is a separate explicit task after the user logs in themselves or provides PDFs.

## Scripts

| Script | Purpose | Key subcommands |
|---|---|---|
| `scripts/daily_literature_digest.py` | Fetch papers from APIs, write JSON, mark success | `fetch`, `mark-success` |
| `scripts/paper_vault.py` | Build and update local static web vault | `init`, `import-high` |
| `scripts/markdown_to_docx.py` | Convert Markdown digest to DOCX | _(called directly)_ |

Frontend template for the vault lives in `assets/frontend-template/`.

## Setup Workflow

1. Confirm or infer the user's settings:
   - Recipient email for the digest.
   - Research keywords, grouped by theme. Each group may have a `vault_category` to control how papers appear in the vault (separate from PubMed search granularity).
   - Language: ask if unclear; default to `auto`. `auto` detects the operating-system locale and resolves it to a digest language. Explicit values such as `de`, `en`, or `zh-CN` must be preserved and must not trigger auto-detection.
   - Timezone: ask if unclear; otherwise use the user's local timezone.
   - Schedule time: default to `09:00`.
   - Sources: PubMed is always on; Crossref defaults to Elsevier, Springer Nature, Wiley, and Taylor & Francis; arXiv is on by default.
2. Copy `scripts/daily_literature_digest.py` into the user's workspace, plus `scripts/markdown_to_docx.py` only when DOCX output is requested.
3. Create `nursing-literature-digest.config.json` in the workspace:
   ```json
   {
     "recipient_email": "user@example.com",
     "crossref_mailto": "user@example.com",
     "ncbi_email": "user@example.com",
     "language": "auto",
     "timezone": "Europe/Berlin",
     "schedule_time": "09:00",
     "output_dir": "nursing-literature-digests",
     "keyword_groups": [
       {
         "label": "psychiatric nursing",
         "vault_category": "Pflege als Profession und Wissenschaft",
         "terms": ["psychiatric nursing", "mental health nursing", "psychiatric-mental health nursing"]
       },
       {
         "label": "borderline personality disorder",
         "vault_category": "Psychische Erkrankungen und Diagnostik",
         "terms": ["borderline personality disorder", "emotionally unstable personality disorder", "BPD nursing care"]
       },
       {
         "label": "dialectical behavior therapy",
         "vault_category": "Behandlung und Therapieansätze",
         "terms": ["dialectical behavior therapy", "dialectical behaviour therapy", "DBT skills training"]
       }
     ],
     "include_arxiv": true,
     "include_pubmed": true,
     "rows": 20,
     "arxiv_rows": 25,
     "pubmed_rows": 30,
     "max_papers": 40
   }
   ```
   Use full keyword groups from `references/default-config.md` for full psychiatric nursing coverage (46 groups, 5 vault categories).
4. Run a dry fetch:
   ```bash
   python scripts/daily_literature_digest.py --config nursing-literature-digest.config.json fetch --include-seen
   ```
5. Read the printed JSON file and write the digest:
   - Save full Markdown to `nursing-literature-digests/YYYY-MM-DD.md`.
   - Summarize using only title, abstract, keywords, subject tags, DOI, journal, authors, publisher, and source metadata.
   - Mark arXiv items as preprints. Mark PubMed items with their source journal.
   - Note MeSH terms when available — they indicate indexer-confirmed topic relevance.
   - If there are no matches, still write a short no-results digest.
6. For no-abstract/title-only papers, write `nursing-literature-digests/fulltext-inbox/to-download-YYYY-MM-DD.md` with DOI/URL/PMID and a note that no abstract/full text was read.
7. Check Gmail:
   - Call Gmail profile if Gmail tools are available.
   - If Gmail is connected, send a concise email body with the full local Markdown path.
   - If Gmail is unavailable, do not ask for SMTP credentials; tell the user to connect Gmail and record email status as `not-configured` or `failed`.
8. Mark success only after the Markdown archive exists:
   ```bash
   python scripts/daily_literature_digest.py --config nursing-literature-digest.config.json mark-success --data-file <JSON_PATH> --digest-file <DIGEST_PATH> --email-status <sent|failed|not-configured>
   ```
9. Update the Paper Vault (see Paper Vault section below):
   ```bash
   python scripts/paper_vault.py import-high --vault-dir <VAULT_DIR> \
     --digest-data-dir nursing-literature-digests/data \
     --config nursing-literature-digest.config.json \
     --priority Medium --digest-label "Nursing-Digest" --no-require-fulltext
   ```
10. Create a Codex cron automation at the user's configured local time. For 09:00 daily:
    ```text
    FREQ=DAILY;BYHOUR=9;BYMINUTE=0;BYSECOND=0
    ```

## Summary Rules

- Treat matching as inclusive: one keyword term is enough to include a paper.
- Use priority for ranking, not for exclusion.
- For each paper include title, source/publisher, journal, date, authors, DOI/PMID/URL, matched keywords, MeSH terms (if available), priority, research goal, method, main result, relevance to the user, and next action.
- If the abstract is missing, include the paper only as a title-level candidate and state clearly: `No abstract/full text was available; this is a title-level judgment only.`
- Do not infer research goal, method, or result for no-abstract papers.
- Highlight papers from high-impact nursing journals: Journal of Psychiatric and Mental Health Nursing, International Journal of Mental Health Nursing, Archives of Psychiatric Nursing, Issues in Mental Health Nursing, Perspectives in Psychiatric Care.
- Mention PubMed, Crossref, OpenAlex, or arXiv API errors in the digest and summarize successfully fetched results.

## Digest Structure

Group papers by priority using `##` section headings, then give each paper a `###` heading with a short German title:

```
## HOHE PRIORITÄT

---

### 1 — [Kurzer deutscher Titel]

**Titel:** [Original English title]
...

## MITTLERE PRIORITÄT

---

### 2 — [Kurzer deutscher Titel]
...

## NIEDRIGE PRIORITÄT

---

### 3 — [Kurzer deutscher Titel]
...
```

- The `###` heading uses a short descriptive German title (translated/paraphrased from the original), not a literal word-for-word translation.
- The original English title follows immediately as `**Titel:**` field below the heading.
- If the digest language is not German, use the configured language for the short heading title instead.
- If `language` is `auto`, use the resolved language from the fetch JSON's `language` field, not the literal word `auto`.

## Paper Vault

The Paper Vault is a local static web dashboard that makes high-priority papers permanently visible, categorized, and searchable. It complements the daily digest — the digest finds and emails papers, the vault keeps them organized for long-term reference.

### When to use

- After a fetch has produced new High or Medium papers.
- When the user wants a persistent visual library across multiple digest runs.
- For multi-digest setups (nursing + psychiatry-medicine + AI nursing), each with its own `--digest-label`.

### Vault categories vs. keyword groups

Keyword groups control PubMed/Crossref/arXiv search granularity. The `vault_category` field on each group controls how papers are grouped in the vault display. Use 3–5 broad `vault_category` values per digest regardless of how many keyword groups exist.

Example for psychiatric nursing (5 vault categories, 46 keyword groups):
- `"Psychische Erkrankungen und Diagnostik"` — schizophrenia, BPD, depression, anxiety, substance use, …
- `"Behandlung und Therapieansätze"` — DBT, trauma-informed care, de-escalation, psychoeducation, …
- `"Pflege als Profession und Wissenschaft"` — inpatient, community, evidence-based, nursing theory, …
- `"Forensische Psychiatrie"` — forensic nursing, coercion, restraint, involuntary treatment, …
- `"Pflegende selbst"` — burnout, supervision, moral distress, workforce, education, …

### Setup

```bash
# Initialize once
python scripts/paper_vault.py init --vault-dir <VAULT_DIR>

# Import after each fetch (add to daily run script as Step 5)
python scripts/paper_vault.py import-high \
  --vault-dir <VAULT_DIR> \
  --digest-data-dir nursing-literature-digests/data \
  --config nursing-literature-digest.config.json \
  --priority Medium \
  --max-areas 12 \
  --digest-label "Nursing-Digest" \
  --no-require-fulltext

# Serve locally
cd <VAULT_DIR> && python3 -m http.server 8766 --bind 127.0.0.1
# Open: http://127.0.0.1:8766/index.html
```

### Multi-digest vault

Run `import-high` once per digest config, each with its own `--digest-label`. Papers are deduplicated by DOI/PMID across runs. The frontend shows a tab strip (Alle Digests / Nursing-Digest / Psychiatrie-Medizin-Digest / …) and groups papers by Digest → Vault Category → Paper.

### Full-text requirement

By default, `import-high` requires a local PDF or extracted full-text before importing a paper as a normal card (`--require-fulltext`). Papers without full text are written to `sources/fulltext-inbox/to-download-YYYY-MM-DD.md`.

Use `--no-require-fulltext` only for temporary abstract-level cards. Cards created this way get `readingStatus: needs-fulltext` and display a limitation notice.

### launchd server (macOS)

To start the vault server automatically at login, install a launchd agent:

```xml
<!-- ~/Library/LaunchAgents/com.nursing.paper-vault.server.plist -->
<key>ProgramArguments</key>
<array>
  <string>/usr/bin/python3</string>
  <string>-m</string><string>http.server</string>
  <string>8766</string>
  <string>--bind</string><string>127.0.0.1</string>
</array>
<key>WorkingDirectory</key>
<string>/path/to/vault-dir</string>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
```

```bash
launchctl load ~/Library/LaunchAgents/com.nursing.paper-vault.server.plist
```

## Automation Prompt Requirements

The automation prompt must include:

- Exact workspace path and Python executable or `python` command that works in that workspace.
- Exact config path.
- Exact fetch command using `--config`.
- Recipient email, digest language, schedule time, timezone, and output directory.
- Instruction to summarize abstracts/open metadata only during the unattended run.
- Instruction to use Gmail connector if available.
- Instruction to call `mark-success` with `sent`, `failed`, or `not-configured`.
- Instruction to run `paper_vault.py import-high` as Step 5 after mark-success.
- A warning that local Codex automations may not run if the computer is asleep or the local runner is not active.

## Full-Text Follow-Up

When the user says they have logged in to ScienceDirect, PubMed Central, a university library, or another publisher site:

- Do not ask for passwords.
- Use only the current active browser/session or PDFs the user downloaded into `nursing-literature-digests/fulltext-inbox`.
- Process only the explicit batch/list the user asked about.
- Download/read accessible PDFs or article pages only when allowed by the active session.
- Summarize each full-text paper with topic, population/setting, method, data/case, main results, limitations, and relevance to nursing practice.
- Save summaries to `nursing-literature-digests/fulltext-summaries/YYYY-MM-DD-fulltext.md`.
- Do not create unattended daily publisher-download automation.

## References

- Read `references/default-config.md` when a user asks what defaults are used or wants a starter configuration.
- Use `scripts/markdown_to_docx.py` only when the user explicitly wants DOCX output.

## Credits

`scripts/paper_vault.py` and `assets/frontend-template/` are adapted from
**research-radar-paper-vault** by [xuezheng627](https://github.com/xuezheng627).
Source: <https://github.com/xuezheng627/research-radar-paper-vault>

Adaptations made for this skill:
- `vault_category` field on keyword groups to separate search granularity from vault display
- `digestSource` tagging for multi-digest vaults with tab-based navigation
- Digest → Area → Paper three-level frontend hierarchy
- Python 3.9 compatibility (`write_text` newline handling)
- Bidirectional substring matching in `matching_keyword_groups()`

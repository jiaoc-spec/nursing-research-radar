---
name: paper-vault
description: Create, update, or troubleshoot a local visual Paper Vault for saved research papers. Use when the user wants to import High or Medium papers from a daily literature digest, connect the vault with the nursing-literature-digest skill, classify papers into broad research categories with drill-down subtopics using vault_category, build a searchable card-style paper dashboard, add bilingual notes, attach local PDF paths, run a multi-digest vault with digest-tab navigation (Digest → Area → Paper), or share a reusable Paper Vault workflow across different research fields.
---

# Paper Vault

## Purpose

Use this skill to turn selected papers from a daily literature digest into a local static web vault. The daily digest finds and prioritizes papers; Paper Vault keeps the important ones visible, categorized, searchable, and revisitable across daily runs.

`scripts/paper_vault.py` is bundled with the **nursing-literature-digest** skill. All commands below use that path.

The skill generalizes to any field. Never reuse example categories unless the user's keywords actually match them.

## Credits

Originally developed as **research-radar-paper-vault** by [xuezheng627](https://github.com/xuezheng627).
Source: <https://github.com/xuezheng627/research-radar-paper-vault>

Adaptations made for nursing-literature-digest:
- `vault_category` field on keyword groups to separate PubMed search granularity from vault display categories
- `digestSource` tagging for multi-digest vaults with digest-tab navigation
- Digest → Area → Paper three-level frontend hierarchy with tab strip
- Python 3.9 compatibility (`write_text` newline handling)
- Bidirectional substring matching in `matching_keyword_groups()`

## Core Workflow

1. Locate the user's digest workspace:
   - Prefer `nursing-literature-digest.config.json` (or equivalent) in the current workspace.
   - Prefer digest JSON under `nursing-literature-digests/data` (or equivalent).
   - Use a user-provided path if they name one.
2. Decide what to import:
   - "High papers" means `priority: High`.
   - "Medium and above" means `priority: High` and `priority: Medium`.
   - Do not import Low unless explicitly requested.
   - Default rule: only import papers after Codex has read an accessible full text, local PDF, or user-provided article text. Papers without accessible full text go to `sources/fulltext-inbox` first.
3. Initialize the vault if needed:
   ```bash
   python3 scripts/paper_vault.py init --vault-dir paper-vault-site
   ```
4. Import selected papers:
   ```bash
   python3 scripts/paper_vault.py import-high \
     --vault-dir paper-vault-site \
     --digest-data-dir nursing-literature-digests/data \
     --config nursing-literature-digest.config.json \
     --priority Medium \
     --max-areas 12 \
     --digest-label "Nursing-Digest"
   ```
   This command defaults to `--require-fulltext`. It imports only papers with a local PDF or extracted full-text source file. Use `--no-require-fulltext` only when the user explicitly asks for temporary abstract/title cards.
5. Review the generated site:
   - Broad categories come from `vault_category` in the config; use 3–5 per digest.
   - Subtopics sit under a broad category and can be more specific.
   - Paper cards show title, tags, short summary first; objective, method, result, usefulness, and next step only after expanding details.
   - DOI/arXiv and journal links are clickable.
   - Local PDFs display as copyable local paths, not hidden browser downloads.
6. Run locally:
   ```bash
   cd paper-vault-site
   python3 -m http.server 8766 --bind 127.0.0.1
   ```
   Open `http://127.0.0.1:8766/index.html`.

## vault_category — Search vs. Display

Keyword groups control API search granularity. The optional `vault_category` field controls how papers are grouped in the vault. Set 3–5 broad `vault_category` values per digest regardless of how many keyword groups exist.

```json
{
  "label": "dialectical behavior therapy",
  "vault_category": "Treatment and interventions",
  "terms": ["dialectical behavior therapy", "DBT skills training"]
}
```

Papers whose matched keyword group has a `vault_category` use that as their vault area. Papers without one fall back to the raw group label.

## Multi-Digest Vault

Run `import-high` once per digest config, each with a distinct `--digest-label`:

```bash
python3 scripts/paper_vault.py import-high \
  --vault-dir nursing-paper-vault-site \
  --digest-data-dir nursing-literature-digests/data \
  --config nursing-literature-digest.config.json \
  --priority Medium --max-areas 12 \
  --digest-label "Nursing-Digest" --no-require-fulltext

python3 scripts/paper_vault.py import-high \
  --vault-dir nursing-paper-vault-site \
  --digest-data-dir psychiatry-medicine-digests/data \
  --config psychiatry-medicine-digest.config.json \
  --priority Medium --max-areas 12 \
  --digest-label "Psychiatry-Medicine-Digest" --no-require-fulltext
```

Papers are deduplicated by DOI/PMID across runs. The frontend renders a tab strip (All Digests / Nursing-Digest / Psychiatry-Medicine-Digest / …) and groups papers by Digest → Vault Category → Paper when multiple digests are present.

## Classification Rules

- Use `vault_category` from the config as the primary area signal.
- Fall back to the matched keyword group label when no `vault_category` is set.
- Keep at most 5 broad `area` values per digest. If more exist, merge smaller/rare areas into `Other Research` (controlled by `--max-areas`).
- Keep one `primarySubtopic` per paper for counted drill-down filters.
- Keep `subtopics` and `tags` as descriptive secondary labels; they may overlap.
- Deduplicate by DOI, arXiv id, source key, URL, then normalized title.

Examples of acceptable broad categories:

- For psychiatric nursing: `Mental disorders and diagnostics`, `Treatment and interventions`, `Nursing profession and science`, `Forensic psychiatry`, `Nurses themselves`.
- For biomedical research: `Clinical Evidence`, `Molecular Mechanisms`, `Imaging and Diagnostics`, `Therapeutics`, `Data Methods`.
- For social science: `Policy`, `Behavior`, `Institutions`, `Methods`, `Equity`.

These are examples only. Infer categories from the user's actual keyword groups.

## AI Fields

For each card, maintain:

- `summary`: one skimmable paragraph.
- `objective`: the research problem or question.
- `method`: algorithms, models, data, experiments, or framework.
- `result`: findings explicitly supported by abstract/full text.
- `usefulness`: why this matters for the user's stated research interests.
- `nextAction`: what to read, extract, compare, or reproduce next.

## Full-Text Requirement

Before adding a paper as a normal Paper Vault card:

- Read the full PDF, article HTML, or user-provided full-text file.
- Base `objective`, `method`, `result`, `usefulness`, and `nextAction` on that full text.
- Set `readingStatus` honestly, e.g. `fulltext-read`, `article-page-read`, or `preview-read`.
- Attach `pdfPath` when a local PDF exists, or `fullTextPath`/`sourcePath` when article text was extracted.

If only title, metadata, or abstract is available:

- Do not import it as a normal card by default.
- Write it to `sources/fulltext-inbox/to-download-YYYY-MM-DD.md` with DOI/URL and why it is worth following up.
- Actively tell the user how many High/Medium papers need full text and ask whether they want to log in through the active browser now.
- If the user logs in, use only that explicit current browser session to open the paper pages, download/read the PDF or full article text, then summarize from the full text before importing.
- If the user does not want to log in now, keep the papers in `sources/fulltext-inbox` and do not show them as normal cards.
- Only create a temporary card if the user explicitly says to save it before full-text reading; set `readingStatus: needs-fulltext`, keep limitations visible, and do not infer method or results.

Paywalled access rules:

- Use an active user-logged-in browser session or PDFs the user manually downloads.
- Do not store passwords, cookies, HTML login pages, or institutional session traces.
- Do not create unattended publisher-login download automation.

## Bilingual Notes

The frontend supports bilingual display through `data/paper-bilingual.js`.

- If the user wants bilingual notes, add translations under `window.PAPER_VAULT_BILINGUAL`.
- Preserve UTF-8 encoding.
- After editing, validate generated HTML/JS/JSON for mojibake. Search for `????`, `锟`, `鐮`, `浼`, `寤`, `璁`, `鎽`, `涓`, `娑`, `閻`, `閸`, and `瀵`.
- If mojibake already exists in a user's data file, repair it by mapping known labels/text back to valid UTF-8 or by adding a UTF-8 override file loaded after the damaged data.

## Vault Structure

Generated runtime files belong in the user's workspace, not inside the skill folder:

```
paper-vault-site/
  index.html
  styles.css
  app.js
  data/
    papers.js
    vault-settings.js
    paper-bilingual.js
  notes/
  pdfs/
  sources/
    fulltext-inbox/
```

Do not commit generated papers, PDFs, notes, source pages, cookies, or login traces unless the user explicitly wants to publish that vault.

## Script Reference

Common commands (macOS/Linux paths):

```bash
python3 scripts/paper_vault.py init --vault-dir paper-vault-site

python3 scripts/paper_vault.py import-high \
  --vault-dir paper-vault-site \
  --digest-data-dir nursing-literature-digests/data \
  --priority High --max-areas 5

python3 scripts/paper_vault.py import-high \
  --vault-dir paper-vault-site \
  --digest-data-dir nursing-literature-digests/data \
  --priority Medium --max-areas 5

python3 scripts/paper_vault.py import-high \
  --vault-dir paper-vault-site \
  --digest-data-dir nursing-literature-digests/data \
  --priority Medium --min-impact-factor 5 --download-arxiv-pdfs

python3 scripts/paper_vault.py import-high \
  --vault-dir paper-vault-site \
  --digest-data-dir nursing-literature-digests/data \
  --priority Medium --no-require-fulltext
```

`--priority Medium` imports Medium and High. `--priority Low` imports all priority levels.

`--min-impact-factor 5` skips journals with a numeric IF below 5 while keeping arXiv/preprints by default. Add `--no-keep-preprints` to exclude preprints too.

`--require-fulltext` is the default. `--no-require-fulltext` creates temporary abstract/title cards.

`--digest-label` tags each card with a source digest name for multi-digest tab navigation.

`--max-areas 12` allows up to 12 distinct area values before merging into "Other Research" — useful for combined multi-digest vaults.

## launchd Server (macOS)

```xml
<!-- ~/Library/LaunchAgents/com.nursing.paper-vault.server.plist -->
<key>ProgramArguments</key>
<array>
  <string>/usr/bin/python3</string>
  <string>-m</string><string>http.server</string>
  <string>8766</string>
  <string>--bind</string><string>127.0.0.1</string>
</array>
<key>WorkingDirectory</key><string>/path/to/vault-dir</string>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
```

```bash
launchctl load ~/Library/LaunchAgents/com.nursing.paper-vault.server.plist
```

## Safety

- Do not store passwords, cookies, or login state in the vault.
- Do not run unattended publisher login/download workflows.
- For paywalled papers, use explicit user-provided PDFs or an active user-logged-in browser session for that batch only.
- Keep institutional-access artifacts out of the shareable skill repository.

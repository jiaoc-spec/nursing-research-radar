#!/bin/bash
# Daily nursing literature digest runner.
# Public template: configure paths with environment variables or a local config file.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PLUGIN_SCRIPT="${NURSING_DIGEST_SCRIPT:-$REPO_ROOT/scripts/daily_literature_digest.py}"
CONFIG="${NURSING_DIGEST_CONFIG:-$REPO_ROOT/config/nursing-literature-digest.config.json}"
OUTPUT_DIR="${NURSING_DIGEST_OUTPUT_DIR:-$REPO_ROOT/nursing-literature-digests}"
EMAIL_SCRIPT="${NURSING_DIGEST_EMAIL_SCRIPT:-$REPO_ROOT/email-scripts/nursing-literature-digest-email.py}"
VAULT_SCRIPT="${NURSING_DIGEST_VAULT_SCRIPT:-$REPO_ROOT/scripts/paper_vault.py}"
VAULT_DIR="${NURSING_DIGEST_VAULT_DIR:-$REPO_ROOT/paper-vault-site}"
TODAY=$(date +%Y-%m-%d)
DIGEST_FILE="$OUTPUT_DIR/$TODAY.md"
INBOX_FILE="$OUTPUT_DIR/fulltext-inbox/to-download-$TODAY.md"
LOG_FILE="$OUTPUT_DIR/run-$TODAY.log"

mkdir -p "$OUTPUT_DIR" "$OUTPUT_DIR/fulltext-inbox"
exec >> "$LOG_FILE" 2>&1

echo "=== Nursing Literature Digest: $TODAY $(date +%T) ==="
echo "Config: $CONFIG"

# Step 1: fetch papers via PubMed / Crossref / OpenAlex / arXiv.
echo "[1] Fetching papers..."
JSON_PATH=$(/usr/bin/python3 "$PLUGIN_SCRIPT" --config "$CONFIG" fetch)

if [ -z "$JSON_PATH" ]; then
    echo "ERROR: fetch returned no JSON path. Aborting."
    exit 1
fi
echo "    JSON: $JSON_PATH"

DIGEST_LANGUAGE=$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("language") or "en")' "$JSON_PATH")
echo "    Digest language: $DIGEST_LANGUAGE"

# Step 2: Claude writes the digest (up to 3 attempts for transient API errors).
echo "[2] Writing digest with Claude..."
CLAUDE_PROMPT="$(cat <<PROMPT
Today is $TODAY.
Write the daily nursing literature digest in this target language: $DIGEST_LANGUAGE.
If the target language is zh-CN, use Simplified Chinese. If it is zh-TW, use Traditional Chinese.

Read the fetch JSON: $JSON_PATH
Save the complete Markdown digest to: $DIGEST_FILE

Audience and scope:
- Nursing and psychiatric/mental health nursing readers.
- Use only metadata, title, abstract, MeSH terms, keywords, authors, DOI/PMID/URL, journal, publisher, source, and relevance fields in the JSON.
- Do not invent methods, results, limitations, or conclusions when they are not present.
- Mark arXiv items as preprints.
- Mark high-impact clinical or nursing journals as required reading when justified.

Required output language rule:
- All generated headings, section labels, explanations, and summaries must be in $DIGEST_LANGUAGE.
- Keep original paper titles in their original language in a dedicated original-title field.
- Give each paper a short descriptive heading in $DIGEST_LANGUAGE, not a copied English title.

Header:
# [Localized title for "Nursing Literature Digest"] — [localized written date]

Include a compact metadata table with localized labels for:
- date
- number of qualified papers
- priority distribution
- search window
- data sources
- run_id
- run_stamp

If no papers qualified:
- State clearly in $DIGEST_LANGUAGE that no qualified papers were found today.
- Include API/source errors from the JSON errors array as a localized table.

If papers are present:
- Group papers by priority with localized ## section headings for high, medium, and low priority.
- Use one ### heading per paper:
  ### [N] — [short descriptive heading in $DIGEST_LANGUAGE, max. 80 characters]
- Number papers continuously across sections.

For each paper include localized field labels for:
- original title
- journal
- publication type
- date
- authors
- DOI/URL
- PMID, if available
- source
- matched keywords
- MeSH terms, or a localized "none provided"
- relevance score
- research objective
- method
- key findings or main statements
- limitations, only if mentioned in the abstract
- relevance for psychiatric/mental health nursing
- next steps, only if useful

No-abstract rule:
- If no abstract is available, do not infer research objective, method, or results.
- Write a title-level assessment only.
- Add title + DOI/PMID/URL to: $INBOX_FILE with a localized note meaning "No abstract - retrieve full text manually".

Finish by running exactly this command after the Markdown file exists:
/usr/bin/python3 "$PLUGIN_SCRIPT" --config "$CONFIG" mark-success --data-file "$JSON_PATH" --digest-file "$DIGEST_FILE" --email-status EMAIL_PENDING

At the very end, output exactly one line: DIGEST_OK or DIGEST_FAILED
PROMPT
)"

CLAUDE_MAX_ATTEMPTS=3
CLAUDE_ATTEMPT=0
CLAUDE_SUCCESS=0
while [ $CLAUDE_ATTEMPT -lt $CLAUDE_MAX_ATTEMPTS ]; do
    CLAUDE_ATTEMPT=$((CLAUDE_ATTEMPT + 1))
    echo "    Attempt $CLAUDE_ATTEMPT/$CLAUDE_MAX_ATTEMPTS..."
    if /usr/local/bin/claude -p \
        --allowedTools "Bash,Read,Write,Edit" \
        --output-format text \
        "$CLAUDE_PROMPT"; then
        CLAUDE_SUCCESS=1
        break
    else
        echo "    WARN: Claude call failed (attempt $CLAUDE_ATTEMPT). Exit: $?"
        if [ $CLAUDE_ATTEMPT -lt $CLAUDE_MAX_ATTEMPTS ]; then
            echo "    Retrying in 30 seconds..."
            sleep 30
        fi
    fi
done

if [ $CLAUDE_SUCCESS -eq 0 ]; then
    echo "ERROR: Claude failed after $CLAUDE_MAX_ATTEMPTS attempts. Aborting."
    exit 1
fi

# Step 3: send email via Gmail SMTP, if configured.
echo "[3] Sending email..."
EMAIL_STATUS="not-configured"
if /usr/bin/python3 "$EMAIL_SCRIPT" "$DIGEST_FILE" "$TODAY" --config "$CONFIG" --language "$DIGEST_LANGUAGE"; then
    EMAIL_STATUS="sent"
else
    EMAIL_STATUS="failed"
fi
echo "    Email status: $EMAIL_STATUS"

# Step 4: update state with final email status.
/usr/bin/python3 "$PLUGIN_SCRIPT" --config "$CONFIG" mark-success \
  --data-file "$JSON_PATH" \
  --digest-file "$DIGEST_FILE" \
  --email-status "$EMAIL_STATUS"

# Step 5: update Paper Vault. This is non-fatal.
echo "[5] Updating Paper Vault..."
/usr/bin/python3 "$VAULT_SCRIPT" import-high \
  --vault-dir "$VAULT_DIR" \
  --digest-data-dir "$OUTPUT_DIR/data" \
  --config "$CONFIG" \
  --priority Medium \
  --max-areas 12 \
  --digest-label "Nursing-Digest" \
  --no-require-fulltext \
  || echo "    WARN: Vault import failed (non-fatal)"

echo "[5] Done. Digest: $DIGEST_FILE"
echo "=== Finished $(date +%T) ==="

#!/bin/bash
# Daily nursing literature digest — triggered by launchd at 09:00
set -euo pipefail
cd /Users/jiaocheng

PLUGIN_SCRIPT="/Users/jiaocheng/.claude/plugins/nursing-literature-digest/scripts/daily_literature_digest.py"
CONFIG="/Users/jiaocheng/nursing-literature-digest.config.json"
OUTPUT_DIR="/Users/jiaocheng/nursing-literature-digests"
TODAY=$(date +%Y-%m-%d)
DIGEST_FILE="$OUTPUT_DIR/$TODAY.md"
INBOX_FILE="$OUTPUT_DIR/fulltext-inbox/to-download-$TODAY.md"
LOG_FILE="$OUTPUT_DIR/run-$TODAY.log"

exec >> "$LOG_FILE" 2>&1
echo "=== Nursing Literature Digest: $TODAY $(date +%T) ==="

# Step 1: fetch papers via PubMed / Crossref / arXiv
echo "[1] Fetching papers..."
JSON_PATH=$(/usr/bin/python3 "$PLUGIN_SCRIPT" --config "$CONFIG" fetch)

if [ -z "$JSON_PATH" ]; then
    echo "ERROR: fetch returned no JSON path. Aborting."
    exit 1
fi
echo "    JSON: $JSON_PATH"

# Step 2: Claude writes the digest
echo "[2] Writing digest with Claude..."
/usr/local/bin/claude -p \
  --allowedTools "Bash,Read,Write,Edit" \
  --output-format text \
  "$(cat <<PROMPT
Heute ist $TODAY. Schreibe den täglichen Pflegeliteratur-Digest auf Deutsch.
Der Fokus liegt auf psychiatrischer und mentaler Pflegeforschung:
psychiatrische Pflege, therapeutische Beziehung, Persönlichkeitsstörungen, DBT, psychische Krisen, traumainformierte Pflege, forensische Psychiatriepflege, Psychopharmakologie in der Pflege.

Lies: $JSON_PATH
Speichere vollständigen Digest als Markdown in: $DIGEST_FILE

WICHTIG: Verwende folgendes detailliertes Format (analog zum Beispiel-Digest vom 26. Mai 2026):

KOPFZEILE:
# Psychiatrische Pflegeliteratur-Digest — [Datum ausgeschrieben, z.B. 27. Mai 2026]
**Zeitfenster:** [window_from_date]–[window_until_date]
**Quellen:** [Datenquellen aus JSON, z.B. PubMed/MEDLINE, Crossref, OpenAlex; arXiv-Status erwähnen]
**Papiere im Digest:** [N] (davon [M] Systematic Reviews / Meta-Analysen falls vorhanden)
**Gefiltert (Relevanzwert < 2):** [K] weitere Einträge

WENN KEINE PAPER GEFUNDEN (alle unter Relevanzschwelle):
- Klarer Hinweis, dass heute keine qualifizierten Paper gefunden wurden
- Vollständiges Fehlerprotokoll aus dem errors-Array als Tabelle

STRUKTUR (wenn Paper vorhanden):
- Sortiere alle Paper nach relevance_score in Prioritätssektionen:
  ## Papier [N] — HOHE PRIORITÄT   (relevance_score ≥ 4)
  ## Papier [N] — MITTLERE PRIORITÄT (relevance_score 2–3)
  ## Papier [N] — NIEDRIGE PRIORITÄT (relevance_score < 2, aber Abstract vorhanden)
- Nummeriere Paper fortlaufend (1, 2, 3 ...)
- Besonders wichtige Paper (Lancet, NEJM, Nature, Science, Cell, Cochrane) mit [PFLICHTLEKTÜRE] markieren

PRO PAPER — PFLICHTFELDER:
**Titel:** [vollständiger englischer Originaltitel]
**Zeitschrift:** [Journal-Name] [*(hochrangige psychiatrische Pflegezeitschrift)* o.ä. bei Top-Journals]
**Publikationstyp:** [Studientyp, z.B. Editorial, RCT, Systematischer Review, Kohortenstudie]
**Datum:** [Datum]
**Autoren:** [Autoren aus JSON]
**DOI/URL:** [URL]
**PMID:** [PMID falls vorhanden]
**Quelle:** [PubMed/MEDLINE, Crossref, OpenAlex, arXiv]
**Matched Keyword:** [matched_keywords aus JSON]
**MeSH-Terme:** [mesh_terms aus JSON, oder "keine angegeben"]
**Relevanz-Score:** [score]/10

**Forschungsziel:**
[1–2 Sätze: Was wurde untersucht? Welche Frage/Hypothese? Nur aus title+abstract — nichts erfinden]

**Methode:**
[1–3 Sätze: Studiendesign, n, Intervention/Exposition, Outcomes, Statistik — nur wenn im Abstract beschrieben; bei Reviews: Suchstrategie, Einschlusskriterien]
[WEGLASSEN wenn kein Abstract vorhanden — stattdessen: "Kein Abstract verfügbar — Titelbasierte Einschätzung:"]

**Wesentliche Aussagen / Ergebnisse:**
- [konkretes Ergebnis oder Aussage mit Zahlen/Statistik wo vorhanden, fett für Schlüsselzahlen]
- [weiteres Ergebnis oder Kernaussage]
[Bei Reviews/Editorials: Wesentliche Aussagen statt Ergebnisse]

**Limitationen:**
[Nur wenn im Abstract erwähnt, 1 Satz; sonst weglassen]

**Relevanz für die psychiatrische Pflege:**
[2–3 Sätze: Bedeutung für psychiatrische Pflegepraxis, Ausbildung oder Forschung. Open Access erwähnen falls zutreffend]

**Nächste Schritte:** [Volltext-Link, Verwendungsmöglichkeit — optional, nur wenn sinnvoll]

---

ZUSATZ:
- Paper ohne Abstract → Titel + DOI/PMID auch in: $INBOX_FILE mit Hinweis [Kein Abstract – Volltext manuell abrufen]
- Fehler aus dem errors-Array am Ende auflisten (z.B. arXiv-Timeouts) als Tabelle
- Keine Schlussfolgerungen erfinden: Nur aus title, abstract, MeSH, keywords schöpfen

Führe abschliessend aus:
/usr/bin/python3 "$PLUGIN_SCRIPT" --config "$CONFIG" mark-success --data-file "$JSON_PATH" --digest-file "$DIGEST_FILE" --email-status EMAIL_PENDING

Gib am Ende genau eine Zeile aus: DIGEST_OK oder DIGEST_FAILED
PROMPT
)"

# Step 3: send email via Gmail SMTP
echo "[3] Sending email..."
EMAIL_STATUS="not-configured"
if /usr/bin/python3 /Users/jiaocheng/nursing-literature-digest-email.py "$DIGEST_FILE" "$TODAY"; then
    EMAIL_STATUS="sent"
else
    EMAIL_STATUS="failed"
fi
echo "    Email status: $EMAIL_STATUS"

# Step 4: update state with final email status
/usr/bin/python3 "$PLUGIN_SCRIPT" --config "$CONFIG" mark-success \
  --data-file "$JSON_PATH" \
  --digest-file "$DIGEST_FILE" \
  --email-status "$EMAIL_STATUS"

# Step 5: update Paper Vault
echo "[5] Updating Paper Vault..."
/usr/bin/python3 /Users/jiaocheng/.claude/skills/paper-vault/scripts/paper_vault.py import-high \
  --vault-dir /Users/jiaocheng/nursing-paper-vault-site \
  --digest-data-dir /Users/jiaocheng/nursing-literature-digests/data \
  --config "$CONFIG" \
  --priority Medium \
  --max-areas 12 \
  --digest-label "Nursing-Digest" \
  --no-require-fulltext \
  --translate \
  || echo "    WARN: Vault import failed (non-fatal)"

echo "[5] Done. Digest: $DIGEST_FILE"
echo "=== Finished $(date +%T) ==="

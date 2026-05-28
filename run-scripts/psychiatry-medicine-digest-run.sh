#!/bin/bash
# Daily psychiatry medicine digest — triggered by launchd at 09:00
set -euo pipefail
cd /Users/jiaocheng

PLUGIN_SCRIPT="/Users/jiaocheng/.claude/plugins/nursing-literature-digest/scripts/daily_literature_digest.py"
CONFIG="/Users/jiaocheng/psychiatry-medicine-digest.config.json"
OUTPUT_DIR="/Users/jiaocheng/psychiatry-medicine-digests"
TODAY=$(date +%Y-%m-%d)
DIGEST_FILE="$OUTPUT_DIR/$TODAY.md"
INBOX_FILE="$OUTPUT_DIR/fulltext-inbox/to-download-$TODAY.md"
LOG_FILE="$OUTPUT_DIR/run-$TODAY.log"

exec >> "$LOG_FILE" 2>&1
echo "=== Psychiatrie-Medizin-Digest: $TODAY $(date +%T) ==="

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
Heute ist $TODAY. Schreibe den täglichen Psychiatrie-Medizin-Digest auf Deutsch.
Der Fokus liegt auf psychiatrischer medizinischer Forschung (nicht pflegerisch):
Psychopharmakologie, Neurobiologie, klinische Psychiatrie, Diagnostik, Therapiestudien.

Lies: $JSON_PATH
Speichere vollständigen Digest als Markdown in: $DIGEST_FILE

WICHTIG: Verwende folgendes detailliertes Format (analog zum Beispiel-Digest vom 26. Mai 2026):

KOPFZEILE:
# Psychiatrie-Medizin-Digest — [Datum ausgeschrieben, z.B. 27. Mai 2026]
**Zeitfenster:** [window_from_date]–[window_until_date]
**Quellen:** PubMed/MEDLINE (alle Papiere), arXiv (falls verfügbar oder Fehlerbeschreibung)
**Papiere im Digest:** [N] (davon [M] Systematic Reviews / Meta-Analysen)
**Gefiltert (Relevanzwert < 2):** [K] weitere Einträge

STRUKTUR:
- Sortiere alle Paper nach relevance_score in drei Prioritätssektionen:
  ## HOHE PRIORITÄT    (relevance_score ≥ 4)
  ## MITTLERE PRIORITÄT  (relevance_score 2–3)
  ## NIEDRIGE PRIORITÄT  (relevance_score < 2, aber Abstract vorhanden)
- Nummeriere Paper fortlaufend (1, 2, 3 ...) über alle Sektionen
- Besonders wichtige Paper (Lancet, NEJM, Nature, Science, Cell, GBD) mit [PFLICHTLEKTÜRE] markieren

PRO PAPER — PFLICHTFELDER:
### [Nummer] — [Kurztitel: Thema + Methode/Population, ca. 8–12 Wörter]

**Titel:** [vollständiger englischer Originaltitel]
**Zeitschrift:** [Journal-Name] [*(höchste/hohe/mittlere klinische Wirkung)* bei Top-Journals]
**Typ:** [Studientyp, z.B. RCT, Kohortenstudie, Systematischer Review + Meta-Analyse (PRISMA)] — nur wenn is_review_or_meta:true oder explizit im Abstract
**Datum:** [Datum] | **PMID:** [PMID]
**DOI:** [URL]
**Keywords:** [matched_keywords aus JSON, kommagetrennt]
**MeSH:** [mesh_terms aus JSON, falls vorhanden]
[**PROSPERO:** CRD... falls im Abstract erwähnt]
[**[Preprint]** falls source=arXiv]

**Forschungsziel:**
[1–2 Sätze: Was wurde untersucht? Welche Frage/Hypothese? Nur aus title+abstract — nichts erfinden]

**Methode:**
[1–3 Sätze: Studiendesign, n, Intervention/Exposition, Outcomes, Statistik — nur wenn im Abstract beschrieben; bei Reviews: Suchstrategie, Einschlusskriterien, Auswertung]
[WEGLASSEN wenn kein Abstract vorhanden oder Methode nicht beschrieben]

**Wesentliche Ergebnisse:**
- [konkretes Ergebnis mit Zahlen/Statistik, fett für Schlüsselzahlen]
- [weiteres Ergebnis]
- [ggf. weitere Punkte — nur was im Abstract steht]
[WEGLASSEN und durch Hinweis ersetzen wenn kein Abstract: "Kein Abstract verfügbar — Volltext erforderlich."]

**Relevanz:**
[2–3 Sätze: Bedeutung für psychiatrische Forschung/Klinik/Lehre. Was bringt dieses Paper? Open Access erwähnen falls zutreffend]

**Nächste Schritte:** [Volltext-Link, Datenquelle, Lehrmaterial-Hinweis — optional, nur wenn sinnvoll]

---

ZUSATZ:
- Paper ohne Abstract → Titel + DOI/PMID auch in: $INBOX_FILE mit Hinweis [Kein Abstract – Volltext manuell abrufen]
- Fehler aus dem errors-Array am Ende des Digests auflisten (z.B. arXiv-Timeouts)
- Keine Schlussfolgerungen erfinden: Nur aus title, abstract, MeSH, keywords schöpfen

Führe abschliessend aus:
/usr/bin/python3 "$PLUGIN_SCRIPT" --config "$CONFIG" mark-success --data-file "$JSON_PATH" --digest-file "$DIGEST_FILE" --email-status EMAIL_PENDING

Gib am Ende genau eine Zeile aus: DIGEST_OK oder DIGEST_FAILED
PROMPT
)"

# Step 3: send email via Gmail SMTP
echo "[3] Sending email..."
EMAIL_STATUS="not-configured"
if /usr/bin/python3 /Users/jiaocheng/psychiatry-medicine-digest-email.py "$DIGEST_FILE" "$TODAY"; then
    EMAIL_STATUS="sent"
else
    EMAIL_STATUS="failed"
fi
echo "    Email status: $EMAIL_STATUS"

# Step 4: update state with final email status
/usr/bin/python3 "$PLUGIN_SCRIPT" --config "$CONFIG" mark-success \
  --state-file "$OUTPUT_DIR/state.json" \
  --data-file "$JSON_PATH" \
  --digest-file "$DIGEST_FILE" \
  --email-status "$EMAIL_STATUS"

# Step 5: update Paper Vault
echo "[5] Updating Paper Vault..."
/usr/bin/python3 /Users/jiaocheng/.claude/skills/paper-vault/scripts/paper_vault.py import-high \
  --vault-dir /Users/jiaocheng/nursing-paper-vault-site \
  --digest-data-dir /Users/jiaocheng/psychiatry-medicine-digests/data \
  --config "$CONFIG" \
  --priority Medium \
  --max-areas 12 \
  --digest-label "Psychiatrie-Medizin-Digest" \
  --no-require-fulltext \
  --translate \
  || echo "    WARN: Vault import failed (non-fatal)"

echo "[5] Done. Digest: $DIGEST_FILE"
echo "=== Finished $(date +%T) ==="

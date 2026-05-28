#!/bin/bash
# Daily KI-Pflege digest — triggered by launchd at 09:00
set -euo pipefail
cd /Users/jiaocheng

PLUGIN_SCRIPT="/Users/jiaocheng/.claude/plugins/nursing-literature-digest/scripts/daily_literature_digest.py"
CONFIG="/Users/jiaocheng/ki-pflege-digest.config.json"
OUTPUT_DIR="/Users/jiaocheng/ki-pflege-digests"
TODAY=$(date +%Y-%m-%d)
DIGEST_FILE="$OUTPUT_DIR/$TODAY.md"
INBOX_FILE="$OUTPUT_DIR/fulltext-inbox/to-download-$TODAY.md"
LOG_FILE="$OUTPUT_DIR/run-$TODAY.log"

exec >> "$LOG_FILE" 2>&1
echo "=== KI-Pflege-Digest: $TODAY $(date +%T) ==="

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
Heute ist $TODAY. Schreibe den täglichen KI-Pflege-Digest auf Deutsch.
Der Fokus liegt auf KI und Technologie in der Pflege:
prädiktive Algorithmen (Sturzrisiko, Dekubitus, Dienstplanung, Frühwarnsysteme),
Robotik (Assistenzroboter, Exoskelette, soziale Roboter),
digitale Pflegedokumentation (NLP, KI-Spracherkennung, EHR, klinische Entscheidungsunterstützung),
technische Assistenzsysteme (Sensorik, Wearables, Smart Home, AAL),
KI in der Pflegeausbildung, Telemedizin/Fernpflege, Computer Vision in der Pflege.

Lies: $JSON_PATH
Speichere vollständigen Digest als Markdown in: $DIGEST_FILE

WICHTIG: Verwende folgendes detailliertes Format:

KOPFZEILE:
# KI-Pflege-Digest — [Datum ausgeschrieben, z.B. 27. Mai 2026]
**Zeitfenster:** [window_from_date]–[window_until_date]
**Quellen:** [Datenquellen aus JSON; arXiv-Status erwähnen]
**Abstract-Quellen:** PubMed, OpenAlex, Semantic Scholar
**Papiere im Digest:** [N] (davon [M] Systematic Reviews / Meta-Analysen)
**Gefiltert (Relevanzwert < 2):** [K] weitere Einträge

WENN KEINE PAPER GEFUNDEN (alle unter Relevanzschwelle):
- Klarer Hinweis, dass keine qualifizierten Paper gefunden wurden
- Vollständiges Fehlerprotokoll als Tabelle mit Quelle, Keyword-Gruppe, Fehler

STRUKTUR (wenn Paper vorhanden):
- Sortiere alle Paper nach relevance_score in drei Prioritätssektionen:
  ## HOHE PRIORITÄT    (relevance_score >= 4)
  ## MITTLERE PRIORITÄT  (relevance_score 2–3)
  ## NIEDRIGE PRIORITÄT  (relevance_score < 2, aber Abstract vorhanden)
- Nummeriere Paper fortlaufend (1, 2, 3 ...) über alle Sektionen
- Landmark-Paper (Nature, Science, Nature Medicine, Lancet Digital Health) mit [PFLICHTLEKTÜRE] markieren

PRO PAPER — PFLICHTFELDER:
### [Nummer] — [Kurztitel: Technologie + Anwendungsbereich + Setting, ca. 8–12 Wörter]

**Titel:** [vollständiger englischer Originaltitel]
**Zeitschrift:** [Journal-Name] [*(hochrangige Pflegeinformatik/KI-Zeitschrift)* bei Top-Journals]
**Typ:** [Studientyp, z.B. prospektive Kohortenstudie, RCT, Systematischer Review + Meta-Analyse] — nur wenn bekannt
**Datum:** [Datum] | **PMID:** [PMID falls vorhanden]
**DOI:** [URL]
**Keywords:** [matched_keywords aus JSON, kommagetrennt]
**MeSH:** [mesh_terms aus JSON, falls vorhanden]
**Abstract-Quelle:** [PubMed / OpenAlex / Semantic Scholar]
[**[Preprint]** falls source=arXiv]

**Forschungsziel:**
[1–2 Sätze: Welche KI/Technologie? Welcher Pflegekontext? Welche Frage? Nur aus title+abstract]

**Methode:**
[1–3 Sätze: Modelltyp/Algorithmus (z.B. Random Forest, LSTM, CNN), Datensatz, Stichprobengröße, Validierungsansatz, technische Details — nur wenn im Abstract beschrieben]
[WEGLASSEN wenn kein Abstract oder nicht beschrieben]

**Wesentliche Ergebnisse:**
- [konkretes Ergebnis mit Metriken: AUC, Sensitivität, Spezifität, F1-Score, RMSE o.ä., fett für Schlüsselzahlen]
- [weiteres Ergebnis oder Vergleich mit Baseline]
- [klinische oder praktische Implikation falls im Abstract]

**Relevanz:**
[2–3 Sätze: Bedeutung für Pflegeinformatik/Pflegepraxis/Pflegeausbildung. Implementierungspotenzial. Open Access erwähnen falls zutreffend]

**Nächste Schritte:** [Volltext-Link, Code-Repository falls erwähnt — optional]

---

ZUSATZ:
- Paper ohne Abstract → Titel + DOI/PMID auch in: $INBOX_FILE mit Hinweis [Kein Abstract – Volltext manuell abrufen]
- Fehler aus dem errors-Array am Ende des Digests als Tabelle auflisten
- Keine Schlussfolgerungen erfinden: Nur aus title, abstract, MeSH, keywords schöpfen

Führe abschliessend aus:
/usr/bin/python3 "$PLUGIN_SCRIPT" --config "$CONFIG" mark-success --data-file "$JSON_PATH" --digest-file "$DIGEST_FILE" --email-status EMAIL_PENDING

Gib am Ende genau eine Zeile aus: DIGEST_OK oder DIGEST_FAILED
PROMPT
)"

# Step 3: send email via Gmail SMTP
echo "[3] Sending email..."
EMAIL_STATUS="not-configured"
if /usr/bin/python3 /Users/jiaocheng/ki-pflege-digest-email.py "$DIGEST_FILE" "$TODAY"; then
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
  --digest-data-dir /Users/jiaocheng/ki-pflege-digests/data \
  --config "$CONFIG" \
  --priority Medium \
  --max-areas 12 \
  --digest-label "KI-Pflege-Digest" \
  --no-require-fulltext \
  --translate \
  || echo "    WARN: Vault import failed (non-fatal)"

echo "[5] Done. Digest: $DIGEST_FILE"
echo "=== Finished $(date +%T) ==="

#!/usr/bin/env python3
"""Send a daily nursing literature digest via Gmail SMTP."""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_TEXT = {
    "de": {
        "subject": "Pflegeliteratur-Digest {date}",
        "full": "Vollständiger Digest:",
        "sent": "E-Mail gesendet",
        "missing_file": "Digest-Datei nicht gefunden",
        "missing_secret": "Kein App-Passwort gefunden",
        "failed": "E-Mail fehlgeschlagen",
    },
    "en": {
        "subject": "Nursing Literature Digest {date}",
        "full": "Full digest:",
        "sent": "Email sent",
        "missing_file": "Digest file not found",
        "missing_secret": "No app password found",
        "failed": "Email failed",
    },
    "zh-CN": {
        "subject": "护理文献 Digest {date}",
        "full": "完整 Digest：",
        "sent": "邮件已发送",
        "missing_file": "未找到 Digest 文件",
        "missing_secret": "未找到应用专用密码",
        "failed": "邮件发送失败",
    },
    "zh-TW": {
        "subject": "護理文獻 Digest {date}",
        "full": "完整 Digest：",
        "sent": "郵件已寄出",
        "missing_file": "找不到 Digest 檔案",
        "missing_secret": "找不到應用程式專用密碼",
        "failed": "郵件寄送失敗",
    },
    "fr": {
        "subject": "Digest de littérature infirmière {date}",
        "full": "Digest complet :",
        "sent": "E-mail envoyé",
        "missing_file": "Fichier digest introuvable",
        "missing_secret": "Mot de passe d'application introuvable",
        "failed": "Échec de l'envoi de l'e-mail",
    },
    "ja": {
        "subject": "看護文献ダイジェスト {date}",
        "full": "完全版ダイジェスト:",
        "sent": "メールを送信しました",
        "missing_file": "Digest ファイルが見つかりません",
        "missing_secret": "アプリパスワードが見つかりません",
        "failed": "メール送信に失敗しました",
    },
}


def normalize_language(value: str | None) -> str:
    lang = (value or "").strip().replace("_", "-")
    lower = lang.lower()
    if lower in {"zh", "zh-cn", "zh-hans", "zh-hans-cn", "zh-sg"}:
        return "zh-CN"
    if lower in {"zh-tw", "zh-hant", "zh-hant-tw", "zh-hk", "zh-mo"}:
        return "zh-TW"
    if lower.startswith("de"):
        return "de"
    if lower.startswith("fr"):
        return "fr"
    if lower.startswith("ja"):
        return "ja"
    return "en"


def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def load_password(secret_file: Path) -> str:
    return secret_file.read_text(encoding="utf-8").strip().replace(" ", "")


def build_email(digest_path: Path, date: str, sender: str, recipient: str, language: str) -> MIMEMultipart:
    body = digest_path.read_text(encoding="utf-8")
    lines = body.splitlines()
    preview_lines = [line for line in lines[:30] if line.strip()][:12]
    preview = "\n".join(preview_lines)
    text = EMAIL_TEXT.get(language, EMAIL_TEXT["en"])

    msg = MIMEMultipart("alternative")
    msg["Subject"] = text["subject"].format(date=date)
    msg["From"] = sender
    msg["To"] = recipient

    plain = f"{preview}\n\n---\n\n{text['full']}\n\n{body}"
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    return msg


def send(digest_path: Path, date: str, sender: str, recipient: str, secret_file: Path, language: str) -> None:
    password = load_password(secret_file)
    msg = build_email(digest_path, date, sender, recipient, language)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
    print(f"{EMAIL_TEXT.get(language, EMAIL_TEXT['en'])['sent']}: {sender} -> {recipient}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a nursing literature digest via Gmail SMTP.")
    parser.add_argument("digest_file")
    parser.add_argument("date")
    parser.add_argument("--config", default="", help="Optional digest config JSON path.")
    parser.add_argument("--language", default="", help="Digest/email language, e.g. de, en, zh-CN, fr, ja.")
    parser.add_argument("--sender", default=os.environ.get("NURSING_DIGEST_EMAIL_SENDER", ""))
    parser.add_argument("--recipient", default=os.environ.get("NURSING_DIGEST_EMAIL_RECIPIENT", ""))
    parser.add_argument("--secret-file", default=os.environ.get("NURSING_DIGEST_GMAIL_SECRET", ""))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    language = normalize_language(args.language or config.get("language"))
    text = EMAIL_TEXT.get(language, EMAIL_TEXT["en"])

    digest_path = Path(args.digest_file)
    if not digest_path.exists():
        print(f"{text['missing_file']}: {digest_path}", file=sys.stderr)
        return 1

    sender = args.sender or config.get("sender_email") or config.get("recipient_email") or ""
    recipient = args.recipient or config.get("recipient_email") or sender
    secret_file = Path(args.secret_file or config.get("gmail_secret_file") or Path.home() / ".nursing-digest-gmail.secret").expanduser()

    if not sender or not recipient:
        print("Email sender/recipient is not configured", file=sys.stderr)
        return 1
    if not secret_file.exists():
        print(f"{text['missing_secret']}: {secret_file}", file=sys.stderr)
        return 1

    try:
        send(digest_path, args.date, sender, recipient, secret_file, language)
        return 0
    except Exception as exc:  # pragma: no cover - depends on SMTP/network
        print(f"{text['failed']}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

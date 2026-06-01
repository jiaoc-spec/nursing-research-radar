#!/usr/bin/env python3
"""Fetch daily nursing literature candidates for Claude-authored digest summaries.

Adapted from daily-literature-digest-skill by xuezheng627.
Source: https://github.com/xuezheng627/daily-literature-digest-skill

This script intentionally does not call an LLM. It gathers open metadata and
abstracts from PubMed/MEDLINE, Crossref, OpenAlex, and arXiv, then writes a
JSON payload for a Codex automation to summarize.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import locale
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


RECIPIENT_EMAIL = ""
CROSSREF_MAILTO = ""
NCBI_EMAIL = ""
LANGUAGE = "auto"
LANGUAGE_MODE = "auto"
DETECTED_LOCALE = ""
TIMEZONE = ""
SCHEDULE_TIME = "09:00"
DEFAULT_OUTPUT_DIR = Path("nursing-literature-digests")
DEFAULT_STATE_FILE = DEFAULT_OUTPUT_DIR / "state.json"

LOCALE_LANGUAGE_MAP = {
    "de-de": "de",
    "de-at": "de",
    "de-ch": "de",
    "en-us": "en",
    "en-gb": "en",
    "en-au": "en",
    "en-ca": "en",
    "zh-cn": "zh-CN",
    "zh-sg": "zh-CN",
    "zh-hans": "zh-CN",
    "zh-hans-cn": "zh-CN",
    "zh-tw": "zh-TW",
    "zh-hk": "zh-TW",
    "zh-mo": "zh-TW",
    "zh-hant": "zh-TW",
    "zh-hant-tw": "zh-TW",
    "fr-fr": "fr",
    "fr-ca": "fr",
    "ja-jp": "ja",
}

PUBLISHERS = [
    {
        "key": "elsevier",
        "display": "Elsevier",
        "crossref_member": "78",
        "crossref_name": "Elsevier BV",
        "crossref_date_mode": "created-date",
        "openalex_publishers": ["P4310320990"],
    },
    {
        "key": "springer-nature",
        "display": "Springer Nature",
        "crossref_member": "297",
        "crossref_name": "Springer Science and Business Media LLC",
        "crossref_date_mode": "pub-date",
        "openalex_publishers": ["P4310319965", "P4310320108", "P4404664013"],
    },
    {
        "key": "wiley",
        "display": "Wiley",
        "crossref_member": "311",
        "crossref_name": "Wiley",
        "crossref_date_mode": "pub-date",
        "openalex_publishers": ["P4310320595"],
    },
    {
        "key": "taylor-francis-routledge",
        "display": "Taylor & Francis / Routledge",
        "crossref_member": "301",
        "crossref_name": "Informa UK Limited",
        "crossref_date_mode": "pub-date",
        "openalex_publishers": ["P4310320547", "P4310319847"],
    },
]

KEYWORD_GROUPS: list[dict[str, Any]] = [
    # ── Psychische Erkrankungen und Diagnostik ────────────────────────────────
    {
        "label": "schizophrenia / psychosis nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "schizophrenia nursing",
            "psychosis nursing",
            "first-episode psychosis",
            "early psychosis intervention",
            "antipsychotic nursing",
            "psychotic disorder nursing",
        ],
        "pubmed_query": '("Schizophrenia"[MeSH] OR "Psychotic Disorders"[MeSH]) AND ("Psychiatric Nursing"[MeSH] OR nurs*[tiab])',
    },
    {
        "label": "borderline personality disorder",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "borderline personality disorder",
            "emotionally unstable personality disorder",
            "BPD nursing",
            "borderline nursing care",
        ],
        "pubmed_query": '"Borderline Personality Disorder"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "bipolar disorder nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "bipolar disorder nursing",
            "bipolar disorder care nursing",
            "mania nursing",
            "mood stabilizer nursing",
            "bipolar nursing intervention",
        ],
        "pubmed_query": '"Bipolar Disorder"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "major depression nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "depression nursing",
            "major depressive disorder nursing",
            "depressive disorder nursing care",
            "antidepressant nursing",
        ],
        "pubmed_query": '"Depressive Disorder, Major"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "anxiety disorders nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "anxiety disorders nursing",
            "anxiety nursing care",
            "panic disorder nursing",
            "social anxiety nursing",
            "phobia nursing",
        ],
        "pubmed_query": '"Anxiety Disorders"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "OCD nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "OCD nursing",
            "obsessive-compulsive disorder nursing",
            "obsessive compulsive nursing care",
        ],
        "pubmed_query": '"Obsessive-Compulsive Disorder"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "eating disorders nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "eating disorders nursing",
            "anorexia nervosa nursing",
            "bulimia nursing",
            "eating disorder nursing care",
        ],
        "pubmed_query": '"Feeding and Eating Disorders"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "PTSD / trauma nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "PTSD nursing",
            "post-traumatic stress disorder nursing",
            "complex PTSD care",
            "trauma disorder nursing",
        ],
        "pubmed_query": '"Stress Disorders, Post-Traumatic"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "substance use disorders nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "substance use disorder nursing",
            "addiction nursing",
            "alcohol use disorder nursing",
            "drug addiction nursing",
            "opioid use disorder nursing",
        ],
        "pubmed_query": '"Substance-Related Disorders"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "dual diagnosis / comorbidity nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "dual diagnosis nursing",
            "comorbidity mental health nursing",
            "co-occurring disorders nursing",
            "dual diagnosis care",
        ],
        "pubmed_query": '(dual diagnosis[tiab] OR comorbidity[tiab] OR "co-occurring disorders"[tiab]) AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "dementia psychiatric nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "dementia nursing psychiatric",
            "dementia behavioural symptoms nursing",
            "BPSD nursing",
            "Alzheimer nursing psychiatric",
        ],
        "pubmed_query": '("Dementia"[MeSH] OR "Alzheimer Disease"[MeSH]) AND ("Psychiatric Nursing"[MeSH] OR psychiatric nurs*[tiab])',
    },
    {
        "label": "ADHD nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "ADHD nursing",
            "attention deficit hyperactivity disorder nursing",
            "ADHD nursing care",
        ],
        "pubmed_query": '"Attention Deficit Disorder with Hyperactivity"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "autism spectrum disorder nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "autism spectrum disorder nursing",
            "ASD nursing",
            "autism nursing care",
        ],
        "pubmed_query": '"Autism Spectrum Disorder"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "personality disorders nursing",
        "vault_category": "Psychische Erkrankungen und Diagnostik",
        "terms": [
            "personality disorders nursing",
            "personality disorder nursing care",
            "narcissistic personality disorder nursing",
            "antisocial personality nursing",
        ],
        "pubmed_query": '"Personality Disorders"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    # ── Behandlung und Therapieansätze ────────────────────────────────────────
    {
        "label": "dialectical behavior therapy",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "dialectical behavior therapy",
            "dialectical behaviour therapy",
            "DBT skills training",
            "DBT nursing",
            "DBT psychiatric",
        ],
        "pubmed_query": '"Dialectical Behavior Therapy"[MeSH] OR (dialectical behavior therap*[tiab] AND (nurs*[tiab] OR psychiatr*[tiab]))',
    },
    {
        "label": "trauma-informed care nursing",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "trauma-informed care",
            "trauma-informed nursing",
            "trauma-informed approach",
            "adverse childhood experiences nursing",
        ],
        "pubmed_query": '("Trauma-Informed Care"[MeSH] OR trauma-informed care[tiab] OR trauma-informed nursing[tiab]) AND (nurs*[tiab] OR psychiatr*[tiab])',
    },
    {
        "label": "therapeutic relationship / communication",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "therapeutic relationship nursing",
            "therapeutic communication nursing",
            "nurse-patient relationship",
            "therapeutic alliance nursing",
            "milieu therapy",
        ],
        "pubmed_query": '("Nurse-Patient Relations"[MeSH] OR therapeutic relationship[tiab] OR therapeutic communication[tiab] OR nurse-patient relationship[tiab]) AND (psychiatr*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "psychoeducation nursing",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "psychoeducation nursing",
            "psychiatric patient education",
            "mental health psychoeducation",
        ],
        "pubmed_query": '(psychoeducation[tiab] OR "patient education"[tiab]) AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "recovery-oriented care nursing",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "recovery-oriented care nursing",
            "recovery approach psychiatry",
            "mental health recovery nursing",
            "strengths-based psychiatric nursing",
        ],
        "pubmed_query": '(recovery-oriented[tiab] OR "recovery approach"[tiab] OR "strengths-based"[tiab]) AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "de-escalation / aggression management psychiatric",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "de-escalation psychiatric",
            "aggression management psychiatric nursing",
            "violence prevention psychiatric nursing",
            "conflict resolution psychiatric nursing",
        ],
        "pubmed_query": '(de-escalation[tiab] OR "aggression management"[tiab] OR "violence prevention"[tiab]) AND (nurs*[tiab] OR psychiatr*[tiab])',
    },
    {
        "label": "family interventions psychiatric nursing",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "family intervention psychiatric nursing",
            "family therapy psychiatric nursing",
            "carer support mental health nursing",
            "family psychoeducation",
        ],
        "pubmed_query": '("Family Therapy"[MeSH] OR family intervention*[tiab] OR carer support[tiab]) AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "early intervention psychosis nursing",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "early intervention psychosis nursing",
            "first episode psychosis nursing",
            "early psychosis program nursing",
        ],
        "pubmed_query": '(early intervention[tiab] AND psychos*[tiab] OR first-episode psychosis[tiab]) AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "safewards / milieu therapy",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "safewards",
            "milieu therapy psychiatric",
            "therapeutic milieu nursing",
            "ward atmosphere nursing",
        ],
        "pubmed_query": '(safewards[tiab] OR "milieu therapy"[tiab] OR "therapeutic milieu"[tiab] OR "ward atmosphere"[tiab]) AND (nurs*[tiab] OR psychiatr*[tiab])',
    },
    {
        "label": "open dialogue psychiatric nursing",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "open dialogue psychiatry",
            "open dialogue nursing",
            "dialogical practice psychiatric",
        ],
        "pubmed_query": '"open dialogue"[tiab] AND (nurs*[tiab] OR psychiatr*[tiab])',
    },
    {
        "label": "motivational interviewing psychiatric nursing",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "motivational interviewing psychiatric nursing",
            "motivational interviewing mental health nursing",
        ],
        "pubmed_query": '"Motivational Interviewing"[MeSH] AND (psychiatr*[tiab] OR nurs*[tiab])',
    },
    {
        "label": "mindfulness psychiatric nursing",
        "vault_category": "Behandlung und Therapieansätze",
        "terms": [
            "mindfulness psychiatric nursing",
            "mindfulness-based intervention psychiatric nursing",
            "MBSR psychiatric nursing",
        ],
        "pubmed_query": '(mindfulness[tiab] OR "mindfulness-based"[tiab]) AND psychiatr*[tiab] AND nurs*[tiab]',
    },
    # ── Pflege als Profession und Wissenschaft ────────────────────────────────
    {
        "label": "inpatient psychiatric nursing",
        "vault_category": "Pflege als Profession und Wissenschaft",
        "terms": [
            "inpatient psychiatric nursing",
            "acute psychiatric ward nursing",
            "closed ward psychiatric nursing",
            "psychiatric unit nursing",
        ],
        "pubmed_query": '("Psychiatric Department, Hospital"[MeSH] OR inpatient psychiatr*[tiab] OR acute psychiatric ward[tiab]) AND nurs*[tiab]',
    },
    {
        "label": "community mental health nursing",
        "vault_category": "Pflege als Profession und Wissenschaft",
        "terms": [
            "community mental health nursing",
            "community psychiatric nursing",
            "outpatient mental health nursing",
        ],
        "pubmed_query": '"Community Mental Health Services"[MeSH] AND nurs*[tiab]',
    },
    {
        "label": "home treatment / crisis resolution nursing",
        "vault_category": "Pflege als Profession und Wissenschaft",
        "terms": [
            "home treatment mental health nursing",
            "crisis resolution nursing",
            "assertive community treatment nursing",
            "home-based psychiatric nursing",
        ],
        "pubmed_query": '(home treatment[tiab] OR crisis resolution[tiab] OR "assertive community treatment"[tiab]) AND (mental health[tiab] OR psychiatr*[tiab]) AND nurs*[tiab]',
    },
    {
        "label": "child adolescent psychiatric nursing",
        "vault_category": "Pflege als Profession und Wissenschaft",
        "terms": [
            "child psychiatric nursing",
            "adolescent psychiatric nursing",
            "child adolescent mental health nursing",
            "CAMHS nursing",
        ],
        "pubmed_query": '("Child Psychiatry"[MeSH] OR "Adolescent Psychiatry"[MeSH] OR child and adolescent mental health[tiab]) AND nurs*[tiab]',
    },
    {
        "label": "geriatric psychiatric nursing",
        "vault_category": "Pflege als Profession und Wissenschaft",
        "terms": [
            "geriatric psychiatric nursing",
            "old age psychiatry nursing",
            "elderly mental health nursing",
            "psychogeriatric nursing",
        ],
        "pubmed_query": '("Geriatric Psychiatry"[MeSH] OR old age psychiatry[tiab] OR psychogeriatric*[tiab]) AND nurs*[tiab]',
    },
    {
        "label": "perinatal mental health nursing",
        "vault_category": "Pflege als Profession und Wissenschaft",
        "terms": [
            "perinatal mental health nursing",
            "postpartum psychiatric nursing",
            "perinatal psychiatry nursing",
            "maternal mental health nursing",
        ],
        "pubmed_query": '(perinatal mental health[tiab] OR postpartum psychiatr*[tiab] OR maternal mental health[tiab]) AND nurs*[tiab]',
    },
    {
        "label": "transcultural / refugee mental health nursing",
        "vault_category": "Pflege als Profession und Wissenschaft",
        "terms": [
            "transcultural psychiatric nursing",
            "cultural competence mental health nursing",
            "refugee mental health nursing",
            "migrant mental health nursing",
        ],
        "pubmed_query": '(transcultural[tiab] OR refugee*[tiab] OR migrant*[tiab] OR "cultural competence"[tiab]) AND mental health[tiab] AND nurs*[tiab]',
    },
    {
        "label": "intellectual disability psychiatric nursing",
        "vault_category": "Pflege als Profession und Wissenschaft",
        "terms": [
            "intellectual disability psychiatric nursing",
            "learning disability mental health nursing",
            "intellectual disability mental health nursing",
        ],
        "pubmed_query": '"Intellectual Disability"[MeSH] AND (psychiatr*[tiab] OR mental health[tiab]) AND nurs*[tiab]',
    },
    {
        "label": "evidence-based psychiatric nursing",
        "vault_category": "Pflege als Profession und Wissenschaft",
        "terms": [
            "evidence-based psychiatric nursing",
            "evidence-based mental health nursing",
            "psychiatric nursing research",
        ],
        "pubmed_query": '(evidence-based[tiab] OR "evidence based"[tiab]) AND "Psychiatric Nursing"[MeSH]',
    },
    {
        "label": "nursing theory / models psychiatry",
        "vault_category": "Pflege als Profession und Wissenschaft",
        "terms": [
            "nursing theory psychiatry",
            "psychiatric nursing models",
            "tidal model nursing",
            "nursing conceptual framework psychiatry",
        ],
        "pubmed_query": '(nursing theory[tiab] OR nursing model*[tiab] OR "tidal model"[tiab] OR nursing conceptual framework[tiab]) AND (psychiatr*[tiab] OR mental health[tiab])',
    },
    # ── Forensische Psychiatrie ───────────────────────────────────────────────
    {
        "label": "forensic psychiatric nursing",
        "vault_category": "Forensische Psychiatrie",
        "terms": [
            "forensic psychiatric nursing",
            "forensic mental health nursing",
            "secure psychiatric unit nursing",
            "offender mental health nursing",
        ],
        "pubmed_query": '"Forensic Psychiatry"[MeSH] AND (nurs*[tiab] OR "Psychiatric Nursing"[MeSH])',
    },
    {
        "label": "coercion / seclusion / restraint nursing",
        "vault_category": "Forensische Psychiatrie",
        "terms": [
            "seclusion psychiatric nursing",
            "restraint psychiatric nursing",
            "coercion psychiatry nursing",
            "physical restraint mental health",
        ],
        "pubmed_query": '("Restraint, Physical"[MeSH] OR seclusion[tiab] OR coercion[tiab] OR "mechanical restraint"[tiab]) AND (nurs*[tiab] OR psychiatr*[tiab])',
    },
    {
        "label": "involuntary treatment / mental health law",
        "vault_category": "Forensische Psychiatrie",
        "terms": [
            "involuntary psychiatric treatment",
            "compulsory treatment nursing",
            "involuntary hospitalization mental health",
            "mental health law nursing",
        ],
        "pubmed_query": '(involuntary[tiab] AND (treatment[tiab] OR hospitalization[tiab])) AND (psychiatr*[tiab] OR nurs*[tiab] OR mental health[tiab])',
    },
    {
        "label": "autonomy / ethics psychiatric nursing",
        "vault_category": "Forensische Psychiatrie",
        "terms": [
            "autonomy psychiatric nursing",
            "informed consent psychiatry nursing",
            "ethics psychiatric nursing",
            "human rights psychiatric nursing",
        ],
        "pubmed_query": '(autonomy[tiab] OR "informed consent"[tiab] OR ethics[tiab] OR "human rights"[tiab]) AND "Psychiatric Nursing"[MeSH]',
    },
    # ── Pflegende selbst ──────────────────────────────────────────────────────
    {
        "label": "psychiatric nursing burnout / compassion fatigue",
        "vault_category": "Pflegende selbst",
        "terms": [
            "psychiatric nursing burnout",
            "compassion fatigue psychiatric nursing",
            "emotional exhaustion psychiatric nurses",
            "secondary traumatic stress nursing",
        ],
        "pubmed_query": '(burnout[tiab] OR "compassion fatigue"[tiab] OR "secondary traumatic stress"[tiab]) AND ("Psychiatric Nursing"[MeSH] OR psychiatric nurs*[tiab])',
    },
    {
        "label": "psychiatric nurse supervision / wellbeing",
        "vault_category": "Pflegende selbst",
        "terms": [
            "clinical supervision psychiatric nursing",
            "psychiatric nurse wellbeing",
            "psychiatric nurse support",
            "reflective practice psychiatric nursing",
        ],
        "pubmed_query": '(supervision[tiab] OR wellbeing[tiab] OR well-being[tiab] OR "reflective practice"[tiab]) AND ("Psychiatric Nursing"[MeSH] OR psychiatric nurs*[tiab])',
    },
    {
        "label": "psychiatric nursing education / training",
        "vault_category": "Pflegende selbst",
        "terms": [
            "psychiatric nursing education",
            "mental health nursing training",
            "psychiatric nurse competencies",
            "nursing preceptorship psychiatry",
        ],
        "pubmed_query": '("Education, Nursing"[MeSH] OR nursing education[tiab] OR nursing training[tiab] OR competenc*[tiab]) AND psychiatr*[tiab]',
    },
    {
        "label": "psychiatric nursing workforce / staffing",
        "vault_category": "Pflegende selbst",
        "terms": [
            "psychiatric nursing workforce",
            "mental health nursing staffing",
            "psychiatric nurse-to-patient ratio",
            "mental health nursing shortage",
        ],
        "pubmed_query": '(workforce[tiab] OR staffing[tiab] OR "nurse-to-patient ratio"[tiab] OR shortage[tiab]) AND (psychiatr*[tiab] OR mental health nurs*[tiab])',
    },
    {
        "label": "psychiatric nursing leadership / management",
        "vault_category": "Pflegende selbst",
        "terms": [
            "psychiatric nursing leadership",
            "mental health nursing management",
            "nurse manager psychiatry",
        ],
        "pubmed_query": '(leadership[tiab] OR management[tiab] OR "nurse manager"[tiab]) AND ("Psychiatric Nursing"[MeSH] OR psychiatric nurs*[tiab])',
    },
    {
        "label": "moral distress / ethical stress nursing",
        "vault_category": "Pflegende selbst",
        "terms": [
            "moral distress psychiatric nursing",
            "ethical stress nursing",
            "moral injury nursing",
        ],
        "pubmed_query": '("moral distress"[tiab] OR "moral injury"[tiab] OR ethical stress[tiab]) AND nurs*[tiab]',
    },
]

EXCLUDED_TITLE_PATTERNS = [
    r"\bcorrection\b",
    r"\berratum\b",
    r"\bretraction\b",
    r"\bexpression of concern\b",
    r"\beditorial board\b",
    r"\bannouncement\b",
    r"\bbook review\b",
    r"\bcalendar\b",
]

USER_AGENT_BASE = "NursingLiteratureDigest/1.0"
ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_date(value: str) -> dt.datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def date_only(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).date().isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def clean_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [clean_text(value) for value in values if clean_text(value)]


def configured_keyword_groups(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    groups: list[dict[str, Any]] = []
    for group in values:
        if not isinstance(group, dict):
            continue
        label = clean_text(group.get("label"))
        terms = clean_list(group.get("terms"))
        if label and terms:
            entry: dict[str, Any] = {"label": label, "terms": terms}
            pubmed_query = group.get("pubmed_query", "")
            if isinstance(pubmed_query, str) and pubmed_query.strip():
                entry["pubmed_query"] = pubmed_query.strip()
            groups.append(entry)
    return groups


def configured_publishers(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    publishers: list[dict[str, Any]] = []
    for publisher in values:
        if not isinstance(publisher, dict):
            continue
        key = clean_text(publisher.get("key"))
        display = clean_text(publisher.get("display"))
        member = clean_text(publisher.get("crossref_member"))
        if not key or not display or not member:
            continue
        publishers.append(
            {
                "key": key,
                "display": display,
                "crossref_member": member,
                "crossref_name": clean_text(publisher.get("crossref_name")) or display,
                "crossref_date_mode": clean_text(publisher.get("crossref_date_mode")) or "pub-date",
                "openalex_publishers": clean_list(publisher.get("openalex_publishers")),
            }
        )
    return publishers


def read_config(path_value: str | None) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    return read_json(path, {})


def normalize_locale_name(value: str | None) -> str:
    text = clean_text(value)
    if not text:
        return ""
    text = text.split(":", 1)[0].split(".", 1)[0].split("@", 1)[0]
    text = text.replace("_", "-").strip()
    if text.lower() in {"c", "posix", "utf-8"}:
        return ""
    return text


def detect_os_locale() -> str:
    candidates: list[str] = []
    for env_key in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(env_key)
        if value:
            candidates.append(value)
    for category in (locale.LC_CTYPE, locale.LC_TIME):
        try:
            language, encoding = locale.getlocale(category)
            if language:
                candidates.append(language)
            current = locale.setlocale(category, None)
            if current:
                candidates.append(current)
        except (TypeError, ValueError, locale.Error):
            continue
    for candidate in candidates:
        normalized = normalize_locale_name(candidate)
        if normalized:
            return normalized
    return ""


def language_from_locale(locale_name: str) -> str:
    normalized = normalize_locale_name(locale_name)
    if not normalized:
        return ""
    key = normalized.lower()
    if key in LOCALE_LANGUAGE_MAP:
        return LOCALE_LANGUAGE_MAP[key]
    if key.startswith("zh-hant") or key in {"zh-tw", "zh-hk", "zh-mo"}:
        return "zh-TW"
    if key.startswith("zh-hans") or key.startswith("zh-cn") or key.startswith("zh-sg") or key == "zh":
        return "zh-CN"
    base = key.split("-", 1)[0]
    if base in {"de", "en", "fr", "ja"}:
        return base
    return ""


def resolve_language(language_value: str | None) -> tuple[str, str, str]:
    requested = clean_text(language_value) or "auto"
    if requested.lower() != "auto":
        return "explicit", "", requested
    detected = detect_os_locale()
    return "auto", detected, language_from_locale(detected) or "en"


def log_language_selection() -> None:
    print(f"Language mode: {LANGUAGE_MODE}", file=sys.stderr)
    print(f"Detected locale: {DETECTED_LOCALE or 'unavailable'}", file=sys.stderr)
    print(f"Selected digest language: {LANGUAGE}", file=sys.stderr)


def int_setting(cli_value: int | None, config: dict[str, Any], key: str, default: int) -> int:
    if cli_value is not None:
        return cli_value
    value = config.get(key)
    if value is None:
        return default
    return int(value)


def float_setting(cli_value: float | None, config: dict[str, Any], key: str, default: float) -> float:
    if cli_value is not None:
        return cli_value
    value = config.get(key)
    if value is None:
        return default
    return float(value)


def apply_runtime_config(args: argparse.Namespace) -> None:
    config = read_config(getattr(args, "config", None))
    global RECIPIENT_EMAIL, CROSSREF_MAILTO, NCBI_EMAIL, LANGUAGE, LANGUAGE_MODE, DETECTED_LOCALE, TIMEZONE, SCHEDULE_TIME, PUBLISHERS, KEYWORD_GROUPS
    RECIPIENT_EMAIL = clean_text(config.get("recipient_email"))
    CROSSREF_MAILTO = clean_text(config.get("crossref_mailto")) or RECIPIENT_EMAIL
    NCBI_EMAIL = clean_text(config.get("ncbi_email")) or CROSSREF_MAILTO
    LANGUAGE_MODE, DETECTED_LOCALE, LANGUAGE = resolve_language(config.get("language") or LANGUAGE)
    TIMEZONE = clean_text(config.get("timezone")) or TIMEZONE
    SCHEDULE_TIME = clean_text(config.get("schedule_time")) or SCHEDULE_TIME
    log_language_selection()

    configured_groups = configured_keyword_groups(config.get("keyword_groups"))
    if configured_groups:
        KEYWORD_GROUPS = configured_groups
    configured_sources = configured_publishers(config.get("publishers"))
    if configured_sources:
        PUBLISHERS = configured_sources

    if args.command == "fetch":
        output_dir = args.output_dir or clean_text(config.get("output_dir")) or str(DEFAULT_OUTPUT_DIR)
        args.output_dir = output_dir
        args.state_file = args.state_file or clean_text(config.get("state_file")) or str(Path(output_dir) / "state.json")
        args.lookback_days = int_setting(args.lookback_days, config, "lookback_days", 7)
        args.rows = int_setting(args.rows, config, "rows", 20)
        args.arxiv_rows = int_setting(args.arxiv_rows, config, "arxiv_rows", 25)
        args.pubmed_rows = int_setting(args.pubmed_rows, config, "pubmed_rows", 30)
        args.max_papers = int_setting(args.max_papers, config, "max_papers", 40)
        args.min_relevance_score = int_setting(args.min_relevance_score, config, "min_relevance_score", 2)
        args.sleep = float_setting(args.sleep, config, "sleep", 0.34)
        if args.include_arxiv is None:
            args.include_arxiv = bool(config.get("include_arxiv", True))
        if args.include_pubmed is None:
            args.include_pubmed = bool(config.get("include_pubmed", True))
    elif args.command == "mark-success":
        args.state_file = args.state_file or clean_text(config.get("state_file")) or str(DEFAULT_STATE_FILE)


def user_agent() -> str:
    if CROSSREF_MAILTO:
        return f"{USER_AGENT_BASE} (mailto:{CROSSREF_MAILTO})"
    return USER_AGENT_BASE


def http_json(url: str, *, retries: int = 3, delay: float = 0.6) -> Any:
    headers = {"User-Agent": user_agent(), "Accept": "application/json"}
    last_error: str | None = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code} for {url}"
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                retry_after = exc.headers.get("Retry-After")
                sleep_for = float(retry_after) if retry_after and retry_after.isdigit() else delay * attempt
                time.sleep(sleep_for)
                continue
            raise RuntimeError(last_error) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(delay * attempt)
                continue
            raise RuntimeError(last_error) from exc
    raise RuntimeError(last_error or f"Failed to fetch {url}")


def http_text(url: str, *, retries: int = 3, delay: float = 0.6) -> str:
    headers = {"User-Agent": user_agent(), "Accept": "application/atom+xml,text/xml,*/*"}
    last_error: str | None = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code} for {url}"
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                retry_after = exc.headers.get("Retry-After")
                sleep_for = float(retry_after) if retry_after and retry_after.isdigit() else delay * attempt
                time.sleep(sleep_for)
                continue
            raise RuntimeError(last_error) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(delay * attempt)
                continue
            raise RuntimeError(last_error) from exc
    raise RuntimeError(last_error or f"Failed to fetch {url}")


def clean_text(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item)
    if not isinstance(value, str):
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_doi(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    doi = value.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = doi.strip()
    return doi


def doi_url(doi: str) -> str:
    return f"https://doi.org/{doi}" if doi else ""


def date_from_parts(parts: Any) -> str:
    if not isinstance(parts, dict):
        return ""
    date_parts = parts.get("date-parts")
    if not date_parts or not isinstance(date_parts, list) or not date_parts[0]:
        return ""
    nums = date_parts[0]
    year = int(nums[0])
    month = int(nums[1]) if len(nums) > 1 else 1
    day = int(nums[2]) if len(nums) > 2 else 1
    try:
        return dt.date(year, month, day).isoformat()
    except ValueError:
        return ""


def crossref_date(item: dict[str, Any]) -> str:
    for field in ("published-print", "published-online", "published", "issued", "created"):
        value = date_from_parts(item.get(field))
        if value:
            return value
    return ""


def format_authors(authors: Any, max_authors: int = 6) -> str:
    if not isinstance(authors, list):
        return ""
    names: list[str] = []
    for author in authors[:max_authors]:
        if not isinstance(author, dict):
            continue
        given = clean_text(author.get("given"))
        family = clean_text(author.get("family"))
        literal = clean_text(author.get("name"))
        name = " ".join(part for part in [given, family] if part).strip() or literal
        if name:
            names.append(name)
    if len(authors) > max_authors:
        names.append("et al.")
    return "; ".join(names)


def inverted_abstract(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, indexes in index.items():
        if not isinstance(indexes, list):
            continue
        for position in indexes:
            if isinstance(position, int):
                positions.append((position, word))
    positions.sort(key=lambda pair: pair[0])
    return clean_text(" ".join(word for _, word in positions))


def text_blob(*parts: str) -> str:
    return " ".join(part for part in parts if part).lower()


def keyword_hits(title: str, abstract: str, subjects: list[str]) -> tuple[list[str], int]:
    title_l = title.lower()
    abstract_l = abstract.lower()
    subjects_l = " ".join(subjects).lower()
    hits: list[str] = []
    score = 0
    for group in KEYWORD_GROUPS:
        group_hit = False
        for term in group["terms"]:
            term_l = term.lower()
            if term_l in title_l:
                score += 3
                group_hit = True
            if term_l in abstract_l:
                score += 2
                group_hit = True
            if term_l in subjects_l:
                score += 1
                group_hit = True
        if group_hit:
            hits.append(group["label"])
    return hits, score


def keyword_group_for_term(term: str) -> str:
    term_l = term.lower()
    for group in KEYWORD_GROUPS:
        if term_l == group["label"].lower() or term_l in [item.lower() for item in group["terms"]]:
            return group["label"]
    return term


def priority_for(score: int, abstract: str) -> str:
    if score >= 6 and abstract:
        return "High"
    if score >= 3:
        return "Medium"
    return "Low"


def is_excluded_title(title: str) -> bool:
    title_l = title.lower()
    return any(re.search(pattern, title_l) for pattern in EXCLUDED_TITLE_PATTERNS)


def crossref_date_filter(date_mode: str, from_date: str, until_date: str) -> str:
    if date_mode == "created-date":
        return f"from-created-date:{from_date},until-created-date:{until_date}"
    if date_mode == "index-date":
        return f"from-index-date:{from_date},until-index-date:{until_date}"
    return f"from-pub-date:{from_date},until-pub-date:{until_date}"


def crossref_query_url(member: str, term: str, from_date: str, until_date: str, rows: int, date_mode: str = "pub-date") -> str:
    params = {
        "filter": f"member:{member},type:journal-article,{crossref_date_filter(date_mode, from_date, until_date)}",
        "query.bibliographic": term,
        "rows": str(rows),
        "sort": "created" if date_mode == "created-date" else "published",
        "order": "desc",
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO
    return "https://api.crossref.org/works?" + urllib.parse.urlencode(params)


def arxiv_query_url(term: str, rows: int) -> str:
    quoted = f'all:"{term}"'
    params = {
        "search_query": quoted,
        "start": "0",
        "max_results": str(rows),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return ARXIV_API + "?" + urllib.parse.urlencode(params)


def openalex_doi_url(doi: str) -> str:
    params = {"filter": f"doi:{doi}", "per-page": "1"}
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO
    return "https://api.openalex.org/works?" + urllib.parse.urlencode(params)


def semantic_scholar_url(doi: str) -> str:
    fields = "abstract,title,year,externalIds"
    return f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi)}?fields={fields}"


def merge_semantic_scholar(paper: dict[str, Any], ss_data: dict[str, Any]) -> None:
    abstract = clean_text(ss_data.get("abstract") or "")
    if abstract and not paper.get("abstract"):
        paper["abstract"] = abstract
        paper["abstract_source"] = "Semantic Scholar"
        hits, score = keyword_hits(paper["title"], abstract, paper.get("subjects", []))
        if hits:
            paper["keyword_hits"] = list(dict.fromkeys([*paper.get("keyword_hits", []), *hits]))
            paper["relevance_score"] = max(paper.get("relevance_score", 0), score)
            paper["metadata_match_confidence"] = "direct"
        paper["priority"] = priority_for(paper["relevance_score"], abstract)


def pubmed_esearch_url(group: dict[str, Any], from_date: str, until_date: str, rows: int) -> str:
    # Use explicit pubmed_query (MeSH or boolean) if defined, else fall back to free-text terms
    query = group.get("pubmed_query", "")
    if not query:
        parts = [f'"{t}"[Title/Abstract]' for t in group.get("terms", [])]
        query = f"({' OR '.join(parts)})" if len(parts) > 1 else (parts[0] if parts else group["label"])
    mindate = from_date.replace("-", "/")
    maxdate = until_date.replace("-", "/")
    params: dict[str, str] = {
        "db": "pubmed",
        "term": query,
        "datetype": "pdat",
        "mindate": mindate,
        "maxdate": maxdate,
        "retmax": str(rows),
        "retmode": "json",
        "sort": "pub+date",
    }
    if NCBI_EMAIL:
        params["email"] = NCBI_EMAIL
    return f"{PUBMED_BASE}/esearch.fcgi?" + urllib.parse.urlencode(params)


def pubmed_efetch_url(pmids: list[str]) -> str:
    params: dict[str, str] = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    if NCBI_EMAIL:
        params["email"] = NCBI_EMAIL
    return f"{PUBMED_BASE}/efetch.fcgi?" + urllib.parse.urlencode(params)


def _xml_text(element: ET.Element | None, tag: str) -> str:
    if element is None:
        return ""
    child = element.find(tag)
    if child is None:
        return ""
    return clean_text("".join(child.itertext()))


def _xml_find_text(root: ET.Element, path: str) -> str:
    element = root.find(path)
    if element is None:
        return ""
    return clean_text("".join(element.itertext()))


def parse_pubmed_abstract(article: ET.Element) -> str:
    abstract_el = article.find(".//Abstract")
    if abstract_el is None:
        return ""
    parts: list[str] = []
    for text_el in abstract_el.findall("AbstractText"):
        label = text_el.get("Label", "")
        text = clean_text("".join(text_el.itertext()))
        if text:
            parts.append(f"{label}: {text}" if label else text)
    return " ".join(parts)


def parse_pubmed_date(article: ET.Element) -> str:
    pub_date = article.find(".//JournalIssue/PubDate")
    if pub_date is None:
        return ""
    year = _xml_text(pub_date, "Year")
    month_text = _xml_text(pub_date, "Month")
    day = _xml_text(pub_date, "Day")
    medline_date = _xml_text(pub_date, "MedlineDate")
    if not year and medline_date:
        match = re.search(r"\b(\d{4})\b", medline_date)
        if match:
            year = match.group(1)
    if not year:
        return ""
    month_map = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
        "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
        "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
    }
    month_num = month_map.get(month_text[:3].capitalize(), "01") if month_text else "01"
    day_num = day.zfill(2) if day and day.isdigit() else "01"
    try:
        return dt.date(int(year), int(month_num), int(day_num)).isoformat()
    except ValueError:
        return f"{year}-{month_num}-01"


def parse_pubmed_authors(article: ET.Element, max_authors: int = 6) -> str:
    names: list[str] = []
    for author in article.findall(".//AuthorList/Author")[:max_authors]:
        last = _xml_text(author, "LastName")
        fore = _xml_text(author, "ForeName")
        collective = _xml_text(author, "CollectiveName")
        name = " ".join(part for part in [fore, last] if part).strip() or collective
        if name:
            names.append(name)
    total = len(article.findall(".//AuthorList/Author"))
    if total > max_authors:
        names.append("et al.")
    return "; ".join(names)


def parse_pubmed_mesh(article: ET.Element) -> list[str]:
    terms: list[str] = []
    for heading in article.findall(".//MeshHeadingList/MeshHeading"):
        descriptor = heading.find("DescriptorName")
        if descriptor is not None:
            text = clean_text("".join(descriptor.itertext()))
            if text:
                terms.append(text)
    return terms


def parse_pubmed_keywords(article: ET.Element) -> list[str]:
    terms: list[str] = []
    for kw in article.findall(".//KeywordList/Keyword"):
        text = clean_text("".join(kw.itertext()))
        if text:
            terms.append(text)
    return terms


def normalize_pubmed_article(article_set_child: ET.Element, query_term: str) -> dict[str, Any] | None:
    citation = article_set_child.find("MedlineCitation")
    if citation is None:
        return None
    article = citation.find("Article")
    if article is None:
        return None

    pmid_el = citation.find("PMID")
    pmid = clean_text("".join(pmid_el.itertext())) if pmid_el is not None else ""
    title = _xml_find_text(article, "ArticleTitle")
    if not title or is_excluded_title(title):
        return None

    journal_el = article.find("Journal")
    journal = _xml_find_text(journal_el, "Title") if journal_el is not None else ""
    abstract = parse_pubmed_abstract(article)
    published = parse_pubmed_date(article)
    authors = parse_pubmed_authors(article)
    mesh_terms = parse_pubmed_mesh(citation)
    keywords = parse_pubmed_keywords(citation)
    subjects = list(dict.fromkeys([*mesh_terms, *keywords]))

    pubmed_data = article_set_child.find("PubmedData")
    doi = ""
    pmc_id = ""
    if pubmed_data is not None:
        for article_id in pubmed_data.findall(".//ArticleIdList/ArticleId"):
            id_type = article_id.get("IdType", "")
            id_val = clean_text("".join(article_id.itertext()))
            if id_type == "doi" and not doi:
                doi = normalize_doi(id_val)
            elif id_type == "pmc" and not pmc_id:
                pmc_id = id_val

    url = doi_url(doi) if doi else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
    open_access_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/" if pmc_id else ""

    pub_type_els = article.findall(".//PublicationTypeList/PublicationType")
    pub_types = [clean_text("".join(el.itertext())) for el in pub_type_els if el is not None]
    is_review = any("review" in pt.lower() or "meta-analysis" in pt.lower() for pt in pub_types)

    hits, score = keyword_hits(title, abstract, subjects)
    if not hits:
        hits = [keyword_group_for_term(query_term)]
        score = 1

    return {
        "title": title,
        "doi": doi,
        "pmid": pmid,
        "url": url,
        "publisher": "PubMed/MEDLINE",
        "publisher_key": "pubmed",
        "crossref_publisher": "",
        "journal": journal,
        "published_date": published,
        "authors": authors,
        "abstract": abstract,
        "abstract_source": "PubMed" if abstract else "",
        "subjects": subjects,
        "mesh_terms": mesh_terms,
        "publication_types": pub_types,
        "is_review_or_meta": is_review,
        "keyword_hits": hits,
        "query_term": query_term,
        "metadata_match_confidence": "direct" if score > 1 else "query-only",
        "relevance_score": score,
        "priority": priority_for(score, abstract),
        "openalex_id": "",
        "openalex_url": "",
        "open_access_url": open_access_url,
        "pdf_url": "",
        "source": "PubMed",
    }


def fetch_pubmed_papers(
    args: argparse.Namespace,
    from_date: str,
    until_date: str,
    seen_keys: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    papers_by_key: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []

    all_pmids_by_term: dict[str, str] = {}

    for group in KEYWORD_GROUPS:
        url = pubmed_esearch_url(group, from_date, until_date, args.pubmed_rows)
        try:
            payload = http_json(url)
            pmids: list[str] = payload.get("esearchresult", {}).get("idlist", [])
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "PubMed-esearch", "term": group["label"], "error": str(exc)})
            time.sleep(0.34)
            continue

        for pmid in pmids:
            if pmid not in all_pmids_by_term:
                all_pmids_by_term[pmid] = group["label"]
        time.sleep(0.34)

    pmid_list = list(all_pmids_by_term.keys())
    batch_size = 100
    for batch_start in range(0, len(pmid_list), batch_size):
        batch = pmid_list[batch_start : batch_start + batch_size]
        url = pubmed_efetch_url(batch)
        try:
            xml_text = http_text(url)
            root = ET.fromstring(xml_text)
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "PubMed-efetch", "pmids": batch[:5], "error": str(exc)})
            time.sleep(0.34)
            continue

        for child in root:
            pmid_el = child.find(".//MedlineCitation/PMID")
            pmid = clean_text("".join(pmid_el.itertext())) if pmid_el is not None else ""
            query_term = all_pmids_by_term.get(pmid, "")
            paper = normalize_pubmed_article(child, query_term)
            if not paper:
                continue
            state_key = f"pmid:{pmid}" if pmid else f"doi:{paper['doi']}" if paper["doi"] else f"title:{paper['title'].lower()}"
            if state_key in seen_keys and not args.include_seen:
                continue
            paper["state_key"] = state_key
            key = paper["doi"] or f"pmid:{pmid}" or paper["title"].lower()
            existing = papers_by_key.get(key)
            if not existing or paper["relevance_score"] > existing["relevance_score"]:
                papers_by_key[key] = paper
        time.sleep(0.34)

    return list(papers_by_key.values()), errors


def normalize_crossref_item(item: dict[str, Any], publisher: dict[str, Any], query_term: str) -> dict[str, Any] | None:
    title = clean_text(item.get("title"))
    doi = normalize_doi(item.get("DOI"))
    if not title or is_excluded_title(title):
        return None
    journal = clean_text(item.get("container-title"))
    abstract = clean_text(item.get("abstract"))
    subjects = [clean_text(value) for value in item.get("subject", []) if clean_text(value)]
    hits, score = keyword_hits(title, abstract, subjects)
    if not hits:
        hits = [keyword_group_for_term(query_term)]
        score = 1
    published = crossref_date(item)
    return {
        "title": title,
        "doi": doi,
        "pmid": "",
        "url": doi_url(doi) or clean_text(item.get("URL")),
        "publisher": publisher["display"],
        "publisher_key": publisher["key"],
        "crossref_publisher": clean_text(item.get("publisher")) or publisher["crossref_name"],
        "journal": journal,
        "published_date": published,
        "authors": format_authors(item.get("author")),
        "abstract": abstract,
        "abstract_source": "Crossref" if abstract else "",
        "subjects": subjects,
        "mesh_terms": [],
        "publication_types": [],
        "is_review_or_meta": False,
        "keyword_hits": hits,
        "query_term": query_term,
        "metadata_match_confidence": "direct" if score > 1 else "query-only",
        "relevance_score": score,
        "priority": priority_for(score, abstract),
        "openalex_id": "",
        "openalex_url": "",
        "open_access_url": "",
        "pdf_url": "",
        "source": "Crossref",
    }


def merge_openalex(paper: dict[str, Any], openalex_work: dict[str, Any]) -> dict[str, Any]:
    paper["openalex_id"] = clean_text(openalex_work.get("id"))
    paper["openalex_url"] = clean_text(openalex_work.get("id"))
    if not paper.get("abstract"):
        abstract = inverted_abstract(openalex_work.get("abstract_inverted_index"))
        if abstract:
            paper["abstract"] = abstract
            paper["abstract_source"] = "OpenAlex"
    concepts = [
        clean_text(topic.get("display_name"))
        for topic in openalex_work.get("concepts", [])
        if isinstance(topic, dict) and clean_text(topic.get("display_name"))
    ]
    topics = [
        clean_text(topic.get("display_name"))
        for topic in openalex_work.get("topics", [])
        if isinstance(topic, dict) and clean_text(topic.get("display_name"))
    ]
    combined_subjects = list(dict.fromkeys([*paper.get("subjects", []), *concepts, *topics]))
    paper["subjects"] = combined_subjects
    primary_location = openalex_work.get("primary_location") if isinstance(openalex_work.get("primary_location"), dict) else {}
    landing = clean_text(primary_location.get("landing_page_url"))
    pdf = clean_text(primary_location.get("pdf_url"))
    if landing and not paper.get("url"):
        paper["url"] = landing
    if not paper.get("open_access_url"):
        paper["open_access_url"] = landing
    paper["pdf_url"] = pdf
    hits, score = keyword_hits(paper["title"], paper.get("abstract", ""), combined_subjects)
    if hits:
        paper["keyword_hits"] = hits
        paper["relevance_score"] = score
        paper["metadata_match_confidence"] = "direct"
    else:
        paper["keyword_hits"] = paper.get("keyword_hits", [])
        paper["relevance_score"] = paper.get("relevance_score", 1)
    paper["priority"] = priority_for(paper["relevance_score"], paper.get("abstract", ""))
    return paper


def parse_arxiv_date(value: str) -> str:
    if not value:
        return ""
    try:
        return parse_date(value).date().isoformat()
    except ValueError:
        return ""


def arxiv_id_from_url(value: str) -> str:
    value = value.strip()
    match = re.search(r"arxiv\.org/abs/([^?#]+)", value)
    if match:
        return match.group(1)
    return value.rsplit("/", 1)[-1]


def normalize_arxiv_entry(entry: ET.Element) -> dict[str, Any] | None:
    title = clean_text(entry.findtext("atom:title", default="", namespaces=ARXIV_NS))
    abstract = clean_text(entry.findtext("atom:summary", default="", namespaces=ARXIV_NS))
    published_raw = clean_text(entry.findtext("atom:published", default="", namespaces=ARXIV_NS))
    updated_raw = clean_text(entry.findtext("atom:updated", default="", namespaces=ARXIV_NS))
    entry_url = clean_text(entry.findtext("atom:id", default="", namespaces=ARXIV_NS))
    if not title or is_excluded_title(title):
        return None
    arxiv_id = arxiv_id_from_url(entry_url)
    authors = []
    for author in entry.findall("atom:author", namespaces=ARXIV_NS):
        name = clean_text(author.findtext("atom:name", default="", namespaces=ARXIV_NS))
        if name:
            authors.append(name)
    subjects = []
    for category in entry.findall("atom:category", namespaces=ARXIV_NS):
        term = clean_text(category.attrib.get("term"))
        if term:
            subjects.append(term)
    pdf_url = ""
    for link in entry.findall("atom:link", namespaces=ARXIV_NS):
        if link.attrib.get("title") == "pdf":
            pdf_url = clean_text(link.attrib.get("href"))
            break
    hits, score = keyword_hits(title, abstract, subjects)
    if not hits:
        return None
    return {
        "title": title,
        "doi": "",
        "pmid": "",
        "arxiv_id": arxiv_id,
        "url": entry_url or f"https://arxiv.org/abs/{arxiv_id}",
        "publisher": "arXiv",
        "publisher_key": "arxiv",
        "crossref_publisher": "",
        "journal": "arXiv preprint",
        "published_date": parse_arxiv_date(published_raw) or parse_arxiv_date(updated_raw),
        "authors": "; ".join(authors[:6] + (["et al."] if len(authors) > 6 else [])),
        "abstract": abstract,
        "abstract_source": "arXiv",
        "subjects": subjects,
        "mesh_terms": [],
        "publication_types": ["Preprint"],
        "is_review_or_meta": False,
        "keyword_hits": hits,
        "relevance_score": score,
        "priority": priority_for(score, abstract),
        "openalex_id": "",
        "openalex_url": "",
        "open_access_url": entry_url,
        "pdf_url": pdf_url,
        "source": "arXiv",
        "source_type": "preprint",
    }


def fetch_arxiv_papers(
    args: argparse.Namespace,
    window_from: dt.datetime,
    window_until: dt.datetime,
    seen_keys: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    papers_by_key: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    for group in KEYWORD_GROUPS:
        term = group.get("arxiv_term") or group["label"]
        url = arxiv_query_url(term, args.arxiv_rows)
        try:
            xml_text = http_text(url)
            root = ET.fromstring(xml_text)
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "arXiv", "term": term, "error": str(exc)})
            continue
        for entry in root.findall("atom:entry", namespaces=ARXIV_NS):
            paper = normalize_arxiv_entry(entry)
            if not paper:
                continue
            published = paper.get("published_date")
            if published:
                published_dt = dt.datetime.fromisoformat(published).replace(tzinfo=dt.timezone.utc)
                if published_dt.date() < window_from.date() or published_dt.date() > window_until.date():
                    continue
            state_key = f"arxiv:{paper.get('arxiv_id') or paper['title'].lower()}"
            if state_key in seen_keys and not args.include_seen:
                continue
            paper["state_key"] = state_key
            existing = papers_by_key.get(state_key)
            if not existing or paper["relevance_score"] > existing["relevance_score"]:
                papers_by_key[state_key] = paper
        time.sleep(max(args.sleep, 3.1))
    return list(papers_by_key.values()), errors


def fetch_candidates(args: argparse.Namespace) -> Path:
    output_dir = Path(args.output_dir)
    state_file = Path(args.state_file)
    state = read_json(state_file, {})
    now = utc_now()
    if args.from_date:
        window_from = parse_date(args.from_date)
    elif state.get("last_success_utc"):
        window_from = parse_date(state["last_success_utc"])
        # PubMed publication-date indexing lags 1-2 days; ensure at least 3-day window
        # so recent papers aren't missed. Seen-items deduplication prevents repeats.
        min_window_from = now - dt.timedelta(days=3)
        if window_from > min_window_from:
            window_from = min_window_from
    else:
        window_from = now - dt.timedelta(days=args.lookback_days)
    if args.until_date:
        window_until = parse_date(args.until_date)
    else:
        window_until = now

    from_date = date_only(window_from)
    until_date = date_only(window_until)
    seen_dois = {normalize_doi(doi) for doi in state.get("seen_dois", []) if normalize_doi(doi)}
    seen_keys = {str(item) for item in state.get("seen_items", []) if item}
    seen_keys.update(f"doi:{doi}" for doi in seen_dois)
    papers_by_key: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []

    if args.include_pubmed:
        pubmed_papers, pubmed_errors = fetch_pubmed_papers(args, from_date, until_date, seen_keys)
        errors.extend(pubmed_errors)
        for paper in pubmed_papers:
            key = paper.get("doi") or paper.get("pmid") or paper["title"].lower()
            papers_by_key[key] = paper

    for publisher in PUBLISHERS:
        for group in KEYWORD_GROUPS:
            url = crossref_query_url(
                publisher["crossref_member"],
                group["label"],
                from_date,
                until_date,
                args.rows,
                publisher.get("crossref_date_mode", "pub-date"),
            )
            try:
                payload = http_json(url)
                items = payload.get("message", {}).get("items", [])
            except Exception as exc:  # noqa: BLE001
                errors.append({"source": "Crossref", "publisher": publisher["display"], "term": group["label"], "error": str(exc)})
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                paper = normalize_crossref_item(item, publisher, group["label"])
                if not paper:
                    continue
                key = paper["doi"] or f"{paper['title'].lower()}|{paper.get('journal', '').lower()}|{paper.get('published_date', '')}"
                state_key = f"doi:{paper['doi']}" if paper["doi"] else f"title:{key}"
                if state_key in seen_keys and not args.include_seen:
                    continue
                paper["state_key"] = state_key
                existing = papers_by_key.get(key)
                if not existing or paper["relevance_score"] > existing["relevance_score"]:
                    papers_by_key[key] = paper
            time.sleep(args.sleep)

    if args.include_arxiv:
        arxiv_papers, arxiv_errors = fetch_arxiv_papers(args, window_from, window_until, seen_keys)
        errors.extend(arxiv_errors)
        for paper in arxiv_papers:
            papers_by_key[paper["state_key"]] = paper

    papers = sorted(
        papers_by_key.values(),
        key=lambda item: (
            item.get("is_review_or_meta", False),
            item.get("priority") == "High",
            item.get("relevance_score", 0),
            item.get("published_date", ""),
        ),
        reverse=True,
    )
    papers = papers[: args.max_papers]

    for paper in papers:
        doi = paper.get("doi", "")
        if not doi:
            continue
        # OpenAlex enrichment
        try:
            payload = http_json(openalex_doi_url(doi), retries=2)
            results = payload.get("results", [])
            if results:
                merge_openalex(paper, results[0])
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "OpenAlex", "doi": doi, "error": str(exc)})
        time.sleep(args.sleep)
        # Semantic Scholar enrichment — only for papers still missing an abstract
        if not paper.get("abstract"):
            try:
                ss_data = http_json(semantic_scholar_url(doi), retries=1)
                merge_semantic_scholar(paper, ss_data)
            except RuntimeError as exc:
                if "HTTP 404" not in str(exc):  # 404 = not yet indexed, not an error
                    errors.append({"source": "SemanticScholar", "doi": doi, "error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                errors.append({"source": "SemanticScholar", "doi": doi, "error": str(exc)})
            time.sleep(args.sleep)

    papers = [paper for paper in papers if paper.get("keyword_hits")]

    # Drop query-only false positives: papers where no keyword matched in title/abstract/subjects.
    # Score=1 means only the query term was matched (fallback), not actual content.
    min_score = getattr(args, "min_relevance_score", 2)
    papers_before_filter = len(papers)
    papers = [paper for paper in papers if paper.get("relevance_score", 0) >= min_score]
    filtered_count = papers_before_filter - len(papers)

    papers.sort(
        key=lambda item: (
            item.get("is_review_or_meta", False),
            item.get("priority") == "High",
            item.get("relevance_score", 0),
            item.get("published_date", ""),
        ),
        reverse=True,
    )

    run_utc = window_until.astimezone(dt.timezone.utc)
    run_id = run_utc.strftime("%Y-%m-%d")
    run_stamp = run_utc.strftime("%Y-%m-%dT%H%M%SZ")
    output_path = output_dir / "data" / f"{run_stamp}.json"
    payload = {
        "run_id": run_id,
        "run_stamp": run_stamp,
        "created_utc": now.isoformat(),
        "recipient_email": RECIPIENT_EMAIL,
        "language": LANGUAGE,
        "language_mode": LANGUAGE_MODE,
        "detected_locale": DETECTED_LOCALE,
        "timezone": TIMEZONE,
        "schedule_time": SCHEDULE_TIME,
        "window_from_utc": window_from.isoformat(),
        "window_until_utc": window_until.isoformat(),
        "window_from_date": from_date,
        "window_until_date": until_date,
        "keywords": KEYWORD_GROUPS,
        "publishers": [
            *([{"key": "pubmed", "display": "PubMed/MEDLINE", "url": "https://pubmed.ncbi.nlm.nih.gov/"}] if args.include_pubmed else []),
            *PUBLISHERS,
            *([{"key": "arxiv", "display": "arXiv", "source_type": "preprint", "url": "https://arxiv.org/"}] if args.include_arxiv else []),
        ],
        "papers": papers,
        "filtered_query_only_count": filtered_count,
        "min_relevance_score": min_score,
        "errors": errors,
        "notes": [
            "AI interpretation must be based only on title, abstract, MeSH terms, keywords, and metadata in this JSON.",
            "Do not infer research goals, methods, or results when abstract is missing.",
            "PubMed/MEDLINE is the primary source; MeSH terms confirm indexer-verified topic relevance.",
            "Papers marked is_review_or_meta:true are systematic reviews or meta-analyses — higher evidence level.",
        ],
    }
    write_json(output_path, payload)
    print(str(output_path.resolve()))
    return output_path


def mark_success(args: argparse.Namespace) -> None:
    state_file = Path(args.state_file)
    data_file = Path(args.data_file)
    state = read_json(state_file, {})
    payload = read_json(data_file, {})
    seen = {normalize_doi(doi) for doi in state.get("seen_dois", []) if normalize_doi(doi)}
    seen_items = {str(item) for item in state.get("seen_items", []) if item}
    for paper in payload.get("papers", []):
        doi = normalize_doi(paper.get("doi"))
        if doi:
            seen.add(doi)
            seen_items.add(f"doi:{doi}")
        pmid = clean_text(paper.get("pmid"))
        if pmid:
            seen_items.add(f"pmid:{pmid}")
        state_key = clean_text(paper.get("state_key"))
        if state_key:
            seen_items.add(state_key)
    state.update(
        {
            "last_success_utc": payload.get("window_until_utc") or utc_now().isoformat(),
            "last_run_id": payload.get("run_id"),
            "last_data_file": str(data_file.resolve()),
            "last_digest_file": str(Path(args.digest_file).resolve()) if args.digest_file else "",
            "last_email_status": args.email_status,
            "updated_utc": utc_now().isoformat(),
            "seen_dois": sorted(seen)[-2000:],
            "seen_items": sorted(seen_items)[-3000:],
        }
    )
    write_json(state_file, state)
    print(str(state_file.resolve()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch daily nursing literature digest candidates.")
    parser.add_argument("--config", help="Path to nursing-literature-digest.config.json.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="Fetch candidate papers and write JSON.")
    fetch.add_argument("--output-dir")
    fetch.add_argument("--state-file")
    fetch.add_argument("--lookback-days", type=int)
    fetch.add_argument("--from-date", help="UTC ISO timestamp or date for forced start.")
    fetch.add_argument("--until-date", help="UTC ISO timestamp or date for forced end.")
    fetch.add_argument("--rows", type=int, help="Crossref rows per publisher/keyword query.")
    fetch.add_argument("--arxiv-rows", type=int, help="arXiv rows per keyword query.")
    fetch.add_argument("--pubmed-rows", type=int, help="PubMed rows per keyword group.")
    fetch.add_argument("--max-papers", type=int)
    fetch.add_argument("--min-relevance-score", type=int, help="Drop papers with relevance_score below this (default: 2).")
    fetch.add_argument("--sleep", type=float)
    fetch.add_argument("--include-arxiv", dest="include_arxiv", action="store_true", default=None)
    fetch.add_argument("--no-arxiv", dest="include_arxiv", action="store_false")
    fetch.add_argument("--include-pubmed", dest="include_pubmed", action="store_true", default=None)
    fetch.add_argument("--no-pubmed", dest="include_pubmed", action="store_false")
    fetch.add_argument("--include-seen", action="store_true")
    fetch.set_defaults(func=fetch_candidates)

    success = subparsers.add_parser("mark-success", help="Update state after a digest is generated.")
    success.add_argument("--state-file")
    success.add_argument("--data-file", required=True)
    success.add_argument("--digest-file", default="")
    success.add_argument("--email-status", choices=["sent", "failed", "not-configured", "skipped"], default="skipped")
    success.set_defaults(func=mark_success)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_runtime_config(args)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

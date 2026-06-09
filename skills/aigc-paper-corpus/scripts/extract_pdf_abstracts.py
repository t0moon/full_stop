#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader


logging.getLogger("pypdf").setLevel(logging.ERROR)


CHINESE_ABSTRACT_PATTERNS = (
    re.compile(r"\u6458\s*\u8981\s*[:\uff1a]?\s*(.+?)\s*\u5173\s*\u952e\s*\u8bcd\s*[:\uff1a]?", re.S),
    re.compile(r"\u5185\s*\u5bb9\s*\u6458\s*\u8981\s*[:\uff1a]?\s*(.+?)\s*\u5173\s*\u952e\s*\u8bcd\s*[:\uff1a]?", re.S),
)

ENGLISH_ABSTRACT_PATTERNS = (
    re.compile(
        r"(?is)\babstract\b\s*[:.]?\s*(.+?)(?=\b(?:keywords?|index terms)\b\s*[:.]|\b(?:1|i)\s*[.)]?\s*introduction\b|\bintroduction\b|$)"
    ),
)

CHINESE_KEYWORD_PATTERNS = (
    re.compile(
        r"\u5173\s*\u952e\s*\u8bcd\s*[:\uff1a]?\s*(.+?)(?:DOI|\u4e2d\u56fe\u5206\u7c7b\u53f7|\u5206\u7c7b\u53f7|\u6587\u732e\u6807\u8bc6\u7801|\u4f5c\u8005\u7b80\u4ecb|\u57fa\u91d1\u9879\u76ee|\u4e00\u3001|1[.\uff0e\u3001])",
        re.S,
    ),
)

ENGLISH_KEYWORD_PATTERNS = (
    re.compile(
        r"(?is)\b(?:keywords?|index terms)\b\s*[:.]?\s*(.+?)(?=\b(?:doi|introduction|received|accepted|funding)\b|$)"
    ),
)

TITLE_HINT_WORDS = (
    "ai",
    "aigc",
    "advertising",
    "video",
    "content",
    "generated",
    "comparison",
    "evaluation",
    "study",
    "analysis",
)

META_MARKERS = (
    "doi",
    "issn",
    "journal homepage",
    "received:",
    "accepted:",
    "article info",
    "correspondence",
    "funding",
    "published online",
    "to cite this article",
    "view related articles",
    "submit your article",
    "article views",
    "open access article",
    "permits use and distribution",
    "downloaded from",
    "university of",
    "department of",
    "faculty of",
    "school of",
    "journal of",
    "www.",
    "http",
)

NOISY_KEYWORD_MARKERS = (
    "\u3010\u4f5c\u8005\u5355\u4f4d\u3011",
    "\u4f5c\u8005\u5355\u4f4d",
    "special plan",
    "\u7279\u522b\u7b56\u5212",
    "\u4f20\u5a92",
    "\u65b0\u5a92\u4f53\u7814\u7a76",
)

MANUAL_METADATA_OVERRIDES: dict[str, dict[str, str]] = {
    "1-s2.0-S0360131524001787-main.pdf": {
        "title": "Comparing human-made and AI-generated teaching videos: An experimental study on learning effects",
    },
    "Brit J Educational Tech - 2024 - Xu - From recorded to AI‐generated instructional videos  A comparison of learning.pdf": {
        "title": "From recorded to AI-generated instructional videos: A comparison of learning performance and experience",
    },
    "Content_Quality_Over_Functionality_How_Aesthetics_Authenticity_and_Creativity_Drive_Designers_Adoption_of_AI-Generated_Video_Advertising_Tools.pdf": {
        "title": "Content Quality Over Functionality: How Aesthetics, Authenticity, and Creativity Drive Designers' Adoption of AI-Generated Video Advertising Tools",
    },
    "Effect of disclosing AI-generated content on prosocial advertising evaluation.pdf": {
        "title": "Effect of disclosing AI-generated content on prosocial advertising evaluation",
    },
    "Mastersthesis_Lankinen_Elina.pdf": {
        "title": "The effect of an AI-generated advertisement on consumer attitudes",
        "author_hint": "Elina Lankinen",
    },
    "s41598-025-96508-3.pdf": {
        "title": "Comparing large Language models and human annotators in latent content analysis of sentiment, political leaning, emotional intensity and sarcasm",
    },
    "The Impact of Artificial Intelligence in Advertising_ An Experime.pdf": {
        "title": "The Impact of Artificial Intelligence in Advertising: An Experimental Evaluation of AI Video Generators",
    },
}


@dataclass
class PaperDigest:
    source_file: str
    title: str
    author_hint: str
    pages: int
    abstract: str
    keywords: list[str]


def collapse_whitespace(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[\t\r\f\v]+", " ", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s+([,.!?;:，。！？；：、】【（）])", r"\1", text)
    text = re.sub(r"([【（])\s+", r"\1", text)
    text = re.sub(r"\s+([】）])", r"\1", text)
    return text


def clean_field(value: str) -> str:
    value = collapse_whitespace(value)
    value = value.strip("[]【】()（）")
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip()


def extract_field(patterns: tuple[re.Pattern[str], ...], text: str) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return clean_field(match.group(1))
    return ""


def split_keywords(raw: str) -> list[str]:
    if not raw:
        return []
    raw = clean_field(raw)
    for marker in NOISY_KEYWORD_MARKERS:
        low_raw = raw.lower()
        low_marker = marker.lower()
        if low_marker in low_raw:
            raw = raw[: low_raw.index(low_marker)].strip()
            break
    parts = re.split(r"[；;，,]\s*", raw)
    cleaned: list[str] = []
    for part in parts:
        candidate = clean_field(part).strip("[]【】()（）")
        if not candidate:
            continue
        candidate = re.split(r"[。！？.!?]", candidate, maxsplit=1)[0].strip()
        if not candidate:
            continue
        if len(candidate) > 40:
            continue
        cleaned.append(candidate)
    if cleaned:
        return cleaned
    return [raw] if len(raw) <= 80 else []


def read_preview_text(pdf_path: Path, page_limit: int) -> tuple[str, str, int]:
    reader = PdfReader(str(pdf_path))
    pages = len(reader.pages)
    raw_preview = []
    for page in reader.pages[: min(page_limit, pages)]:
        raw_preview.append(page.extract_text() or "")
    raw_text = "\n".join(raw_preview)
    return raw_text, collapse_whitespace(raw_text), pages


def sanitize_filename_title(stem: str) -> str:
    title = stem.replace("_", " ").replace("  ", " ").strip()
    title = re.sub(r"\s+-\s+", " - ", title)
    return title


def is_meta_line(line: str) -> bool:
    low = line.lower()
    if any(marker in low for marker in META_MARKERS):
        return True
    if re.fullmatch(r"[\d\s/|:().,\-]+", line):
        return True
    return False


def is_author_or_affiliation_line(line: str) -> bool:
    low = line.lower()
    if any(token in low for token in ("department of", "faculty of", "school of", "university", "correspondence", "funding")):
        return True
    if re.search(r"\bet al\.?\b", low):
        return True
    if "*" in line and re.search(r"[A-Z]", line):
        return True
    capitalized_words = re.findall(r"[A-Z][A-Za-z'`\-.]+", line)
    if 2 <= len(capitalized_words) <= 12 and ("," in line or "|" in line or " & " in line):
        return True
    return False


def is_likely_title_line(line: str) -> bool:
    if len(line) < 12 or len(line) > 180:
        return False
    if is_meta_line(line) or is_author_or_affiliation_line(line):
        return False
    if re.search(r"^(abstract|keywords?|index terms)\b", line, re.I):
        return False
    if not re.match(r"^[A-Z\u4e00-\u9fff]", line):
        return False
    alpha_words = re.findall(r"[A-Za-z][A-Za-z'`\-.]+", line)
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", line))
    return has_cjk or len(alpha_words) >= 3


def extract_title_from_text(raw_text: str) -> str:
    lines = [clean_field(line) for line in raw_text.splitlines()]
    lines = [line for line in lines if line]
    scan_limit = min(len(lines), 40)
    for index, line in enumerate(lines[:40]):
        if re.match(r"^(abstract|摘要)\b", line, re.I):
            scan_limit = max(1, index)
            break
    candidates: list[tuple[int, str]] = []
    for index, line in enumerate(lines[:scan_limit]):
        if not is_likely_title_line(line):
            continue
        parts = [line]
        for next_line in lines[index + 1 : min(index + 4, scan_limit)]:
            if is_meta_line(next_line) or is_author_or_affiliation_line(next_line):
                break
            if not is_likely_title_line(next_line):
                break
            if len(" ".join(parts + [next_line])) > 220:
                break
            parts.append(next_line)
        candidate = " ".join(parts).strip()
        if not candidate:
            continue
        score = len(candidate)
        score += max(0, 50 - index * 3)
        if ":" in candidate:
            score += 10
        low = candidate.lower()
        if any(word in low for word in TITLE_HINT_WORDS):
            score += 20
        if candidate.endswith("."):
            score -= 20
        if re.match(r"(?i)(in the|this study|the findings|with advancements|our analysis|given these findings|the results)", candidate):
            score -= 40
        candidates.append((score, candidate))
    if not candidates:
        return ""
    return max(candidates, key=lambda item: item[0])[1]


def title_and_author_from_filename(pdf_path: Path, raw_text: str) -> tuple[str, str]:
    stem = pdf_path.stem
    if "_" in stem and re.search(r"[\u4e00-\u9fff]", stem):
        title, author = stem.rsplit("_", 1)
        return sanitize_filename_title(title), author.strip()

    extracted_title = extract_title_from_text(raw_text)
    if extracted_title:
        return extracted_title, ""

    return sanitize_filename_title(stem), ""


def extract_abstract(normalized_text: str) -> str:
    abstract = extract_field(CHINESE_ABSTRACT_PATTERNS, normalized_text)
    if abstract:
        return abstract
    abstract = extract_field(ENGLISH_ABSTRACT_PATTERNS, normalized_text)
    if abstract:
        return abstract
    fallback = re.search(r"(?is)(.+?)(?=\bkeywords\b)", normalized_text)
    if fallback:
        candidate = clean_field(fallback.group(1))
        sentences = candidate.split(". ")
        if len(sentences) >= 3 and "abstract" not in candidate.lower()[:30]:
            return candidate
    return ""


def extract_keywords(normalized_text: str) -> list[str]:
    raw = extract_field(CHINESE_KEYWORD_PATTERNS, normalized_text)
    if raw:
        return split_keywords(raw)
    raw = extract_field(ENGLISH_KEYWORD_PATTERNS, normalized_text)
    if raw:
        return split_keywords(raw)
    return []


def digest_pdf(pdf_path: Path, page_limit: int) -> PaperDigest:
    raw_text, normalized_text, pages = read_preview_text(pdf_path, page_limit)
    title, author_hint = title_and_author_from_filename(pdf_path, raw_text)
    abstract = extract_abstract(normalized_text)
    keywords = extract_keywords(normalized_text)
    override = MANUAL_METADATA_OVERRIDES.get(pdf_path.name, {})
    if override.get("title"):
        title = override["title"]
    if override.get("author_hint"):
        author_hint = override["author_hint"]
    return PaperDigest(
        source_file=pdf_path.name,
        title=title,
        author_hint=author_hint,
        pages=pages,
        abstract=abstract,
        keywords=keywords,
    )


def format_markdown(digests: list[PaperDigest]) -> str:
    lines = [
        "# AIGC Paper Abstracts",
        "",
        f"Total papers: {len(digests)}",
        "",
        "This file is generated from the PDFs in the project root. Re-run `scripts/extract_pdf_abstracts.py` after adding or replacing papers.",
        "",
    ]
    for index, digest in enumerate(digests, start=1):
        lines.extend(
            [
                f"## {index}. {digest.title}",
                "",
                f"- Source file: `{digest.source_file}`",
                f"- Author hint: `{digest.author_hint}`" if digest.author_hint else "- Author hint: `unknown`",
                f"- Pages: `{digest.pages}`",
                f"- Keywords: `{', '.join(digest.keywords) if digest.keywords else 'not extracted'}`",
                "",
                "### Abstract",
                "",
                digest.abstract or "Abstract extraction failed. Inspect the PDF manually.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract abstracts and keywords from project PDFs.")
    parser.add_argument("--pdf-dir", type=Path, required=True, help="Directory containing the PDF corpus.")
    parser.add_argument("--markdown-out", type=Path, help="Optional Markdown output path.")
    parser.add_argument("--json-out", type=Path, help="Optional JSON output path.")
    parser.add_argument("--page-limit", type=int, default=8, help="How many leading pages to inspect per PDF.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_dir = args.pdf_dir.resolve()
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        raise SystemExit(f"No PDF files found in {pdf_dir}")

    digests = [digest_pdf(path, args.page_limit) for path in pdf_paths]

    if args.markdown_out:
        args.markdown_out.write_text(format_markdown(digests), encoding="utf-8")

    if args.json_out:
        args.json_out.write_text(
            json.dumps([asdict(digest) for digest in digests], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if not args.markdown_out and not args.json_out:
        print(json.dumps([asdict(digest) for digest in digests], ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import hashlib
import os
import re
import subprocess
import sys
import textwrap
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET
import difflib


W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Version:
    source: str
    label: str
    sort_key: datetime
    name: str
    size: int
    paragraphs: list[str]
    path: str | None = None
    commit: str | None = None
    note: str | None = None
    sha1: str = field(init=False)

    def __post_init__(self) -> None:
        normalized = "\n".join(self.paragraphs).encode("utf-8")
        self.sha1 = hashlib.sha1(normalized).hexdigest()


def run_git(repo_root: Path, args: list[str], *, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def parse_iso_to_local_naive(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str).astimezone().replace(tzinfo=None)


def extract_paragraphs_from_docx_bytes(docx_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(io_from_bytes(docx_bytes)) as zf:
        xml_bytes = zf.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for para in root.iter(f"{W_NS}p"):
        parts: list[str] = []
        for node in para.iter():
            if node.tag == f"{W_NS}t":
                parts.append(node.text or "")
            elif node.tag == f"{W_NS}tab":
                parts.append("\t")
            elif node.tag in {f"{W_NS}br", f"{W_NS}cr"}:
                parts.append("\n")
        text = normalize_text("".join(parts))
        if text:
            paragraphs.append(text)
    return paragraphs


def io_from_bytes(data: bytes):
    from io import BytesIO

    return BytesIO(data)


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    lines = [line.strip() for line in text.splitlines()]
    text = " ".join(line for line in lines if line)
    return " ".join(text.split())


def safe_first(items: Iterable[str], default: str = "") -> str:
    for item in items:
        if item:
            return item
    return default


def load_loose_docx_versions(workdir: Path) -> list[Version]:
    versions: list[Version] = []
    for path in sorted(workdir.glob("*.docx"), key=lambda p: p.stat().st_mtime):
        if path.name.startswith("~$"):
            continue
        docx_bytes = path.read_bytes()
        try:
            paragraphs = extract_paragraphs_from_docx_bytes(docx_bytes)
        except Exception as exc:
            paragraphs = [f"[解析失败] {exc}"]
        stat = path.stat()
        versions.append(
            Version(
                source="workspace",
                label=f"Workspace file: {path.name}",
                sort_key=datetime.fromtimestamp(stat.st_mtime),
                name=path.name,
                size=stat.st_size,
                paragraphs=paragraphs,
                path=str(path),
            )
        )
    return versions


def parse_git_docx_history(repo_root: Path, relative_dir: Path) -> list[Version]:
    history = run_git(
        repo_root,
        ["-c", "core.quotepath=false", "log", "--name-status", "--format=%H|%ad|%s", "--date=iso", "--", str(relative_dir)],
    )
    versions: list[Version] = []
    current_commit: tuple[str, datetime, str] | None = None

    for raw_line in history.splitlines():
        line = raw_line.rstrip("\n")
        if not line:
            continue
        if "|" in line and len(line.split("|", 2)) == 3 and all(line[:7]):
            commit_hash, date_str, subject = line.split("|", 2)
            current_commit = (commit_hash, parse_iso_to_local_naive(date_str), subject)
            continue
        if current_commit is None:
            continue
        status, *rest = line.split("\t")
        tracked_path: str | None = None
        if status.startswith("R") and len(rest) == 2:
            tracked_path = rest[1]
        elif status and rest:
            tracked_path = rest[0]
        if not tracked_path or not tracked_path.lower().endswith(".docx"):
            continue
        blob = subprocess.run(
            ["git", "show", f"{current_commit[0]}:{tracked_path}"],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        if blob.returncode != 0:
            continue
        try:
            paragraphs = extract_paragraphs_from_docx_bytes(blob.stdout)
        except Exception as exc:
            paragraphs = [f"[解析失败] {exc}"]
        versions.append(
            Version(
                source="git",
                label=f"Git commit {current_commit[0][:7]}: {current_commit[2]}",
                sort_key=current_commit[1],
                name=Path(tracked_path).name,
                size=len(blob.stdout),
                paragraphs=paragraphs,
                path=tracked_path,
                commit=current_commit[0],
            )
        )
    versions.sort(key=lambda item: item.sort_key)
    return versions


def clip(text: str, width: int = 120) -> str:
    return textwrap.shorten(text, width=width, placeholder="...")


def informative_score(text: str) -> int:
    cleaned = re.sub(r"[\W_0-9]+", "", text, flags=re.UNICODE)
    return len(cleaned)


def pick_informative(paragraphs: list[str], limit: int = 2) -> list[str]:
    scored = sorted(
        ((informative_score(paragraph), index, paragraph) for index, paragraph in enumerate(paragraphs)),
        key=lambda item: (-item[0], item[1]),
    )
    picked: list[str] = []
    for score, _, paragraph in scored:
        if score == 0:
            continue
        clipped = clip(paragraph, 80)
        if clipped and clipped != "...":
            picked.append(clipped)
        if len(picked) >= limit:
            break
    if picked:
        return picked
    fallback = [clip(paragraph, 80) for paragraph in paragraphs[:limit] if paragraph]
    return [item for item in fallback if item] or ["[空]"]


def summarize_diff(previous: Version, current: Version) -> dict[str, object]:
    matcher = difflib.SequenceMatcher(a=previous.paragraphs, b=current.paragraphs, autojunk=False)
    changes: list[str] = []
    added = removed = replaced = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            added += j2 - j1
            for paragraph in current.paragraphs[j1:j2]:
                changes.append(f"新增: {clip(paragraph)}")
        elif tag == "delete":
            removed += i2 - i1
            for paragraph in previous.paragraphs[i1:i2]:
                changes.append(f"删除: {clip(paragraph)}")
        elif tag == "replace":
            replaced += max(i2 - i1, j2 - j1)
            old_chunk = " / ".join(pick_informative(previous.paragraphs[i1:i2])) or "[空]"
            new_chunk = " / ".join(pick_informative(current.paragraphs[j1:j2])) or "[空]"
            changes.append(f"改写: {old_chunk} -> {new_chunk}")

    return {
        "added": added,
        "removed": removed,
        "replaced": replaced,
        "changed_examples": changes[:12],
        "unchanged_ratio": matcher.ratio(),
    }


def build_timeline(workdir: Path, repo_root: Path) -> tuple[list[Version], list[list[Version]]]:
    relative_dir = workdir.relative_to(repo_root)
    git_versions = parse_git_docx_history(repo_root, relative_dir)
    loose_versions = load_loose_docx_versions(workdir)
    versions = sorted([*git_versions, *loose_versions], key=lambda item: item.sort_key)

    groups: dict[str, list[Version]] = {}
    for version in versions:
        groups.setdefault(version.sha1, []).append(version)

    for same_versions in groups.values():
        if len(same_versions) > 1:
            names = ", ".join(version.name for version in same_versions)
            for version in same_versions:
                version.note = f"与以下版本正文一致: {names}"

    duplicate_groups = [group for group in groups.values() if len(group) > 1]
    return versions, duplicate_groups


def render_report(workdir: Path, repo_root: Path) -> str:
    versions, duplicate_groups = build_timeline(workdir, repo_root)
    lines: list[str] = []
    lines.append("# DOCX 版本差异报告")
    lines.append("")
    lines.append(f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- 工作目录: `{workdir}`")
    lines.append(f"- Git 仓库根目录: `{repo_root}`")
    lines.append("")

    lines.append("## 时间线")
    lines.append("")
    for index, version in enumerate(versions, start=1):
        first_para = clip(safe_first(version.paragraphs, "[空文档]"), 90)
        lines.append(
            f"{index}. `{version.sort_key.isoformat(sep=' ', timespec='seconds')}` | `{version.source}` | "
            f"`{version.name}` | {version.size} bytes | 段落数 {len(version.paragraphs)}"
        )
        lines.append(f"   标识: {version.label}")
        lines.append(f"   首段: {first_para}")
        if version.commit:
            lines.append(f"   提交: `{version.commit}`")
        if version.note:
            lines.append(f"   备注: {version.note}")
        if version.path:
            lines.append(f"   路径: `{version.path}`")
        lines.append("")

    if duplicate_groups:
        lines.append("## 正文完全一致的版本")
        lines.append("")
        for group in duplicate_groups:
            lines.append(f"- 相同正文哈希 `{group[0].sha1[:10]}`:")
            for version in group:
                lines.append(
                    f"  - `{version.sort_key.isoformat(sep=' ', timespec='seconds')}` | `{version.source}` | `{version.name}`"
                )
        lines.append("")

    lines.append("## 相邻版本差异")
    lines.append("")
    for previous, current in zip(versions, versions[1:]):
        diff = summarize_diff(previous, current)
        lines.append(f"### `{previous.name}` -> `{current.name}`")
        lines.append("")
        lines.append(
            f"- 时间: `{previous.sort_key.isoformat(sep=' ', timespec='seconds')}` -> "
            f"`{current.sort_key.isoformat(sep=' ', timespec='seconds')}`"
        )
        lines.append(
            f"- 变化概况: 新增 {diff['added']} 段, 删除 {diff['removed']} 段, 改写 {diff['replaced']} 段, "
            f"相似度 {diff['unchanged_ratio']:.3f}"
        )
        if previous.sha1 == current.sha1:
            lines.append("- 结论: 正文完全一致，只是文件名、时间或存储副本不同。")
        elif diff["changed_examples"]:
            lines.append("- 典型变化:")
            for item in diff["changed_examples"]:
                lines.append(f"  - {item}")
        else:
            lines.append("- 结论: 没有抽取到显著正文差异。")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze DOCX versions in the current workspace.")
    parser.add_argument("--workdir", default=".", help="Directory that contains the DOCX files.")
    parser.add_argument(
        "--output",
        default="docx_version_diff_report.md",
        help="Markdown report path, relative to workdir when not absolute.",
    )
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    repo_root = Path(run_git(workdir, ["rev-parse", "--show-toplevel"]).strip()).resolve()
    report = render_report(workdir, repo_root)
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = workdir / output_path
    output_path.write_text(report, encoding="utf-8-sig")
    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

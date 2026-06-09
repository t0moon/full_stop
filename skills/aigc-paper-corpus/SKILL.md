---
name: aigc-paper-corpus
description: Summarize, compare, and synthesize the AIGC research PDF corpus stored in this project. Use when Codex needs to work from these local papers for literature review, theme clustering, research-gap extraction, theory framing, or paper-by-paper digest generation about AIGC in information search, publishing, reading, advertising, AI advertising video, disclosure effects, human-versus-AI content comparison, short video, audiovisual production, and intelligent communication.
---

# AIGC Paper Corpus

Use this skill to answer questions from the local PDF corpus in `C:\Users\ws\Desktop\lunwen`.

## Quick Start

1. Read [references/corpus-map.md](references/corpus-map.md) first.
2. Read [references/paper-abstracts.md](references/paper-abstracts.md) when the task needs the original abstract wording for one or more papers.
3. Read `*.pdf` files directly only when the user needs evidence beyond the abstract, such as section structure, argument detail, or quoted wording.
4. Treat theses and project papers as useful but lower-confidence sources than peer-reviewed journal articles unless the task is explicitly about recent exploratory evidence or stimulus design.

## Workflow

### Orient The Request

Decide whether the user wants:

- a quick summary of one paper
- a comparative synthesis across several papers
- a literature review or research-gap section
- a theory/governance/risk framework derived from the corpus
- an AI advertising video / disclosure / human-versus-AI comparison review

Prefer the smallest amount of corpus material needed for the request.

### Build The Answer From Layers

Use the sources in this order:

1. [references/corpus-map.md](references/corpus-map.md) for themes, methods, and recurring risk frames
2. [references/paper-abstracts.md](references/paper-abstracts.md) or [references/paper-abstracts.json](references/paper-abstracts.json) for paper-level abstract details
3. The original PDF when abstract-only evidence is insufficient

State clearly when a claim comes from abstract-level reading rather than full-text reading.

### Synthesize Carefully

When writing from this corpus:

- distinguish empirical papers from conceptual, normative, or review papers
- identify each paper's object of study, method, and core claim
- separate efficiency claims from governance or ethics claims
- avoid flattening all papers into the same "AIGC opportunity plus risk" template
- surface disagreements, especially around trust, alienation, platform power, and human-machine collaboration

### Refresh The Corpus Index

If PDFs are added, removed, or replaced, regenerate the abstract index:

```powershell
python skills\aigc-paper-corpus\scripts\extract_pdf_abstracts.py --pdf-dir . --markdown-out skills\aigc-paper-corpus\references\paper-abstracts.md --json-out skills\aigc-paper-corpus\references\paper-abstracts.json
```

Run the command from the project root.

## Output Patterns

### For Single-Paper Requests

Report:

- research problem
- method or perspective
- main finding or argument
- how the paper is useful in the user's context

### For Cross-Paper Requests

Organize by one strong axis:

- theme
- method
- theory
- governance problem
- media form

Do not list papers mechanically unless the user explicitly wants an inventory.

### For Literature Reviews

Default structure:

1. define the subfield
2. group papers into 3-5 clusters
3. compare methods and findings inside each cluster
4. identify what is still weak, missing, or under-tested

Prefer research gaps that follow from the corpus, such as:

- limited longitudinal evidence
- weak cross-platform comparison
- overreliance on normative discussion without field data
- insufficient integration between user cognition studies and governance studies

## Resources

### references/

- [references/corpus-map.md](references/corpus-map.md): curated overview, theme clusters, method map, reusable angles
- [references/paper-abstracts.md](references/paper-abstracts.md): generated abstract index for all PDFs
- [references/paper-abstracts.json](references/paper-abstracts.json): machine-readable version of the same index

### scripts/

- [scripts/extract_pdf_abstracts.py](scripts/extract_pdf_abstracts.py): regenerate abstract and keyword indexes from the local PDF corpus

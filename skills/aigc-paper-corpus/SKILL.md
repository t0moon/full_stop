---
name: aigc-paper-corpus
description: Summarize, compare, and synthesize the research PDF corpus stored in this project. Use when Codex needs to work from these local sources for literature review, theme clustering, research-gap extraction, theory framing, or paper-by-paper and book-by-book digest generation about AIGC in information search, publishing, reading, advertising, brand image, positioning, concept-image management, AI advertising video, disclosure effects, human-versus-AI content comparison, short video, audiovisual production, multimodal discourse, cultural representation, national image, and intelligent communication.
---

# AIGC Research Corpus

Use this skill to answer questions from the local PDF corpus in `C:\Users\ws\Desktop\lunwen`.

## Quick Start

1. Read [references/corpus-map.md](references/corpus-map.md) first.
2. Read [references/paper-abstracts.md](references/paper-abstracts.md) when the task needs the original abstract wording or source-level index entry for one or more items.
3. Read `*.pdf` files directly when the user needs evidence beyond the abstract, such as section structure, argument detail, quoted wording, or theory exposition from a book.
4. Treat theses and project papers as useful but lower-confidence sources than peer-reviewed journal articles unless the task is explicitly about recent exploratory evidence or stimulus design.
5. Treat books and monographs as theory and method anchors rather than substitutes for empirical evidence.

## Workflow

### Orient The Request

Decide whether the user wants:

- a quick summary of one source
- a comparative synthesis across several sources
- a literature review or research-gap section
- a theory/governance/risk framework derived from the corpus
- a brand image / positioning / concept-image theory frame
- an AI advertising video / disclosure / human-versus-AI comparison review
- a short-video / multimodal discourse / cultural-representation review
- a theory/method grounding request for multimodal discourse analysis

Prefer the smallest amount of corpus material needed for the request.

### Build The Answer From Layers

Use the sources in this order:

1. [references/corpus-map.md](references/corpus-map.md) for themes, methods, and recurring risk frames
2. [references/paper-abstracts.md](references/paper-abstracts.md) or [references/paper-abstracts.json](references/paper-abstracts.json) for source-level abstract details
3. The original PDF when abstract-only evidence is insufficient or when the source is a book with weak extractable text

State clearly when a claim comes from abstract-level reading rather than full-text reading.

### Synthesize Carefully

When writing from this corpus:

- distinguish empirical papers from conceptual, normative, or review papers
- distinguish articles, theses, and books by their evidentiary role
- identify each paper's object of study, method, and core claim
- distinguish AIGC production studies from non-AIGC multimodal discourse studies
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

### For Single-Source Requests

Report:

- research problem
- method, perspective, or theory contribution
- main finding or argument
- how the source is useful in the user's context

### For Cross-Paper Requests

Organize by one strong axis:

- theme
- method
- theory
- governance problem
- media form

Do not list sources mechanically unless the user explicitly wants an inventory.

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
- weak integration between AIGC production research and multimodal discourse analysis
- limited explicit linkage between multimodal discourse theory books and applied case studies

## Resources

### references/

- [references/corpus-map.md](references/corpus-map.md): curated overview, theme clusters, method map, reusable angles
- [references/paper-abstracts.md](references/paper-abstracts.md): generated abstract index for all PDFs
- [references/paper-abstracts.json](references/paper-abstracts.json): machine-readable version of the same index

### scripts/

- [scripts/extract_pdf_abstracts.py](scripts/extract_pdf_abstracts.py): regenerate abstract and keyword indexes from the local PDF corpus

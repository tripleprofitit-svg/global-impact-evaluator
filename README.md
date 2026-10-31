# Global Impact Evaluator — MVP v0.1

Evidence-first prototype for comparing international organizations. No external AI API, automated research, or real-world organization rankings are included yet.

## Run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The application creates `impact.db` on first launch. Add an organization, record source evidence, and create an assessment with six justified dimension scores. The Rankings tab displays a provisional score only when all dimensions exist, at least two sources are linked, at least one is independent, and average evidence quality is >= 3/5. These thresholds are *prototype rules*, not validated scientific standards.

## Data model

- `organizations`: identity and sector
- `projects`: intervention metadata (schema ready; UI later)
- `indicators`: project outcome metrics (schema ready; UI later)
- `evidence`: sources, findings, independence, quality
- `assessments`: organization/year/methodology version
- `scores`: dimension values and rationales
- `assessment_evidence`: assessment-source linkage

## Limitations and next steps

1. No user authentication, permissions, backups, or audit log. Do not deploy publicly or enter sensitive data as-is.
2. SQLite is suitable for local single-user prototyping; migrate to PostgreSQL for production.
3. No automated extraction or source verification; users manually enter evidence and ratings.
4. Cross-sector numerical comparisons are exploratory; causal attribution and uncertainty intervals require stronger evaluation designs.
5. Add FastAPI, background workers, source connectors (IATI and others subject to access terms), duplicate detection, source snapshots, rubric calibration, and independent reviewer approval before production.
6. Do not treat scores as objective measures of global impact.

## v0.2: Research discovery and review

The Research agent section lets an analyst select an organization, discover public
source *candidates* using Wikipedia search and Crossref publication metadata, and
accept/reject each candidate. Network access is required when searching. Search
results are NOT verified evidence; the reviewer must open the original document,
verify it concerns the correct organization, record a specific finding with
limitations, and choose evidence quality and independence. Only accepted items
enter the existing evidence table. The agent never invents an impact score.

This is a deliberately conservative first automation stage, **not** full autonomous
impact assessment. Discovery may return false positives, miss sources, or fail due
to network/API availability. No LLM API key is required. IATI ingestion, document
full-text extraction, deduplication beyond URL, audit logging, authentication,
production scheduling and robust impact attribution remain future work.

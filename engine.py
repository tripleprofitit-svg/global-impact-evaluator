import sqlite3
from pathlib import Path

DB = Path(__file__).with_name('impact.db')
WEIGHTS = {'outcomes': .30, 'efficiency': .20, 'sustainability': .15, 'reach': .15, 'local_ownership': .10, 'transparency': .10}
LABELS = {'outcomes':'Measured outcomes','efficiency':'Cost effectiveness','sustainability':'Sustainability','reach':'Reach and depth','local_ownership':'Local ownership','transparency':'Transparency'}
SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS organizations (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, sector TEXT NOT NULL, country TEXT, website TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id), name TEXT NOT NULL, country TEXT, start_year INTEGER, end_year INTEGER, budget_usd REAL);
CREATE TABLE IF NOT EXISTS indicators (id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id), name TEXT NOT NULL, unit TEXT, baseline REAL, observed REAL, counterfactual REAL, observation_year INTEGER);
CREATE TABLE IF NOT EXISTS evidence (id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id), project_id INTEGER REFERENCES projects(id), title TEXT NOT NULL, url TEXT, publication_year INTEGER, source_type TEXT NOT NULL, independence TEXT NOT NULL, finding TEXT NOT NULL, quality INTEGER NOT NULL CHECK(quality BETWEEN 1 AND 5), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS assessments (id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id), assessment_year INTEGER NOT NULL, methodology_version TEXT NOT NULL DEFAULT '0.1', status TEXT NOT NULL DEFAULT 'draft', notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS scores (assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE, dimension TEXT NOT NULL, score REAL NOT NULL CHECK(score BETWEEN 0 AND 100), rationale TEXT NOT NULL, PRIMARY KEY(assessment_id, dimension));
CREATE TABLE IF NOT EXISTS assessment_evidence (assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE, evidence_id INTEGER NOT NULL REFERENCES evidence(id), PRIMARY KEY(assessment_id,evidence_id));
'''
def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def init_db():
    with connect() as c: c.executescript(SCHEMA)

def evaluate(scores, evidence_count, independent_count, evidence_quality):
    missing = [key for key in WEIGHTS if key not in scores]
    if missing: return None, 'Incomplete dimensions: ' + ', '.join(missing)
    if evidence_count < 2 or independent_count < 1 or evidence_quality < 3:
        return None, 'Insufficient evidence (requires 2 sources, 1 independent, mean quality >= 3/5)'
    return round(sum(float(scores[k]) * w for k,w in WEIGHTS.items()), 1), 'Eligible for provisional comparison'

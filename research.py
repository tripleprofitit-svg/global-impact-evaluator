"""Conservative public-source discovery. Results are leads, never verified impact findings."""
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from engine import connect

TIMEOUT = 12
HEADERS = {'User-Agent': 'GlobalImpactEvaluatorMVP/0.2 (research prototype; public metadata)', 'Accept': 'application/json'}

SCHEMA = '''
CREATE TABLE IF NOT EXISTS research_runs (
 id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id),
 created_at TEXT NOT NULL, status TEXT NOT NULL, error TEXT,
 sources_found INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS research_candidates (
 id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES research_runs(id),
 organization_id INTEGER NOT NULL REFERENCES organizations(id),
 title TEXT NOT NULL, url TEXT NOT NULL, publication_year INTEGER,
 provider TEXT NOT NULL, snippet TEXT NOT NULL DEFAULT '',
 review_status TEXT NOT NULL DEFAULT 'pending',
 UNIQUE(organization_id,url));
'''

def init_research_db():
    with connect() as db:
        db.executescript(SCHEMA)

def clean_text(value):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', str(value or ''))).strip()[:900]

def safe_url(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password

def wikipedia(name):
    # Search metadata only; no assumption that a same-named article represents the organization.
    response = requests.get('https://en.wikipedia.org/w/api.php', params={
        'action':'query','list':'search','srsearch':f'"{name}" organization',
        'srlimit':5,'format':'json'}, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    for item in response.json().get('query',{}).get('search',[]):
        yield {'title':clean_text(item.get('title')), 'url':'https://en.wikipedia.org/?curid='+str(item['pageid']),
               'year':None, 'provider':'Wikipedia search', 'snippet':clean_text(item.get('snippet'))}

def crossref(name):
    response = requests.get('https://api.crossref.org/works', params={
        'query':f'"{name}" impact evaluation', 'rows':8,
        'select':'DOI,title,published,abstract,URL'}, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    for item in response.json().get('message',{}).get('items',[]):
        title = clean_text((item.get('title') or [''])[0])
        if not title: continue
        year = (item.get('published',{}).get('date-parts') or [[None]])[0][0]
        yield {'title':title, 'url':item.get('URL',''), 'year':year,
               'provider':'Crossref discovery', 'snippet':clean_text(item.get('abstract',''))}

def discover(organization_id, name):
    """Store candidate source links for human screening; never assign impact scores."""
    init_research_db()
    with connect() as db:
        run_id=db.execute('INSERT INTO research_runs(organization_id,created_at,status) VALUES(?,?,?)',
            (organization_id,datetime.now(timezone.utc).isoformat(),'running')).lastrowid
    errors=[]; inserted=0
    for provider in (wikipedia,crossref):
        try:
            for result in provider(name):
                if not safe_url(result['url']): continue
                with connect() as db:
                    cur=db.execute('''INSERT OR IGNORE INTO research_candidates
                    (run_id,organization_id,title,url,publication_year,provider,snippet)
                    VALUES(?,?,?,?,?,?,?)''',(run_id,organization_id,result['title'],result['url'],
                        result['year'],result['provider'],result['snippet']))
                    inserted+=cur.rowcount
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            errors.append(f'{provider.__name__}: {exc}')
    status='complete' if not errors else ('partial' if inserted else 'failed')
    with connect() as db:
        db.execute('UPDATE research_runs SET status=?,error=?,sources_found=? WHERE id=?',
                   (status,'; '.join(errors)[:1500],inserted,run_id))
    return {'run_id':run_id,'status':status,'new_candidates':inserted,'errors':errors}

def review_candidate(candidate_id, action, finding='', quality=1, independence='Unknown'):
    if action not in ('accept','reject'): raise ValueError('Invalid action')
    with connect() as db:
        candidate=db.execute('SELECT * FROM research_candidates WHERE id=?',(candidate_id,)).fetchone()
        if not candidate or candidate['review_status']!='pending': raise ValueError('Candidate not pending')
        if action=='accept':
            if not finding.strip(): raise ValueError('Reviewer must record an actual finding and limitations')
            if quality not in range(1,6): raise ValueError('Quality must be 1-5')
            db.execute('''INSERT INTO evidence(organization_id,title,url,publication_year,source_type,independence,quality,finding)
                          VALUES(?,?,?,?,?,?,?,?)''',
                (candidate['organization_id'],candidate['title'],candidate['url'],candidate['publication_year'],
                 'Other',independence,quality,finding.strip()))
        db.execute('UPDATE research_candidates SET review_status=? WHERE id=?',
                   ('accepted' if action=='accept' else 'rejected',candidate_id))

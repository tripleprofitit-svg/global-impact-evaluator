import streamlit as st
import pandas as pd
from engine import connect, init_db, evaluate, WEIGHTS, LABELS

st.set_page_config(page_title='Global Impact Evaluator', layout='wide')
init_db()
st.title('Global Impact Evaluator')
st.caption('Evidence-first organization comparisons · MVP 0.1 · Scores are analyst assessments, not causal impact estimates')

def query(sql, params=()):
    with connect() as c: return pd.read_sql_query(sql, c, params=params)

orgs = query('SELECT * FROM organizations ORDER BY name')
tab1,tab2,tab3,tab4 = st.tabs(['Rankings','Organizations','Evidence','Assessments'])
with tab1:
    rows=[]
    assessments=query('SELECT a.*, o.name, o.sector FROM assessments a JOIN organizations o ON o.id=a.organization_id ORDER BY a.id DESC')
    for _,a in assessments.iterrows():
        scores_df=query('SELECT dimension,score FROM scores WHERE assessment_id=?',(int(a.id),))
        scores=dict(zip(scores_df.dimension,scores_df.score))
        ev=query('SELECT e.quality,e.independence FROM evidence e JOIN assessment_evidence ae ON e.id=ae.evidence_id WHERE ae.assessment_id=?',(int(a.id),))
        value,reason=evaluate(scores,len(ev),int((ev.independence=='Independent').sum()) if len(ev) else 0,float(ev.quality.mean()) if len(ev) else 0)
        rows.append({'Organization':a['name'],'Sector':a['sector'],'Year':int(a.assessment_year),'Score':value,'Status':reason,'Assessment ID':int(a.id)})
    if rows:
        ranking=pd.DataFrame(rows)
        sector=st.selectbox('Sector', ['All']+sorted(ranking.Sector.unique().tolist()))
        if sector!='All': ranking=ranking[ranking.Sector==sector]
        st.dataframe(ranking.sort_values('Score',ascending=False,na_position='last'),hide_index=True,use_container_width=True)
        st.info('Cross-sector scores are exploratory only. Compare within sectors and review source evidence before drawing conclusions.')
    else: st.info('No assessments yet. Add organizations, evidence, and an assessment.')
with tab2:
    st.dataframe(orgs,hide_index=True,use_container_width=True)
    with st.form('new_org'):
        name=st.text_input('Organization name')
        sector=st.selectbox('Sector', ['Health','Education','Environment','Agriculture','Humanitarian','Economic development','Human rights','Other'])
        country=st.text_input('Headquarters country')
        website=st.text_input('Website')
        if st.form_submit_button('Add organization'):
            if not name.strip(): st.error('Name required')
            else:
                try:
                    with connect() as c: c.execute('INSERT INTO organizations(name,sector,country,website) VALUES(?,?,?,?)',(name.strip(),sector,country,website))
                    st.success('Added'); st.rerun()
                except Exception as e: st.error(str(e))
with tab3:
    if orgs.empty: st.info('Add an organization first.')
    else:
        selected=st.selectbox('Organization',orgs.name.tolist(),key='ev_org')
        oid=int(orgs.loc[orgs.name==selected,'id'].iloc[0])
        st.dataframe(query('SELECT id,title,url,publication_year,source_type,independence,quality,finding FROM evidence WHERE organization_id=?',(oid,)),hide_index=True,use_container_width=True)
        with st.form('new_evidence'):
            title=st.text_input('Source title'); url=st.text_input('Source URL')
            year=st.number_input('Publication year',min_value=1950,max_value=2100,value=2026)
            source_type=st.selectbox('Source type',['Evaluation','Academic study','Annual report','Administrative data','Other'])
            independence=st.selectbox('Independence',['Independent','Organization-produced','Unknown'])
            quality=st.slider('Evidence quality (1–5)',1,5,3)
            finding=st.text_area('Specific finding and limitations')
            if st.form_submit_button('Save evidence'):
                if not title.strip() or not finding.strip(): st.error('Title and finding required')
                else:
                    with connect() as c: c.execute('INSERT INTO evidence(organization_id,title,url,publication_year,source_type,independence,quality,finding) VALUES(?,?,?,?,?,?,?,?)',(oid,title,url,int(year),source_type,independence,int(quality),finding))
                    st.success('Saved'); st.rerun()
with tab4:
    if orgs.empty: st.info('Add an organization first.')
    else:
        selected=st.selectbox('Organization',orgs.name.tolist(),key='as_org')
        oid=int(orgs.loc[orgs.name==selected,'id'].iloc[0])
        evidence=query('SELECT id,title,independence,quality FROM evidence WHERE organization_id=?',(oid,))
        with st.form('new_assessment'):
            year=st.number_input('Assessment year',min_value=2000,max_value=2100,value=2026)
            st.caption('Scores must be justified by evidence. They are analyst inputs, not automatically inferred.')
            values={}; rationales={}
            for key in WEIGHTS:
                st.markdown(f'**{LABELS[key]} ({int(WEIGHTS[key]*100)}%)**')
                values[key]=st.slider(LABELS[key]+' score',0,100,50,key='score_'+key)
                rationales[key]=st.text_input(LABELS[key]+' rationale',key='rationale_'+key)
            choices=st.multiselect('Supporting evidence IDs',evidence.id.astype(int).tolist(),format_func=lambda i: evidence.loc[evidence.id==i,'title'].iloc[0] if len(evidence) else str(i))
            notes=st.text_area('Assessment notes and limitations')
            if st.form_submit_button('Save assessment'):
                if not all(x.strip() for x in rationales.values()): st.error('Provide a rationale for every dimension')
                else:
                    with connect() as c:
                        cur=c.execute('INSERT INTO assessments(organization_id,assessment_year,notes) VALUES(?,?,?)',(oid,int(year),notes))
                        aid=cur.lastrowid
                        c.executemany('INSERT INTO scores(assessment_id,dimension,score,rationale) VALUES(?,?,?,?)',[(aid,k,values[k],rationales[k]) for k in WEIGHTS])
                        c.executemany('INSERT INTO assessment_evidence(assessment_id,evidence_id) VALUES(?,?)',[(aid,int(i)) for i in choices])
                    st.success('Assessment saved'); st.rerun()

# Automated discovery extension: results are unverified leads until reviewed.
from research import init_research_db, discover, review_candidate
init_research_db()
st.divider()
st.header('Research agent · v0.2')
st.caption('Discovers public source candidates from Wikipedia and Crossref. It does not verify impact claims or assign scores.')
if orgs.empty:
    st.info('Add an organization to run research.')
else:
    chosen=st.selectbox('Research organization',orgs.name.tolist(),key='research_org')
    chosen_id=int(orgs.loc[orgs.name==chosen,'id'].iloc[0])
    if st.button('Find public sources',key='research_run'):
        with st.spinner('Searching public metadata sources...'):
            result=discover(chosen_id,chosen)
        st.info(f"Research {result['status']}: {result['new_candidates']} new source candidates")
        for err in result['errors']: st.warning(err)
    candidates=query('SELECT id,title,url,publication_year,provider,snippet FROM research_candidates WHERE organization_id=? AND review_status=? ORDER BY id DESC',(chosen_id,'pending'))
    st.write(f'Pending review: {len(candidates)}')
    if not candidates.empty:
        candidate_id=st.selectbox('Candidate',candidates.id.astype(int).tolist(),format_func=lambda i: candidates.loc[candidates.id==i,'title'].iloc[0])
        record=candidates.loc[candidates.id==candidate_id].iloc[0]
        st.write('Source:',record['provider'])
        st.write('Link:',record['url'])
        st.write('Discovery snippet (not a verified claim):',record['snippet'])
        with st.form('candidate_review'):
            finding=st.text_area('Verified finding AND limitations (review the original source first)')
            independence=st.selectbox('Source independence',['Unknown','Independent','Organization-produced'])
            quality=st.slider('Evidence quality',1,5,1)
            action=st.radio('Decision',['accept','reject'],horizontal=True)
            if st.form_submit_button('Save review'):
                try:
                    review_candidate(int(candidate_id),action,finding,int(quality),independence)
                    st.success('Review saved'); st.rerun()
                except ValueError as exc: st.error(str(exc))

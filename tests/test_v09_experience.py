from __future__ import annotations
import datetime as dt
from living_assistant.experience import ExperienceEngine


def engine(tmp_path, **cfg):
    defaults={
        'min_inject_confidence':0.55,
        'confidence_half_life_days':30,
        'confirmed_half_life_days':365,
        'auto_promote_repeats':2,
        'episode_retention_days':7,
    }
    defaults.update(cfg)
    return ExperienceEngine(tmp_path/'experience.sqlite3', {'experience':defaults})


def recovery_trace():
    return [
        {'tool_name':'run_command','success':False,'arguments_summary':'{"command":"npm start"}','result_summary':'{"ok":false,"error":"missing script"}'},
        {'tool_name':'run_command','success':True,'arguments_summary':'{"command":"npm run dev"}','result_summary':'{"ok":true,"returncode":0}'},
    ]


def test_automatic_recovery_is_candidate_first_then_promotes_after_repeat(tmp_path):
    e=engine(tmp_path)
    first=e.learn_from_trace('Run the frontend',recovery_trace(),project='RetailEye')
    assert len(first)==1
    assert first[0]['status']=='candidate'
    assert e.context_for('Run the RetailEye frontend',project='RetailEye')==''
    second=e.learn_from_trace('Run the frontend',recovery_trace(),project='RetailEye')
    assert second[0]['status']=='active'
    assert second[0]['observation_count']==2
    assert 'npm run dev' in e.context_for('Run the RetailEye frontend',project='RetailEye')


def test_verified_postmortem_is_immediately_retrievable(tmp_path):
    e=engine(tmp_path)
    item=e.record('failure','Backend crashes after restart','Check service only','RetailEye',
                  action_taken='restart API',outcome='crashed again',root_cause='MongoDB unavailable',
                  better_action='check MongoDB before restarting',verified=True,evidence='DB connection failed then recovered')
    assert item['status']=='active' and item['verified'] is True
    ctx=e.context_for('Backend is down check database before restart',project='RetailEye')
    assert 'MongoDB' in ctx and item['id'] in ctx


def test_user_confirmation_makes_lesson_high_confidence(tmp_path):
    e=engine(tmp_path)
    item=e.record('procedure','Start frontend','Use pnpm dev',project='WebApp',better_action='pnpm dev')
    assert item['status']=='candidate'
    confirmed=e.confirm(item['id'],'I verified this is our current command')
    exp=confirmed['experience']
    assert exp['user_confirmed'] is True and exp['status']=='active'
    assert exp['confidence'] >= .95


def test_negative_verification_reduces_confidence_and_can_demote(tmp_path):
    e=engine(tmp_path)
    item=e.record('procedure','Deploy app','Use command A',project='App',better_action='command A',verified=True)
    original=item['confidence']
    for _ in range(4):
        out=e.verify(item['id'],False,'No longer works after project migration')
    assert out['experience']['confidence'] < original
    assert out['experience']['status']=='candidate'


def test_stale_unconfirmed_lesson_decays_but_confirmed_lesson_has_longer_memory(tmp_path):
    e=engine(tmp_path,confidence_half_life_days=10,confirmed_half_life_days=365)
    a=e.record('procedure','Build app','Run make',verified=True)
    b=e.record('procedure','Build app confirmed','Run make safely',verified=True,user_confirmed=True)
    old=(dt.datetime.now().astimezone()-dt.timedelta(days=40)).isoformat(timespec='seconds')
    e.conn.execute('UPDATE experience_lessons SET last_verified_at=?,last_seen_at=?',(old,old)); e.conn.commit()
    a2=e.get(a['id']); b2=e.get(b['id'])
    assert a2['effective_confidence'] < .3
    assert b2['effective_confidence'] > .8


def test_conflicting_procedures_are_marked_and_context_warns(tmp_path):
    e=engine(tmp_path)
    a=e.record('procedure','Start API','Use uvicorn',project='App',better_action='uvicorn app:app',verified=True)
    b=e.record('procedure','Start API','Use gunicorn',project='App',better_action='gunicorn app:app',verified=True)
    assert e.get(a['id'])['conflict_count'] >= 1
    assert e.get(b['id'])['conflict_count'] >= 1
    ctx=e.context_for('Start API',project='App')
    assert 'CONFLICT' in ctx


def test_superseded_lesson_is_not_retrieved(tmp_path):
    e=engine(tmp_path)
    old=e.record('procedure','Start frontend','npm run dev',project='App',better_action='npm run dev',verified=True)
    new=e.record('procedure','Start frontend v2','pnpm dev',project='App',better_action='pnpm dev',verified=True)
    assert e.supersede(old['id'],new['id'])['ok'] is True
    ids=[x['id'] for x in e.search('Start frontend',project='App',limit=10)]
    assert old['id'] not in ids


def test_episode_and_lesson_storage_redacts_secrets(tmp_path):
    e=engine(tmp_path)
    ep=e.record_episode('login','run_command',{'command':'curl -H "Authorization: Bearer abc123"','password':'hunter2'},
                        {'ok':False,'error':'token=supersecret'})
    assert 'abc123' not in ep['arguments_summary']
    assert 'hunter2' not in ep['arguments_summary']
    assert 'supersecret' not in ep['result_summary']
    item=e.record('failure','API token=foo failed','Do not expose password=bar',verified=True)
    rendered=str(item)
    assert 'token=foo' not in rendered and 'password=bar' not in rendered


def test_episode_maintenance_prunes_old_traces_not_lessons(tmp_path):
    e=engine(tmp_path,episode_retention_days=2)
    e.record_episode('x','tool',{}, {'ok':False})
    e.record('procedure','x','lesson',verified=True)
    old=(dt.datetime.now().astimezone()-dt.timedelta(days=10)).isoformat(timespec='seconds')
    e.conn.execute('UPDATE experience_episodes SET created_at=?',(old,)); e.conn.commit()
    result=e.maintenance()
    assert result['episodes_pruned']==1
    assert len(e.list('active'))==1


def test_search_is_project_and_query_sensitive(tmp_path):
    e=engine(tmp_path)
    e.record('procedure','Start frontend Vite','Use npm run dev',project='RetailEye',better_action='npm run dev',verified=True)
    e.record('procedure','Rotate database backups','Use backup script',project='Finance',better_action='backup.sh',verified=True)
    result=e.search('frontend Vite',project='RetailEye',limit=2)
    assert result and result[0]['project']=='RetailEye'


def test_stats_distinguish_trusted_lessons_from_episodes(tmp_path):
    e=engine(tmp_path)
    e.record('procedure','a','candidate')
    e.record('procedure','b','verified',verified=True)
    e.record_episode('task','tool',{}, {'ok':True})
    s=e.stats()
    assert s['trusted_lessons']==1 and s['episodes']==1

def test_failure_patterns_cluster_repeated_recent_errors(tmp_path):
    e=engine(tmp_path)
    for code in (500,501,502):
        e.record_episode('deploy','run_command',{'command':'npm test'},{'ok':False,'error':f'Connection refused code {code}'})
    patterns=e.failure_patterns(limit=5,min_count=2)
    assert patterns and patterns[0]['tool_name']=='run_command'
    assert patterns[0]['count']==3
    assert '<n>' in patterns[0]['signature']

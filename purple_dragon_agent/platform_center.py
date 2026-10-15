"""Passive platform catalog and bounded session overview; no operations performed."""
from copy import deepcopy
from . import __version__

_FEATURES = (
    ('workspace','Project Workspace','Choose a folder, inspect files and select coding context.'),
    ('coding','Coding & Validation','Validate selected sources, stage proposals and review full diffs before applying.'),
    ('terminal','Tests & Results','Preview fixed test commands and run current files with separate approval.'),
    ('agents','Agent Planning','Review sequential role plans, pause at tool boundaries and prepare controlled retries.'),
    ('memory','Project Memory','Search notes and decisions, edit reviewed revisions and preview selected context.'),
    ('research','Research & Sources','Fetch permitted HTTPS sources, preview context and inspect cached citations.'),
    ('git','Git & GitHub','Prepare repository operations and review remote writes before approval.'),
    ('plugins','Plugins','Inspect installed plugin manifests and review their controlled operations.'),
    ('security','Security & Permissions','Review session restrictions, protected paths, Sandbox boundaries and credential metadata.'),
    ('recovery','Recovery & Release Trust','Inspect local integrity evidence, settings recovery and workspace rollback.'),
    ('settings','Local Model & Settings','Configure LM Studio, run explicit connection tests and manage model profiles.'),
    ('activity','Activity','Inspect recorded requests, approvals and outcomes.')
)


def feature_catalog():
    return [{'route':route,'title':title,'description':description} for route,title,description in _FEATURES]


def platform_status(config, connection, files, busy, pending, profile, restricted_count, job=None):
    enabled = config.get('lm_studio',{}).get('enabled') is True
    connection_status = connection.get('status','configured') if enabled else 'disabled'
    policies = config.get('permissions',{})
    result = {
        'version':__version__, 'safe_mode':True,
        'model':{'enabled':enabled,'status':connection_status,'verified':enabled and connection_status=='verified',
                 'checked_at':connection.get('checked_at') if enabled else None},
        'workspace':{'indexed_files':files,'index_status':'not_indexed' if files is None else 'last_index_count'},
        'session':{'busy':bool(busy),'approval_pending':bool(pending),'profile':profile,'restricted_actions':restricted_count},
        'policies':{value:sum(v==value for v in policies.values()) for value in ('allow','ask','deny')},
        'context':{'memory_enabled':config.get('project_memory',{}).get('use_context') is True,
                   'research_enabled':config.get('research',{}).get('enabled') is True},
        'task':{'kind':job.get('kind'),'state':job.get('state')} if job else None,
        'next_steps':[],
        'note':'Session metadata only. No files were scanned, model tested, tools executed, or release acceptance established.'
    }
    if files is None:
        result['next_steps'].append({'route':'workspace','text':'Confirm the project folder and explicitly refresh its file list.'})
    if not enabled:
        result['next_steps'].append({'route':'settings','text':'For generated answers, configure and test a local model. Offline tools remain available.'})
    elif connection_status!='verified':
        result['next_steps'].append({'route':'settings','text':'The local model has not passed its last inference check. Review Settings and test it explicitly.'})
    if pending:
        result['next_steps'].append({'route':'activity','text':'A permission decision is pending. Review the active approval dialog.'})
    if profile!='standard':
        result['next_steps'].append({'route':'security','text':'A restricted session profile is active. Review its limits before planning work.'})
    result['next_steps'].append({'route':'recovery','text':'Inspect release trust for local checksum evidence and pending Windows acceptance.'})
    return deepcopy(result)

"""Executed only inside the frozen disposable Linux evaluator domain."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    phase = sys.argv[1]
    if phase not in ('a', 'b', 'controls'):
        raise ValueError('phase outside frozen physical profile')
    sys.path[:0] = ['/checkout', '/dependencies', '/public']
    import django
    from django.conf import settings
    import policy
    from django.db import connections, router, models
    from django.db.migrations.operations.models import CreateModel
    from django.db.migrations.state import ProjectState
    config = json.loads(Path('/public/deployment.json').read_text())
    components = {'primary': policy.DefaultPolicy(), 'scoped': policy.LedgerPolicy()}
    settings.configure(SECRET_KEY='owned-disposable-fixture', INSTALLED_APPS=[],
                       DATABASES={alias: {'ENGINE': 'django.db.backends.sqlite3',
                                           'NAME': '/scratch/' + alias + '.sqlite3'}
                                  for alias in ('default', 'reporting')},
                       DATABASE_ROUTERS=[components[x] for x in config['router_order']],
                       DEFAULT_AUTO_FIELD='django.db.models.AutoField')
    django.setup()
    cells = []
    original_router = router.allow_migrate
    events = []

    def observed_router(alias, app, **hints):
        answer = original_router(alias, app, **hints)
        events.append({'alias': alias, 'app': app, 'model_name': hints.get('model_name'),
                       'answer': answer})
        return answer

    router.allow_migrate = observed_router
    origins = {}
    for name in ('django.db.migrations.operations.models', 'django.db.migrations.operations.base',
                 'django.db.utils', 'django.db.models.options', 'policy'):
        module = sys.modules[name]
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(Path('/checkout') if name != 'policy' else Path('/public')):
            raise ValueError('framework/policy imported outside captured snapshot')
        origins[name] = {'path': str(path), 'sha256': sha(path.read_bytes())}
    for alias in ('default', 'reporting'):
        connection = connections[alias]
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE xrai_sentinel (payload TEXT NOT NULL)')
            cursor.execute('INSERT INTO xrai_sentinel VALUES (%s)', [phase + ':' + alias])
    if connections['default'].settings_dict['NAME'] == connections['reporting'].settings_dict['NAME']:
        raise ValueError('aliases share a database')

    class Abstain:
        def allow_migrate(self, db, app_label, **hints):
            return None

    class NoMethod:
        pass

    class Deny:
        def allow_migrate(self, db, app_label, **hints):
            return False

    if phase == 'controls':
        targets = [('all-none', 'xrai', 'allnone', True, [Abstain(), Abstain()]),
                   ('absent-then-false', 'xrai', 'absentfalse', True, [NoMethod(), Deny()])]
    else:
        targets = [(None, m['app_label'], m['model_name'], m['managed'], None)
                   for m in config['models']]
    for control, app, name, managed, controls in targets:
        if controls is not None:
            router.routers = controls
        operation = CreateModel(name=name, fields=[('id', models.AutoField(primary_key=True))],
                                options={'managed': managed})
        previous = ProjectState()
        target = previous.clone()
        operation.state_forwards(app, target)
        historical = target.apps.get_model(app, name)
        if historical._meta.managed is not managed:
            raise ValueError('historical model options lost')
        for alias in ('default', 'reporting'):
            connection = connections[alias]
            table = historical._meta.db_table
            with connection.cursor() as cursor:
                initial = connection.introspection.table_names(cursor)
            if table in initial:
                raise ValueError('model table present before migration')
            events.clear()
            with connection.schema_editor() as editor:
                # Calls the captured real operation/model/connection-router/schema
                # editor. Observation wraps the router and delegates unchanged.
                operation.database_forwards(app, editor, previous, target)
            operation_events = list(events)
            with connection.cursor() as cursor:
                creates = table in connection.introspection.table_names(cursor)
                cursor.execute('SELECT payload FROM xrai_sentinel')
                sentinel = cursor.fetchall()
            events.clear()
            isolated = original_router(alias, app, model_name=name, model=historical)
            gate = historical._meta.can_migrate(connection)
            row = {'alias': alias, 'app': app, 'model': name, 'table': table,
                   'creates_table': creates, 'model_can_migrate': gate,
                   'router_events_during_operation': operation_events,
                   'router_consulted': bool(operation_events),
                   'isolated_router_allows': isolated,
                   'sentinel': sentinel, 'historical_model': True,
                   'real_database_forwards': True, 'real_schema_editor': True}
            if control:
                row['control'] = control
            else:
                row['state'] = phase
            cells.append(row)
    names = [Path(connections[x].settings_dict['NAME']) for x in ('default', 'reporting')]
    dbfiles = [{'alias': alias, 'name': str(path), 'inode': path.stat().st_ino}
               for alias, path in zip(('default', 'reporting'), names)]
    if dbfiles[0]['inode'] == dbfiles[1]['inode']:
        raise ValueError('SQLite aliases share physical storage')
    for connection in connections.all():
        connection.close()
    print(json.dumps({'schema': 'xrai.eval.django-router.physical.v2', 'phase': phase,
                      'oracle_executed': True, 'cells': cells, 'database_files': dbfiles,
                      'module_origins': origins, 'python_version': sys.version.split()[0],
                      'sqlite_version': sqlite3.sqlite_version,
                      'configuration_sha256': sha(Path('/public/deployment.json').read_bytes()),
                      'policy_sha256': sha(Path('/public/policy.py').read_bytes()),
                      'provider_used': False, 'qualified': False, 'admitted': False},
                     sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()

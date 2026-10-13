#!/usr/bin/env python3
"""S02 frozen-data availability and prospective inspection contract; no fetch.

A recorded cache pathname is not a retained source byte, a selected MVS version,
a compiled package or advisory reachability. This module never grants S01
execution, invokes a downloader or imports/executes inspected source.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import tarfile
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'eval/security/gitea/inspection-v2'
MOD = 'eval/qualification/l5-real/go/setup/go.mod'
SUM = 'eval/qualification/l5-real/go/setup/go.sum'
ARCHIVE = 'eval/qualification/l5-real/go/sources/base.tar.gz'
ZIP = 'docs/relatorios/logs/L5-C02/ci-next-first/l5-real-go.zip'
CACHE = 'docs/relatorios/logs/L5-C02/ci-next-first/go/base/module-cache-manifest.json'
REF_CACHE = 'docs/relatorios/logs/L5-C02/ci-next-first/go/reference/module-cache-manifest.json'
DECISIONS = 'eval/security/gitea/decisions.json'
IMPORTS = 'eval/security/gitea/source-import-evidence.json'
AVAILABILITY_SHA = 'a1fd8469775afbbf78dab02adc8980dc3c742b623248b54dda4a42186f459949'
MISSING_PATH = 'eval/security/gitea/inspection-v2/missing-cache-files.json.gz'
MISSING_SHA = '83956daffa87cf6cc45bd33f5c7cf58c14b1dff441e06166f13063df7c88c9d0'
PINS = {
    MOD: '29f295d7e8f60ffad2245b64498ee0d3268a0a97b199da41872cd34009cf3127',
    SUM: '3b0849aae4c1c40fbebb12d3f0b40809f86fe866e2d561d4c38c09188b32e115',
    ARCHIVE: '3cd918c96a563db6a64e8c9717d556097240de799f9f0948ba50060e6143c190',
    ZIP: '9fbdfef0962e483310dc0ea983ed7e9077f4a0c33c64c8e972d492b5116449a0',
    CACHE: '86dd3184b3b3e300c595cd2b9c7b71222e0a0cf7a26889b4dc6e7a0e742311ad',
    REF_CACHE: '86dd3184b3b3e300c595cd2b9c7b71222e0a0cf7a26889b4dc6e7a0e742311ad',
    DECISIONS: 'db0f572bbb4bbe20fa04c6b0f8608bf3cc1bd7b5f617a997433c96dc7fc14bf3',
    IMPORTS: '6852864bc1a725d2d1183c83a29f129d962b4e65d88875e3e77a47a13e520983',
}
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_FILES = 50000
MAX_OBJECT_BYTES = 32 * 1024 * 1024
MAX_OBJECTS = 128
ZIP_NAMES = {f'{side}/{name}' for side in ['base', 'reference'] for name in
             ['module-cache-manifest.json', 'toolchain-manifest.json', 'probe.json',
              'requirement-harness.json', 'regression-harness.json',
              'requirement-go-test.jsonl', 'regression-go-test.jsonl']}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def safe_name(name):
    need(isinstance(name, str) and name and not name.startswith('/') and '\\' not in name and
         ':' not in name and not any(ord(c) < 32 for c in name) and
         all(part not in ['', '.', '..'] for part in name.split('/')), 'relative ordinary path required')
    return name


def read_pinned(path, *, root=ROOT):
    safe_name(path)
    source = root / path
    need(all(not p.is_symlink() for p in [source, *source.parents] if p.is_relative_to(root)) and
         source.resolve().is_relative_to(root.resolve()) and source.is_file(), 'pinned source symlink/escape/unavailable')
    need(0 < source.stat().st_size <= MAX_INPUT_BYTES, 'input byte limit')
    raw = source.read_bytes()
    need(sha(raw) == PINS[path], 'frozen source hash changed: ' + path)
    return raw


def parse_go_mod(raw):
    """Exact supported syntax of this pinned go.mod, not a Go graph resolver."""
    required, replacements, exclusions = {}, {}, []
    module = go = None
    in_require = False
    for line_no, original in enumerate(raw.decode('utf-8').splitlines(), 1):
        text, _, comment = original.partition('//')
        text = text.strip()
        if not text:
            continue
        if text == 'require (':
            need(not in_require, 'nested require block'); in_require = True; continue
        if text == ')':
            need(in_require, 'unmatched require block'); in_require = False; continue
        if in_require:
            words = text.split()
            need(len(words) == 2 and words[0] not in required and words[1].startswith('v'), 'unique module requirement')
            need(comment.strip() in ['', 'indirect'], 'unsupported requirement comment')
            required[words[0]] = {'version': words[1], 'requirement_kind': 'indirect' if comment.strip() == 'indirect' else 'direct', 'line': line_no}
            continue
        words = text.split()
        if words[0] == 'module':
            need(len(words) == 2 and module is None, 'one root module'); module = words[1]
        elif words[0] == 'go':
            need(len(words) == 2 and go is None, 'one Go language version'); go = words[1]
        elif words[0] == 'replace':
            need(len(words) == 5 and words[2] == '=>' and words[1] not in replacements and words[4].startswith('v'), 'explicit remote replacement syntax')
            replacements[words[1]] = {'module': words[3], 'version': words[4], 'line': line_no}
        elif words[0] == 'exclude':
            need(len(words) == 3 and words[2].startswith('v'), 'explicit exclude syntax')
            exclusions.append({'module': words[1], 'version': words[2], 'line': line_no})
        else:
            raise ValueError('unsupported go.mod directive: ' + words[0])
    need(module and go and required and not in_require, 'complete root module requirements')
    need(set(replacements) <= set(required), 'replacement without declared root requirement')
    return {'module': module, 'go': go, 'requirements': required, 'replacements': replacements, 'excludes': exclusions}


def parse_go_sum(raw):
    result = defaultdict(dict)
    for line_no, line in enumerate(raw.decode('utf-8').splitlines(), 1):
        words = line.split()
        need(len(words) == 3 and words[1].startswith('v') and words[2].startswith('h1:'), 'go.sum record syntax')
        try:
            digest = base64.b64decode(words[2][3:], validate=True)
        except ValueError as error:
            raise ValueError('go.sum checksum encoding') from error
        need(len(digest) == 32, 'go.sum checksum length')
        key = words[1]
        need(key not in result[words[0]], 'duplicate go.sum module/version')
        result[words[0]][key] = {'h1': words[2], 'line': line_no}
    return dict(result)


def cache_key(module):
    """Literal cache spelling observed in this inventory; not module selection."""
    need(isinstance(module, str) and re.fullmatch('[A-Za-z0-9._~+/-]+', module) and '!' not in module,
         'supported literal module path')
    return ''.join('!' + c.lower() if 'A' <= c <= 'Z' else c for c in module)


def validate_cache(cache):
    files = cache['files']
    need(type(cache['file_count']) is int and len(files) == cache['file_count'] <= MAX_MANIFEST_FILES, 'cache manifest count')
    need(len({f['path'] for f in files}) == len(files), 'duplicate cache file')
    for row in files:
        safe_name(row['path'])
        need(set(row) == {'path', 'bytes', 'sha256'} and type(row['bytes']) is int and 0 <= row['bytes'] <= 2 ** 63 - 1 and
             re.fullmatch('[0-9a-f]{64}', row['sha256']), 'cache file receipt')
    need(type(cache['bytes']) is int and sum(f['bytes'] for f in files) == cache['bytes'], 'cache declared byte total')
    need(sha(json.dumps(files, sort_keys=True).encode()) == cache['manifest_sha256'], 'cache inventory aggregate hash')
    return files


def retained_zip(raw):
    """Inspect bounded members in memory; no extraction or archive execution."""
    members = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as tree:
        infos = tree.infolist()
        need(len(infos) == len({i.filename for i in infos}) == 14, 'exact fourteen unique historical ZIP members')
        need({i.filename for i in infos} == ZIP_NAMES, 'historical ZIP closure differs')
        need(sum(i.file_size for i in infos) <= MAX_EXPANDED_BYTES, 'ZIP expansion limit')
        for entry in infos:
            safe_name(entry.filename)
            mode = stat.S_IFMT(entry.external_attr >> 16)
            need(mode in [0, stat.S_IFREG] and not entry.is_dir() and not entry.flag_bits & 1 and
                 entry.file_size <= MAX_INPUT_BYTES, 'ordinary bounded ZIP member')
            members[entry.filename] = tree.read(entry)
    return members


def root_lock_bytes(raw):
    prefix = 'gitea-8eefa1f6dedf2488db2c9e12c916e8e51f673160/'
    found, expanded, count = {}, 0, 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for entry in archive:
            count += 1; expanded += entry.size
            need(count <= MAX_MANIFEST_FILES and expanded <= MAX_EXPANDED_BYTES and entry.size <= MAX_INPUT_BYTES,
                 'root source archive bounds')
            if entry.name in [prefix + 'go.mod', prefix + 'go.sum']:
                need(entry.isfile() and not entry.issym() and not entry.islnk() and entry.name not in found,
                     'root lock must be an ordinary unique file')
                found[entry.name[len(prefix):]] = archive.extractfile(entry).read()
    need(set(found) == {'go.mod', 'go.sum'}, 'root source lock missing')
    return found


def declared_versions(files, module):
    key = cache_key(module)
    versions = defaultdict(list)
    for row in files:
        path = row['path']
        if path.startswith('cache/download/' + key + '/@v/'):
            leaf = path[len('cache/download/' + key + '/@v/'):]
            match = re.fullmatch(r'(v[A-Za-z0-9.+-]+)\.(info|mod|zip|ziphash|lock)', leaf)
            if match:
                versions[match[1]].append(row)
        elif path.startswith(key + '@'):
            suffix = path[len(key) + 1:]
            version, separator, _ = suffix.partition('/')
            if separator:
                versions[version].append(row)
    return [{'version': version, 'declared_files': len(rows), 'declared_bytes': sum(r['bytes'] for r in rows),
             'archive_metadata': [r for r in rows if r['path'].startswith('cache/download/')],
             'retained_module_bytes': 0, 'selected': 'unknown', 'compiled': 'unknown'}
            for version, rows in sorted(versions.items())]


def compose(*, root=ROOT):
    raw = {path: read_pinned(path, root=root) for path in PINS}
    members = retained_zip(raw[ZIP])
    need(members['base/module-cache-manifest.json'] == raw[CACHE] == raw[REF_CACHE] == members['reference/module-cache-manifest.json'],
         'cache manifests must equal original ZIP bytes on both sides')
    cache = decode(raw[CACHE]); files = validate_cache(cache)
    need(cache['file_count'] == 36892 and cache['bytes'] == 1076105923, 'fixed historical declared cache totals')
    for side in ['base', 'reference']:
        probe = decode(members[side + '/probe.json'])
        need(probe['module_cache_manifest_sha256'] == PINS[CACHE], 'historical probe manifest binding')
    locks = root_lock_bytes(raw[ARCHIVE])
    need(locks['go.mod'] == raw[MOD] and locks['go.sum'] == raw[SUM], 'source/setup locks differ')
    mod = parse_go_mod(raw[MOD]); sums = parse_go_sum(raw[SUM])
    decisions = decode(raw[DECISIONS]); imports = decode(raw[IMPORTS])['packages']
    alerts = decisions['alerts']
    need(len(alerts) == len({a['number'] for a in alerts}) == 55 and decisions['execution_allowed'] is False,
         'S01 remains fifty-five blocking individual alerts')
    rows = []
    for module, required in sorted(mod['requirements'].items()):
        versions = declared_versions(files, module)
        replacement = mod['replacements'].get(module)
        replacement_versions = declared_versions(files, replacement['module']) if replacement else []
        rows.append({'module': module, 'required': required,
                     'go_sum': sums.get(module, {}), 'replacement_declared': replacement,
                     'replacement_go_sum': sums.get(replacement['module'], {}) if replacement else {},
                     'historical_cache_versions_declared': versions,
                     'replacement_cache_versions_declared': replacement_versions,
                     'present_now': {'status': 'module_bytes_not_retained_in_historical_ci_export', 'verified_bytes': 0},
                     'selected_version': {'status': 'unknown', 'reason': 'No retained module graph/MVS evidence; require/cache/replacement spelling is not selection.'},
                     'compiled_version': {'status': 'unknown', 'reason': 'Historical probe success does not identify each compiled dependency/version.'}})
    by_module = {row['module']: row for row in rows}
    alert_rows = []
    for alert in sorted(alerts, key=lambda a: (a['priority'], a['number'])):
        package = alert['package']; row = by_module[package]
        need(alert['resolved_pin'] == row['required'] and alert['decision'] == 'pending_blocks_execution', 'S01 requirement/decision changed')
        alert_rows.append({'number': alert['number'], 'ghsa_id': alert['ghsa_id'], 'package': package,
                           'severity': alert['severity'], 'priority': alert['priority'],
                           'requirement': row['required'],
                           'declared_cached_versions': [r['version'] for r in row['historical_cache_versions_declared']],
                           'present_module_bytes': 0, 'selected_version': 'unknown', 'compiled_version': 'unknown',
                           'import_witness_count': imports[package]['import_witness_count'],
                           'import_witnesses': imports[package]['import_witnesses'],
                           'reachability': 'unknown', 'decision': 'pending_blocks_execution',
                           'phase_decisions': {phase: 'blocked' for phase in ['download', 'build', 'probe']},
                           'missing_evidence': ['dependency source/go.mod bytes', 'selected module/package closure for platform/tags/CGO/oracle',
                                                'advisory-specific input/call/initializer/TestMain/subprocess paths'],
                           'absence_of_import_is_not_exclusion': True})
    missing = {'schema': 'xrai.eval.gitea.inspection.missing-cache.v2', 'data_only': True,
               'manifest_sha256': PINS[CACHE], 'missing_scope': 'Exact module-cache files are absent from the retained fourteen-file CI ZIP; no whole-machine absence claim.',
               'file_count': len(files), 'declared_bytes': sum(r['bytes'] for r in files), 'files': files}
    # Retain the original gzip bytes; recompute every decompressed record rather
    # than assume different interpreter/zlib releases recompress identically.
    missing_path = root / MISSING_PATH
    need(missing_path.is_file() and not missing_path.is_symlink() and
         missing_path.stat().st_size <= MAX_INPUT_BYTES, 'frozen missing-file enumeration unavailable')
    compressed = missing_path.read_bytes()
    need(sha(compressed) == MISSING_SHA, 'frozen enumeration byte fingerprint')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as enumeration:
        plain = enumeration.read(MAX_INPUT_BYTES + 1)
        need(len(plain) <= MAX_INPUT_BYTES and not enumeration.read(1), 'enumeration expansion limit')
    need(plain == encoded(missing), 'full missing-file enumeration differs from source manifest')
    availability = {'schema': 'xrai.eval.gitea.inspection.availability.v2', 'data_only': True,
                    'source_bindings': {path: {'sha256': PINS[path], 'bytes': len(data)} for path, data in sorted(raw.items())},
                    'root_module': mod['module'], 'go_language_requirement': mod['go'],
                    'root_source_locks_retained': True, 'source_setup_locks_identical': True,
                    'requirements': rows, 'replacements': mod['replacements'], 'excludes': mod['excludes'],
                    'missing_cache': {'path': 'eval/security/gitea/inspection-v2/missing-cache-files.json.gz',
                                      'sha256': sha(compressed), 'bytes': len(compressed)},
                    'alerts': alert_rows,
                    'summary': {'root_requirements': len(rows), 'direct_requirements': sum(r['required']['requirement_kind'] == 'direct' for r in rows),
                                'indirect_requirements': sum(r['required']['requirement_kind'] == 'indirect' for r in rows),
                                'replacement_requirements': len(mod['replacements']), 'excluded_module_versions': len(mod['excludes']),
                                'historical_cache_files_declared': 36892, 'historical_cache_bytes_declared': 1076105923,
                                'retained_ci_zip_files': 14, 'retained_module_cache_files': 0, 'retained_module_cache_bytes': 0,
                                'root_requirements_with_matching_declared_cache_version': sum(any(v['version'] == r['required']['version'] for v in r['historical_cache_versions_declared']) for r in rows),
                                'alerts': 55, 'critical_high_priority': sum(a['priority'] == 1 for a in alert_rows),
                                'alerts_selected_version_unknown': 55, 'alerts_compiled_version_unknown': 55,
                                'execution_allowed': False, 'new_acquisitions': 0},
                    'context_pending': {'GOOS': 'Linux historical probe, no per-package closure', 'GOARCH': 'per-package closure unknown',
                                        'tags': ['sqlite', 'sqlite_unlock_notify'], 'CGO_ENABLED': '1 historical command; affected dependency closure unknown',
                                        'oracle': 'frozen services/convert/xrai_url_contract_test.go; no advisory reachability adjudication'},
                    'limits': ['A manifest records historical copies; it is not the copied source bytes.',
                               'go.sum checksum strings are retained, not independently fetched/verified module archives.',
                               'No go list, downloader, build, imports upstream, hooks, generation, tests or native executable ran.',
                               'Regexp import witnesses provide no absence or compiled/call closure proof.',
                               'Inspection request validation is separate from S01 execution; all fifty-five decisions remain blocked.']}
    return {'availability.json': encoded(availability), 'missing-cache-files.json.gz': compressed}


def policy():
    return {'schema': 'xrai.eval.gitea.inspection.contract.v2', 'profile': 'restricted_frozen_data_inspection_v2',
            'status': 'offline_contract_validated_acquisition_not_implemented',
            'reader': {'language': 'Python', 'version': '3.13.13', 'dependencies': 'standard_library_only',
                       'source': 'eval/scripts/inventory_gitea_availability.py', 'sha256': sha(Path(__file__).read_bytes())},
            'network': {'scheme': 'https', 'host': 'proxy.golang.org', 'port': None, 'method': 'GET',
                        'redirects': False, 'credentials': False, 'headers': {}, 'query': '', 'fragment': '',
                        'versioned_extensions': ['mod', 'info', 'zip']},
            'limits': {'objects': MAX_OBJECTS, 'object_bytes': MAX_OBJECT_BYTES, 'total_bytes': MAX_EXPANDED_BYTES,
                       'archive_files': MAX_MANIFEST_FILES, 'expanded_bytes': MAX_EXPANDED_BYTES,
                       'timeout_seconds': 30, 'output_bytes': 1048576},
            'runtime_requirements': ['fresh disposable Linux inspection directory; no project credentials or environment passthrough',
                                     'authenticated frozen input bytes read-only; inspect owned immutable in-memory copies',
                                     'raw response quarantine; expected hash/length before any reader',
                                     'no archive extraction; bounded inventory/read only; reject symlinks/traversal/duplicates/special files',
                                     'own Python reader/runtime bytes fixed and recorded before acquisition',
                                     'actual acquisition/containment requires separate implementation and receipts; request flags do not prove it'],
            'operators': ['sha256', 'regular_path_inventory', 'bounded_utf8_read'],
            'forbidden': ['go_mod_download', 'go_list', 'build', 'probe', 'upstream_import', 'source_execution',
                          'hooks', 'generation', 'tests', 'subprocess', 'remote_alert_dismiss', 'project_credentials'],
            'S01_execution_allowed': False, 'acquisition_implemented': False, 'remote_actions': 'none'}


def validate_requests(contract, requests, availability):
    """Validate prospective data requests only; never perform or permit IO."""
    need(encoded(contract) == encoded(policy()), 'inspection policy differs from the fixed offline contract')
    need(sha(encoded(availability)) == AVAILABILITY_SHA, 'availability must match the frozen recomputed evidence, never caller flags')
    need(availability['schema'] == 'xrai.eval.gitea.inspection.availability.v2' and
         availability['summary']['execution_allowed'] is False, 'inspection does not unlock S01')
    trusted = {row['path']: row for module in availability['requirements']
               for group in ['historical_cache_versions_declared', 'replacement_cache_versions_declared']
               for version in module[group] for row in version['archive_metadata']}
    need(isinstance(requests, list) and 0 < len(requests) <= MAX_OBJECTS, 'inspection object count')
    seen, total = set(), 0
    for request in requests:
        need(set(request) == {'operation', 'artifact', 'url', 'method', 'headers', 'credentials', 'redirects',
                             'destination', 'operators', 'reader_sha256', 'timeout_seconds'}, 'exact inspection request fields')
        need(request['operation'] == 'planned_data_acquisition' and request['method'] == 'GET' and
             request['headers'] == {} and request['credentials'] is False and request['redirects'] is False,
             'no execution/auth/redirect request')
        artifact = request['artifact']; path = artifact['path']
        need(path in trusted and encoded(artifact) == encoded(trusted[path]) and path not in seen,
             'distinct manifest-bound expected artifact/hash/length')
        seen.add(path)
        need(type(artifact['bytes']) is int and 0 < artifact['bytes'] <= MAX_OBJECT_BYTES, 'inspection object byte limit')
        total += artifact['bytes']; need(total <= MAX_EXPANDED_BYTES, 'inspection aggregate byte limit')
        suffix = path.removeprefix('cache/download/')
        need(path.startswith('cache/download/') and suffix.endswith(('.mod', '.info', '.zip')), 'only fixed version module data endpoints')
        parts = urlsplit(request['url'])
        need(request['url'] == 'https://proxy.golang.org/' + suffix and parts.scheme == 'https' and
             parts.hostname == 'proxy.golang.org' and parts.port is None and parts.username is None and
             parts.password is None and not parts.query and not parts.fragment, 'exact permitted acquisition destination')
        expected_destination = 'inspection-data/' + artifact['sha256'] + '/raw/' + suffix
        need(safe_name(request['destination']) == expected_destination, 'fresh content-addressed quarantine destination')
        need(request['operators'] == contract['operators'] and request['reader_sha256'] == contract['reader']['sha256'] and
             type(request['timeout_seconds']) is int and request['timeout_seconds'] == 30,
             'fixed reader/operators/timeout; no imported source or hooks')
    return {'schema': 'xrai.eval.gitea.inspection.request-verification.v2', 'data_only': True,
            'prospective_shape_valid': True, 'objects': len(requests), 'declared_bytes': total,
            'acquisition_performed': False, 'execution_allowed': False, 'remote_actions': 'none',
            'limits': ['No downloader is implemented or authorized by this return value.',
                       'Runtime containment, interpreter binary pin and actual response bytes require a separate acquisition receipt.',
                       'S01 download/build/probe guard remains unchanged and blocking.']}


def sample_requests(availability):
    candidates = [r for module in availability['requirements'] if module['module'] == 'github.com/go-git/go-git/v5'
                  for version in module['historical_cache_versions_declared'] for r in version['archive_metadata'] if r['path'].endswith('.mod')]
    need(len(candidates) == 1, 'one fixed prioritized Go-git module metadata candidate')
    artifact = candidates[0]; suffix = artifact['path'][len('cache/download/'):]
    contract = policy()
    return [{'operation': 'planned_data_acquisition', 'artifact': artifact,
             'url': 'https://proxy.golang.org/' + suffix, 'method': 'GET', 'headers': {}, 'credentials': False,
             'redirects': False, 'destination': 'inspection-data/' + artifact['sha256'] + '/raw/' + suffix,
             'operators': contract['operators'], 'reader_sha256': contract['reader']['sha256'], 'timeout_seconds': 30}]


def verify(directory=DEST):
    import verify_gitea_exposure
    s01 = verify_gitea_exposure.check_data()
    need(s01['execution_allowed'] is False and s01['alerts'] == 55, 'S01 unchanged blocking inventory')
    outputs = compose()
    outputs['inspection-policy.json'] = encoded(policy())
    availability = decode(outputs['availability.json'])
    requests = sample_requests(availability)
    outputs['sample-request.json'] = encoded(requests)
    need(directory.is_dir() and not directory.is_symlink() and
         {p.name for p in directory.iterdir()} == set(outputs), 'exact ordinary inspection-v2 artifact closure')
    for name, content in outputs.items():
        path = directory / name
        need(path.is_file() and not path.is_symlink() and path.read_bytes() == content, 'recomputed inspection artifact differs: ' + name)
    request = validate_requests(decode(outputs['inspection-policy.json']), requests, availability)
    return {'schema': 'xrai.eval.gitea.inspection.verification.v2', 'verified': True, 'data_only': True,
            'summary': availability['summary'], 'request_verification': request,
            'artifact_sha256': {name: sha(raw) for name, raw in outputs.items()},
            'source_sha256': sha(Path(__file__).read_bytes()), 'execution_allowed': False, 'new_acquisitions': 0}


def prepare(directory=DEST):
    outputs = compose(); availability = decode(outputs['availability.json'])
    outputs['inspection-policy.json'] = encoded(policy())
    outputs['sample-request.json'] = encoded(sample_requests(availability))
    directory.mkdir(parents=True, exist_ok=True)
    need(not directory.is_symlink(), 'ordinary inspection destination')
    for name, raw in outputs.items():
        path = directory / name
        need(not path.exists() or (not path.is_symlink() and path.read_bytes() == raw), 'refuse to rewrite frozen prospective inspection artifact')
        if not path.exists():
            path.write_bytes(raw)
    return verify(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['prepare', 'verify'], default='verify')
    args = parser.parse_args()
    print(encoded(prepare() if args.action == 'prepare' else verify()).decode(), end='')


if __name__ == '__main__':
    main()

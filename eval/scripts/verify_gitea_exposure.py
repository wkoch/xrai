#!/usr/bin/env python3
"""S01 data-only acceptance and fail-closed execution gate for frozen Gitea.

This checkpoint permits pending assessments, never execution waivers. A future
permission needs reviewed reachability/control evidence and a new verifier policy;
changing JSON labels, counts, hashes or adding a blanket waiver cannot enable it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'eval/security/gitea'
SNAPSHOT = 'docs/relatorios/logs/revisao-L5-C02/dependencias.json'
SETUP = 'eval/qualification/l5-real/go/setup/'
ARCHIVE = 'eval/qualification/l5-real/go/sources/base.tar.gz'
SCHEMA = 'xrai.eval.gitea.exposure.v1'
PHASES = ('download', 'build', 'probe')
PINNED_SNAPSHOT_SHA256 = '05b375d76b57941e337131712e9e83f2ebfc1348f19a4efd2b0ab78337c0778b'
PINNED_BINDINGS = {'crates/xrai-eval/harness/adapters.py': '90218bd545a99dee1a4530a2b1155f69b0ece2e3dcaf8fbd07fd89c88b8041e4',
 'crates/xrai-eval/harness/supervisor.py': '8fb13b93a1c3ebdd7a1cf7ab2d1c5f75e8beccf335ad53c064165d95a85d1571',
 'eval/qualification/l5-real/go/oracles/xrai_url_contract_test.go': '79821b7011b6145def1266cf9bffb97c3034ffc49a8c41ec41556a29a06d4f59',
 'eval/qualification/l5-real/go/setup/go.mod': '29f295d7e8f60ffad2245b64498ee0d3268a0a97b199da41872cd34009cf3127',
 'eval/qualification/l5-real/go/setup/go.sum': '3b0849aae4c1c40fbebb12d3f0b40809f86fe866e2d561d4c38c09188b32e115',
 'eval/qualification/l5-real/go/sources/base.tar.gz': '3cd918c96a563db6a64e8c9717d556097240de799f9f0948ba50060e6143c190'}
PINNED_ADVISORIES = {'GHSA-29wx-vh33-7x7r': 'ca23a4c611eaa182f511e1d3e05f9ebf19b6a1caf464af8bca375f2401232592',
 'GHSA-2v4p-qf9q-27wj': '6388432d6f2cf64fa6e64936811f8af1bdce2288a6c60bdfb607cd5860264f33',
 'GHSA-2x5j-vhc8-9cwm': '6df9f3e307e207c4a35bbe5a31b4dfe74784525814742be186de8bdd2d9e47a2',
 'GHSA-37cx-329c-33x3': 'e4a326247adc273c783768a671646f974b0d74ae87397b590591c07a1fae3962',
 'GHSA-389r-gv7p-r3rp': '3eb9ed7d0c567f65e1092e1118485cd6644521ca8a97829453703fc9e0bded1e',
 'GHSA-3xc5-wrhm-f963': '08e7294220ff852fa9b2ca39d917a7545b1c38c1a84beb0ae8b38be5dcb8b1f1',
 'GHSA-44p7-9xx4-hf2g': 'b23920062861e079be7dba3f28601610005677127e926a39e64280cf215ebace',
 'GHSA-45gg-vh54-h5m9': 'd6658a74d103bdbebe3a63779090f4d3df83c76ef0b436115f0b5e63af215736',
 'GHSA-5cgq-3rg8-m6cv': '10b134df28bd17e8c95cd52e345c48020c84e1f28783fbde38f5b54b3425e966',
 'GHSA-5cv4-jp36-h3mw': '8b352b1f2ccf7e5c0c03839fd24192d88ed714149b6e27cbdbf055eeb5838bff',
 'GHSA-6v2p-p543-phr9': 'f3bb371e8608f94921e7c7b321911c1780457b14295fd918165e43aaa6e2c2bb',
 'GHSA-78mq-xcr3-xm33': 'f8460c3aa3b11e9ea7b92f6a7718f4f7fb0f8f079cf1766dc4bc3967b3db3e7e',
 'GHSA-89gr-r52h-f8rx': '36ca4691d409957b924fdf4c704c70614b2f57928d3a2f948ed923b2f9a7e811',
 'GHSA-92cp-5422-2mw7': '2d99a81a85e0ec2e6bb8194e32ba9ef979458ddffb0666467180d74f2abe54ba',
 'GHSA-9m57-25v3-79x9': '000e87ec107b8405e26d07a63cf4db551d8b61c65e937dd29424fb947a5e13b1',
 'GHSA-9w9f-6mg8-jp7w': '3097aca2013307de06125279bafeec75105f384de8f8bc52b7ff1027634622f3',
 'GHSA-cp6g-7hqx-qxhp': 'ae481610dd45005aa6a70106fbabdf66d15fe011f64e7fde83d519bf9d1ad8f1',
 'GHSA-crhj-59gh-8x96': '550df7caa22c91f40f50bb6a87cf95482105ba46b5caee9e5e532239f5844863',
 'GHSA-f5wc-c3c7-36mc': '6c6fc5113eb697b9e69807b7c72dd228864323ec249c59df21937adbec6c0224',
 'GHSA-f6x5-jh6r-wrfv': '36d0989c41c55c673cc2895262849fb97820dc843149866c44303e5cf613d920',
 'GHSA-fw7p-63qq-7hpr': 'e35fc76d3571acd96f3b6cb9c4cfa071dc45a3e7d3136753192e6a8349d3173f',
 'GHSA-gm2x-2g9h-ccm8': 'f43392925d5ba8101e95408087f24cad683fe785e0136c0f05c11fd35b0bd20c',
 'GHSA-hc8v-wwc9-vgxm': '4bc7cec0ecc83ea459c077a45f83c92b0396b77fb074ba2b42c0317324bd7e1a',
 'GHSA-hcg3-q754-cr77': '6387ad6c82360a48a8557ffb948985f0237d640d5c11b0ba1e9e6890b619cfc9',
 'GHSA-hrxh-6v49-42gf': '131be03e2e0c682405433cabaa329b7e52acea9cdce78b217d735bf24e815d32',
 'GHSA-j5w8-q4qc-rx2x': '879bc8cb2813ef8bf4aca947050722d7ab18f2594ab5236cb28a8725e850e46c',
 'GHSA-jc7w-c686-c4v9': 'af7a5b4fe88f716500ee591625d9892c5e288603f9c453f035b4637249548c7d',
 'GHSA-jhf3-xxhw-2wpp': 'e4c1b7468b531618db20168a8244759592a4778316527174d07ba0426a5d8e5f',
 'GHSA-jppx-rxg9-jmrx': '9c2765bee7c79d05a2c4e39b30da7a63cf890cef56e8be5473deef4c2b0bef13',
 'GHSA-m3xc-h892-ggx6': '2a7e8e57dee3106bdb08cbf079a3a2cb22d5758cbd51811876e3885838ae320b',
 'GHSA-m454-3xv7-qj85': '438ca8e6c6ceee96d0b08f72bcb5fddeeb5d9dc67f7139e8d9316105d876030a',
 'GHSA-m7cr-m3pv-hgrp': '8351d316776b4672cfe1a7f768b8c898c87575fe3ed6e8aa62101c4f3aea6cf3',
 'GHSA-mh63-6h87-95cp': '9612d7d60cc4138059058d01887686a3c81f82ed8af038e66ed4b545bb7ae8a3',
 'GHSA-p77j-4mvh-x3m3': '5daa5ff5338ce9b719140878d8ffaf0414492cdbb71dfe20fbf3fb03996a7585',
 'GHSA-pjcq-xvwq-hhpj': '60c31c77231ca35e83025dd64146c390b8ab2c45c3784330d03037341c82461d',
 'GHSA-q4h4-gmj2-qvw2': 'c9d41b10d89be90a9535b02e31a9a1c1c6445de7436ff21d101e475bee399d18',
 'GHSA-q675-qj96-32m9': 'a40af9c41eabfd3e0320b14ef72bd98b0217d58b99ea38512fa3c2458d05b814',
 'GHSA-q9hv-hpm4-hj6x': '187bbf4aa4f54317318a06d3a516552949264cb6521c91c0e4d88b992f2e503e',
 'GHSA-qc2q-p7wx-3px3': 'ada95f99bd3b396772367f25d005a526370916d3172c867abea722cf2475ec62',
 'GHSA-qgq7-7hm3-q39j': '31c807f9032dee40e6c9e8587086261e5b6cbcf971b9a1bceca75ee9c3e7daac',
 'GHSA-qpw4-5x99-6vjp': '901fd3e135630fdffada719929bc76bb0a915f61b7fd05f87c6a345e659a75eb',
 'GHSA-qw64-3x98-g7q2': 'aea2597eb86428c9aeb5e3967776668ea70b71a425f26363b5a3aa4530744847',
 'GHSA-qxp5-gwg8-xv66': '48a3d81cc2cd57682ca5eeda5bab9db70a07cedec0e783ddeb02fc3c39d35839',
 'GHSA-r9px-m959-cxf4': '3556bf34b10bc775b62d842200d9efc4f08070127f7addcc22051c0f66143fa0',
 'GHSA-rm3j-f69w-wqmq': '33fd0d6749a3b6f102dfb0f69f95998afa467c2f6deae0872c101d03d723f7da',
 'GHSA-rwvp-r38j-9rgg': 'eced19fd7de41ddd610c329d19afda189205fdebd1760c7fe7a5f6433d3200ab',
 'GHSA-v725-9546-7q7m': 'fdfddb243a5522d5b0fe4b1190c867a3bf0ccb7d79d3001a5dd7aff24d3a4816',
 'GHSA-vgwf-h737-ff37': 'abb5aef8e1f6ffd3d29d2c9f6fc73644c3bedb2bb36adb142e161bd068a27903',
 'GHSA-vp52-pcj8-j9qc': '972d896c897897f0b17f7ca9f56cac6ee115f2bfab5af113eb9ae6a77508b62b',
 'GHSA-vrw8-fxc6-2r93': '2ba045944bc48c183303693b9fcf21ffec18d8f1e0c4547ad81058e52b39a781',
 'GHSA-vvgc-356p-c3xw': '6d006922ab32a40cf4d91afa3d10c19bd5eea6cbc809168af937bd9d3808b9ce',
 'GHSA-w5pp-99ch-qj29': '34e309e0759d6dee5d7eb57e822614d56027f4883e399ed431bb8d0c674fb60b',
 'GHSA-w879-237q-wc7r': '2952467ad4df10d4fa08efbdfb5203c7f48c11e3a597878e203c580b8184532e',
 'GHSA-x527-x647-q7gg': 'c7d201ca6efc984fa5ce2a6740b3c2dcd3f339b579e94e25f10bc219a504e351'}
CONTROLS = {'build_probe': {'limits': ['workspace and copied runtime/module cache remain writable in '
                            'historical executor; files and subprocesses remain inputs',
                            'read-only system executable access permits invoking subprocesses; no '
                            'advisory reachability proof',
                            'network isolation narrows network vectors but does not remove local '
                            'file transport, archive parsing, authentication/configuration inputs '
                            'or resource exhaustion',
                            'prospective guard blocks execution; controls are source-observed, not '
                            'a claim that the next job ran'],
                 'present': ['Linux bubblewrap unshare-all + mandatory user namespace; private PID '
                             'namespace and pidfd teardown',
                             'clearenv; source workspace bind; /usr,/bin,/lib,/lib64 read-only; '
                             '/tmp tmpfs',
                             'Go probe requests timeout <=900s, Go tests timeout600s, 1MiB bounded '
                             'outputs, GOPROXY/GOSUMDB off and readonly module mode']},
 'download': {'limits': ['go mod download executes outside the probe namespace and has '
                         'network/host access in the historical workflow; no claim of safe future '
                         'download'],
              'present': ['frozen go.mod/go.sum retained; dependency checksum inputs exist']}}
PHASE_INPUTS = {'build': {'decision': 'blocked',
           'exposed_inputs': ['frozen Go/C sources, module cache and toolchain bytes, cgo '
                              'compiler/linker subprocesses, package initialization and TestMain '
                              'under go test'],
           'limit': 'Compiled package/function closure and build constraints not computed; all '
                    'syntactic imports are conservative witnesses, not a compilation or '
                    'reachability proof.',
           'reachability': 'unknown'},
 'download': {'decision': 'blocked',
              'exposed_inputs': ['module archive bytes, metadata, checksum/proxy responses; '
                                 'untrusted dependency names and archive paths handled by Go tool'],
              'limit': 'No affected library code executed by this assessment; module fetch runs '
                       'outside probe isolation in historical CI. Advisory-specific exposure of Go '
                       'downloader is unknown.',
              'reachability': 'unknown'},
 'probe': {'decision': 'blocked',
           'exposed_inputs': ['frozen URL contract cases, SQLite fixtures and setup configuration, '
                              'workspace/module/toolchain files, local subprocess arguments and '
                              'any package init/TestMain behavior'],
           'limit': 'No per-advisory input-to-vulnerable-function path proved or disproved. '
                    'Network-off does not exclude local files, subprocesses, authentication logic '
                    'or CPU/memory exhaustion.',
           'reachability': 'unknown'}}

INPUTS_OF_CONCERN = {'filippo.io/edwards25519': 'MultiScalarMult receiver state and scalar/point inputs',
 'github.com/Azure/go-ntlmssp': 'NTLM challenge bytes',
 'github.com/ClickHouse/ch-go': 'query payloads and protocol framing',
 'github.com/blevesearch/bleve/v2': 'REST handlers and role/authentication configuration',
 'github.com/cloudflare/circl': 'curve points/scalars and validation inputs',
 'github.com/go-chi/chi/v5': 'HTTP Host/path headers and redirect middleware',
 'github.com/go-git/go-billy/v5': 'filesystem paths and symlink graphs; local filesystem remains '
                                  'accessible in copied workspace',
 'github.com/go-git/go-git/v5': 'Git URLs (including local file transport), repository '
                                'objects/refs/pack/index files, symlinks, subprocess flags and '
                                'redirects',
 'github.com/golang-jwt/jwt/v4': 'JWT token/header bytes and ParseWithClaims error handling',
 'github.com/golang-jwt/jwt/v5': 'JWT token/header bytes',
 'github.com/nwaples/rardecode': 'RAR archive headers/dictionary sizes',
 'github.com/redis/go-redis/v9': 'Redis connection setup/timeouts and ordered response streams',
 'github.com/ulikunitz/xz': 'XZ/LZMA archive bytes',
 'go.mongodb.org/mongo-driver': 'GSSAPI error buffers and authentication configuration',
 'golang.org/x/crypto': 'SSH messages, key/certificate/agent constraint data, authentication '
                        'configuration, channel and cryptographic parameter inputs',
 'golang.org/x/image': 'crafted TIFF/image bytes and decompression parameters',
 'golang.org/x/net': 'HTML text, URL/proxy fields and IPv6 zone strings',
 'golang.org/x/oauth2': 'OAuth URLs/configuration and token exchanges',
 'google.golang.org/grpc': 'HTTP/2 frames/headers, xDS routing/RBAC configuration and '
                           'authentication path handling'}
RESOLUTION_LIMIT = 'Pinned root go.mod requirement and go.sum bytes; selected dependency graph/MVS and compiled library version not independently recomputed in this data-only assessment.'

def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def import_evidence(root=ROOT):
    """Recompute conservative import witnesses without loading upstream code."""
    snapshot = load(root / SNAPSHOT)
    packages = sorted({a['package'] for a in snapshot['alerts']})
    mods = {}
    for i, line in enumerate((root / SETUP / 'go.mod').read_text().splitlines(), 1):
        match = re.match(r'\s*([^\s()]+)\s+(v\S+)(?:\s+//\s+(indirect))?\s*$', line)
        if match:
            mods[match[1]] = {'version': match[2], 'requirement_kind': 'indirect' if match[3] else 'direct', 'line': i}
    witnesses = {p: [] for p in packages}
    with tarfile.open(root / ARCHIVE) as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith('.go'):
                continue
            data = archive.extractfile(member).read()
            name = member.name.split('/', 1)[1]
            text = data.decode('utf-8')
            for block in re.finditer(r'(?m)^import\s*(?:\((.*?)^\)|([^\n]+))', text, re.S | re.M):
                for quoted in re.finditer(r'"([^"\n]+)"', block[0]):
                    imported = quoted[1]
                    for package in packages:
                        if imported == package or imported.startswith(package + '/'):
                            witnesses[package].append({'path': name, 'line': text.count('\n', 0, block.start() + quoted.start()) + 1, 'import': imported, 'source_sha256': sha(data)})
    return {'method': 'Data-only regexp of frozen Go import declarations, including tests and all build tags. Witnesses are syntactic imports anywhere in Gitea, NOT compiled package closure, function reachability, or absence proof. Indirect dependency graph is unavailable without dependency source/module graph.', 'archive_sha256': sha((root / ARCHIVE).read_bytes()), 'packages': {p: {'resolved_pin': mods[p], 'import_witness_count': len(witnesses[p]), 'import_witnesses': sorted(witnesses[p], key=lambda r: (r['path'], r['line']))[:3], 'probe_package': './services/convert', 'probe_compile_and_call_chain': 'unknown; no go list/build/test/execution performed by this analysis'} for p in packages}}


def check_data(directory=DIRECTORY, root=ROOT):
    """Validate actual frozen evidence; caller flags never grant permission."""
    directory, root = Path(directory), Path(root)
    inventory = load(directory / 'decisions.json')
    if set(inventory) != {'schema', 'author', 'assessed_at_utc', 'snapshot_sha256', 'snapshot_at_utc', 'setup_bindings', 'import_evidence_sha256', 'controls', 'alerts', 'data_only', 'execution_allowed', 'remote_actions', 'scope_limit'}:
        raise ValueError('unsupported inventory fields or blanket waiver')
    snapshot_bytes = (root / SNAPSHOT).read_bytes()
    if sha(snapshot_bytes) != PINNED_SNAPSHOT_SHA256:
        raise ValueError('official alert snapshot changed')
    snapshot = json.loads(snapshot_bytes)
    if snapshot['total'] != 55 or len(snapshot['alerts']) != 55:
        raise ValueError('snapshot must retain all 55 alerts')
    if inventory['schema'] != SCHEMA or inventory['author'] != '/root/s01_exposure':
        raise ValueError('unknown assessment schema or responsible author')
    if inventory['snapshot_sha256'] != PINNED_SNAPSHOT_SHA256:
        raise ValueError('assessment snapshot mismatch')
    if inventory['controls'] != CONTROLS:
        raise ValueError('unsupported containment claim')
    if inventory['setup_bindings'] != PINNED_BINDINGS:
        raise ValueError('setup bindings changed')
    for path, digest in PINNED_BINDINGS.items():
        if sha((root / path).read_bytes()) != digest:
            raise ValueError('bound setup/control source changed: ' + path)
    evidence = load(directory / 'source-import-evidence.json')
    if evidence != import_evidence(root):
        raise ValueError('syntactic import evidence cannot be recomputed')
    if inventory['import_evidence_sha256'] != sha((directory / 'source-import-evidence.json').read_bytes()):
        raise ValueError('import evidence hash mismatch')
    rows = inventory['alerts']
    if any(type(row.get('number')) is not int for row in rows):
        raise ValueError('alert ID must be an integer, not a flag')
    if len(rows) != 55 or len({r['number'] for r in rows}) != 55:
        raise ValueError('missing or duplicate alert decision')
    expected = {a['number']: a for a in snapshot['alerts']}
    if set(expected) != {r['number'] for r in rows}:
        raise ValueError('unknown alert ID')
    for row in rows:
        source = expected[row['number']]
        for key in ('number', 'ghsa_id', 'package', 'severity', 'vulnerable_range', 'first_patched_version', 'summary', 'relationship', 'manifest'):
            if row[key] != source[key]:
                raise ValueError('official alert field changed: ' + key)
        if row['inputs_of_concern'] != INPUTS_OF_CONCERN[row['package']] or row['resolution_limit'] != RESOLUTION_LIMIT:
            raise ValueError('unsupported input or selected-version claim')
        pin = evidence['packages'][row['package']]['resolved_pin']
        if row['resolved_pin'] != pin:
            raise ValueError('resolved package pin mismatch')
        expected_chain = {'root_module': 'code.gitea.io/gitea', 'requirement': row['package'], 'evidence': SETUP + 'go.mod:' + str(pin['line']), 'module_graph_intermediates': 'unknown; no module graph retained', 'compiled_probe_chain': 'unknown; syntactic imports are not compiled closure'}
        if row['dependency_chain'] != expected_chain:
            raise ValueError('unsupported dependency-chain claim')
        advisory_path = directory / 'advisories' / (row['ghsa_id'] + '.json')
        raw = advisory_path.read_bytes()
        if sha(raw) != PINNED_ADVISORIES[row['ghsa_id']]:
            raise ValueError('frozen official advisory changed')
        advisory = json.loads(raw)
        official = {'url': source['advisory_url'], 'raw_sha256': sha(raw), 'published_at': advisory.get('published_at'), 'updated_at': advisory.get('updated_at'), 'revision': advisory.get('updated_at'), 'revision_kind': 'GitHub official advisory updated_at; not Git commit revision', 'fetch_status': 'retrieved' if advisory.get('ghsa_id') == row['ghsa_id'] and 'published_at' in advisory else 'unknown'}
        if row['official_source'] != official:
            raise ValueError('official advisory provenance mismatch')
        if official['fetch_status'] == 'retrieved' and advisory['html_url'] != source['advisory_url']:
            raise ValueError('official advisory identity mismatch')
        expected_advisory_evidence = {'description_sha256': sha(advisory.get('description', '').encode()), 'cwe_ids': [x['cwe_id'] for x in advisory.get('cwes', [])], 'package_records': [x for x in advisory.get('vulnerabilities', []) if x['package']['name'] == row['package']]}
        if row['advisory_evidence'] != expected_advisory_evidence:
            raise ValueError('advisory-specific evidence changed')
        if row['assessment'] != 'unknown' or row['decision'] != 'pending_blocks_execution' or row['controls'] != inventory['controls']:
            raise ValueError('unsupported allowance or reachability claim')
        if row['phases'] != PHASE_INPUTS:
            raise ValueError('unsupported affected-phase evidence')
        if set(row['phases']) != set(PHASES):
            raise ValueError('missing affected phase')
        for phase in PHASES:
            value = row['phases'][phase]
            if value['reachability'] != 'unknown' or value['decision'] != 'blocked' or not value['exposed_inputs'] or not value['limit']:
                raise ValueError('unsupported phase decision or missing exposure limit')
        if row['priority'] != (1 if row['severity'] in ('critical', 'high') else 2):
            raise ValueError('severity priority changed')
        if not row['reason'] or not row['pending'] or row['responsible'] != inventory['author']:
            raise ValueError('missing reason, pending investigation or responsibility')
    if inventory['execution_allowed'] is not False or inventory['remote_actions'] != 'none' or inventory['data_only'] is not True:
        raise ValueError('unsupported blanket permission or remote action')
    return {'schema': 'xrai.eval.gitea.exposure.verification.v1', 'data_only': True, 'data_acceptance': True, 'snapshot_sha256': PINNED_SNAPSHOT_SHA256, 'inventory_sha256': sha((directory / 'decisions.json').read_bytes()), 'alerts': 55, 'prioritized_critical_high': sum(r['priority'] == 1 for r in rows), 'execution_allowed': False, 'blocking_alerts': sorted(r['number'] for r in rows), 'reasons': [{'number': r['number'], 'ghsa_id': r['ghsa_id'], 'decision': r['decision'], 'pending': r['pending']} for r in sorted(rows, key=lambda r: (r['priority'], r['number']))]}


def check_consumer_workflow(text):
    """Check guard order in this workflow's explicit Go-job subset.

    This is a bounded source check, not a general YAML parser or CI execution.
    Unsupported aliases, merged mappings and error/condition overrides fail.
    """
    match = re.search(r'(?ms)^  go:\n(.*?)^  python:\n', text)
    if not match:
        raise ValueError('explicit bounded Go job missing')
    go = match[1]
    if any(marker in go for marker in ('continue-on-error:', '<<:', 'shell: sh', 'shell: python')):
        raise ValueError('unsupported YAML/error/shell override in Go job')
    if re.search(r'(?m)^\s*(?:-\s*)?[A-Za-z_-]+:\s*[&*]\w+|^\s*-\s*\*\w+', go):
        raise ValueError('unsupported YAML alias or anchor in Go job')
    if '        shell: bash' not in go:
        raise ValueError('Go job must retain fail-on-error bash default')
    starts = list(re.finditer(r'(?m)^      - ', go))
    chunks = [go[m.start():starts[i + 1].start() if i + 1 < len(starts) else len(go)] for i, m in enumerate(starts)]
    steps = []
    for chunk in chunks:
        lines = chunk.splitlines()
        run = re.search(r'(?m)^        run: (.*)$', chunk)
        commands = []
        if run:
            if run[1] == '|':
                after = chunk[run.end():].splitlines()
                commands = [line.strip() for line in after if line.startswith('          ') and line.strip()]
            else:
                commands = [run[1]]
        condition = re.search(r'(?m)^        if: (.*)$', chunk)
        steps.append({'source': chunk, 'commands': commands, 'condition': condition[1] if condition else None})
    download = 'python eval/scripts/verify_gitea_exposure.py --require-execution --phase download'
    probe = 'python eval/scripts/verify_gitea_exposure.py --require-execution --phase probe'
    guards = [i for i, step in enumerate(steps) if step['commands'] == [download] and step['condition'] is None]
    if len(guards) != 1:
        raise ValueError('unique unconditional download admission guard required')
    guard = guards[0]
    guarded = []
    probes = []
    for i, step in enumerate(steps):
        affected = 'actions/setup-go@' in step['source'] or any('run_l5_go.py' in c or 'go mod download' in c for c in step['commands'])
        if not affected:
            continue
        if i <= guard:
            raise ValueError('Go execution precedes download guard')
        guarded.append(i)
        if step['condition'] is not None:
            if step['condition'] != '${{ !cancelled() }}' or not step['commands'] or step['commands'][0] != probe:
                raise ValueError('conditional Go path must gate probe as its first command')
        if any('run_l5_go.py probe' in c for c in step['commands']):
            probes.append(i)
    if len(probes) != 2 or not any('go mod download' in c for step in steps for c in step['commands']):
        raise ValueError('expected two probes and pinned module download required')
    return {'verified': True, 'method': 'bounded explicit Go job source/step-order check; general YAML validity checked separately', 'download_guard_step_index': guard, 'affected_guarded_step_indices': guarded, 'probe_step_indices': probes, 'execution_observed': False, 'upstream_executed': False}


def require_execution(phase='probe', directory=DIRECTORY, root=ROOT):
    if phase not in PHASES:
        raise ValueError('unknown execution phase')
    result = check_data(directory, root)
    raise PermissionError('S01 blocks ' + phase + '; unresolved alerts: ' + ','.join(map(str, result['blocking_alerts'])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check-data', action='store_true')
    action.add_argument('--require-execution', action='store_true')
    parser.add_argument('--phase', choices=PHASES, default='probe')
    args = parser.parse_args()
    try:
        result = check_data() if args.check_data else require_execution(args.phase)
    except (ValueError, PermissionError, KeyError, OSError, TypeError) as error:
        print(json.dumps({'verified': False, 'execution_allowed': False, 'error': str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

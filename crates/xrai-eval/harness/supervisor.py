"""Trusted domain lifecycle supervisor, outside the executed PID namespace.

Linux pins the held namespace init with a pidfd before release. PID enumeration is
never the teardown proof. macOS local process groups only support bounded known
smokes; arbitrary-agent operations require a disposable adapter (unavailable).
"""
import errno
import json
import os
from pathlib import Path
import platform
import re
import select
import selectors
import signal
import subprocess
import tempfile
import time
import uuid

from adapters import MacDisposableAdapter, sandbox


def map_held_user_namespace(pid):
    """The external-userns gate delegates UID/GID maps to this supervisor.

    One current-user mapping only, in a fresh child namespace. Never map extra
    host identities or retain host supplementary groups. The bwrap init is held
    and pidfd-pinned before this function is called.
    """
    proc = Path('/proc')/str(pid)
    for name in ['uid_map','gid_map']:
        if (proc/name).read_text().strip():
            raise RuntimeError('expected fresh unmapped user namespace')
    (proc/'setgroups').write_text('deny')
    uid, gid = os.getuid(), os.getgid()
    (proc/'uid_map').write_text(f'{uid} {uid} 1\n')
    (proc/'gid_map').write_text(f'{gid} {gid} 1\n')
    return {'uid':uid,'gid':gid,'count':1,'setgroups':'deny'}


class LinuxDomain:
    containment = 'linux_pid_namespace'

    def __init__(self):
        self.pidfd = None
        self.last_cleanup = 'not_created'
        self.setup_streams = {'stdout': b'', 'stderr': b''}
        self.evidence = {'init_pid': None, 'pid_namespace': None,
                         'init_held_before_pin': False, 'pidfd_exit_observed': False,
                         'wrapper_reaped': False}

    def launch(self, wrapped, workspace, env, deadline):
        if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
            raise RuntimeError('pidfd APIs required; refusing weaker teardown')
        info_r, info_w = os.pipe()
        gate_r, gate_w = os.pipe()
        process = None
        try:
            wrapped = [wrapped[0], '--info-fd', str(info_w), '--userns-block-fd', str(gate_r), *wrapped[1:]]
            process = subprocess.Popen(wrapped, cwd=workspace, env=env,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True,
                                       pass_fds=(info_w, gate_r))
            os.close(info_w); info_w = None
            os.close(gate_r); gate_r = None
            os.set_blocking(info_r, False)
            data = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('domain setup deadline exceeded')
                if select.select([info_r], [], [], .02)[0]:
                    chunk = os.read(info_r, 4096)
                    data.extend(chunk)
                    if len(data) > 16384:
                        raise RuntimeError('bubblewrap identity exceeds limit')
                    try:
                        identity = json.loads(data)
                        break
                    except (ValueError, UnicodeDecodeError):
                        if not chunk:
                            raise RuntimeError('bubblewrap failed before init identity')
                if process.poll() is not None:
                    raise RuntimeError('bubblewrap exited before init pin')
            pid = identity['child-pid']
            if type(pid) is not int or pid <= 1:
                raise RuntimeError('invalid init PID')
            # Child is held on bwrap's setup gate, so no PID-reuse race between
            # identity and pidfd_open. Gate release happens only after the pin.
            self.pidfd = os.pidfd_open(pid)
            namespace_id = identity.get('pid-namespace')
            if type(namespace_id) is not int or namespace_id == os.stat('/proc/self/ns/pid').st_ino:
                raise RuntimeError('trusted wrapper did not establish a private PID namespace')
            self.evidence.update(init_pid=pid, pid_namespace=f'pid:[{namespace_id}]',
                                 init_held_before_pin=True)
            self.evidence['user_namespace_mapping'] = map_held_user_namespace(pid)
            os.write(gate_w, b'1')
            return process
        except BaseException:
            if self.pidfd is not None:
                self.last_cleanup, _ = self.destroy(process)
            elif process is not None:
                # Before release, there can be no untrusted descendants.
                process.kill()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            if process is not None:
                for name in self.setup_streams:
                    stream = getattr(process,name)
                    os.set_blocking(stream.fileno(),False)
                    try:
                        self.setup_streams[name] = os.read(stream.fileno(),16384)
                    except BlockingIOError:
                        pass
                    stream.close()
            raise
        finally:
            for fd in (info_r, info_w, gate_r, gate_w):
                if fd is not None:
                    os.close(fd)

    def destroy(self, process):
        errors = []
        dead = self.evidence['pidfd_exit_observed']
        if self.pidfd is not None:
            try:
                signal.pidfd_send_signal(self.pidfd, signal.SIGKILL)
            except OSError as error:
                if error.errno != errno.ESRCH:
                    errors.append(str(error))
            try:
                dead = bool(select.select([self.pidfd], [], [], 1)[0])
            except OSError as error:
                errors.append(str(error))
                dead = False
            self.evidence['pidfd_exit_observed'] = dead
            os.close(self.pidfd)
            self.pidfd = None
        if process is not None:
            try:
                process.wait(timeout=1)
                self.evidence['wrapper_reaped'] = True
            except subprocess.TimeoutExpired:
                # Auxiliary cleanup cannot turn missing namespace proof into success.
                process.kill()
                try:
                    process.wait(timeout=.25)
                except subprocess.TimeoutExpired:
                    errors.append('wrapper not reaped')
        return ('confirmed' if dead and self.evidence['wrapper_reaped'] else 'incomplete'), errors


class KnownSmokeDomain:
    containment = 'macos_local_known_smoke'

    def __init__(self):
        self.evidence = {'wrapper_reaped': False, 'scope': 'process_group_only_no_daemon_guarantee'}

    def launch(self, wrapped, workspace, env, deadline):
        return subprocess.Popen(wrapped, cwd=workspace, env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)

    def destroy(self, process):
        errors = []
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append(str(error))
        try:
            process.wait(timeout=.25)
            self.evidence['wrapper_reaped'] = True
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=.25)
            except subprocess.TimeoutExpired:
                errors.append('wrapper not reaped')
        return 'not_proven', errors


def valid_mapping(receipt):
    mapping = receipt.get('user_namespace_mapping')
    return (isinstance(mapping,dict) and set(mapping)=={'uid','gid','count','setgroups'} and
            all(type(mapping[k]) is int and 0 <= mapping[k] < 2**32-1 for k in ['uid','gid']) and
            type(mapping['count']) is int and mapping['count']==1 and mapping['setgroups']=='deny')


def confirmed_receipt(turn):
    receipt = turn['termination_evidence']
    pid = receipt.get('init_pid')
    namespace = receipt.get('pid_namespace')
    return (turn['containment']=='linux_pid_namespace' and turn['cleanup_status']=='confirmed' and
            type(pid) is int and 1 < pid < 2**31 and isinstance(namespace,str) and
            re.fullmatch(r'pid:\[[1-9][0-9]*\]',namespace) is not None and
            all(receipt.get(k) is True for k in ['init_held_before_pin','pidfd_exit_observed','wrapper_reaped']))


def verify_receipt(turn):
    receipt=turn['termination_evidence']
    domain=turn['domain_id']
    try:
        identifier=uuid.UUID(domain)
    except (ValueError,TypeError,AttributeError):
        raise ValueError('invalid execution domain identity') from None
    if str(identifier)!=domain or identifier.version!=4 or not isinstance(receipt,dict):
        raise ValueError('invalid execution domain identity/evidence')
    confirmed=confirmed_receipt(turn)
    if turn['cleanup_status']=='confirmed' and not confirmed:
        raise ValueError('confirmed teardown lacks concrete namespace/init evidence')
    eligible=confirmed and valid_mapping(receipt)
    if type(turn['eligible_for_agent_run']) is not bool or turn['eligible_for_agent_run'] != eligible:
        raise ValueError('agent eligibility disagrees with teardown evidence')
    if (turn['cleanup_status']=='incomplete') != (turn['status']=='teardown_failed'):
        raise ValueError('incomplete cleanup must invalidate result')
    if turn['cleanup_status']=='not_proven' and turn['containment']!='macos_local_known_smoke':
        raise ValueError('unproven local-smoke receipt must identify its platform')


def supervise(command, workspace, *, timeout, output_limit, cancel=None, arbitrary_agent=False,
              domain_factory=None):
    if timeout <= 0 or output_limit < 1:
        raise ValueError('positive timeout/output_limit required')
    if not command or not Path(command[0]).is_absolute():
        raise ValueError('adapter executable must be absolute')
    start = time.monotonic()
    saved = {'stdout': bytearray(), 'stderr': bytearray()}
    observed = {'stdout': 0, 'stderr': 0}
    result = {'status': 'spawn_error', 'execution_status': 'spawn_error', 'exit_code': None,
              'sandbox': 'Linux bubblewrap' if platform.system() == 'Linux' else 'macOS Seatbelt',
              'containment': 'unavailable', 'cleanup_status': 'not_created',
              'domain_id': str(uuid.uuid4()), 'termination_evidence': {},
              'eligible_for_agent_run': False, 'diagnostic': None}
    if cancel is not None and cancel.is_set():
        result.update(status='cancelled', execution_status='cancelled')
    elif arbitrary_agent and platform.system() != 'Linux':
        result.update(status='containment_unavailable', execution_status='containment_unavailable',
                      diagnostic=MacDisposableAdapter.reason)
    else:
        domain = (domain_factory or (LinuxDomain if platform.system() == 'Linux' else KnownSmokeDomain))()
        result['containment'] = domain.containment
        process = None
        cleanup_attempted = False
        try:
            with tempfile.TemporaryDirectory(prefix='xrai-profile-') as profiles:
                wrapped, result['sandbox'] = sandbox(command, workspace, profiles)
                env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
                       'HOME': str(Path(workspace).resolve()), 'TMPDIR': str(Path(workspace).resolve())}
                process = domain.launch(wrapped, workspace, env, start+timeout)
                status = None
                with selectors.DefaultSelector() as sel:
                    for key in saved:
                        pipe = getattr(process, key)
                        os.set_blocking(pipe.fileno(), False)
                        sel.register(pipe, selectors.EVENT_READ, key)
                    while True:
                        if cancel is not None and cancel.is_set():
                            status = 'cancelled'
                        elif time.monotonic() >= start+timeout:
                            status = 'timeout'
                        elif process.poll() is not None:
                            status = 'ok' if process.returncode == 0 else 'error'
                        if status is not None:
                            break
                        for event, _ in sel.select(.02):
                            chunk = os.read(event.fd, 16384)
                            if not chunk:
                                sel.unregister(event.fileobj)
                                continue
                            key = event.data
                            observed[key] += len(chunk)
                            room = max(0, output_limit-sum(len(v) for v in saved.values()))
                            saved[key].extend(chunk[:room])
                            if sum(observed.values()) > output_limit:
                                status = 'output_limit'
                        if status is not None:
                            break
                    cleanup, errors = domain.destroy(process)
                    cleanup_attempted = True
                    # Drain only bounded time after domain termination, preserving
                    # captured bytes even when cleanup is inconclusive.
                    drain_until = time.monotonic()+.25
                    while sel.get_map() and time.monotonic() < drain_until:
                        for event, _ in sel.select(.02):
                            chunk = os.read(event.fd, 16384)
                            if not chunk:
                                sel.unregister(event.fileobj)
                                continue
                            key = event.data
                            observed[key] += len(chunk)
                            room = max(0, output_limit-sum(len(v) for v in saved.values()))
                            saved[key].extend(chunk[:room])
                            if sum(observed.values()) > output_limit and status in ('ok', 'error'):
                                status = 'output_limit'
                result.update(execution_status=status, status='teardown_failed' if cleanup == 'incomplete' else status,
                              cleanup_status=cleanup, exit_code=process.returncode,
                              termination_evidence=domain.evidence, diagnostic='; '.join(errors) or None)
                result['eligible_for_agent_run'] = (domain.containment == 'linux_pid_namespace' and cleanup == 'confirmed')
        except (OSError, RuntimeError, TimeoutError, ValueError) as error:
            result['diagnostic'] = str(error)
            if isinstance(error, TimeoutError):
                result.update(status='timeout', execution_status='timeout')
            result['termination_evidence'] = domain.evidence
            result['cleanup_status'] = getattr(domain,'last_cleanup','not_created')
            if result['cleanup_status'] == 'incomplete':
                result['status'] = 'teardown_failed'
            for name, data in getattr(domain,'setup_streams',{}).items():
                observed[name] += len(data)
                room = max(0, output_limit-sum(len(v) for v in saved.values()))
                saved[name].extend(data[:room])
        finally:
            if process is not None:
                if not cleanup_attempted:
                    cleanup, errors = domain.destroy(process)
                    result.update(cleanup_status=cleanup, termination_evidence=domain.evidence,
                                  status='teardown_failed' if cleanup == 'incomplete' else result['status'])
                    if errors:
                        result['diagnostic'] = '; '.join([result['diagnostic'] or '', *errors])
                for stream in (process.stdout, process.stderr):
                    stream.close()
    result['eligible_for_agent_run'] = confirmed_receipt(result) and valid_mapping(result['termination_evidence'])
    result.update(elapsed_seconds=time.monotonic()-start,
                  streams={k: bytes(v) for k, v in saved.items()}, observed=observed)
    return result

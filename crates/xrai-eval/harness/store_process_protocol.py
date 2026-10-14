"""Bounded owned-process session I/O. This helper does not authorize execution."""
import base64
import hashlib
import json
import math
import os
import selectors
import signal
import subprocess
import threading
import time

MAX_FRAME = 512 * 1024
MAX_STDERR = 64 * 1024
MAX_COMMANDS = 512


class SessionFault(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise SessionFault('duplicate_json_key')
            result[key] = value
        return result
    def constant(_):
        raise SessionFault('nonfinite_json')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise SessionFault('json_depth')
        if type(item) is float and not math.isfinite(item):
            raise SessionFault('nonfinite_json')
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
    return value


def captured(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'base64': base64.b64encode(raw).decode('ascii')}


class SessionProcess:
    """One in-flight command, no implicit retry, fatal transport faults end the instance."""
    def __init__(self, command, *, frame_limit=MAX_FRAME, stderr_limit=MAX_STDERR):
        if not (type(command) is list and command and all(type(arg) is str and arg for arg in command)):
            raise ValueError('explicit_owned_command_required')
        if not (type(frame_limit) is int and 64 <= frame_limit <= MAX_FRAME and type(stderr_limit) is int and 0 <= stderr_limit <= MAX_STDERR):
            raise ValueError('bounded_process_limits')
        self.command = command[:]
        self.frame_limit, self.stderr_limit = frame_limit, stderr_limit
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=True, bufsize=0, env={})
        self.selector = selectors.DefaultSelector()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            os.set_blocking(stream.fileno(), False)
        self.selector.register(self.process.stdout, selectors.EVENT_READ, 'stdout')
        self.selector.register(self.process.stderr, selectors.EVENT_READ, 'stderr')
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._alive = True
        self._last_id = 0
        self._stderr = bytearray()
        self._rows = []
        self._termination = None

    def _kill(self, reason):
        self._alive = False
        signal_error = None
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # A vanished group may be undiscoverable in a restricted host.
            # Preserve uncertainty; only the owned direct child is a fallback.
            signal_error = 'process_group_signal_denied'
            if self.process.poll() is None:
                self.process.kill()
        try:
            code = self.process.wait(timeout=2)
            reaped = True
        except subprocess.TimeoutExpired:
            code, reaped = None, False
        try:
            os.killpg(self.process.pid, 0)
            group_gone = False
        except ProcessLookupError:
            group_gone = True
        except PermissionError:
            group_gone = None
        # Include diagnostics emitted after stdout EOF or while terminating.
        while len(self._stderr) <= self.stderr_limit:
            try:
                chunk = os.read(self.process.stderr.fileno(), min(65536, self.stderr_limit + 1 - len(self._stderr)))
            except (BlockingIOError, OSError):
                break
            if not chunk:
                break
            self._stderr.extend(chunk)
        self._termination = {'reason': reason, 'exit_code': code, 'parent_reaped': reaped,
                             'process_group_absent': group_gone, 'signal_error': signal_error,
                             'stderr_limit_exceeded': len(self._stderr) > self.stderr_limit}
        self.selector.close()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()

    def _read(self, key, output):
        if key.data == 'stderr':
            capacity = self.stderr_limit + 1 - len(self._stderr)
            chunk = os.read(key.fd, min(65536, max(1, capacity)))
            if not chunk:
                self.selector.unregister(key.fileobj)
            else:
                self._stderr.extend(chunk)
                if len(self._stderr) > self.stderr_limit:
                    raise SessionFault('stderr_limit')
            return None
        capacity = self.frame_limit + 1 - len(output)
        chunk = os.read(key.fd, min(65536, max(1, capacity)))
        if not chunk:
            self.selector.unregister(key.fileobj)
            return 'eof'
        output.extend(chunk)
        if len(output) > self.frame_limit:
            raise SessionFault('response_frame_limit')
        return 'data'

    def call(self, request, *, timeout_ms=30_000):
        started = time.monotonic()
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 60_000:
            raise ValueError('bounded_deadline')
        deadline = started + timeout_ms / 1000
        if not self._lock.acquire(blocking=False):
            raise SessionFault('session_busy')
        raw, output, written, outcome = b'', bytearray(), 0, None
        admitted = False
        try:
            if not self._alive:
                raise SessionFault('instance_ended')
            if type(request) is not dict or type(request.get('command_id')) is not int or not self._last_id < request['command_id'] <= MAX_COMMANDS:
                raise ValueError('monotonic_command_id')
            raw = canonical(request) + b'\n'
            if len(raw) > self.frame_limit:
                raise ValueError('request_frame_limit')
            # No pending stdout may become the answer to a different command.
            for key, _ in self.selector.select(0):
                status = self._read(key, output)
                if key.data == 'stdout':
                    raise SessionFault('unsolicited_stdout' if status != 'eof' else 'unexpected_eof')
            if self.process.poll() is not None:
                raise SessionFault('unexpected_exit')
            self._last_id = request['command_id']
            admitted = True
            self.selector.register(self.process.stdin, selectors.EVENT_WRITE, 'stdin')
            while True:
                if self._cancel.is_set():
                    raise SessionFault('operation_cancelled')
                left = deadline - time.monotonic()
                if left <= 0:
                    raise SessionFault('write_read_deadline')
                events = self.selector.select(min(left, .02))
                if not events:
                    continue
                for key, _ in events:
                    if key.data == 'stdin':
                        try:
                            written += os.write(key.fd, raw[written:written + 65536])
                        except BrokenPipeError as error:
                            raise SessionFault('stdin_closed') from error
                        if written == len(raw):
                            self.selector.unregister(self.process.stdin)
                    else:
                        status = self._read(key, output)
                        if status == 'eof' and b'\n' not in output:
                            raise SessionFault('partial_response_eof')
                if b'\n' not in output:
                    continue
                if written != len(raw):
                    raise SessionFault('response_before_complete_request')
                if output.count(b'\n') != 1 or not output.endswith(b'\n'):
                    raise SessionFault('extra_response_bytes')
                response = decode(bytes(output))
                if type(response) is not dict or type(response.get('command_id')) is not int or response['command_id'] != request['command_id']:
                    raise SessionFault('response_command_identity')
                for key, _ in self.selector.select(0):
                    status = self._read(key, output)
                    if key.data == 'stdout' and status != 'eof':
                        raise SessionFault('extra_response_bytes')
                if time.monotonic() > deadline:
                    raise SessionFault('write_read_deadline')
                if self._cancel.is_set():
                    raise SessionFault('operation_cancelled')
                outcome = 'response'
                return response
        except (SessionFault, OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
            outcome = str(error)
            if self._alive:
                self._kill(outcome)
            raise SessionFault(outcome) from error
        finally:
            if admitted or outcome is not None:
                self._rows.append({'command_id': request.get('command_id') if type(request) is dict else None,
                                   'started_monotonic': started, 'elapsed_seconds': time.monotonic() - started,
                                   'timeout_ms': timeout_ms, 'request': captured(raw), 'written_bytes': written,
                                   'response': captured(bytes(output)), 'outcome': outcome,
                                   'operation_may_have_applied': admitted and written > 0})
            self._lock.release()

    def close(self, command_id, *, timeout_ms=5000):
        deadline = time.monotonic() + timeout_ms / 1000
        response = self.call({'command_id': command_id, 'operation': 'close'}, timeout_ms=timeout_ms)
        with self._lock:
            try:
                self.process.stdin.close()
                while any(key.data in ('stdout', 'stderr') for key in self.selector.get_map().values()):
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise SessionFault('shutdown_deadline')
                    for key, _ in self.selector.select(left):
                        output = bytearray()
                        status = self._read(key, output)
                        if key.data == 'stdout' and status != 'eof':
                            raise SessionFault('output_after_close')
                code = self.process.wait(timeout=max(0.001, deadline - time.monotonic()))
                if code != 0:
                    raise SessionFault('nonzero_exit')
                self._kill('explicit_close')
                return response
            except (SessionFault, subprocess.TimeoutExpired, OSError) as error:
                self._kill(str(error))
                raise SessionFault(str(error)) from error

    def abort(self):
        with self._lock:
            if self._alive:
                self._kill('explicit_abort')

    def cancel(self):
        """Signal the in-flight operation without acquiring its I/O lock."""
        self._cancel.set()

    def record(self):
        with self._lock:
            return decode(canonical({'schema_version': 'xrai.eval.store-process.v1', 'command': self.command,
                                     'pid': self.process.pid, 'frame_limit': self.frame_limit,
                                     'stderr_limit': self.stderr_limit, 'stderr': captured(bytes(self._stderr)),
                                     'active': self._alive, 'rows': self._rows, 'termination': self._termination,
                                     'native_execution_authorized_by_helper': False}))

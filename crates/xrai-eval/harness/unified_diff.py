"""Experimental data-only unified diff intake; never reads repository paths or runs Git.

Profile: exact a/b relative paths, LF patch records, UTF-8 source bytes, no rename,
binary or combined diff. CR is source content. Full captured HEAD is mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Mapping

PROFILE = 'captured-unified-diff-v1'
MAX_DIFF_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
MAX_FILES = 128
MAX_HUNKS = 4096
MAX_LINES = 100_000
MAX_RECORDS = 200_000
MARKER = b'\\ No newline at end of file\n'
HEADER = re.compile(rb'@@ -(\d{1,8})(?:,(\d{1,8}))? \+(\d{1,8})(?:,(\d{1,8}))? @@\n')


class DiffError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DiffError(code)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path(path: str) -> str:
    _require(type(path) is str and 0 < len(path) <= 4096, 'invalid_path')
    try:
        encoded = path.encode('utf-8')
    except UnicodeEncodeError as error:
        raise DiffError('invalid_path') from error
    _require(0 < len(encoded) <= 4096, 'invalid_path')
    _require(not path.startswith('/') and '\\' not in path and ':' not in path,
             'invalid_path')
    _require(all(part not in ('', '.', '..') for part in path.split('/')), 'invalid_path')
    _require(not any(ord(c) < 33 or ord(c) == 127 for c in path), 'invalid_path')
    return path


def _lines(source: bytes) -> tuple[bytes, ...]:
    if not source:
        return ()
    _require(source.count(b'\n') + int(not source.endswith(b'\n')) <= MAX_LINES, 'line_limit')
    parts = source.split(b'\n')
    result = tuple(part + b'\n' for part in parts[:-1])
    if parts[-1]:
        result += (parts[-1],)
    _require(len(result) <= MAX_LINES, 'line_limit')
    return result


def _snapshot(files: Mapping[str, bytes]) -> dict[str, bytes]:
    _require(isinstance(files, Mapping) and len(files) <= MAX_FILES, 'file_limit')
    result = {}
    size = 0
    for path, source in files.items():
        _path(path)
        _require(type(source) is bytes and len(source) <= MAX_FILE_BYTES, 'source_limit')
        size += len(source)
        _require(size <= MAX_SNAPSHOT_BYTES, 'snapshot_limit')
        try:
            source.decode('utf-8')
        except UnicodeDecodeError as error:
            raise DiffError('source_utf8') from error
        _lines(source)
        result[path] = source
    return result


def snapshot_id(files: Mapping[str, bytes]) -> str:
    checked = _snapshot(files)
    records = [[p, _sha(b), len(b)] for p, b in sorted(checked.items())]
    return _sha(json.dumps(records, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


@dataclass(frozen=True)
class Hunk:
    base_start: int
    base_end: int
    head_start: int
    head_end: int
    removed: bytes
    replacement: bytes


@dataclass(frozen=True)
class FileChange:
    path: str
    kind: str
    base_present: bool
    head_present: bool
    base_sha256: str | None
    head_sha256: str | None
    hunks: tuple[Hunk, ...]


@dataclass(frozen=True)
class ValidatedDiff:
    diff_sha256: str
    base_snapshot_id: str
    head_snapshot_id: str
    changes: tuple[FileChange, ...]

    def receipt(self) -> dict:
        return {'schema': PROFILE, 'scope': 'data_only_typed_reconstruction',
                'diff_sha256': self.diff_sha256, 'base_snapshot_id': self.base_snapshot_id,
                'head_snapshot_id': self.head_snapshot_id, 'integral_head_verified': True,
                'native_p3_support': False, 'changes': [
                    {'path': c.path, 'kind': c.kind, 'base_present': c.base_present,
                     'head_present': c.head_present, 'base_sha256': c.base_sha256,
                     'head_sha256': c.head_sha256, 'hunks': [
                         {'base_span': [h.base_start, h.base_end],
                          'head_span': [h.head_start, h.head_end],
                          'removed_sha256': _sha(h.removed),
                          'replacement_sha256': _sha(h.replacement),
                          'replacement_hex': h.replacement.hex()} for h in c.hunks]}
                    for c in self.changes]}


def apply_typed(base: Mapping[str, bytes], changes: tuple[FileChange, ...]) -> dict[str, bytes]:
    """Consumer of typed byte spans; does not parse diff or search/fuzz source content."""
    result = _snapshot(base)
    _require(type(changes) is tuple and len(changes) <= MAX_FILES, 'typed_shape')
    seen = set()
    count = 0
    total_bytes = sum(len(source) for source in result.values())
    for change in changes:
        _require(type(change) is FileChange, 'typed_shape')
        path = _path(change.path)
        _require(path not in seen, 'duplicate_path')
        seen.add(path)
        _require(type(change.base_present) is bool and type(change.head_present) is bool,
                 'typed_shape')
        _require(change.kind in ('create', 'delete', 'modify'), 'typed_shape')
        _require((change.base_present, change.head_present) ==
                 {'create': (False, True), 'delete': (True, False), 'modify': (True, True)}[change.kind],
                 'typed_presence')
        _require((path in result) == change.base_present, 'typed_presence')
        source = result[path] if change.base_present else b''
        _require(change.base_sha256 == (_sha(source) if change.base_present else None), 'typed_hash')
        _require(type(change.hunks) is tuple and bool(change.hunks), 'typed_shape')
        output = bytearray()
        position = 0
        for hunk in change.hunks:
            count += 1
            _require(count <= MAX_HUNKS and type(hunk) is Hunk, 'hunk_limit')
            _require(all(type(n) is int for n in (hunk.base_start, hunk.base_end,
                          hunk.head_start, hunk.head_end)), 'typed_shape')
            _require(position <= hunk.base_start <= hunk.base_end <= len(source), 'typed_span')
            _require(type(hunk.removed) is bytes and type(hunk.replacement) is bytes,
                     'typed_shape')
            _require(source[hunk.base_start:hunk.base_end] == hunk.removed, 'typed_content')
            _require(len(hunk.replacement) <= MAX_FILE_BYTES, 'source_limit')
            _require(len(output) + hunk.base_start - position <= MAX_FILE_BYTES, 'source_limit')
            output.extend(source[position:hunk.base_start])
            _require(hunk.head_start == len(output), 'typed_span')
            _require(len(output) + len(hunk.replacement) <= MAX_FILE_BYTES, 'source_limit')
            output.extend(hunk.replacement)
            _require(len(output) <= MAX_FILE_BYTES, 'source_limit')
            _require(hunk.head_end == len(output), 'typed_span')
            position = hunk.base_end
        _require(len(output) + len(source) - position <= MAX_FILE_BYTES, 'source_limit')
        output.extend(source[position:])
        reconstructed = bytes(output)
        _require(len(reconstructed) <= MAX_FILE_BYTES, 'source_limit')
        total_bytes += len(reconstructed) - len(source)
        _require(total_bytes <= MAX_SNAPSHOT_BYTES, 'snapshot_limit')
        if change.head_present:
            _require(change.head_sha256 == _sha(reconstructed), 'typed_hash')
            result[path] = reconstructed
        else:
            _require(reconstructed == b'' and change.head_sha256 is None, 'typed_presence')
            del result[path]
    return _snapshot(result)


def decode_unified(diff: bytes, base: Mapping[str, bytes], head: Mapping[str, bytes]) -> ValidatedDiff:
    """Validate all hunks and reconstruct the whole mandatory captured HEAD exactly."""
    _require(type(diff) is bytes and len(diff) <= MAX_DIFF_BYTES, 'diff_limit')
    before, after = _snapshot(base), _snapshot(head)
    _require(not diff or diff.endswith(b'\n'), 'diff_framing')
    _require(diff.count(b'\n') <= MAX_RECORDS, 'record_limit')
    physical = tuple(part + b'\n' for part in diff.split(b'\n')[:-1]) if diff else ()
    _require(len(physical) <= MAX_RECORDS, 'record_limit')
    index = 0
    changes = []
    seen = set()
    hunk_count = 0

    def take_path(prefix: bytes, side: bytes) -> str | None:
        nonlocal index
        _require(index < len(physical) and physical[index].startswith(prefix), 'file_header')
        raw = physical[index][len(prefix):-1]
        index += 1
        if raw == b'/dev/null':
            return None
        _require(raw.startswith(side + b'/'), 'invalid_path')
        try:
            return _path(raw[2:].decode('utf-8'))
        except UnicodeDecodeError as error:
            raise DiffError('invalid_path') from error

    while index < len(physical):
        old, new = take_path(b'--- ', b'a'), take_path(b'+++ ', b'b')
        _require(old is not None or new is not None, 'absent_both')
        _require(old is None or new is None or old == new, 'rename_unsupported')
        path = old if old is not None else new
        _require(path not in seen, 'duplicate_path')
        seen.add(path)
        _require(len(seen) <= MAX_FILES, 'file_limit')
        kind = 'create' if old is None else 'delete' if new is None else 'modify'
        _require(path in before if old is not None else path not in before,
                 'base_absent' if old is not None else 'create_present')
        _require(path in after if new is not None else path not in after,
                 'head_absent' if new is not None else 'delete_present')
        source = before[path] if old is not None else b''
        original_lines = _lines(source)
        head_lines = _lines(after[path]) if new is not None else ()
        offsets = [0]
        for line in original_lines:
            offsets.append(offsets[-1] + len(line))
        previous = 0
        output = bytearray()
        output_line_count = 0
        hunks = []
        while index < len(physical) and not physical[index].startswith(b'--- '):
            match = HEADER.fullmatch(physical[index])
            _require(match is not None, 'newline_marker' if physical[index] == MARKER else 'hunk_count')
            index += 1
            hunk_count += 1
            _require(hunk_count <= MAX_HUNKS, 'hunk_limit')
            bs, bn, hs, hn = [int(v) if v is not None else 1 for v in match.groups()]
            _require(max(bs, bn, hs, hn) <= MAX_LINES, 'line_limit')
            _require((bn == 0 or bs > 0) and (hn == 0 or hs > 0), 'hunk_origin')
            bi, hi = bs - 1 if bn else bs, hs - 1 if hn else hs
            _require(previous <= bi <= len(original_lines), 'hunk_overlap')
            _require(bi + bn <= len(original_lines), 'hunk_count')
            gap = original_lines[previous:bi]
            output.extend(b''.join(gap))
            output_line_count += len(gap)
            removed, added = [], []
            marked = [False, False]
            while len(removed) < bn or len(added) < hn:
                _require(index < len(physical), 'hunk_count')
                record = physical[index]
                _require(record != MARKER, 'newline_marker')
                _require(record[:1] in (b' ', b'-', b'+'), 'record')
                prefix, content = record[:1], record[1:]
                index += 1
                sides = (0, 1) if prefix == b' ' else (0,) if prefix == b'-' else (1,)
                _require(not any(marked[s] for s in sides), 'newline_marker')
                if index < len(physical) and physical[index] == MARKER:
                    content = content[:-1]
                    index += 1
                    for side in sides:
                        marked[side] = True
                if 0 in sides:
                    removed.append(content)
                if 1 in sides:
                    added.append(content)
                _require(len(removed) <= bn and len(added) <= hn, 'hunk_count')
            _require(not marked[0] or bi + bn == len(original_lines), 'newline_marker')
            _require(not marked[1] or hi + hn == len(head_lines), 'newline_marker')
            _require(tuple(removed) == original_lines[bi:bi + bn], 'base_mismatch')
            _require(hi == output_line_count, 'head_origin')
            head_start = len(output)
            replacement = b''.join(added)
            output.extend(replacement)
            _require(len(output) <= MAX_FILE_BYTES, 'source_limit')
            hunks.append(Hunk(offsets[bi], offsets[bi + bn], head_start, len(output),
                              b''.join(removed), replacement))
            output_line_count += len(added)
            previous = bi + bn
        _require(bool(hunks), 'missing_hunks')
        output.extend(b''.join(original_lines[previous:]))
        reconstructed = bytes(output)
        _require(reconstructed == (after[path] if new is not None else b''), 'head_mismatch')
        changes.append(FileChange(path, kind, old is not None, new is not None,
                                  _sha(source) if old is not None else None,
                                  _sha(reconstructed) if new is not None else None, tuple(hunks)))
    typed = tuple(changes)
    _require(apply_typed(before, typed) == after, 'head_mismatch')
    return ValidatedDiff(_sha(diff), snapshot_id(before), snapshot_id(after), typed)

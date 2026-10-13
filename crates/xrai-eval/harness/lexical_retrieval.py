"""Owned, immutable UTF-8 source retrieval. No language execution or semantic claims.

BM25 (Robertson/Sparck Jones positive IDF) and sublinear TF-IDF cosine share
exactly the same chunks, identifier tokenizer, and path weighting. Inputs are
only caller-owned path/bytes; expected labels and repository identity are absent.
"""
from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType


def digest(data):
    return sha256(data).hexdigest()


def wire_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def tokenize(text):
    result = []
    for word in re.findall(r'[^\W]+', text, re.UNICODE):
        whole = word.casefold()
        result.append(whole)
        components = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', word)
        components = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', components)
        parts = [p.casefold() for p in re.split(r'[_\s]+', components) if p]
        if parts != [whole]:
            result.extend(parts)
    return result


def _integer(name, value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be integer in [{low}, {high}]')


class LexicalIndex:
    """In-memory source snapshot, bounded to 128 files/16 MiB/4096 chunks.

    Handles bind content/configuration/span, not authorization or P3 retention.
    A fresh index with identical bytes/config intentionally has identical handles.
    """
    def __init__(self, files: Mapping[str, bytes], *, chunk_lines=40,
                 overlap_lines=10, path_term_weight=3, k1=1.2, b=.75):
        _integer('chunk_lines', chunk_lines, 1, 200)
        _integer('overlap_lines', overlap_lines, 0, chunk_lines-1)
        _integer('path_term_weight', path_term_weight, 0, 10)
        if isinstance(k1, bool) or not isinstance(k1, (int, float)) or not math.isfinite(k1) or not 0 < k1 <= 10:
            raise ValueError('k1 must be finite in (0, 10]')
        if isinstance(b, bool) or not isinstance(b, (int, float)) or not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError('b must be finite in [0, 1]')
        if not isinstance(files, Mapping) or not 1 <= len(files) <= 128:
            raise ValueError('files must be a nonempty mapping of at most 128 sources')
        owned = {}
        for path, content in files.items():
            if not isinstance(path, str) or not path or len(path.encode()) > 4096 or '\\' in path or any(ord(c) < 32 for c in path):
                raise ValueError('invalid relative source path')
            p = PurePosixPath(path)
            if p.is_absolute() or str(p) != path or '..' in p.parts:
                raise ValueError('source path must be normalized and relative')
            if not isinstance(content, (bytes, bytearray)) or len(content) > 1048576:
                raise ValueError('sources must be bytes of at most 1 MiB')
            raw = bytes(content)
            raw.decode('utf-8')
            owned[path] = raw
        if sum(map(len, owned.values())) > 16777216:
            raise ValueError('snapshot exceeds 16 MiB')
        self._files = MappingProxyType(owned)
        self._hashes = {p:digest(v) for p,v in owned.items()}
        self.producer_sha256 = digest(Path(__file__).read_bytes())
        self.snapshot_id = digest(wire_bytes([{'path':p,'sha256':self._hashes[p],'bytes':len(owned[p])} for p in sorted(owned)]))
        self.configuration = {'chunk_lines':chunk_lines,'overlap_lines':overlap_lines,
            'path_term_weight':path_term_weight,'k1':k1,'b':b,
            'tokenizer':'unicode-whole-camel-snake.v1','producer_sha256':self.producer_sha256}
        config_bytes = wire_bytes(self.configuration)
        self.configuration = MappingProxyType(self.configuration)
        self.configuration_id = digest(config_bytes)
        self._chunks = []
        self._handles = {}
        for path, raw in sorted(owned.items()):
            lines = raw.splitlines(keepends=True)
            offsets = [0]
            for line in lines:
                offsets.append(offsets[-1]+len(line))
            for first in range(0, len(lines), chunk_lines-overlap_lines):
                endline = min(first+chunk_lines, len(lines))
                start, end = offsets[first], offsets[endline]
                chunk = self._snippet(path, start, end)
                bag = Counter(tokenize(chunk['text']))
                bag.update(tokenize(path)*path_term_weight)
                self._chunks.append((chunk, bag))
                self._handles[chunk['id']] = chunk
                if endline == len(lines):
                    break
        if len(self._chunks) > 4096:
            raise ValueError('snapshot exceeds 4096 chunks')
        self._df = Counter(term for _,bag in self._chunks for term in bag)
        self._avgdl = sum(sum(bag.values()) for _,bag in self._chunks)/max(1,len(self._chunks))
        self._idf = {term:math.log((len(self._chunks)+1)/(count+1))+1 for term,count in self._df.items()}
        self._norms = [math.sqrt(sum(((1+math.log(tf))*self._idf[t])**2 for t,tf in bag.items())) for _,bag in self._chunks]

    def _snippet(self, path, start, end):
        raw = self._files[path][start:end]
        identity = {'snapshot_id':self.snapshot_id,'configuration_id':self.configuration_id,
                    'path':path,'start':start,'end':end}
        return {'id':digest(wire_bytes(identity)),'path':path,'start':start,'end':end,
                'source_sha256':self._hashes[path],'snippet_sha256':digest(raw),'text':raw.decode('utf-8')}

    def _envelope(self, mode, method=None, query_sha256=None):
        return {'schema':'lexical-delivery.v1','snapshot_id':self.snapshot_id,
            'configuration_id':self.configuration_id,'producer_sha256':self.producer_sha256,
            'mode':mode,'method':method,'query_sha256':query_sha256,'status':'no_lexical_match_captured_scope',
            'snippets':[],'refusals':[],'requested_ids':[],
            'coverage':{'captured_scope_only':True,'whole_repository':False,
                'captured_files':len(self._files),'source_bytes':sum(map(len,self._files.values())),
                'indexed_chunks':len(self._chunks),'empty_files':sum(not v for v in self._files.values()),
                'complete_captured_index':True,'parse_status':'unknown','semantic_status':'unknown'},
            'model_tokens':None,'financial_cost':None,'wire_bytes':0}

    @staticmethod
    def _measure(envelope):
        for _ in range(16):
            count = len(wire_bytes(envelope))
            if envelope['wire_bytes'] == count:
                return count
            envelope['wire_bytes'] = count
        raise ValueError('wire size did not converge')

    def search(self, query, *, method='bm25', top_k=5, max_wire_bytes=65536):
        if not isinstance(query, str) or len(query.encode()) > 16384:
            raise ValueError('query must be UTF-8 text of at most 16 KiB')
        if method not in ('bm25','tfidf_cosine'):
            raise ValueError('unknown lexical method')
        _integer('top_k', top_k, 1, 20)
        _integer('max_wire_bytes', max_wire_bytes, 1, 16777216)
        q = Counter(tokenize(query))
        n = len(self._chunks)
        qweights = {t:(1+math.log(tf))*self._idf[t] for t,tf in q.items() if t in self._idf}
        qnorm = math.sqrt(sum(v*v for v in qweights.values()))
        scores = []
        for i,(chunk,bag) in enumerate(self._chunks):
            if method == 'bm25':
                dl = sum(bag.values())
                k1, b = self.configuration['k1'], self.configuration['b']
                score = sum(math.log(1+(n-self._df[t]+.5)/(self._df[t]+.5))*bag[t]*(k1+1)/
                    (bag[t]+k1*(1-b+b*dl/self._avgdl)) for t in q if bag[t])
            else:
                score = sum(qweights[t]*(1+math.log(bag[t]))*self._idf[t] for t in qweights if bag[t])
                score = score/(qnorm*self._norms[i]) if qnorm and self._norms[i] else 0
            if score > 0:
                scores.append((score,chunk))
        scores.sort(key=lambda item:(-item[0],item[1]['path'],item[1]['start'],item[1]['end']))
        result = self._envelope('search',method,digest(query.encode()))
        if self._measure(result) > max_wire_bytes:
            raise ValueError('budget cannot hold the complete empty envelope')
        for score,chunk in scores:
            if len(result['snippets']) == top_k:
                break
            if any(old['path']==chunk['path'] and old['start'] < chunk['end'] and chunk['start'] < old['end'] for old in result['snippets']):
                continue
            candidate = {**chunk,'score':score,'rank':len(result['snippets'])+1}
            result['snippets'].append(candidate)
            result['status'] = 'lexical_matches'
            if self._measure(result) > max_wire_bytes:
                result['snippets'].pop()
                result['status'] = 'lexical_matches' if result['snippets'] else 'insufficient_byte_budget'
                self._measure(result)
                # A whole chunk that does not fit is omitted; smaller later chunks may fit.
        if self._measure(result) > max_wire_bytes:
            raise ValueError('budget cannot hold the complete refusal envelope')
        return result

    def expand(self, snippet_ids, *, max_wire_bytes=65536):
        _integer('max_wire_bytes', max_wire_bytes, 1, 16777216)
        if not isinstance(snippet_ids, (list,tuple)) or not 1 <= len(snippet_ids) <= 20 or any(not isinstance(v,str) for v in snippet_ids):
            raise ValueError('snippet_ids must be 1..20 handles')
        result = self._envelope('full_captured_file')
        result['requested_ids'] = list(snippet_ids)
        unknown = [v for v in snippet_ids if v not in self._handles]
        if unknown:
            result['status'] = 'unknown_handles'
            result['refusals'] = [{'id':v,'reason':'handle_not_in_snapshot_and_configuration'} for v in unknown]
        else:
            paths = sorted({self._handles[v]['path'] for v in snippet_ids})
            result['snippets'] = [self._snippet(p,0,len(self._files[p])) for p in paths]
            result['status'] = 'expanded_full_captured_files'
            if self._measure(result) > max_wire_bytes:
                result['snippets'] = []
                result['status'] = 'insufficient_byte_budget'
                result['refusals'] = [{'reason':'full_files_exceed_budget','paths':paths}]
            else:
                for snippet in result['snippets']:
                    self._handles[snippet['id']] = snippet
        if self._measure(result) > max_wire_bytes:
            raise ValueError('budget cannot hold the complete refusal envelope')
        return result

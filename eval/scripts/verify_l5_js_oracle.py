#!/usr/bin/env python3
"""Read-only source guard for the frozen oracle; not a JavaScript runtime proof."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / 'eval/qualification/l5-real/js'


def verify_text(oracle, natural_input):
    if re.search(r'same (?:call )?stack|before (?:publish|notification).*return|before returning', natural_input, re.I):
        raise ValueError('natural input demands same-stack completion; microtask checkpoint cannot reinterpret it')
    # This source-layout guard is intentionally limited to our small frozen
    # fixture, not advertised as a JavaScript parser or behavioral verifier.
    code = re.sub(r'//[^\n]*|/\*.*?\*/', '', oracle, flags=re.S)
    titles = re.findall(r"test\('([^']+)'", code)
    if sum(t.startswith('contract ') for t in titles) != 3 or sum(t.startswith('regression ') for t in titles) != 2 or len(titles) != 5:
        raise ValueError('oracle requirement/regression counts changed')
    if 'flushSync' in code or 'unstable_flush' in code:
        raise ValueError('oracle explicitly forces or drains scheduler work')
    main = code.split("test('contract snapshot notifications and equality bailout',", 1)[1].split("test('contract store replacement", 1)[0]
    checkpoint = re.compile(r"React\.startTransition\(\(\) => source\.publish\('next'\)\);\s*await Promise\.resolve\(\);\s*expect\(Scheduler\)\.toHaveYielded\(\['next'\]\);")
    if not checkpoint.search(main) or main.count('await Promise.resolve()') != 1:
        raise ValueError('main notification must use exactly one microtask checkpoint outside act')
    call_to_assert = main[main.index('React.startTransition'):main.index("expect(Scheduler).toHaveYielded(['next'])")]
    if 'act(' in call_to_assert:
        raise ValueError('main notification was put inside act')
    if not re.match(r'\s*async \(\) =>', main):
        raise ValueError('main oracle must await the microtask checkpoint')
    control = code.split("test('regression ordinary state update remains supported',", 1)[1].split("test('regression layout", 1)[0]
    negative = re.compile(r"React\.startTransition\(\(\) => update\('deferred'\)\);\s*await Promise\.resolve\(\);\s*expect\(Scheduler\)\.toHaveYielded\(\[\]\);\s*expect\(root\)\.toMatchRenderedOutput\('start'\);\s*await act\(\(\) => \{\}\);\s*expect\(Scheduler\)\.toHaveYielded\(\['deferred'\]\);")
    if not negative.search(control):
        raise ValueError('ordinary transition negative control missing or weakened')
    for pattern in [r'await act\(\(\) => second\.publish\(', r'await act\(\(\) => source\.publish\(\{a:']:
        if not re.search(pattern, code):
            raise ValueError('store lifecycle notification is not awaited as in captured tests')
    return {'source_guard_verified':True,'requirements':3,'regressions':2,
            'main_checkpoint':'one Promise microtask outside act',
            'negative_control':'ordinary transition remains pending until subsequent act',
            'runtime_behavior_verified':False}


if __name__ == '__main__':
    print(json.dumps(verify_text((CASE/'oracles/XraiExternalStoreContract-test.js').read_text(), (CASE/'agent/input.md').read_text()), sort_keys=True))

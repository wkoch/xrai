"""Execution policies: public workspace only, no evaluator credentials or network."""
import json
from pathlib import Path
import platform
import shutil

def sandbox(command, workspace, profile_dir):
    """A fail-closed sandbox: only workspace writable, evaluator/other arms absent."""
    workspace = Path(workspace).resolve(strict=True)
    if not command or not Path(command[0]).is_absolute():
        raise ValueError('adapter executable must be absolute')
    if platform.system() == 'Darwin':
        executable = str(Path(command[0]).resolve(strict=True))
        # No global file-read permission: even same-user evaluator files are denied.
        paths = ['/System', '/usr', '/bin', '/dev', '/etc', '/private/etc', '/Library/Apple',
                 '/private/var/db/dyld', str(workspace)]
        rules = ' '.join('(subpath ' + json.dumps(p) + ')' for p in paths)
        profile = '(version 1)(deny default)(allow process-fork)(allow process-exec)(allow sysctl-read)(allow mach-lookup)(allow file-read-metadata)'
        profile += '(allow file-read* ' + rules + ' (literal ' + json.dumps(executable) + '))'
        profile += '(allow file-map-executable ' + rules + ' (literal ' + json.dumps(executable) + '))'
        # Anchored traversal opens directory handles for every ancestor. Literal
        # directory data permits that traversal/listing, never descendants' data.
        ancestors = ' '.join('(literal ' + json.dumps(str(p)) + ')' for p in workspace.parents)
        profile += '(allow file-read-data ' + ancestors + ')'
        profile += '(allow file-write* (subpath ' + json.dumps(str(workspace)) + ') (literal "/dev/null"))'
        p = Path(profile_dir) / 'sandbox.sb'
        p.write_text(profile, encoding='utf-8')
        return ['/usr/bin/sandbox-exec', '-f', str(p), *command], 'macOS Seatbelt'
    if platform.system() == 'Linux':
        bwrap = shutil.which('bwrap')
        if not bwrap:
            raise RuntimeError('bubblewrap required: refusing an unsandboxed run')
        # --unshare-all only requests userns opportunistically; the supervisor's
        # --userns-block-fd gate requires an explicit, mandatory user namespace.
        args = [bwrap, '--unshare-all', '--unshare-user', '--die-with-parent', '--new-session']
        for p in ['/usr', '/bin', '/lib', '/lib64']:
            if Path(p).exists():
                args += ['--ro-bind', p, p]
        args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                 '--bind', str(workspace), '/workspace', '--chdir', '/workspace',
                 '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8']
        exe = Path(command[0]).resolve(strict=True)
        if not any(exe.is_relative_to(Path(p)) for p in ['/usr', '/bin', '/lib', '/lib64']):
            args += ['--ro-bind', str(exe), '/adapter']
            command = ['/adapter', *command[1:]]
        return [*args, '--', *command], 'Linux bubblewrap'
    raise RuntimeError('no sandbox for this platform')



class MacDisposableAdapter:
    """Reserved external lifecycle contract; no authorized VM/runner configured."""
    available = False
    reason = "dedicated disposable macOS VM/runner unavailable; local Seatbelt is known-smoke only"

    def create(self):
        raise RuntimeError(self.reason)

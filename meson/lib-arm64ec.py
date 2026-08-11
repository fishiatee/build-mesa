#!/usr/bin/env python3
import os
import re
import subprocess
import sys

# Meson cannot distinguish ARM64EC from ARM64 when invoking the static linker,
# so it emits /MACHINE:ARM64. lib.exe rejects ARM64EC objects with that flag.


def fix(arg: str) -> str:
    return re.sub(r'/machine:arm64(?!ec)', '/machine:arm64ec', arg, flags=re.IGNORECASE)


args = sys.argv[1:]

if '--version' in args:
    sys.exit(subprocess.call(['lib.exe', '/?']))

cleanup = []
for i, arg in enumerate(args):
    if arg.startswith('@'):
        rsp = arg[1:]
        rewritten = rsp + '.arm64ec'
        with open(rsp, encoding='utf-8', errors='replace') as source:
            content = source.read()
        with open(rewritten, 'w', encoding='utf-8') as destination:
            destination.write(fix(content))
        args[i] = '@' + rewritten
        cleanup.append(rewritten)
    else:
        args[i] = fix(arg)

try:
    rc = subprocess.call(['lib.exe', *args])
finally:
    for name in cleanup:
        try:
            os.remove(name)
        except OSError:
            pass

sys.exit(rc)

#!/usr/bin/env python3
"""MSVC link wrapper for the ARM64EC half of an ARM64X build.

Takes the normal ARM64EC link command, swaps /MACHINE:ARM64EC for
/MACHINE:ARM64X, and injects the pure-ARM64 objects/libs/def recorded by
link-arm64x-repro.py so the result is a hybrid ARM64X image.
"""
import os
import re
import subprocess
import sys


def parse_rsp_text(text):
    """Split a linker response-file body into individual arguments."""
    args = []
    token = []
    in_quote = False
    for ch in text:
        if ch == '"':
            in_quote = not in_quote
            token.append(ch)
        elif ch in ' \t\r\n' and not in_quote:
            if token:
                args.append(''.join(token))
                token = []
        else:
            token.append(ch)
    if token:
        args.append(''.join(token))
    return args


def expand_args(args):
    expanded = []
    for arg in args:
        if arg.startswith('@'):
            path = arg[1:]
            with open(path, encoding='utf-8', errors='replace') as handle:
                expanded.extend(parse_rsp_text(handle.read()))
        else:
            expanded.append(arg)
    return expanded


def strip_quotes(value):
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def find_out(args):
    for arg in args:
        lower = arg.lower()
        if lower.startswith('/out:') or lower.startswith('-out:'):
            return strip_quotes(arg.split(':', 1)[1])
    return None


def is_lib_only(args):
    for arg in args:
        lower = arg.lower()
        if lower in ('/lib', '-lib') or lower.startswith('/lib:') or lower.startswith('-lib:'):
            return True
    return False


def collect_arm64_inputs(rsp_path):
    """Read a LINKREPROFULLPATHRSP file and return extra link args for ARM64X."""
    with open(rsp_path, encoding='utf-8', errors='replace') as handle:
        entries = parse_rsp_text(handle.read())

    extra = []
    for entry in entries:
        raw = strip_quotes(entry)
        lower = raw.lower()

        # /def:"path" or /def:path from the ARM64 link becomes the native def.
        if lower.startswith('/def:') or lower.startswith('-def:'):
            path = strip_quotes(raw.split(':', 1)[1])
            extra.append(f'/defArm64Native:{path}')
            continue

        # Bare paths to linker inputs recorded by LINKREPROFULLPATHRSP.
        if lower.endswith('.obj') or lower.endswith('.o'):
            extra.append(raw)
        elif lower.endswith('.lib'):
            extra.append(raw)
        elif lower.endswith('.def'):
            extra.append(f'/defArm64Native:{raw}')

    return extra


def to_arm64x_args(args):
    rewritten = []
    saw_machine = False
    for arg in args:
        if re.match(r'[-/]machine:arm64ec$', arg, flags=re.IGNORECASE):
            rewritten.append('/machine:arm64x')
            saw_machine = True
        elif re.match(r'[-/]machine:', arg, flags=re.IGNORECASE):
            # Replace any other machine flag with ARM64X for image links.
            rewritten.append('/machine:arm64x')
            saw_machine = True
        else:
            rewritten.append(arg)
    if not saw_machine:
        rewritten.insert(0, '/machine:arm64x')
    return rewritten


raw_args = sys.argv[1:]
args = expand_args(raw_args)
repro_dir = os.environ.get('ARM64X_REPRO_DIR', '')
out = find_out(args)

# Static/import-lib creation stays on the EC machine type; hybrid only for images.
if is_lib_only(args):
    sys.exit(subprocess.call(['link.exe', *raw_args]))

# Expand @rsp so we can rewrite /machine and append ARM64 inputs safely.
args = to_arm64x_args(args)

if repro_dir and out:
    base = os.path.splitext(os.path.basename(out))[0]
    rsp_path = os.path.join(repro_dir, base + '.rsp')
    if not os.path.isfile(rsp_path):
        print(f'ERROR: missing ARM64 link repro for {base}: {rsp_path}', file=sys.stderr)
        print(f'       ARM64X_REPRO_DIR={repro_dir}', file=sys.stderr)
        sys.exit(1)
    args.extend(collect_arm64_inputs(rsp_path))
elif out:
    print('ERROR: ARM64X_REPRO_DIR is not set; cannot produce ARM64X image', file=sys.stderr)
    sys.exit(1)

sys.exit(subprocess.call(['link.exe', *args]))

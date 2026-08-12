#!/usr/bin/env python3
"""MSVC link wrapper for the pure-ARM64 half of an ARM64X build.

Runs link.exe normally and, for each real link that produces an output image,
also writes /LINKREPROFULLPATHRSP so the later ARM64EC link can merge both
sets of inputs into a hybrid ARM64X binary.
"""
import os
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


# Meson may probe the linker with /? or similar — always forward to link.exe.
raw_args = sys.argv[1:]
args = expand_args(raw_args)
repro_dir = os.environ.get('ARM64X_REPRO_DIR', '')
out = find_out(args)

# Rebuild the command we pass to link.exe. Prefer original argv (keeps meson's
# @rsp files intact) and only inject LINKREPRO when we know the output name.
link_args = list(raw_args)
if repro_dir and out and not is_lib_only(args):
    os.makedirs(repro_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(out))[0]
    rsp = os.path.join(repro_dir, base + '.rsp')
    link_args = [f'/LINKREPROFULLPATHRSP:{rsp}', *raw_args]

sys.exit(subprocess.call(['link.exe', *link_args]))

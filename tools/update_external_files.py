#!/usr/bin/env python3
"""Sync this database with the release files of each core repository.

Two kinds of file, handled differently, because the database builder forces the
split:

  .mra  copied INTO this repository under _Arcade/. They have to be here: the
        builder opens every .mra it lists and reads <rbf>, <setname> and the
        ROM zip names out of it to tag the entry, so an .mra that only exists
        as a URL makes the build fail outright. They are small text files.

  .rbf  listed in external_files.csv, pointing at the bitstream in the core's
        own repository, pinned to a commit. Nothing reads their content, so
        they need not be here, and this keeps tens of megabytes of bitstream
        out of this repository while still delivering them to the SD card.

Pinning to a COMMIT rather than a branch is the point of the .rbf half: a
branch URL would turn every recorded size and MD5 into a future mismatch the
moment that core is rebuilt.

Adding a core is one entry in CORES below.

Usage:
    tools/update_external_files.py                 # re-pin every core to its branch head
    tools/update_external_files.py --keep-pins     # refresh sizes/hashes at the pinned commits
    tools/update_external_files.py --check         # write nothing, report what would change

Needs no credentials: it reads the public GitHub API and raw.githubusercontent.
"""
import argparse, csv, hashlib, json, os, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, 'external_files.csv')
HEADER = ['Path in MiSTer', 'URL', 'Size in bytes (optional but recommended)',
          'MD5 Hash (optional but recommended)', 'Filter Terms (optional)']

# One entry per core repository.
#
#   repo    owner/name on GitHub
#   branch  the branch whose head is picked up when re-pinning
#   commit  the pinned commit these entries describe (updated in place)
#   source  the directory in that repository holding the released files
#
# The layout rule is the one the MiSTer SD card wants and the one these
# repositories already use: everything under `source` goes to _Arcade/,
# keeping its subdirectories (so `_alternatives/` lands under `_Arcade/`),
# except .rbf files, which go to _Arcade/cores/.
CORES = [
    {
        'repo': 'kuzearcade/Arcade-NMK16_MiSTer',
        'branch': 'master',
        'commit': '7d84cb9bcc54499b81200a5216636c339b4743c9',
        'source': 'releases/',
    },
    {
        'repo': 'kuzearcade/Arcade-SandScrp_MiSTer',
        'branch': 'main',
        'commit': 'fc83d6f9da2a690eaceb982bb7de014f34256c6e',
        'source': 'releases/',
    },
    {
        'repo': 'kuzearcade/Arcade-JalecoMS1BCD_MiSTer',
        'branch': 'main',
        'commit': '244c43148775603cc970de9434ff04ada91deae2',
        'source': 'releases/',
    },
    {
        'repo': 'kuzearcade/Arcade-JalecoMS1Z_MiSTer',
        'branch': 'main',
        'commit': 'c422cb120bf98772f08ba0750fc5df007b904ba6',
        'source': 'releases/',
    },    {
        'repo': 'kuzearcade/Arcade-NMKBP964_MiSTer',
        'branch': 'main',
        'commit': '5f5ac44181a8b5edc20bd516885c6b958a8ac16b',
        'source': 'releases/',
    },
    {
        'repo': 'kuzearcade/Arcade-GingaNin_MiSTer',
        'branch': 'main',
        'commit': '24cdb917776970b317bbccbaf643058919d6c61d',
        'source': 'releases/',
    },
]


def api(url):
    req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json',
                                               'User-Agent': 'kuzecores-db-updater'})
    token = os.getenv('GITHUB_TOKEN')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def head_commit(repo, branch):
    return api(f'https://api.github.com/repos/{repo}/commits/{branch}')['sha']


def tree(repo, commit):
    t = api(f'https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1')
    if t.get('truncated'):
        raise SystemExit(f'{repo}: the tree listing was truncated; this script needs a smarter walk')
    return t['tree']


def raw_url(repo, commit, path):
    return f'https://raw.githubusercontent.com/{repo}/{commit}/' + urllib.parse.quote(path, safe='/')


def md5_of(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'kuzecores-db-updater'})
    h = hashlib.md5()
    size = 0
    with urllib.request.urlopen(req) as r:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def sd_path(rel):
    """Where a released file belongs on the SD card."""
    if rel.lower().endswith('.rbf'):
        return '_Arcade/cores/' + os.path.basename(rel)
    return '_Arcade/' + rel


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'kuzecores-db-updater'})
    with urllib.request.urlopen(req) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep-pins', action='store_true', help='do not move the pins to the branch heads')
    ap.add_argument('--check', action='store_true', help='write nothing; report what would change')
    a = ap.parse_args()

    rows = []
    wanted_mras = set()
    for core in CORES:
        repo, source = core['repo'], core['source']
        commit = core['commit'] if a.keep_pins else head_commit(repo, core['branch'])
        if commit != core['commit']:
            print(f"{repo}: re-pinning {core['commit'][:10]} -> {commit[:10]}")
            core['commit'] = commit
        blobs = [t for t in tree(repo, commit)
                 if t['type'] == 'blob' and t['path'].startswith(source)]
        if not blobs:
            raise SystemExit(f'{repo}: nothing under {source} at {commit[:10]}')
        print(f'{repo} @ {commit[:10]}: {len(blobs)} files under {source}')
        for b in sorted(blobs, key=lambda t: t['path'].lower()):
            rel = b['path'][len(source):]
            dest = sd_path(rel)
            url = raw_url(repo, commit, b['path'])
            if dest.lower().endswith('.rbf'):
                digest, size = md5_of(url)
                if size != b['size']:
                    raise SystemExit(f'{b["path"]}: downloaded {size} bytes, the tree says {b["size"]}')
                rows.append([dest, url, str(size), digest, ''])
            else:
                wanted_mras.add(dest)
                if not a.check:
                    data = fetch(url)
                    if len(data) != b['size']:
                        raise SystemExit(f'{b["path"]}: downloaded {len(data)} bytes, the tree says {b["size"]}')
                    full = os.path.join(ROOT, dest)
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    if not os.path.exists(full) or open(full, 'rb').read() != data:
                        open(full, 'wb').write(data)

    # drop .mra files that no longer exist upstream
    if not a.check:
        arcade = os.path.join(ROOT, '_Arcade')
        for dirpath, _, filenames in os.walk(arcade):
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT).replace(os.sep, '/')
                if rel.lower().endswith('.mra') and rel not in wanted_mras:
                    print('removing (gone upstream):', rel)
                    os.remove(full)
        for dirpath, dirnames, filenames in os.walk(arcade, topdown=False):
            if not dirnames and not filenames:
                os.rmdir(dirpath)

    rows.sort(key=lambda r: r[0].lower())
    print(f'{len(wanted_mras)} .mra files in this repository, {len(rows)} .rbf files listed externally')

    out = [HEADER] + rows
    new = '\n'.join(','.join(csv_quote(f) for f in r) for r in out) + '\n'
    old = open(CSV_PATH, newline='').read() if os.path.exists(CSV_PATH) else ''
    if a.check:
        print('external_files.csv is up to date' if new == old else 'external_files.csv WOULD CHANGE')
        sys.exit(0 if new == old else 1)

    with open(CSV_PATH, 'w', newline='') as f:
        csv.writer(f, lineterminator='\n').writerows(out)
    print(f'wrote {CSV_PATH}: {len(rows)} files')

    # keep the pins in this file in step with what was just written
    src = open(__file__).read()
    for core in CORES:
        import re
        src = re.sub(r"('repo': '" + re.escape(core['repo']) + r"',\s*\n\s*'branch': '[^']*',\s*\n\s*'commit': ')[0-9a-f]{40}",
                     lambda m: m.group(1) + core['commit'], src)
    open(__file__, 'w').write(src)


def csv_quote(field):
    return '"' + field.replace('"', '""') + '"' if any(c in field for c in ',"\n') else field


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Regenerate external_files.csv from the release files of each core repository.

This database ships no game files of its own. Every entry points at a file in
the core's own repository, pinned to a commit, so:

  - the cores stay in one place and are not duplicated here;
  - a recorded size and MD5 stay valid forever, because a pinned commit cannot
    change underneath them (pointing at a branch would make every recorded hash
    a future mismatch the moment that core is rebuilt);
  - adding a core is one entry in CORES below.

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
        'commit': 'ef92781eea05f962b6ec84c42d2959d064423dbe',
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep-pins', action='store_true', help='do not move the pins to the branch heads')
    ap.add_argument('--check', action='store_true', help='write nothing; report what would change')
    a = ap.parse_args()

    rows = []
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
            url = raw_url(repo, commit, b['path'])
            digest, size = md5_of(url)
            if size != b['size']:
                raise SystemExit(f'{b["path"]}: downloaded {size} bytes, the tree says {b["size"]}')
            rows.append([sd_path(rel), url, str(size), digest, ''])

    rows.sort(key=lambda r: r[0].lower())

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

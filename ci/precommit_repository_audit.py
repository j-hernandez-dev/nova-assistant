"""Read-only repository inventory and credential screening before human commit.

No git index/config mutation, cleanup, history rewrite or credential values in
reports. Scans tracked, untracked and ignored physical files. Git longpaths is
enabled for each read command only; .git metadata is outside artifact scope.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {'.py', '.ps1', '.sh', '.js', '.cjs', '.mjs', '.ts', '.tsx', '.cs', '.md',
    '.json', '.jsonl', '.xml', '.yml', '.yaml', '.toml', '.ini', '.cfg', '.config', '.txt',
    '.log', '.env', '.pem', '.key', '.crt', '.cer', '.html', '.csv', '.sln', '.csproj', '.props', '.targets'}
GENERATED_PARTS = {'node_modules', '__pycache__', '.pytest_cache', 'bin', 'obj', '.mypy_cache',
    '.ruff_cache', 'dist', 'dist-electron', 'release', '.venv', 'venv', '.eggs'}
PATTERNS = (
    ('PRIVATE_KEY_BLOCK', re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----[\r\n]+[A-Za-z0-9+/=\r\n]{64,}-----END (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----')),
    ('PROVIDER_KEY_SHAPED', re.compile(rb'(?<![A-Za-z0-9])(?:sk-(?:proj-|ant-api[0-9]+-)?[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AIza[A-Za-z0-9_-]{35})(?![A-Za-z0-9])')),
    ('AWS_ACCESS_KEY_SHAPED', re.compile(rb'(?<![A-Za-z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Za-z0-9])')),
    ('BEARER_OR_COOKIE_LITERAL', re.compile(rb'(?im)^\s*(?:Authorization\s*:\s*Bearer|Cookie\s*:)\s*[^\r\n]{16,}')),
    ('JSON_AUTH_OR_COOKIE_LITERAL', re.compile(rb'(?im)["\'](?:cookie|authorization|proxy-authorization)["\']\s*:\s*["\']([^"\'\r\n]{16,})["\']')),
    ('HTTP_URL_USERINFO_LITERAL', re.compile(rb'https?://[^\s"\'<>/@]{3,}:[^\s"\'<>/@]{3,}@[^\s"\'<>/]{3,}')),
    ('CREDENTIAL_ASSIGNMENT_LITERAL', re.compile(rb'(?im)(?:["\']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret)["\']?)\s*(?:[:=])\s*["\']([^"\'\r\n]{12,})["\']')),
)
SYNTHETIC_MARKERS = (b'synthetic', b'fixture', b'fake-', b'dummy', b'example', b'test-only', b'test_secret',
    b'sk-test', b'not-a-real', b'placeholder', b'redacted', b'known-value', b'known_value')
PUBLIC_TEST_KEY = ('tests/security_v12/network_tls_fixture/server_test_key.pem',
    'fcd129758c2b6b113bb76c579cf3a28f096e4ae5a2ee9cda6cfe1db48368f011')
PUBLIC_MOCK_PROVIDER_CORPUS = ('tests/test_providers/test_claude_provider.py',
    '8221f31837833f5e10349426c25b1fc277890d0887a4ff0411d5fe6692950379')


def git(*arguments, data=None):
    command = ['git', '-c', 'core.longpaths=true', *arguments]
    result = subprocess.run(command, cwd=ROOT, input=data, capture_output=True, timeout=90,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode not in (0, 1):
        raise RuntimeError('READ_ONLY_GIT_QUERY_FAILED:' + ' '.join(arguments[:2]))
    return result.stdout, result.stderr.decode('utf-8', errors='replace')


def git_paths(*arguments):
    body, errors = git(*arguments, '-z')
    return {value.decode('utf-8', errors='surrogateescape').replace('\\', '/') for value in body.split(b'\0') if value}, errors


def changed_paths():
    body, errors = git('status', '--porcelain=v1', '-z', '--untracked-files=all')
    entries = body.split(b'\0')
    rows, index = {}, 0
    while index < len(entries):
        token = entries[index]
        index += 1
        if not token:
            continue
        status = token[:2].decode('ascii')
        path = token[3:].decode('utf-8', errors='surrogateescape').replace('\\', '/')
        rows[path] = status
        if 'R' in status or 'C' in status:
            index += 1  # Rename source is another NUL token; no mutation.
    return rows, errors


def ignore_reasons(paths):
    data = b'\0'.join(path.encode('utf-8', errors='surrogateescape') for path in paths) + b'\0'
    body, errors = git('check-ignore', '--no-index', '--verbose', '--non-matching', '-z', '--stdin', data=data)
    values = body.split(b'\0')
    result = {}
    for index in range(0, len(values)-3, 4):
        source, line, pattern, path = [value.decode('utf-8', errors='surrogateescape') for value in values[index:index+4]]
        result[path] = dict(source=source or None, line=int(line) if line else None, pattern=pattern or None)
    return result, errors


def hash_and_screen(path, logical, generated):
    digest = hashlib.sha256()
    pieces = []
    possible_text = path.suffix.casefold() in TEXT_EXTENSIONS or path.name.startswith('.env') or path.name in ('Dockerfile', '.gitignore', '.gitattributes')
    # Whole-file byte hashes include every binary/dependency. Text scan limit is
    # explicit; files too large to screen fully remain unresolved, never PASS.
    max_text_bytes = 64 * 1024 * 1024
    length = 0
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
            length += len(block)
            if possible_text and length <= max_text_bytes:
                pieces.append(block)
    findings = []
    coverage = 'FULL_TEXT' if possible_text and length <= max_text_bytes else 'NOT_TEXT_BINARY' if not possible_text else 'TEXT_BOUND_EXCEEDED'
    if coverage == 'FULL_TEXT':
        body = b''.join(pieces)
        for label, pattern in PATTERNS:
            matches = list(pattern.finditer(body))
            if not matches:
                continue
            synthetic, potential = 0, 0
            for match in matches:
                start, end = match.span()
                context = body[max(0, start-160):min(len(body), end+160)].lower()
                value = match.group(1) if label in ('CREDENTIAL_ASSIGNMENT_LITERAL', 'JSON_AUTH_OR_COOKIE_LITERAL') else match.group()
                placeholder = (any(marker in context for marker in SYNTHETIC_MARKERS) or
                    b'${' in value or b'os.environ' in value or b'process.env' in value or
                    b'getenv' in value or value.startswith((b'<', b'YOUR_', b'your_')) or
                    value.strip(b'0xX*_.-') == b'')
                # A real PEM block remains a key even when a test generated it.
                if label == 'PRIVATE_KEY_BLOCK' or not placeholder:
                    potential += 1
                else:
                    synthetic += 1
            findings.append(dict(path=logical, fileSha256=digest.hexdigest(), rule=label,
                count=len(matches), syntheticOrPlaceholderCount=synthetic,
                requiresHumanSensitiveReviewCount=potential,
                scope='GENERATED_DEPENDENCY' if generated else 'REPOSITORY_ARTIFACT',
                valuesDisclosed=False))
            # Exact preexisting public test key, explicitly documented and pinned
            # by Security S8. Never exempts another key or an altered fixture.
            if label == 'PRIVATE_KEY_BLOCK' and (logical, digest.hexdigest()) == PUBLIC_TEST_KEY:
                findings[-1].update(classification='INTENTIONAL_PUBLIC_SYNTHETIC_TLS_FIXTURE',
                    requiresHumanSensitiveReviewCount=0, syntheticOrPlaceholderCount=len(matches),
                    authorizationEvidence='tests/security_v12/network_tls_fixture/README.md',
                    scope='EXACT_PATH_AND_SHA256_PUBLIC_TEST_MATERIAL')
            if label == 'CREDENTIAL_ASSIGNMENT_LITERAL' and (logical, digest.hexdigest()) == PUBLIC_MOCK_PROVIDER_CORPUS:
                findings[-1].update(classification='INTENTIONAL_SYNTHETIC_PROVIDER_CONTRACT_DATA',
                    requiresHumanSensitiveReviewCount=0, syntheticOrPlaceholderCount=len(matches),
                    authorizationEvidence='unittest.mock.patch(urllib.request.urlopen); explicit/environment key precedence corpus',
                    scope='EXACT_PATH_AND_SHA256_SHORT_MOCK_TEST_VALUES')
    return digest.hexdigest(), length, coverage, findings


def classification(path, tracked, ignored):
    parts = Path(path).parts
    generated = any(part.casefold() in GENERATED_PARTS for part in parts)
    if path.startswith('docs/memory_v1/') and ('audit' in parts and
            (Path(path).suffix.casefold() == '.lease' or Path(path).name == 'rotation.lock' or 'standalone_v1' in parts)):
        category, generated = 'IGNORED_LOCAL_RUNTIME_AUDIT_LOCK_OR_STANDALONE_STATE', True
    elif path.startswith('docs/memory_v1/') and (any(part in ('pytest-private', 'private', 'state') for part in parts) or
            Path(path).suffix.casefold() in ('.db', '.sqlite', '.sqlite3') or '.db-' in path):
        category, generated = 'IGNORED_LOCAL_MEMORY_FIXTURE_STATE', True
    elif path.startswith('docs/active_web_v1/') or path.startswith('docs/active_web_v1_2/'):
        category = 'FROZEN_OR_ADDITIVE_ACTIVE_WEB_EVIDENCE'
    elif path.startswith('docs/'):
        category = 'DOCUMENTATION_OR_FROZEN_EVIDENCE'
    elif generated:
        category = 'GENERATED_DEPENDENCY_BUILD_OR_CACHE'
    elif path.startswith('tests/') or '/tests/' in path:
        category = 'TEST_SOURCE_OR_FIXTURE'
    else:
        category = 'PRODUCT_SOURCE_OR_REPOSITORY_CONFIGURATION'
    return category, generated


def manifest_references(inventory):
    paths = {row['path'] for row in inventory}
    references = {}
    for row in inventory:
        path = row['path']
        if not path.startswith('docs/') or Path(path).suffix.casefold() != '.json' or row['bytes'] > 32*1024*1024:
            continue
        try:
            data = json.loads((ROOT / path).read_text(encoding='utf-8-sig'))
        except (OSError, ValueError, UnicodeError):
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                raw = item.get('path')
                if isinstance(raw, str) and isinstance(item.get('sha256'), str):
                    candidate = raw.replace('\\', '/')
                    options = (candidate, (Path(path).parent / candidate).as_posix())
                    for option in options:
                        if option in paths:
                            references.setdefault(option, set()).add(path)
                for key, digest in item.items():
                    if isinstance(key, str) and isinstance(digest, str) and re.fullmatch('[0-9a-fA-F]{64}', digest):
                        candidate = key.replace('\\', '/')
                        for option in (candidate, (Path(path).parent / candidate).as_posix()):
                            if option in paths:
                                references.setdefault(option, set()).add(path)
                stack.extend(item.values())
            elif isinstance(item, list):
                # Product profile pin pairs are also exact artifact references.
                if len(item) == 2 and all(isinstance(value, str) for value in item) and re.fullmatch('[0-9a-f]{64}', item[1]):
                    candidate = item[0].replace('\\', '/')
                    if candidate in paths:
                        references.setdefault(candidate, set()).add(path)
                stack.extend(item)
    return references


def audit(destination, *, refresh=False):
    destination = Path(destination).resolve()
    exact_output = Path(os.environ['LOCALAPPDATA']) / 'Temp/nova-precommit-audit'
    if destination != exact_output.resolve() or destination.is_relative_to(ROOT):
        raise ValueError('OUTPUT_MUST_BE_EXACT_OWNED_PRECOMMIT_TEMP')
    cached_inventory, cached_findings = {}, {}
    if refresh:
        # Preserve the original comprehensive scan, then refresh every commit
        # candidate. Large ignored runtime files retain explicitly dated hashes.
        previous = json.loads((destination / 'repository_inventory.json').read_text(encoding='utf-8'))
        cached_inventory = {row['path']: row for row in previous}
        for row in json.loads((destination / 'secret_findings.json').read_text(encoding='utf-8')):
            cached_findings.setdefault(row['path'], []).append(row)
        for leaf in ('repository_inventory.json', 'secret_findings.json', 'repository_audit_summary.json',
                     'ignored_evidence.json', 'large_files.json'):
            saved = destination / ('initial_' + leaf)
            if not saved.exists():
                saved.write_bytes((destination / leaf).read_bytes())
    tracked, tracked_errors = git_paths('ls-files', '--cached')
    visible, visible_errors = git_paths('ls-files', '--others', '--exclude-standard')
    ignored, ignored_errors = git_paths('ls-files', '--others', '--ignored', '--exclude-standard')
    changes, change_errors = changed_paths()
    physical, enumeration_errors, reparse_entries = [], [], []
    for directory, dirs, files in os.walk(ROOT, followlinks=False):
        current = Path(directory)
        if current == ROOT and '.git' in dirs:
            dirs.remove('.git')
        for leaf in tuple(dirs):
            candidate = current / leaf
            try:
                if candidate.is_symlink() or getattr(candidate.lstat(), 'st_file_attributes', 0) & 0x400:
                    dirs.remove(leaf)
                    reparse_entries.append(candidate.relative_to(ROOT).as_posix())
            except OSError:
                dirs.remove(leaf)
                enumeration_errors.append('DIRECTORY_METADATA_UNCONFIRMED:' + candidate.relative_to(ROOT).as_posix())
        for leaf in files:
            physical.append((current / leaf).relative_to(ROOT).as_posix())
    reasons, reason_errors = ignore_reasons(sorted(physical))
    inventory, findings, read_errors = [], [], []
    for index, logical in enumerate(sorted(physical)):
        path = ROOT / logical
        category, generated = classification(logical, logical in tracked, logical in ignored)
        try:
            cache = cached_inventory.get(logical)
            unchanged_ignored = bool(refresh and logical not in tracked and logical in ignored and cache and
                cache['bytes'] == path.stat().st_size and (generated or logical.startswith('docs/memory_v1/')))
            if unchanged_ignored:
                sha, length, coverage = cache['sha256'], cache['bytes'], cache['secretScanCoverage']
                found = cached_findings.get(logical, ())
                freshness = 'CACHED_INITIAL_IGNORED_RUNTIME_SCAN'
            else:
                sha, length, coverage, found = hash_and_screen(path, logical, generated)
                freshness = 'FRESH_CANDIDATE_OR_NEW_FILE_SCAN' if refresh else 'FULL_INITIAL_PHYSICAL_SCAN'
            findings.extend(found)
            inventory.append(dict(path=logical, bytes=length, sha256=sha,
                versioning='TRACKED' if logical in tracked else 'UNTRACKED_VISIBLE' if logical in visible else
                    'UNTRACKED_IGNORED' if logical in ignored else 'PHYSICAL_NOT_ENUMERATED_BY_GIT',
                ignoredReason=reasons.get(logical), classification=category,
                gitStatus=changes.get(logical),
                generated=generated, secretScanCoverage=coverage,
                scanFreshness=freshness,
                absolutePathCharacters=len(str(path))))
        except OSError:
            read_errors.append(dict(path=logical, code='FILE_READ_UNCONFIRMED'))
    references = manifest_references(inventory)
    for row in inventory:
        row['referencedByManifests'] = sorted(references.get(row['path'], ()))
        row['requiredIgnoredEvidence'] = (row['versioning'] == 'UNTRACKED_IGNORED' and bool(row['referencedByManifests']) and
            row['classification'] in ('FROZEN_OR_ADDITIVE_ACTIVE_WEB_EVIDENCE', 'DOCUMENTATION_OR_FROZEN_EVIDENCE') and
            not row['generated'])
    pending_sensitive = [finding for finding in findings if finding['requiresHumanSensitiveReviewCount'] and
        finding['scope'] != 'GENERATED_DEPENDENCY']
    ignored_evidence = [row for row in inventory if row['versioning'] == 'UNTRACKED_IGNORED' and
        row['classification'] in ('FROZEN_OR_ADDITIVE_ACTIVE_WEB_EVIDENCE', 'DOCUMENTATION_OR_FROZEN_EVIDENCE')]
    summary = dict(schemaVersion=1, observedAt=datetime.now(timezone.utc).isoformat(),
        scope='ALL_PHYSICAL_REPOSITORY_FILES_TRACKED_UNTRACKED_IGNORED_EXCLUDING_GIT_METADATA',
        counts=dict(physicalFiles=len(physical), trackedFiles=len(tracked), visibleUntrackedFiles=len(visible),
            ignoredUntrackedFiles=len(ignored), hashedFiles=len(inventory),
            missingTrackedFiles=len(tracked-set(physical)), largeFilesOver10MiB=sum(row['bytes']>10*1024*1024 for row in inventory)),
        versioningCounts=dict(Counter(row['versioning'] for row in inventory)),
        categoryCounts=dict(Counter(row['classification'] for row in inventory)),
        secretScan=dict(valuesDisclosed=False, rules=[label for label,_ in PATTERNS],
            findings=len(findings), pendingNonGeneratedSensitiveReview=len(pending_sensitive),
            textCoverage=dict(Counter(row['secretScanCoverage'] for row in inventory)),
            status='REQUIRES_SENSITIVE_REVIEW' if pending_sensitive else 'NO_POTENTIAL_LIVE_SECRET_DETECTED_BY_SCOPED_SCAN'),
        ignoredDocumentationFiles=len(ignored_evidence), requiredIgnoredEvidence=sum(row['requiredIgnoredEvidence'] for row in inventory),
        enumerationErrors=enumeration_errors, readErrors=read_errors, reparseEntriesExcluded=reparse_entries,
        gitWarnings=[value for value in (tracked_errors,visible_errors,ignored_errors,reason_errors,change_errors) if value],
        commandScopedLongpaths=True, gitConfigurationModified=False, gitIndexModified=False,
        historicalEvidenceModified=False, cleanupAttempted=False,
        incrementalRefresh=refresh, initialAllFilesWereHashed=True,
        freshnessCounts=dict(Counter(row['scanFreshness'] for row in inventory)),
        limitations=['Pattern screening is not universal DLP. Synthetic matches remain classified separately.',
            'Binary files are byte-hashed and inventoried; credential semantics inside binary formats are not inferred.',
            'Ignored generated dependency findings are reported separately; no artifact is deleted or rewritten.'])
    destination.mkdir(parents=True, exist_ok=True)
    for name, body in (('repository_inventory.json', inventory), ('secret_findings.json', findings),
                       ('ignored_evidence.json', ignored_evidence), ('large_files.json', [row for row in inventory if row['bytes']>10*1024*1024]),
                       ('repository_audit_summary.json', summary)):
        (destination / name).write_text(json.dumps(body, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    compact = [dict(path=row['path'], bytes=row['bytes'], sha256=row['sha256'],
        versioning=row['versioning'], gitStatus=row['gitStatus'], classification=row['classification'],
        absolutePathCharacters=row['absolutePathCharacters'], manifestReferenceCount=len(row['referencedByManifests']))
        for row in inventory if row['versioning'] in ('TRACKED', 'UNTRACKED_VISIBLE')]
    (destination / 'candidate_inventory.json').write_text(json.dumps(compact, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    ignored_summary = Counter((row['classification'], (row.get('ignoredReason') or {}).get('pattern'))
        for row in inventory if row['versioning'] == 'UNTRACKED_IGNORED')
    (destination / 'ignored_runtime_summary.json').write_text(json.dumps([
        dict(classification=key[0], ignorePattern=key[1], files=count) for key,count in ignored_summary.items()],
        ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--refresh', action='store_true')
    arguments = parser.parse_args()
    result = audit(arguments.output, refresh=arguments.refresh)
    print(json.dumps(dict(counts=result['counts'], secretScan=result['secretScan'],
        requiredIgnoredEvidence=result['requiredIgnoredEvidence'], ignoredDocumentationFiles=result['ignoredDocumentationFiles'],
        readErrors=len(result['readErrors']), gitWarningCount=len(result['gitWarnings']))))

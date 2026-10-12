"""Positive CI entry point. Collection never runs a contract/fixture or model."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from contract_inventory import ROOT, MANIFEST, ORDINARY_CATEGORIES, SPECIAL_CATEGORIES, base_nodeid, select, validate

sys.path.insert(0, str(ROOT))


def private_environment(output, *, special):
    # Process-local fixture profiles, not an OS sandbox. Never load a user .env.
    permitted = ("SystemRoot", "WINDIR", "PATH", "PATHEXT", "COMSPEC",
                 "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS",
                 "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA",
                 "LANG", "LC_ALL")
    child_env = {key: os.environ[key] for key in permitted if key in os.environ}
    child_env.update(PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                     PYTHONIOENCODING="utf-8", PYTHONPATH=str(ROOT),
                     NOVA_MEMORY_SEMANTIC_PROFILE="NOT_CERTIFIED")
    if output is not None:
        for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                    "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "TEMP", "TMP"):
            folder = output / "private" / key.lower()
            folder.mkdir(parents=True, exist_ok=True)
            child_env[key] = str(folder)
        if platform.system()=='Windows':
            # Python's HOME and PowerShell's native $HOME must refer to the
            # same private identity; neither may resolve to the signed-in user.
            child_env['HOME']=child_env['USERPROFILE']
    if special:
        child_env.update({key: "1" for key in (
            "NOVA_S3_HOST_REAL", "NOVA_S4_HOST_REAL",
            "NOVA_S5_HOST_REAL", "NOVA_S6_HOST_REAL")})
    return child_env


def short_windows_profile(output, env):
    """Owned test-only profile: real KnownFolder API, no ambient user config.

    The registered shell expansion needs USERPROFILE/AppData/Local to exist.
    A long CI output prefix exceeds Nova's unchanged productive UDF ceiling,
    so this temporary leaf uses the local system volume's short namespace.
    It grants no product override and changes no registry or KnownFolder API.
    """
    system_root=Path(os.environ['SystemRoot'])
    if not system_root.is_absolute():raise ValueError('LOCAL_WINDOWS_VOLUME_REQUIRED')
    volume=Path(system_root.anchor)
    profile=Path(tempfile.mkdtemp(prefix='nci-',dir=volume)).resolve()
    marker=json.dumps({'schema':'owned-ci-native-profile-1','output':str(output.resolve())},sort_keys=True)
    ownership=profile/'.nova-ci-profile-owner'
    ownership.write_text(marker,encoding='utf-8')
    record=(profile,volume,marker)
    try:
        from local_cli.infrastructure.active_web.private_directory import protect
        protect(profile)
        local=profile/'AppData'/'Local';roaming=profile/'AppData'/'Roaming'
        local.mkdir(parents=True);roaming.mkdir()
        # Keep the product's 128-unit check intact; the deepest UDF basename
        # remains exactly the existing 82-character opaque identity.
        units=len(str(local/'Nova'/'Wv'/('x'*82)).encode('utf-16-le'))//2
        if units>128:raise ValueError('OWNED_CI_NATIVE_PROFILE_PATH_TOO_LONG')
        env.update(HOME=str(profile),USERPROFILE=str(profile),APPDATA=str(roaming),LOCALAPPDATA=str(local))
        return record
    except Exception:
        cleanup_windows_profile(record)
        raise


def cleanup_windows_profile(record):
    if record is None:return {'status':'NOT_REQUIRED'}
    profile,volume,marker=record
    try:
        # Only this newly issued leaf; never a historical UDF or signed-in
        # profile. Refuse changed ownership/reparse identity before deletion.
        if (profile.resolve()!=profile or profile.parent!=volume or not profile.name.startswith('nci-')
                or profile.is_symlink()or getattr(profile.lstat(),'st_file_attributes',0)&0x400
                or(profile/'.nova-ci-profile-owner').read_text(encoding='utf-8')!=marker):
            raise ValueError('CI_NATIVE_PROFILE_OWNERSHIP_UNCONFIRMED')
        shutil.rmtree(profile)
        return {'status':'CONFIRMED','owned_profile_absent':not profile.exists()}
    except Exception as error:
        return {'status':'CLEANUP_UNCONFIRMED','error_class':type(error).__name__}


def new_output(path):
    if path is None:
        return None
    output = path.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("CI_OUTPUT_INSIDE_CHECKOUT")
    if output.exists():
        raise ValueError("CI_OUTPUT_ALREADY_EXISTS")
    ancestor = output.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    probe = subprocess.run(["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
    if probe.returncode == 0:
        raise ValueError("CI_OUTPUT_INSIDE_GIT_WORKSPACE")
    output.mkdir(parents=True)
    return output


class CollectionGuard:
    def __init__(self, data, selected, job, host, special, output=None):
        self.data = data
        self.selected = set(selected)
        self.job, self.host, self.special = job, host, special
        self.items = []
        self.tests_executed = 0
        self.passed = False
        self.skips_xfails = []
        self.output=output
        self.helper_redirects=[]

    def pytest_configure(self, config):
        import pytest
        # Positive selection must not be narrowed by config/environment filters.
        for name in ("keyword", "markexpr", "ignore", "ignore_glob", "deselect", "lf"):
            if config.getoption(name, default=None):
                raise pytest.UsageError("UNAUTHORIZED_CI_SELECTION_FILTER:" + name)

    def pytest_collection_modifyitems(self, session, config, items):
        import pytest
        declared = {row["nodeid"]: row for row in self.data["contracts"]}
        collected = {base_nodeid(item.nodeid) for item in items}
        errors = []
        for item in items:
            base = base_nodeid(item.nodeid)
            row = declared.get(base)
            if base not in self.selected or row is None:
                errors.append("UNCLASSIFIED_OR_UNSELECTED:" + item.nodeid)
                continue
            rule = self.data["rules"][row["rule"]]
            ordinary = row["classification"] in ORDINARY_CATEGORIES
            native = self.special and row["classification"] in SPECIAL_CATEGORIES
            explicit_native=self.special and self.job in row.get('native_jobs',())and self.host in self.data['jobs'][self.job]['platforms']
            matching_job = rule['job'] == self.job or self.job in row.get('additional_jobs', ())
            if not explicit_native and (not (ordinary or native) or not matching_job or self.host not in rule["platforms"]):
                errors.append("WRONG_CI_SCOPE:" + item.nodeid)
        errors.extend("UNCOLLECTED_POSITIVE_SELECTOR:" + node for node in sorted(self.selected - collected))
        if errors:
            # Fail before any test setup/execution; never remove or skip items.
            raise pytest.UsageError("\n".join(errors))
        self.items = [item.nodeid for item in items]
        self.passed = True

    def pytest_runtest_logstart(self, nodeid, location):
        self.tests_executed += 1

    def pytest_runtest_logreport(self, report):
        if report.skipped or hasattr(report, 'wasxfail'):
            self.skips_xfails.append(dict(nodeid=report.nodeid, phase=report.when, outcome=report.outcome,
                                         xfail=hasattr(report,'wasxfail')))

    def pytest_runtest_setup(self,item):
        if self.output is None:return
        for module in tuple(sys.modules.values()):
            value=getattr(module,'EVIDENCE',None)
            if not isinstance(value,Path):continue
            try:historic=value.resolve().is_relative_to(ROOT/'docs')
            except (OSError,ValueError):historic=False
            if historic:
                target=self.output/'reused-helper-output'/getattr(module,'__name__','module').replace('.','_')
                target.mkdir(parents=True,exist_ok=True);module.EVIDENCE=target
                self.helper_redirects.append(getattr(module,'__name__','module'))


def protect_history():
    """Process-local audit guard, not a product/OS/browser sandbox claim."""
    protected=tuple((ROOT/name).resolve() for name in ('docs/active_web_v1','docs/active_web_v1_2'))
    def protected_path(value):
        if not isinstance(value,(str,bytes,os.PathLike)):return False
        try:
            path=Path(os.fsdecode(value)).resolve()
            return any(path==root or path.is_relative_to(root)for root in protected)
        except (OSError,ValueError):return False
    def audit(event,args):
        write=event in ('os.remove','os.rmdir','os.mkdir','os.rename','os.chmod','os.utime','os.truncate')
        paths=args[:2]if event=='os.rename'else args[:1]
        if event=='open':
            mode=args[1]or'';flags=args[2]or 0
            write=any(c in mode for c in 'wax+')or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if write and any(protected_path(path)for path in paths):
            raise PermissionError('HISTORICAL_EVIDENCE_WRITE_DENIED')
    sys.addaudithook(audit)


def native_environment(args, output, original, env):
    """Require explicit infrastructure; no installation or nominal certificate."""
    env['NOVA_B5_TEST_OUTPUT']=str(output)
    native_tests=ROOT/'native/nova-browser-host/tests'
    env['PYTHONPATH']=os.pathsep.join((str(ROOT),str(native_tests)))
    if args.job in ('web-v12-native','web-v12-windows-native'):
        sdk=original.get('NOVA_WEBVIEW2_SDK_FEED')
        if not sdk or not Path(sdk).is_absolute()or not(Path(sdk)/'microsoft.web.webview2.1.0.4258.31.nupkg').is_file():
            raise ValueError('WEBVIEW2_PINNED_SDK_FEED_REQUIRED')
        env['NOVA_WEBVIEW2_SDK_FEED']=sdk
        dotnet=Path('C:/Program Files/dotnet/dotnet.exe')
        if not dotnet.is_file():raise ValueError('INSTALLED_DOTNET_REQUIRED')
    if args.job=='web-v12-native':
        import ipaddress
        address=original.get('NOVA_CF_B6_PUBLIC_IPV6')or original.get('NOVA_CF_B2_PUBLIC_IPV6')
        openssl=original.get('NOVA_CF_B6_OPENSSL')or original.get('NOVA_CF_B2_OPENSSL')
        if not address or not ipaddress.IPv6Address(address).is_global:
            raise ValueError('EXPLICIT_ASSIGNED_PUBLIC_IPV6_TOPOLOGY_REQUIRED')
        if not openssl or not Path(openssl).is_absolute()or not Path(openssl).is_file():
            raise ValueError('EXACT_PROCESS_SCOPED_TLS_FIXTURE_OPENSSL_REQUIRED')
        from local_cli.bootstrap_web_v12 import CANDIDATE
        if not CANDIDATE.is_file():raise ValueError('FROZEN_V12_PRODUCT_CANDIDATE_REQUIRED')
        env.update(NOVA_CF_B2_NATIVE='1',NOVA_CF_B2_PUBLIC_IPV6=address,NOVA_CF_B2_OPENSSL=openssl,
            NOVA_CF_B6_PUBLIC_IPV6=address,NOVA_CF_B6_OPENSSL=openssl,NOVA_B6_FROZEN_CANDIDATE=str(CANDIDATE),
            NOVA_CF_B2_NATIVE_OUTPUT=str(output/'cf-native.json'))


def install_runtime_import_paths():
    """PYTHONPATH affects children; pytest.main also needs this interpreter."""
    previous=list(sys.path)
    for path in (ROOT, ROOT/'ci', ROOT/'native/nova-browser-host/tests'):
        value=str(path)
        if value not in sys.path:sys.path.insert(0,value)
    return previous



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    data = validate()
    parser.add_argument("--job", choices=tuple(data['jobs']), required=True)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--special", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    actual_host = {"Windows": "Windows", "Linux": "Linux", "Darwin": "macOS"}[platform.system()]
    if args.special != (not data['jobs'][args.job]['ordinary']):
        parser.error("SPECIAL_INFRASTRUCTURE_REQUIRES_EXPLICIT_NATIVE_SCOPE")
    if args.special and actual_host != "Windows":
        parser.error("NATIVE_SECURITY_REQUIRES_WINDOWS")
    if not args.collect_only and args.output is None:
        parser.error("execution requires fresh private output outside checkout")
    if actual_host not in data['jobs'][args.job]['platforms']:
        parser.error('JOB_PLATFORM_NOT_SUPPORTED')
    selected = select(data, args.job, actual_host, special=args.special)
    if args.output is None and args.collect_only and args.job.startswith('web-v12'):
        args.output=Path(tempfile.mkdtemp(prefix='nova-ci-collection-parent-'))/'output'
    output = new_output(args.output)
    # Preserve explicitly supplied import search paths for the already-installed
    # validation runtime; this is not inherited product config or model settings.
    old_env = dict(os.environ)
    ci_env = private_environment(output, special=args.job == 'security-native')
    if args.job=='core-symlink-native'and not args.collect_only:
        probe=output/'private'/'symlink-prerequisite';probe.mkdir()
        target=probe/'owned.txt';link=probe/'owned-link.txt';target.write_text('owned prerequisite',encoding='utf-8')
        try:
            link.symlink_to(target)
            if not link.is_symlink()or link.resolve()!=target.resolve():raise ValueError('SYMLINK_PREREQUISITE_IDENTITY_UNCONFIRMED')
        except OSError as error:
            raise ValueError('WINDOWS_SYMLINK_CREATION_PREREQUISITE_UNAVAILABLE')from None
        finally:
            if link.is_symlink():link.unlink()
            target.unlink();probe.rmdir()
    if output is not None:
        ci_env['NOVA_B5_TEST_OUTPUT']=str(output)
        ci_env['NOVA_CI_OUTPUT_ROOT']=str(output)
        ci_env['PYTHONPATH']=os.pathsep.join((str(ROOT),str(ROOT/'ci'),str(ROOT/'native/nova-browser-host/tests')))
    if args.job.startswith('web-v12'):
        if output is None:parser.error('V12_REQUIRES_OWNED_PRIVATE_OUTPUT')
        ci_env['NOVA_B5_TEST_OUTPUT']=str(output)
        ci_env['NOVA_CI_OUTPUT_ROOT']=str(output)
        if args.job in ('web-v12-native','web-v12-windows-native')and not args.collect_only:
            native_environment(args,output,old_env,ci_env)
    if args.job == 'active-web-native':
        # Explicit manual engine only; private installed engines, never user
        # profiles or model configuration. No install/download in this runner.
        engine_path = old_env.get('PLAYWRIGHT_BROWSERS_PATH')
        if not engine_path or not Path(engine_path).is_absolute() or not Path(engine_path).is_dir():
            parser.error('ACTIVE_WEB_NATIVE_REQUIRES_EXPLICIT_INSTALLED_ENGINE_PATH')
        ci_env['PLAYWRIGHT_BROWSERS_PATH'] = engine_path
    native_profile=None
    if actual_host=='Windows'and not args.collect_only and args.job in (
            'web-v12-windows','web-v12-windows-native','web-v12-native','active-web-native'):
        native_profile=short_windows_profile(output,ci_env)
    os.environ.clear()
    os.environ.update(ci_env)
    old_sys_path=install_runtime_import_paths()
    import pytest
    guard = CollectionGuard(data, selected, args.job, actual_host, args.special, output)
    arguments = ["-q", "-p", "no:cacheprovider", "--rootdir", str(ROOT)]
    if actual_host=='Windows'and output is not None and not args.collect_only:
        arguments+=['-p','v12_b5.history_guard']
    # pytest 9 provides subtests itself; older versions require the installed
    # pytest-subtests plugin. Explicit loading avoids unrelated host plugins.
    if int(pytest.__version__.split(".", 1)[0]) < 9:
        arguments += ["-p", "pytest_subtests"]
    if args.collect_only:
        arguments += ["--collect-only"]
    elif output is not None:
        arguments += ["--basetemp", str(output / "pytest-private"),
                      "--junitxml", str(output / "tests.xml")]
    arguments += selected
    protect_history()
    stream = io.StringIO()
    bootstrap_error=None
    try:
        with redirect_stdout(stream), redirect_stderr(stream):
            exit_code = int(pytest.main(arguments, plugins=[guard]))
    except Exception as error:
        # Keep raw diagnostics local, never publish arbitrary exception text.
        bootstrap_error=type(error).__name__;exit_code=2
        stream.write('PYTEST_BOOTSTRAP_FAILED: '+bootstrap_error+'\n')
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        sys.path[:]=old_sys_path
        profile_cleanup=cleanup_windows_profile(native_profile)
    transcript = stream.getvalue()
    if (guard.skips_xfails or not guard.items or profile_cleanup['status']=='CLEANUP_UNCONFIRMED'
            or (not args.collect_only and guard.tests_executed!=len(guard.items))):
        exit_code=exit_code or 1
    receipt = {
        "schema": "positive-contract-ci-run-1",
        "scope": "COLLECTION_ONLY" if args.collect_only else "CURRENT_REGRESSION_CONTRACT",
        "job": args.job, "host": actual_host, "python": sys.version,
        "pytest": pytest.__version__, "selection_manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "positive_base_contracts": len(selected), "collected_parameter_instances": len(guard.items),
        "collected_nodeids_sha256": hashlib.sha256(json.dumps(guard.items, ensure_ascii=False).encode()).hexdigest(),
        "collection_guard": "PASS" if guard.passed else "FAIL",
        "tests_executed": guard.tests_executed,
        "quality_attempts": 0, "model_campaigns": 0,
        "exit_code": exit_code, "special_infrastructure": args.special,
        "skip_xfail_reports":guard.skips_xfails,
        "zero_collected":not bool(guard.items),
        "execution_complete":args.collect_only or guard.tests_executed==len(guard.items),
        "historical_python_write_veto":True,
        "historical_native_ntfs_guard":actual_host=='Windows'and not args.collect_only,
        "historical_helper_redirects":sorted(set(guard.helper_redirects)),
        "bootstrap_error_class":bootstrap_error,
        "new_skips_xfails_or_deselection":bool(guard.skips_xfails),
        "native_ci_profile_cleanup":profile_cleanup,
    }
    public_receipt={key:value for key,value in receipt.items()if key not in('skip_xfail_reports','historical_helper_redirects')}
    if output is not None:
        (output / "selection.json").write_text(json.dumps(selected, indent=2) + "\n", encoding="utf-8")
        (output / "collected_nodeids.json").write_text(json.dumps(guard.items, indent=2) + "\n", encoding="utf-8")
        (output / "pytest.log").write_text(transcript, encoding="utf-8")
        (output / "run.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        from sanitize_reports import publish
        public_receipt=publish(output)
    if exit_code:
        print('CI_CONTRACT_RUN_FAILED; public counters and sanitized diagnostics follow.',file=sys.stderr)
    print(json.dumps(public_receipt))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


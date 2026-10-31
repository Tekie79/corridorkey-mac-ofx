"""Namespace containment and missing-asset regressions; no live installation writes."""
import importlib.util
from pathlib import Path
import sys
import subprocess
import pytest
from ckmac.installation import PROFILES,installed_profile

REPO=Path(__file__).resolve().parents[1]


def manifest(profile):
    root=profile.root;build='0.9.8-qa1.test';model='ck2-test'
    return dict(installation_profile=profile.name,build_id=build,model_set_id=model,
        python=str(root/'Runtime'/build/'bin/python3'),code_root=str(root/'Runtime'/build/'upstream'),
        model_root=str(root/'Models'/model))


def test_qa_namespace_cannot_resolve_production_manifest_or_component():
    qa=PROFILES['qa'];prod=PROFILES['personal']
    qa.validate_manifest(manifest(qa))
    with pytest.raises(ValueError,match='profile mismatch'):qa.validate_manifest(manifest(prod))
    for key in ('python','model_root','code_root'):
        mixed=manifest(qa);mixed[key]=manifest(prod)[key]
        with pytest.raises(ValueError,match='escapes'):qa.validate_manifest(mixed)
    for key in ('build_id','model_set_id'):
        mixed=manifest(qa);mixed[key]='../CorridorKeyMac'
        with pytest.raises(ValueError,match='Unsafe'):qa.validate_manifest(mixed)


def test_installed_namespace_ignores_environment(monkeypatch):
    monkeypatch.setenv('CKMAC_BUILD_PROFILE','qa');monkeypatch.setenv('PYTHONPATH',str(PROFILES['qa'].root))
    assert installed_profile(REPO/'worker/ckmac/installation.py')==PROFILES['personal']
    for p in PROFILES.values():
        assert installed_profile(p.root/'Runtime/test/lib/python3.12/site-packages/ckmac/installation.py')==p
    assert installed_profile(Path(str(PROFILES['qa'].root)+'Other/Runtime/test/module.py'))==PROFILES['personal']


def test_qa_paths_receipts_and_socket_tokens_are_disjoint():
    prod,qa=PROFILES.values()
    for p in (prod,qa):
        for q in (prod,qa):
            if p==q:continue
            assert not p.root.is_relative_to(q.root)
            assert p.plugin!=q.plugin and p.manager!=q.manager
            assert p.domain!=q.domain and p.url_scheme!=q.url_scheme and p.cache_child!=q.cache_child
            assert p.endpoint('same-build',501).parent!=q.endpoint('same-build',501).parent
            assert len(str(p.endpoint('x'*100,501)))<104


@pytest.mark.parametrize('name',['personal','qa'])
def test_compiled_native_namespace_agrees_with_python(name):
    # Exercise actual preprocessor selection, including the unchanged default.
    import shutil
    compiler=shutil.which('clang++') or shutil.which('c++')
    if not compiler:pytest.skip('Native compiler unavailable')
    flags=['-DCKMAC_QA_PROFILE=1'] if name=='qa' else []
    code='\n'.join(['#include "ckmac/installation.hpp"']+[
        macro for macro in ('CKMAC_PROFILE','CKMAC_DOMAIN','CKMAC_PRODUCT_ROOT',
                            'CKMAC_PLUGIN_PATH','CKMAC_MANAGER_NAME','CKMAC_SOCKET_PREFIX',
                            'CKMAC_URL_SCHEME','CKMAC_DISPLAY_NAME','CKMAC_CACHE_CHILD')])
    result=subprocess.run([compiler,'-E','-P','-x','c++','-I'+str(REPO/'include'),*flags,'-'],
                          input=code,capture_output=True,text=True,check=True)
    import json
    values=[json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    p=PROFILES[name]
    assert values==[p.name,p.domain,str(p.root),str(p.plugin),p.manager_name,
                    p.socket_prefix,p.url_scheme,p.display_name,p.cache_child]


def release_module(name):
    sys.path.insert(0,str(REPO/'scripts/release'))
    spec=importlib.util.spec_from_file_location('profile_test_'+name,REPO/'scripts/release'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_qa_payload_rejects_production_files(tmp_path,monkeypatch):
    build=release_module('build');qa=PROFILES['qa']
    monkeypatch.setattr(build,'PROFILE',qa);monkeypatch.setattr(build,'PRODUCT',qa.root)
    own=tmp_path/qa.plugin.relative_to('/')/'Contents/MacOS/plugin';own.parent.mkdir(parents=True);own.write_bytes(b'QA')
    build.assert_namespace(tmp_path)
    foreign=tmp_path/PROFILES['personal'].root.relative_to('/')/'active.json'
    foreign.parent.mkdir(parents=True);foreign.write_text('{}')
    with pytest.raises(ValueError,match='escapes installation namespace'):build.assert_namespace(tmp_path)


def test_qa_installed_guide_never_directs_maintenance_to_production(monkeypatch):
    build=release_module('build');qa=PROFILES['qa'];prod=PROFILES['personal']
    monkeypatch.setattr(build,'PROFILE',qa);monkeypatch.setattr(build,'PRODUCT',qa.root)
    monkeypatch.setattr(build,'VERSION','0.9.8-qa.1')
    guide=build.installed_guide((REPO/'USER_GUIDE.md').read_text())
    assert str(qa.manager) in guide and str(qa.root/'Maintenance') in guide
    assert str(prod.manager) not in guide and str(prod.root/'Maintenance') not in guide
    assert 'CorridorKeyMac-0.9.8-qa.1-arm64-Offline.pkg' in guide


def test_missing_or_corrupt_model_asset_refuses_package():
    lock=release_module('lock_assets');a=dict(path='weights/model',size=8,sha256='a'*64)
    lock.require_complete_assets([a],dict(files=[a]))
    with pytest.raises(RuntimeError,match='Incomplete'):lock.require_complete_assets([],dict(files=[a]))
    with pytest.raises(RuntimeError,match='differs'):lock.require_complete_assets([dict(a,size=7)],dict(files=[a]))
    with pytest.raises(RuntimeError,match='Incomplete'):lock.require_complete_assets([a,a],dict(files=[a]))


def test_missing_corrupt_or_extra_wheel_refuses_package():
    lock=release_module('lock_assets');a=dict(name='Some_Wheel',version='1.2',sha256='a'*64)
    requirements='some-wheel==1.2 --hash=sha256:'+'a'*64
    lock.require_locked_wheels([a],requirements)
    for wheels in ([],[dict(a,sha256='b'*64)],[a,a],[a,dict(a,name='unexpected')]):
        with pytest.raises(RuntimeError,match='Wheelhouse differs'):lock.require_locked_wheels(wheels,requirements)

"""Fixed installation namespaces shared by packaging and installed maintenance.

Installed Python selects its namespace from its own protected runtime location,
never from HOME, PATH or a user environment variable.
"""
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Installation:
    name: str
    domain: str
    root: Path
    plugin: Path
    manager_name: str
    socket_prefix: str
    url_scheme: str
    display_name: str
    cache_child: str

    @property
    def manager(self):return Path('/Applications')/(self.manager_name+'.app')

    def endpoint(self,build,uid=None):
        return Path('/private/tmp')/(self.socket_prefix+str(os.getuid() if uid is None else uid))/(build[:32]+'.sock')

    def validate_manifest(self,manifest):
        if manifest.get('installation_profile','personal')!=self.name:
            raise ValueError('Installation profile mismatch')
        build=manifest['build_id'];model=manifest['model_set_id']
        for value in (build,model):
            if not value or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in value):
                raise ValueError('Unsafe installation identity')
        runtime=self.root/'Runtime'/build
        expected=dict(python=runtime/'bin/python3',code_root=runtime/'upstream',model_root=self.root/'Models'/model)
        if any(manifest.get(k)!=str(v) for k,v in expected.items()):
            raise ValueError('Installed component escapes its namespace')


PROFILES={
    'personal':Installation('personal','org.harvestpictures.CorridorKeyMac',
        Path('/Library/Application Support/HarvestPictures/CorridorKeyMac'),
        Path('/Library/OFX/Plugins/CorridorKeyMac.ofx.bundle'),'CorridorKey Mac Manager',
        'ckmac-','ckmachp','CorridorKey2.0 hp beta','CorridorKey-hp-Cache-'),
    'qa':Installation('qa','org.harvestpictures.CorridorKeyMac.QA',
        Path('/Library/Application Support/HarvestPictures/CorridorKeyMacQA'),
        Path('/Library/OFX/Plugins/CorridorKeyMacQA.ofx.bundle'),'CorridorKey Mac QA Manager',
        'ckmac-qa-','ckmachpqa','CorridorKey Mac QA','CorridorKey-QA-Cache-'),
}


def installed_profile(module_path=None):
    path=Path(module_path or __file__).resolve()
    for profile in PROFILES.values():
        if path.is_relative_to(profile.root/'Runtime'):return profile
    return PROFILES['personal']  # source/developer tools retain their legacy defaults

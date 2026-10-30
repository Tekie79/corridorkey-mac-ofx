"""Fail-closed profile selection tests; actual MLX evidence is separate."""
import pytest
from ckmac.backends import create_backend
from ckmac.backends.mlx_v2_backend import MLXV2Backend,SOURCE_COMMIT
from ckmac.backend import BackendError
from ckmac.profiles import Profile


def candidate(tmp_path):
    return MLXV2Backend(tmp_path,tmp_path,dict(source_commit=SOURCE_COMMIT,model_manifest_sha256='a'*64))


def test_mlx_profile_selection_is_lazy_and_never_downscales(tmp_path):
    b=candidate(tmp_path)
    b.validate_canvas(720,1280,Profile())
    assert b._model is None and b._torch is None
    for h,w in [(1080,1920),(2160,3840),(864,1536)]:
        with pytest.raises((BackendError,ValueError)):b.validate_canvas(h,w,Profile())
    assert b._model is None and b._torch is None
    # Only an explicit saved resize may choose a lower model canvas.
    b.validate_canvas(1080,1920,Profile(resolution=1))
    with pytest.raises(BackendError,match='t1/t4'):b.validate_canvas(720,1280,Profile(window=8))


def test_backend_choice_and_source_revision_never_fall_back(tmp_path):
    with pytest.raises(ValueError,match='Unsupported backend'):create_backend(dict(backend='automatic'))
    with pytest.raises(BackendError,match='Unreviewed'):MLXV2Backend(tmp_path,tmp_path,dict(source_commit='wrong'))

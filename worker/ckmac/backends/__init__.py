"""Backend selection is explicit, lazy and never falls back after GPU failure."""
def create_backend(manifest):
    backend=manifest.get('backend','mps')
    if backend=='mps':
        from .mps_backend import MPSBackend
        return MPSBackend(manifest['code_root'],manifest['model_root'])
    if backend=='mlx_v2':
        import sys
        sys.path.insert(0,manifest['code_root'])
        from .mlx_v2_backend import MLXV2Backend
        return MLXV2Backend(manifest['mlx_source_root'],manifest['mlx_model_root'],manifest['mlx_lock'])
    raise ValueError('Unsupported backend; choose mps or experimental mlx_v2 explicitly')

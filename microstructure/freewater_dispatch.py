"""Avoid redundant DIPY argument adapters, without replacing any fit mathematics.

Verified serial WLS avoids a dense diagonal; NLS retains its original code
object and uses that same WLS initialization. No DIPY globals are patched.
"""

import hashlib
import inspect
from types import FunctionType


_SOURCE_SHA256 = {
    'nls_iter': 'b25754feef042ba51106bdf6cc44d412f45a97505bb0d525be7f7390654bb019',
    'wls_iter': '17a44218fbc8d8c46aacbdd6c23d4424ce8ece69df1552b06386a1c2e1b0661b',
    '_nls_err_func': '05c48919624ad726525974facc306fdb144e09b69ebe7f4ca1cbaaa85dfbfeec',
    '_nls_jacobian_func': '6a3d0ae7e06d38bb9e8d5aeb4b3c49d98426d5ea5311fdc64fae77c3f11f7b1c',
}


def configure_freewater_dispatch(model, method, engine):
    """Use DIPY's callable fit hook only when the exact author bodies match."""
    record = {'enabled': False, 'implementation': 'dipy_original_dispatch'}
    if method not in {'NLS', 'WLS'} or engine != 'serial':
        return {**record, 'reason': 'Only serial WLS/NLS is qualified for this specialization'}
    import dipy
    from dipy.reconst import fwdti

    record['dipy_version'] = dipy.__version__
    if dipy.__version__ not in {'1.11.0', '1.12.1'}:
        return {**record, 'reason': 'Unqualified DIPY release; retain original dispatch'}
    if type(model) is not fwdti.FreeWaterTensorModel or model.fit_method is not fwdti.common_fit_methods.get(method):
        return {**record, 'reason': 'Custom model or fit method; retain original dispatch'}
    try:
        bodies = {name: inspect.unwrap(getattr(fwdti, name)) for name in _SOURCE_SHA256}
        hashes = {name: hashlib.sha256(inspect.getsource(body).encode('utf-8')).hexdigest()
                  for name, body in bodies.items()}
    except (OSError, TypeError, ValueError, AttributeError):
        return {**record, 'reason': 'Author source unavailable; retain original dispatch'}
    record['author_source_sha256'] = hashes
    if hashes != _SOURCE_SHA256:
        return {**record, 'reason': 'Author source mismatch; retain original dispatch'}
    from microstructure.freewater_wls import wls_iter
    if method == 'WLS':
        model.fit_method = wls_iter
        return {**record, 'enabled': True, 'implementation': 'dipy_verified_serial_wls_diagonal_free',
                'reason': 'Identical author WLS after C-order column scaling instead of a dense diagonal product'}
    body = bodies['nls_iter']
    namespace = dict(body.__globals__)
    namespace.update({name: value for name, value in bodies.items() if name != 'nls_iter'})
    namespace['wls_iter'] = wls_iter
    direct = FunctionType(body.__code__, namespace, body.__name__, body.__defaults__, body.__closure__)
    direct.__kwdefaults__ = dict(body.__kwdefaults__ or {})
    # Every argument already follows the author's keyword-only contract. The
    # copied globals isolate this instance from other models and worker threads.
    model.fit_method = direct
    return {**record, 'enabled': True, 'implementation': 'dipy_verified_serial_nls_diagonal_free_dispatch',
            'reason': 'Same author NLS/residual/Jacobian; diagonal-free WLS initialization; no argument compatibility adapters'}

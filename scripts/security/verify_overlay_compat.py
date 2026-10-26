"""Offline synthetic API probes; never invoke a model or load account settings."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


def probe(root: Path) -> None:
    from filelock import FileLock, Timeout
    from huggingface_hub.utils import WeakFileLock
    from litellm.litellm_core_utils.app_crypto import AppCrypto
    from cryptography import x509
    from cryptography.fernet import Fernet
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.x509.oid import NameOID

    lock_path = root / 'exclusive.lock'
    child = 'from filelock import FileLock,Timeout; import sys\ntry:\n with FileLock(sys.argv[1],timeout=0.1,mode=0o600): sys.exit(9)\nexcept Timeout: sys.exit(0)'
    with FileLock(lock_path, timeout=1, mode=0o600):
        subprocess.run([sys.executable, '-c', child, str(lock_path)], check=True)
        try:
            with FileLock(lock_path, timeout=0.05):
                raise AssertionError('second independent lock unexpectedly acquired')
        except Timeout:
            pass
    with FileLock(lock_path, timeout=1, mode=0o600):
        pass
    with WeakFileLock(root / 'huggingface.lock'):
        pass
    crypto = AppCrypto(bytes(range(32)))
    fixture = {'purpose': 'synthetic compatibility probe'}
    assert crypto.decrypt_json(crypto.encrypt_json(fixture, b'probe'), b'probe') == fixture
    fernet = Fernet(Fernet.generate_key())
    assert fernet.decrypt(fernet.encrypt(b'synthetic')) == b'synthetic'
    assert len(HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'probe').derive(b'synthetic')) == 32
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for pad in (padding.PKCS1v15(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)):
        signature = key.sign(b'synthetic', pad, hashes.SHA256())
        key.public_key().verify(signature, b'synthetic', pad, hashes.SHA256())
    for private in (key, ec.generate_private_key(ec.SECP256R1())):
        pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        restored = serialization.load_pem_private_key(pem, password=None)
        assert restored.public_key().public_numbers() == private.public_key().public_numbers()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'synthetic.invalid')])
    now = datetime.now(timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
                   .serial_number(1).not_valid_before(now).not_valid_after(now + timedelta(days=1)).sign(key, hashes.SHA256()))
    assert x509.load_pem_x509_certificate(certificate.public_bytes(serialization.Encoding.PEM), default_backend()).serial_number == 1
    print(json.dumps({'status': 'pass', 'checks': ['filelock_multiprocess_timeout_release', 'huggingface_weakfilelock',
          'litellm_appcrypto', 'fernet', 'hkdf', 'rsa_pkcs1_pss', 'ec_rsa_pem', 'x509_legacy_backend'],
          'filelock': version('filelock'), 'cryptography': version('cryptography'), 'litellm': version('litellm')}))


if __name__ == '__main__':
    with TemporaryDirectory(prefix='pgise-python-overlay-compat-') as folder:
        target = Path(folder)
        environment = {name: value for name, value in os.environ.items() if name.upper() in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP')}
        os.environ.clear()
        os.environ.update(environment)
        os.environ.update({'HOME': folder, 'USERPROFILE': folder, 'XDG_CONFIG_HOME': folder,
                           'XDG_CACHE_HOME': folder, 'DO_NOT_TRACK': '1', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True',
                           'LITELLM_LOG': 'ERROR', 'HF_HUB_OFFLINE': '1'})
        wrapper = Path(__file__).resolve().parents[2] / 'devtools/run.py'
        for flag in ('--help', '--version'):
            result = subprocess.run([sys.executable, str(wrapper), 'strix', flag], capture_output=True, timeout=60)
            assert result.returncode == 0
            assert (b'Usage' in result.stdout or b'usage' in result.stdout) if flag == '--help' else b'1.7.0' in result.stdout
        probe(target)

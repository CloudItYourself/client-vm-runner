import datetime
import ipaddress
from typing import Tuple
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding


def generate_self_signed_cert(name: str, ip: str) -> Tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, name)
    ])
    cert = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(
        private_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(
        datetime.datetime.utcnow()).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)).add_extension(
        x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]), critical=False).sign(private_key,
                                                                                                      hashes.SHA256(),
                                                                                                      default_backend()
                                                                                                      )
    return cert.public_bytes(Encoding.PEM), private_key.private_bytes(Encoding.PEM,
                                                                      serialization.PrivateFormat.PKCS8,
                                                                      serialization.NoEncryption())

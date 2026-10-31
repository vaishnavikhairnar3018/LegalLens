"""
Local Wi-Fi HTTPS Server for LenseScan
Directly serves the production Flutter Web build and proxies /api/ to FastAPI.
Guarantees instant mobile page loading and live camera streaming over local Wi-Fi.

Runs on https://<LOCAL_IP>:8443
- Static assets & SPA routes -> lensescan/build/web (instant, pre-compiled)
- /api/ -> FastAPI backend (http://127.0.0.1:8000)
"""

import os
import sys
import ssl
import socket
import mimetypes
import datetime
import ipaddress
import urllib.request
import urllib.error
from urllib.parse import urlparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Backend to forward /api/ to. Override: --backend http://127.0.0.1:8001  (or env LEGALLENS_BACKEND)
BACKEND_TARGET = os.environ.get("LEGALLENS_BACKEND", "http://127.0.0.1:8000")
if "--backend" in sys.argv:
    BACKEND_TARGET = sys.argv[sys.argv.index("--backend") + 1]
PROXY_PORT = 8443
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB_DIR = os.path.join(BASE_DIR, "lensescan", "build", "web")
CERT_FILE = os.path.join(os.path.dirname(__file__), "cert.pem")
KEY_FILE = os.path.join(os.path.dirname(__file__), "key.pem")

# Ensure proper mime types
mimetypes.init()
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("text/html", ".html")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/png", ".png")
mimetypes.add_type("image/jpeg", ".jpg")
mimetypes.add_type("image/jpeg", ".jpeg")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("font/otf", ".otf")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/woff2", ".woff2")


def get_local_ip():
    """Detect primary LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "10.244.134.104"


def generate_self_signed_cert(ip_str):
    """Generate self-signed certificate with IP SAN for local Wi-Fi."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    print(f"[*] Generating local SSL certificate for IP: {ip_str}...")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, ip_str),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LenseScan Local Wi-Fi"),
    ])

    san_list = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
    try:
        san_list.append(x509.IPAddress(ipaddress.IPv4Address(ip_str)))
    except Exception:
        san_list.append(x509.DNSName(ip_str))

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .sign(key, hashes.SHA256())
    )

    with open(KEY_FILE, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(CERT_FILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    print(f"[+] Certificate written to {CERT_FILE}")


class LenseScanHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean request logging with port and client IP
        port = getattr(self.server, "server_address", ("", ""))[1]
        sys.stderr.write(f"[{self.log_date_time_string()}] [Port {port}] [{self.client_address[0]}] {args[0]} {args[1]}\n")

    def _proxy_api(self):
        url = BACKEND_TARGET + self.path
        body = None
        if "Content-Length" in self.headers:
            content_len = int(self.headers["Content-Length"])
            body = self.rfile.read(content_len)

        req = urllib.request.Request(url, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length"):
                req.add_header(k, v)

        try:
            # A multi-photo scan runs OCR on every photo and can take several minutes on a CPU.
            with urllib.request.urlopen(req, timeout=900) as resp:
                self.send_response(resp.status)
                for header, val in resp.getheaders():
                    if header.lower() not in ("transfer-encoding", "content-length", "connection"):
                        self.send_header(header, val)
                content = resp.read()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                try:
                    self.wfile.write(content)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for header, val in e.headers.items():
                if header.lower() not in ("transfer-encoding", "content-length", "connection"):
                    self.send_header(header, val)
            err_content = e.read()
            self.send_header("Content-Length", str(len(err_content)))
            self.end_headers()
            try:
                self.wfile.write(err_content)
            except (BrokenPipeError, ConnectionResetError):
                pass
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self.send_response(502)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Backend offline at {BACKEND_TARGET}: {e}".encode())
            except Exception:
                pass

    def _serve_static(self):
        parsed = urlparse(self.path)
        clean_path = parsed.path.lstrip("/")

        # Check if requested file exists in web build
        target_path = os.path.join(WEB_DIR, clean_path)
        if not os.path.exists(target_path) or os.path.isdir(target_path):
            # SPA Fallback for client-side routing (/scan, /history, /profile)
            target_path = os.path.join(WEB_DIR, "index.html")

        if not os.path.exists(target_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Flutter web build not found. Run 'flutter build web' first.")
            return

        # Determine MIME type
        ctype, _ = mimetypes.guess_type(target_path)
        if not ctype:
            ctype = "application/octet-stream"

        try:
            with open(target_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(content)))
            # Flutter's main.dart.js and flutter_bootstrap.js keep the same names across builds,
            # so caching them would keep phones on an old build. Fonts and images are safe to cache.
            if target_path.endswith((".html", ".js", ".json", ".wasm")):
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            else:
                self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Error serving {clean_path}: {e}".encode())
            except Exception:
                pass

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy_api()
        else:
            self._serve_static()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy_api()
        else:
            self.send_response(405)
            self.end_headers()

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self._proxy_api()
        else:
            self.send_response(405)
            self.end_headers()

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy_api()
        else:
            self.send_response(405)
            self.end_headers()

    def do_OPTIONS(self):
        if self.path.startswith("/api/"):
            self._proxy_api()
        else:
            self.send_response(200)
            self.end_headers()


def run():
    import threading
    ip = get_local_ip()
    if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
        generate_self_signed_cert(ip)

    if not os.path.exists(WEB_DIR) or not os.path.exists(os.path.join(WEB_DIR, "index.html")):
        print(f"[!] Warning: {WEB_DIR} does not exist. Please run 'flutter build web' in lensescan/.")

    # 1. Start HTTP server on port 5000 (ideal for Android Chrome with flag)
    http_port = 5000
    try:
        http_server = ThreadingHTTPServer(("0.0.0.0", http_port), LenseScanHandler)
        http_server.daemon_threads = True
        threading.Thread(target=http_server.serve_forever, daemon=True).start()
        print(f"[+] HTTP server active on http://{ip}:{http_port}")
    except Exception as e:
        print(f"[!] Could not start HTTP server on {http_port}: {e}")

    # 2. Start HTTPS server on port 8443 (ideal for iPhone Safari)
    server = ThreadingHTTPServer(("0.0.0.0", PROXY_PORT), LenseScanHandler)
    server.daemon_threads = True
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print("\n" + "=" * 60)
    print(" LENSESCAN WI-FI SERVER READY (DIRECT PRODUCTION BUILD)")
    print("=" * 60)
    print(f"Option A (HTTPS - iPhone/Safari or Android):")
    print(f"   >>> https://{ip}:{PROXY_PORT} <<<")
    print(f"Option B (HTTP - Android Chrome with flag):")
    print(f"   >>> http://{ip}:{http_port} <<<")
    print("=" * 60 + "\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


if __name__ == "__main__":
    run()

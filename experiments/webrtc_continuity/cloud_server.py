"""Dedicated HTTPS-proxied signaling entrypoint for a single controlled Render demo.

The local-only server remains unchanged. This instance uses a Render TLS proxy,
strict public Host/Origin checks, and a high-entropy token supplied in Render env.
Never record SDP, token, URL fragments, or peer addresses in application logs.
"""
import os
import re
import sys
from http.server import ThreadingHTTPServer

from .server import Broker, Handler


class CloudHandler(Handler):
    """Same private broker protocol as the local app; explicit public host."""

    def allowed_origin(self):
        hostname = self.server.public_hostname
        expected_origin = 'https://' + hostname
        return (self.headers.get('Host') == hostname
                and self.headers.get('Sec-Fetch-Site') != 'cross-site'
                and (not self.headers.get('Origin') or self.headers['Origin'] == expected_origin))

    def do_GET(self):
        if self.path == '/healthz':
            if not self.allowed_origin():
                return self.reply(403, {'error': 'origin_not_allowed'})
            return self.reply(200, {'status': 'ok'})
        return super().do_GET()

    def navigation_origin(self):
        hostname = self.server.public_hostname
        return 'https://' + hostname if self.headers.get('Host') == hostname else None


class QuietCloudServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # no raw SDP, addresses, or request details in server logs


def cloud_config(env):
    """Offline-checkable startup validation. No listener created here."""
    if env.get('RENDER') != 'true':
        raise ValueError('Cloud server is only approved for a Render TLS-proxied web service')
    host = env.get('RENDER_EXTERNAL_HOSTNAME', '')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.onrender\.com', host):
        raise ValueError('Missing or invalid Render external hostname')
    token = env.get('SMARTCONNECT_SIGNAL_TOKEN', '')
    if not isinstance(token, str) or len(token) < 40 or len(token) > 256 or not re.fullmatch(r'[A-Za-z0-9_-]+', token):
        raise ValueError('Generate a high-entropy SMARTCONNECT_SIGNAL_TOKEN in Render (40+ URL-safe characters)')
    port = int(env.get('PORT', '10000'))
    if not 1024 <= port <= 65535:
        raise ValueError('Invalid Render PORT')
    return host, token, port


def main():
    try:
        host, token, port = cloud_config(os.environ)
        broker = Broker(token, policy_token=os.environ.get('SMARTCONNECT_POLICY_TOKEN'))
    except (ValueError, TypeError) as error:
        print('Cloud signaling configuration error: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
    server = QuietCloudServer(('0.0.0.0', port), CloudHandler)
    server.public_hostname = host
    server.broker = broker
    print('SmartConnect HTTPS-proxied signaling ready; no media starts until client approval.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

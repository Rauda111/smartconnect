"""New IPv4 HTTPS connection bound with Darwin IP_BOUND_IF. Dry-run default."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import http.client
import ipaddress
import math
import platform
import re
import socket
import ssl
import threading
import time
import uuid

# Verified in Apple's XNU and the installed macOS SDK <netinet/in.h>.
IP_BOUND_IF = 25


@dataclass(frozen=True)
class Target:
    address: str = '1.1.1.1'
    server_name: str = 'one.one.one.one'
    path: str = '/cdn-cgi/trace'
    port: int = 443
    timeout: float = 10.0
    max_bytes: int = 65536

    def validate(self):
        address=ipaddress.IPv4Address(self.address)
        if not address.is_global:
            raise ValueError('Use a public literal IPv4 destination for this experiment')
        if not re.fullmatch(r'[A-Za-z0-9.-]{1,253}',self.server_name):
            raise ValueError('Invalid TLS/HTTP server name')
        if not self.path.startswith('/') or any(ord(c)<33 or ord(c)>126 for c in self.path):
            raise ValueError('Use an ASCII HTTP origin path without whitespace')
        if self.port!=443 or not math.isfinite(self.timeout) or not 0<self.timeout<=30 or not 1<=self.max_bytes<=1048576:
            raise ValueError('Use HTTPS port 443, timeout 0..30s and body limit 1..1048576 bytes')


class Cancelled(Exception):
    pass


class BoundHTTPS(http.client.HTTPSConnection):
    def __init__(self, target, interface, result, cancel):
        super().__init__(target.server_name, target.port, timeout=target.timeout,
                         context=ssl.create_default_context())
        self.target,self.interface,self.result,self.cancel=target,interface,result,cancel
        self.deadline=time.monotonic()+target.timeout
        self.active=None
        self.lock=threading.Lock()

    def remaining(self):
        if self.cancel.is_set():
            raise Cancelled('Cancellation requested')
        value=self.deadline-time.monotonic()
        if value<=0:
            raise TimeoutError('Total request deadline exceeded')
        return value

    def abort(self):
        with self.lock:
            if self.active is not None:
                try:
                    self.active.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def connect(self):
        # Never invoke HTTPSConnection.connect(): it can resolve/connect unbound.
        if platform.system()!='Darwin':
            raise OSError('Live steering requires macOS')
        index=socket.if_nametoindex(self.interface)
        raw=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        with self.lock:
            self.active=raw
        try:
            raw.setsockopt(socket.IPPROTO_IP,IP_BOUND_IF,index)
            actual=raw.getsockopt(socket.IPPROTO_IP,IP_BOUND_IF)
            self.result['binding_index']=actual
            if actual!=index or not actual:
                raise OSError('Interface binding readback mismatch; no fallback')
            self.result['phase']='connect'
            raw.settimeout(self.remaining())
            raw.connect((self.target.address,self.target.port))
            local=raw.getsockname()
            self.result.update(local_ip=local[0],local_port=local[1],tcp_connected_epoch=time.time())
            self.result['tcp_connect_ms']=(time.monotonic()-self.result['_start'])*1000
            self.result['phase']='tls'
            # No proxy, DNS lookup, redirect, retry or shared connection pool.
            self.sock=self._context.wrap_socket(raw,server_hostname=self.target.server_name,do_handshake_on_connect=False)
            with self.lock:
                self.active=self.sock
            self.sock.settimeout(self.remaining())
            self.sock.do_handshake()
            self.result['tls_ready_ms']=(time.monotonic()-self.result['_start'])*1000
        except BaseException:
            raw.close()
            if self.sock is not None:
                self.sock.close()
            raise


def request(interface, target=None, execute=False, cancel=None):
    target=target or Target()
    target.validate()
    if not re.fullmatch(r'en\d+',interface):
        raise ValueError('Use an explicit macOS enN interface')
    cancel=cancel or threading.Event()
    start=time.monotonic()
    result=dict(request_id=uuid.uuid4().hex,source='dry_run' if not execute else 'actual_https',
                timestamp=datetime.now(timezone.utc).isoformat(),start_epoch=time.time(),
                requested_interface=interface,destination_ip=target.address,destination_port=target.port,
                server_name=target.server_name,path=target.path,status='dry_run',phase='planned',
                binding_index=None,local_ip=None,local_port=None,http_status=None,
                tcp_connected_epoch=None,tcp_connect_ms=None,tls_ready_ms=None,ttfb_ms=None,
                request_duration_ms=None,bytes_received=None,response_sha256=None,error='',
                verified_egress=None,egress_status='unverified',_start=start)
    if not execute:
        result.pop('_start')
        result['end_epoch']=time.time()
        return result
    connection=None
    response=None
    finished=threading.Event()
    watcher=None
    try:
        if cancel.is_set():
            raise Cancelled('Cancelled before socket creation')
        connection=BoundHTTPS(target,interface,result,cancel)
        # A request deadline and cancellation actively interrupt a stalled socket.
        def watch():
            while not finished.wait(.05):
                if cancel.is_set() or time.monotonic()>=connection.deadline:
                    connection.abort()
                    return
        watcher=threading.Thread(target=watch,daemon=True)
        watcher.start()
        result['phase']='binding'
        connection.connect()
        result['phase']='http'
        connection.sock.settimeout(connection.remaining())
        connection.request('GET',target.path,headers={'Host':target.server_name,'Connection':'close',
                            'Accept-Encoding':'identity','Cache-Control':'no-cache','User-Agent':'SmartConnect-StageA/1'})
        response=connection.getresponse()
        result['ttfb_ms']=(time.monotonic()-start)*1000
        result['http_status']=response.status
        body=bytearray()
        while True:
            connection.sock.settimeout(connection.remaining()) if connection.sock else None
            chunk=response.read1(min(8192,target.max_bytes+1-len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body)>target.max_bytes:
                raise ValueError('Response exceeds body limit')
        connection.remaining()
        result.update(bytes_received=len(body),response_sha256=hashlib.sha256(body).hexdigest(),
                      status='success' if 200<=response.status<300 else 'http_error',phase='complete')
    except (OSError,ValueError,http.client.HTTPException,Cancelled) as exc:
        if cancel.is_set() or isinstance(exc,Cancelled):
            status='cancelled'
        elif isinstance(exc,TimeoutError) or (connection is not None and time.monotonic()>=connection.deadline):
            status='timeout'
        else:
            status='binding_failed' if result['phase']=='binding' else 'request_failed'
        result.update(status=status,error=f'{type(exc).__name__}: {exc}')
    except KeyboardInterrupt:
        cancel.set()
        result.update(status='cancelled',error='KeyboardInterrupt')
    finally:
        finished.set()
        if response is not None:
            response.close()
        if connection is not None:
            connection.close()
        if watcher is not None:
            watcher.join(timeout=.2)
        result['end_epoch']=time.time()
        result['request_duration_ms']=(time.monotonic()-start)*1000
        result.pop('_start')
    return result


def target_dict(target):
    return asdict(target)

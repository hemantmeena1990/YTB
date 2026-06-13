#!/usr/bin/env python3
"""
Standalone SOCKS to HTTP Bridge Server
Run as a separate background process.
"""

import sys
import os
import socket
import threading
import select
import time
import random
import argparse
from pathlib import Path

try:
    import socks
    SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False
    print("Error: PySocks not installed. Run: pip install PySocks")
    sys.exit(1)


class SocksBridgeServer:
    def __init__(self, tor_port=9050, http_port=8888):
        self.tor_port = tor_port
        self.http_port = http_port
        self.running = False
        self.server_socket = None
        self.thread = None
    
    def start(self):
        """Start the bridge server in a background thread"""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        # Wait for server to start
        time.sleep(1)
        return self.is_running()
    
    def stop(self):
        """Stop the bridge server"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        if self.thread:
            self.thread.join(timeout=2)
    
    def is_running(self):
        """Check if server is running"""
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.settimeout(1)
            result = test_sock.connect_ex(('127.0.0.1', self.http_port))
            test_sock.close()
            return result == 0
        except:
            return False
    
    def _run(self):
        """Main server loop"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('127.0.0.1', self.http_port))
        self.server_socket.listen(50)
        
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                client.settimeout(30)
                thread = threading.Thread(target=self._handle_client, args=(client,))
                thread.daemon = True
                thread.start()
            except OSError:
                break
            except Exception:
                continue
    
    def _handle_client(self, client_sock):
        """Handle a single client connection"""
        try:
            data = client_sock.recv(8192)
            if not data:
                client_sock.close()
                return
            
            request = data.decode('utf-8', errors='ignore')
            lines = request.split('\r\n')
            if not lines:
                client_sock.close()
                return
            
            first_line = lines[0]
            parts = first_line.split(' ')
            if len(parts) < 2:
                client_sock.close()
                return
            
            method = parts[0]
            url = parts[1]
            
            # Handle HTTPS CONNECT
            if method == 'CONNECT':
                host_port = url.split(':')
                dest_host = host_port[0]
                dest_port = int(host_port[1]) if len(host_port) > 1 else 443
                
                client_sock.send(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                
                target = socks.socksocket()
                target.set_proxy(socks.SOCKS5, '127.0.0.1', self.tor_port)
                target.settimeout(30)
                target.connect((dest_host, dest_port))
                
                while self.running:
                    rlist, _, _ = select.select([client_sock, target], [], [], 30)
                    if client_sock in rlist:
                        data = client_sock.recv(8192)
                        if not data:
                            break
                        target.send(data)
                    if target in rlist:
                        data = target.recv(8192)
                        if not data:
                            break
                        client_sock.send(data)
                
                target.close()
                
            else:
                # Handle HTTP
                if url.startswith('http://'):
                    url = url[7:]
                elif url.startswith('https://'):
                    url = url[8:]
                
                if '/' in url:
                    host_part = url.split('/', 1)[0]
                    path = '/' + url.split('/', 1)[1]
                else:
                    host_part = url
                    path = '/'
                
                if ':' in host_part:
                    dest_host, dest_port = host_part.split(':')
                    dest_port = int(dest_port)
                else:
                    dest_host = host_part
                    dest_port = 80
                
                new_first_line = f"{method} {path} HTTP/1.1"
                new_request = new_first_line + '\r\n' + '\r\n'.join(lines[1:])
                
                target = socks.socksocket()
                target.set_proxy(socks.SOCKS5, '127.0.0.1', self.tor_port)
                target.settimeout(30)
                target.connect((dest_host, dest_port))
                target.send(new_request.encode())
                
                while True:
                    response = target.recv(8192)
                    if not response:
                        break
                    client_sock.send(response)
                
                target.close()
                
        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except:
                pass


# Global server instance
_bridge_server = None


def start_bridge_server(tor_port=9050, http_port=8888):
    """Start the bridge server as a background process"""
    global _bridge_server
    _bridge_server = SocksBridgeServer(tor_port, http_port)
    return _bridge_server.start()


def stop_bridge_server():
    """Stop the bridge server"""
    global _bridge_server
    if _bridge_server:
        _bridge_server.stop()
        _bridge_server = None


def is_bridge_running(http_port=8888):
    """Check if bridge server is running"""
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(1)
        result = test_sock.connect_ex(('127.0.0.1', http_port))
        test_sock.close()
        return result == 0
    except:
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='SOCKS to HTTP Bridge Server')
    parser.add_argument('--port', '-p', type=int, default=9050,
                        help='Tor SOCKS port (default: 9050)')
    parser.add_argument('--http-port', '-H', type=int, default=8888,
                        help='HTTP proxy port (default: 8888)')
    
    args = parser.parse_args()
    
    print(f"Starting SOCKS bridge server: {args.port} -> {args.http_port}")
    server = SocksBridgeServer(args.port, args.http_port)
    server.start()
    
    print(f"Bridge running on http://127.0.0.1:{args.http_port}")
    print("Press Ctrl+C to stop...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bridge...")
        server.stop()
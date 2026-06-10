#!/usr/bin/env python3
"""
HTTP to Tor SOCKS5 proxy - Supports both Tor Browser (9150) and Tor Service (9050)
"""

import socket
import threading
import select
import sys
import time
import argparse
import socks

# Default configuration
TOR_HOST = "127.0.0.1"
TOR_PORT = 9050  # Default to Tor Service (change with --port flag)
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8888

running = True

def handle_client(client_sock, client_addr, tor_port):
    """Handle a single client connection"""
    try:
        request = client_sock.recv(8192)
        if not request:
            client_sock.close()
            return
        
        request_str = request.decode('utf-8', errors='ignore')
        lines = request_str.split('\r\n')
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
        
        if url.startswith('http://'):
            url = url[7:]
        elif url.startswith('https://'):
            url = url[8:]
        
        if '/' in url:
            host_part = url.split('/', 1)[0]
        else:
            host_part = url
        
        if ':' in host_part:
            dest_host, dest_port = host_part.split(':', 1)
            dest_port = int(dest_port)
        else:
            dest_host = host_part
            dest_port = 443 if method == 'CONNECT' else 80
        
        # For HTTPS CONNECT method
        if method == 'CONNECT':
            client_sock.send(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            
            dest_sock = socks.socksocket()
            dest_sock.set_proxy(socks.SOCKS5, TOR_HOST, tor_port)
            dest_sock.connect((dest_host, dest_port))
            
            while True:
                rlist, _, _ = select.select([client_sock, dest_sock], [], [], 30)
                if client_sock in rlist:
                    data = client_sock.recv(8192)
                    if not data:
                        break
                    dest_sock.send(data)
                if dest_sock in rlist:
                    data = dest_sock.recv(8192)
                    if not data:
                        break
                    client_sock.send(data)
            
            dest_sock.close()
            client_sock.close()
            return
        
        # For HTTP
        dest_sock = socks.socksocket()
        dest_sock.set_proxy(socks.SOCKS5, TOR_HOST, tor_port)
        dest_sock.connect((dest_host, dest_port))
        dest_sock.send(request)
        
        while True:
            response = dest_sock.recv(8192)
            if not response:
                break
            client_sock.send(response)
        
        dest_sock.close()
        
    except Exception as e:
        print(f"[Proxy] Error: {e}")
    finally:
        client_sock.close()

def start_proxy(tor_port):
    """Start the proxy server"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((PROXY_HOST, PROXY_PORT))
    server.listen(50)
    
    print("=" * 60)
    print(f"Tor HTTP Proxy Server")
    print("=" * 60)
    print(f"Local HTTP Proxy: http://{PROXY_HOST}:{PROXY_PORT}")
    print(f"Tor SOCKS5 Target: {TOR_HOST}:{tor_port}")
    
    # Determine which Tor source is being used
    if tor_port == 9050:
        print("Tor Source: Tor Service (port 9050)")
    elif tor_port == 9150:
        print("Tor Source: Tor Browser (port 9150)")
    else:
        print(f"Tor Source: Custom (port {tor_port})")
    print("=" * 60)
    
    # Test Tor connection
    try:
        test_sock = socks.socksocket()
        test_sock.set_proxy(socks.SOCKS5, TOR_HOST, tor_port)
        test_sock.settimeout(5)
        test_sock.connect(("api.ipify.org", 80))
        test_sock.send(b"GET / HTTP/1.0\r\nHost: api.ipify.org\r\n\r\n")
        response = test_sock.recv(1024)
        test_sock.close()
        print("✅ Tor is running and accessible")
    except Exception as e:
        print(f"⚠️ Tor not accessible on port {tor_port}: {e}")
        print("Make sure Tor Browser (9150) or Tor Service (9050) is running!")
    
    print("=" * 60)
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    global running
    while running:
        try:
            client_sock, client_addr = server.accept()
            print(f"[Proxy] Connection from {client_addr}")
            thread = threading.Thread(target=handle_client, args=(client_sock, client_addr, tor_port))
            thread.daemon = True
            thread.start()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Proxy] Accept error: {e}")
    
    server.close()
    print("\n[Proxy] Stopped")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='HTTP to Tor SOCKS5 Proxy')
    parser.add_argument('--port', '-p', type=int, default=9050, 
                        help='Tor SOCKS5 port (9050 for Tor Service, 9150 for Tor Browser)')
    parser.add_argument('--local-port', '-l', type=int, default=8888,
                        help='Local HTTP proxy port (default: 8888)')
    
    args = parser.parse_args()
    
    PROXY_PORT = args.local_port
    tor_port = args.port
    
    # Validate tor_port
    if tor_port not in [9050, 9150]:
        print(f"Warning: Using custom Tor port {tor_port}. Expected 9050 (Tor Service) or 9150 (Tor Browser)")
    
    start_proxy(tor_port)
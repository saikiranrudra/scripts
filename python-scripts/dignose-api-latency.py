# lib required 
# 1. dnspython

import socket
import ssl
import sys
import time
from urllib.parse import urlparse
import dns.message
import dns.query
import dns.resolver

def parse_user_url(input_url):
    """
    Intelligently parses the user input URL, fallback testing protocols if missing.
    """
    cleaned = input_url.strip()
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        # If no protocol is provided, default to testing both, starting with https
        protocols_to_try = ["https", "http"]
        cleaned_for_parse = f"https://{cleaned}"
    else:
        protocols_to_try = [urlparse(cleaned).scheme]
        cleaned_for_parse = cleaned

    parsed = urlparse(cleaned_for_parse)
    host = parsed.hostname
    path = parsed.path if parsed.path else "/"
    if parsed.query:
        path += f"?{parsed.query}"
        
    return host, path, protocols_to_try

def run_dns_lookup(host):
    """
    Resolves DNS for IPv4 (A) and IPv6 (AAAA) while measuring RTT and packet loops.
    """
    metrics = {"ipv4": None, "ipv6": None, "rtt_ms": 0.0, "round_trips": 0}
    resolver = dns.resolver.Resolver()
    nameservers = resolver.nameservers
    
    start_dns = time.perf_counter()
    
    # Check IPv4 and IPv6
    for record_type, key in [(dns.rdatatype.A, "ipv4"), (dns.rdatatype.AAAA, "ipv6")]:
        query = dns.message.make_query(host, record_type)
        for ns in nameservers:
            metrics["round_trips"] += 1
            try:
                response, rtt = dns.query.udp_with_fallback(query, ns, timeout=1.5)
                if response.answer:
                    for rrset in response.answer:
                        if rrset.rdtype == record_type:
                            metrics[key] = str(rrset[0])
                    break
            except Exception:
                continue # Try the next nameserver if one drops/timeouts
                
    end_dns = time.perf_counter()
    metrics["rtt_ms"] = (end_dns - start_dns) * 1000
    return metrics

def measure_network_pipeline(ip, host, path, scheme, is_ipv6=False):
    """
    Manages low-level socket connections to time TCP, TLS, TTFB and payload transfer.
    """
    port = 443 if scheme == "https" else 80
    family = socket.AF_INET6 if is_ipv6 else socket.AF_INET
    
    # 1. TCP Handshake Time
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    
    try:
        start_tcp = time.perf_counter()
        sock.connect((ip, port))
        end_tcp = time.perf_counter()
        tcp_ms = (end_tcp - start_tcp) * 1000
    except Exception as e:
        sock.close()
        return {"error": f"TCP Connection failed: {e}"}

    # 2. TLS Handshake Time
    tls_ms = 0.0
    secure_sock = sock
    if scheme == "https":
        try:
            context = ssl.create_default_context()
            start_tls = time.perf_counter()
            secure_sock = context.wrap_socket(sock, server_hostname=host)
            end_tls = time.perf_counter()
            tls_ms = (end_tls - start_tls) * 1000
        except Exception as e:
            sock.close()
            return {"error": f"TLS Handshake failed: {e}"}

    # 3. API Actual Time (TTFB) & 4. Data Transfer Time
    try:
        # Build a compliance-safe HTTP/1.1 payload raw string
        http_request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        
        start_api = time.perf_counter()
        secure_sock.sendall(http_request.encode('utf-8'))
        
        # Read the very first byte to calculate True Time-to-First-Byte (API backend crunch time)
        first_byte = secure_sock.recv(1)
        end_api = time.perf_counter()
        
        api_ms = (end_api - start_api) * 1000
        
        # Read the remainder of the inbound server data
        start_transfer = time.perf_counter()
        remaining_data = b""
        while True:
            chunk = secure_sock.recv(4096)
            if not chunk:
                break
            remaining_data += chunk
        end_transfer = time.perf_counter()
        
        # Data transfer begins counting directly from the captured first byte receipt window
        transfer_ms = (end_transfer - start_transfer) * 1000
        
    except Exception as e:
        return {"error": f"Data exchange failed: {e}"}
    finally:
        secure_sock.close()

    return {
        "tcp_ms": tcp_ms,
        "tls_ms": tls_ms,
        "api_ms": api_ms,
        "transfer_ms": transfer_ms,
        "status": "Success"
    }

def main():
    print("=" * 60)
    user_input = input("Enter API URL / Endpoint: ")
    print("=" * 60)
    
    host, path, schemes = parse_user_url(user_input)
    if not host:
        print("[-] Invalid URL or Target Domain parsing failed.")
        return

    print(f"[*] Analyzing Target Domain: {host}")
    print(f"[*] Request Path / Parameters: {path}")
    
    # Execute DNS Metrics
    dns_data = run_dns_lookup(host)
    print(f"\n[+] DNS Round Trips Executed : {dns_data['round_trips']}")
    print(f"[+] Total DNS Resolution Time: {dns_data['rtt_ms']:.2f} ms")
    print(f"    - Resolved IPv4: {dns_data['ipv4']}")
    print(f"    - Resolved IPv6: {dns_data['ipv6']}")

    # Check for active IP configurations discovered
    resolved_ips = []
    if dns_data["ipv4"]: resolved_ips.append((dns_data["ipv4"], "IPv4", False))
    if dns_data["ipv6"]: resolved_ips.append((dns_data["ipv6"], "IPv6", True))
    
    if not resolved_ips:
        print("\n[-] Critical: Could not resolve target domain to valid IP configurations.")
        return

    # Iterate over available protocols and active IPs
    for scheme in schemes:
        for ip, ip_type, is_ipv6 in resolved_ips:
            print(f"\n" + "-"*25 + f" Testing via {scheme.upper()} ({ip_type}) " + "-"*25)
            print(f"Connecting directly to target IP: {ip}")
            
            pipeline = measure_network_pipeline(ip, host, path, scheme, is_ipv6)
            
            if "error" in pipeline:
                print(f"[-] Evaluation Bypass: {pipeline['error']}")
                continue
                
            print(f" 1. TCP Handshake Time   : {pipeline['tcp_ms']:.2f} ms")
            if scheme == "https":
                print(f" 2. TLS Handshake Time   : {pipeline['tls_ms']:.2f} ms")
            else:
                print(f" 2. TLS Handshake Time   : N/A (Plain HTTP Connection)")
            print(f" 3. API Actual Time(TTFB): {pipeline['api_ms']:.2f} ms")
            print(f" 4. Data Transfer Time   : {pipeline['transfer_ms']:.2f} ms")
            
    print("=" * 60)

if __name__ == "__main__":
    main()




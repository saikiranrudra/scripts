# 🚀 API Latency Diagnoser (`diagnose-api-latency.py`)

A high-precision, low-level Python network diagnostics tool designed to dissect and isolate every millisecond of your API lifecycle. It intelligently handles URL variations, tests dual-stack routing (IPv4 + IPv6), and automatically probes fallback schemes (HTTP/HTTPS) to uncover performance bottlenecks.

## 📊 Performance Metrics Tracked

The script maps out the exact network boundaries of an API request:

1. **DNS Round Trips:** Counts the exact number of client-to-resolver packet iterations.
2. **DNS Resolution Time:** Isolation of your domain resolution speed.
3. **TCP Handshake Time:** The raw network transit speed required to open a socket connection.
4. **TLS Handshake Time:** The exact cryptographic negotiation latency (for HTTPS).
5. **API Actual Time (TTFB):** *Time to First Byte*—the true processing latency of your API backend before streaming data.
6. **Data Transfer Time:** The time taken to pull the remainder of the payload down the wire.

---

## 🛠️ Prerequisites & Installation

This project utilizes [uv](https://github.com), an ultra-fast Python package installer and resolver.

### 1. Setup the Environment

If you haven't initialized your workspace directory yet:

```bash
uv init
```

### 2. Add Dependencies

Add the required DNS packet inspection library directly to your project environment:

```bash
uv add dnspython
```

### 3. Sync the Project

Ensure your local lockfile matches and resolves perfectly within your target folder:

```bash
uv sync
```

---

## 💻 Usage

You can safely run the diagnostic utility without manually managing virtual environments by executing it through `uv run`.

```bash
uv run diagnose-api-latency.py
```

### Smart URL Parsing Features

You do not need to clean your URLs before testing. The tool intelligently parses raw user inputs:

* **Protocol Inference:** If you enter `://example.com`, the script will proactively evaluate **both** `https://` and `http://` configurations.
* **Component Extraction:** Automatically detaches query strings and route paths from host identities to feed clean data payloads directly to low-level socket streams.

---

## 📋 Sample Output

```text
============================================================
Enter API URL / Endpoint: ://example.com
============================================================
[*] Analyzing Target Domain: ://example.com
[*] Request Path / Parameters: /v1/status

[+] DNS Round Trips Executed : 2
[+] Total DNS Resolution Time: 42.10 ms
    - Resolved IPv4: 93.184.215.14
    - Resolved IPv6: 2606:2800:220:1:248:1893:25c8:1946

------------------------- Testing via HTTPS (IPv4) -------------------------
Connecting directly to target IP: 93.184.215.14
 1. TCP Handshake Time   : 14.50 ms
 2. TLS Handshake Time   : 28.30 ms
 3. API Actual Time(TTFB): 112.40 ms
 4. Data Transfer Time   : 5.10 ms
============================================================
```

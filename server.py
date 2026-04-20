"""
Chand Parwardigar - 24077691d
Comp 2322 - Multi-threaded Web Server
"""

import socket
import threading
import os
import mimetypes
import logging
import datetime
import email.utils

# Configuration 
HOST = "127.0.0.1"
PORT = 8080
DOCUMENT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "www")
LOG_FILE = "server.log"
BUFFER_SIZE = 4096
SOCKET_TIMEOUT = 30  # seconds for persistent connections

# Logging setup 
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(message)s",
)

def log_request(client_host, method, path, status_code):
    """Write one log line per request: host, time, file, status."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_text = {
        200: "200 OK",
        304: "304 Not Modified",
        400: "400 Bad Request",
        403: "403 Forbidden",
        404: "404 Not Found",
    }.get(status_code, str(status_code))
    logging.info(f"{client_host} | {timestamp} | {method} {path} | {status_text}")


# HTTP helpers

def build_response_headers(status_code, extra_headers=None):
    """Return a bytes object containing the status line + standard headers."""
    reason = {
        200: "OK",
        304: "Not Modified",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
    }.get(status_code, "Unknown")

    lines = [f"HTTP/1.1 {status_code} {reason}"]
    now = email.utils.formatdate(usegmt=True)
    lines.append(f"Date: {now}")
    lines.append("Server: PythonWebServer/1.0")

    if extra_headers:
        for key, value in extra_headers.items():
            lines.append(f"{key}: {value}")

    lines.append("")  # blank line separates headers from body
    lines.append("")
    return "\r\n".join(lines).encode("utf-8")


def send_error(conn, status_code, keep_alive=False):
    """Send a minimal HTML error page."""
    reason = {
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
    }.get(status_code, "Error")

    body = (
        f"<html><head><title>{status_code} {reason}</title></head>"
        f"<body><h1>{status_code} {reason}</h1></body></html>"
    ).encode("utf-8")

    connection_header = "keep-alive" if keep_alive else "close"
    headers = build_response_headers(
        status_code,
        {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": str(len(body)),
            "Connection": connection_header,
        },
    )
    conn.sendall(headers + body)


# Request parser 

def parse_request(raw_data):
    """
    Parse raw HTTP request bytes.
    Returns (method, path, http_version, headers_dict) or raises ValueError.
    """
    try:
        text = raw_data.decode("utf-8", errors="replace")
        # Split request line from headers
        header_section, _, _ = text.partition("\r\n\r\n")
        lines = header_section.split("\r\n")
        request_line = lines[0]
        parts = request_line.split(" ")
        if len(parts) != 3:
            raise ValueError("Malformed request line")

        method, path, version = parts
        if not version.startswith("HTTP/"):
            raise ValueError("Not an HTTP request")

        # Parse headers into a dict (lowercase keys)
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                key, _, value = line.partition(":")
                headers[key.strip().lower()] = value.strip()

        return method.upper(), path, version, headers
    except Exception as exc:
        raise ValueError(f"Parse error: {exc}") from exc


# File-serving logic 

def resolve_path(request_path):
    """
    Safely map URL path to a filesystem path inside DOCUMENT_ROOT.
    Returns the absolute filesystem path, or None if traversal detected.
    """
    # Strip query string
    clean = request_path.split("?")[0]
    # Default to index.html
    if clean == "/" or clean == "":
        clean = "/index.html"

    # Build absolute path and confirm it's inside DOCUMENT_ROOT
    abs_path = os.path.realpath(os.path.join(DOCUMENT_ROOT, clean.lstrip("/")))
    if not abs_path.startswith(os.path.realpath(DOCUMENT_ROOT)):
        return None  # path traversal attempt
    return abs_path


def handle_get_head(conn, method, path, headers, client_host):
    """Handle GET and HEAD requests, including conditional GET (304)."""
    fs_path = resolve_path(path)

    # Path traversal
    if fs_path is None:
        send_error(conn, 403, keep_alive="keep-alive" in headers.get("connection", ""))
        log_request(client_host, method, path, 403)
        return

    # 404
    if not os.path.exists(fs_path):
        send_error(conn, 404, keep_alive="keep-alive" in headers.get("connection", ""))
        log_request(client_host, method, path, 404)
        return

    # 403  file exists but is not readable
    if not os.access(fs_path, os.R_OK):
        send_error(conn, 403, keep_alive="keep-alive" in headers.get("connection", ""))
        log_request(client_host, method, path, 403)
        return

    # Last-Modified
    mtime = os.path.getmtime(fs_path)
    last_modified = email.utils.formatdate(mtime, usegmt=True)

    # Handle If-Modified-Since (304)
    ims = headers.get("if-modified-since")
    if ims:
        try:
            ims_dt = email.utils.parsedate_to_datetime(ims)
            file_dt = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
            if file_dt <= ims_dt:
                keep_alive = "keep-alive" in headers.get("connection", "")
                connection_header = "keep-alive" if keep_alive else "close"
                response = build_response_headers(
                    304,
                    {
                        "Last-Modified": last_modified,
                        "Connection": connection_header,
                    },
                )
                conn.sendall(response)
                log_request(client_host, method, path, 304)
                return
        except Exception:
            pass 

    # 200 OK
    content_type, _ = mimetypes.guess_type(fs_path)
    if content_type is None:
        content_type = "application/octet-stream"

    keep_alive = "keep-alive" in headers.get("connection", "")
    connection_header = "keep-alive" if keep_alive else "close"
    file_size = os.path.getsize(fs_path)

    response_headers = build_response_headers(
        200,
        {
            "Content-Type": content_type,
            "Content-Length": str(file_size),
            "Last-Modified": last_modified,
            "Connection": connection_header,
        },
    )

    conn.sendall(response_headers)

    # HEAD returns only headers
    if method == "GET":
        with open(fs_path, "rb") as f:
            while True:
                chunk = f.read(BUFFER_SIZE)
                if not chunk:
                    break
                conn.sendall(chunk)

    log_request(client_host, method, path, 200)


# Per-connection handler

def handle_client(conn, addr):
    """
    Handle one client connection. Supports persistent connections (keep-alive).
    Each request in the loop is processed sequentially on this thread.
    """
    client_host = addr[0]
    conn.settimeout(SOCKET_TIMEOUT)

    try:
        while True:
            # Receive the full request (may need multiple reads)
            raw = b""
            try:
                while b"\r\n\r\n" not in raw:
                    chunk = conn.recv(BUFFER_SIZE)
                    if not chunk:
                        return  # client closed connection
                    raw += chunk
            except socket.timeout:
                return  # idle persistent connection timed out

            # Parse
            try:
                method, path, version, headers = parse_request(raw)
            except ValueError:
                send_error(conn, 400)
                log_request(client_host, "?", "/", 400)
                return

            # Dispatch
            if method in ("GET", "HEAD"):
                handle_get_head(conn, method, path, headers, client_host)
            else:
                # Method not supported 
                send_error(conn, 400, keep_alive="keep-alive" in headers.get("connection", ""))
                log_request(client_host, method, path, 400)

            # Decide whether to keep connection open
            connection = headers.get("connection", "").lower()
            if version == "HTTP/1.1":
                # Close only if explicitly requested
                if connection == "close":
                    return
            else:
                # Keep alive only if explicitly requested
                if connection != "keep-alive":
                    return

    except Exception as exc:
        print(f"[ERROR] Client {client_host}: {exc}")
    finally:
        conn.close()


# Main server loop

def start_server():
    """Bind the server socket and spawn a thread per incoming connection."""
    os.makedirs(DOCUMENT_ROOT, exist_ok=True)

    # Create a simple default index page
    index_path = os.path.join(DOCUMENT_ROOT, "index.html")
    if not os.path.exists(index_path):
        with open(index_path, "w") as f:
            f.write(
                "<html><head><title>Welcome</title></head>"
                "<body><h1>Welcome to the Python Web Server</h1>"
                "<p>Server is running on {}:{}</p></body></html>".format(HOST, PORT)
            )

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(10)

    print(f"[INFO] Web server started on http://{HOST}:{PORT}")
    print(f"[INFO] Serving files from: {DOCUMENT_ROOT}")
    print(f"[INFO] Log file: {LOG_FILE}")
    print("[INFO] Press Ctrl+C to stop.\n")

    try:
        while True:
            conn, addr = server_socket.accept()
            print(f"[INFO] Connection from {addr[0]}:{addr[1]}")
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("\n[INFO] Server shutting down.")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()

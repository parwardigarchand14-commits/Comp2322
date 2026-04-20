# Multi-threaded Web Server – README

## Requirements

- Python 3.8 or higher

## Directory Structure


project/
├── server.py        # Main server program
├── README.txt       # This file
└── www/             # Document root (auto-created on first run)
    ├── index.html   # Default page
    ├── sample.txt   # (add test files here)
    └── image.png    # (add images here)


## How to Run

1. Open a terminal and navigate to the project directory:

   cd /path/to/project
   

2. Start the server:

   python3 server.py

   The server listens on http://127.0.0.1:8080 by default.

3. Open a browser and visit:

   http://127.0.0.1:8080/
   http://127.0.0.1:8080/index.html


4. To stop the server, press *Ctrl+C* in the terminal.

## Configuration

Edit the constants near the top of `server.py`:

| Constant        | Default        | Description                        |
|-----------------|----------------|------------------------------------|
| `HOST`          | `127.0.0.1`    | Bind address                       |
| `PORT`          | `8080`         | Listening port                     |
| `DOCUMENT_ROOT` | `./www`        | Directory that contains web files  |
| `LOG_FILE`      | `server.log`   | Path to the request log            |
| `SOCKET_TIMEOUT`| `30`           | Idle keep-alive timeout (seconds)  |

## Testing with curl

bash
# GET a text file
curl -v http://127.0.0.1:8080/index.html

# HEAD request
curl -I http://127.0.0.1:8080/index.html

# Conditional GET (304 Not Modified)
curl -v -H "If-Modified-Since: Sat, 01 Jan 2100 00:00:00 GMT" \
     http://127.0.0.1:8080/index.html

# Persistent connection (keep-alive)
curl -v --http1.1 -H "Connection: keep-alive" \
     http://127.0.0.1:8080/index.html

# Non-persistent connection (close)
curl -v -H "Connection: close" http://127.0.0.1:8080/index.html

# Trigger 404
curl -v http://127.0.0.1:8080/missing.html

# Trigger 403 (create a file and remove read permission first)
chmod 000 www/secret.txt
curl -v http://127.0.0.1:8080/secret.txt


## Log File Format

Each line in `server.log` has four fields separated by ` | `:


<client-IP> | <YYYY-MM-DD HH:MM:SS> | <METHOD> <path> | <status>


Example:

127.0.0.1 | 2026-04-20 14:32:01 | GET /index.html | 200 OK
127.0.0.1 | 2026-04-20 14:32:05 | GET /missing.html | 404 Not Found


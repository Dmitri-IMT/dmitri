"""Minimal unauthenticated Telnet protocol responder for isolated lab scans."""

import socket
import threading

HOST = "0.0.0.0"
PORT = 23
IAC = bytes((255,))
WILL = bytes((251,))
WONT = bytes((252,))
DO = bytes((253,))
DONT = bytes((254,))
ECHO = bytes((1,))
SUPPRESS_GO_AHEAD = bytes((3,))


def handle(connection: socket.socket) -> None:
    with connection:
        connection.settimeout(2)
        connection.sendall(IAC + WILL + ECHO + IAC + WILL + SUPPRESS_GO_AHEAD)
        connection.sendall(b"DMITRI isolated Telnet training endpoint\r\nLogin disabled.\r\n")
        try:
            data = connection.recv(128)
            if data:
                # Refuse Telnet option negotiation and never process credentials.
                connection.sendall(IAC + WONT + ECHO + IAC + DONT + SUPPRESS_GO_AHEAD)
        except (TimeoutError, OSError):
            pass


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((HOST, PORT))
    listener.listen(16)
    while True:
        client, _ = listener.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()

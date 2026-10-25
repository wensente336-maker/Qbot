"""本地 TCP 隧道：把 127.0.0.1:10022 的流量经 HTTP 代理转发到腾讯云 SSH（22）。

沙箱直连 22 端口会被拦，只能走 127.0.0.1:18080 的 HTTP CONNECT 代理。
"""

import socket
import threading

TARGET = ("129.204.35.57", 22)
PROXY = ("127.0.0.1", 18080)
LISTEN = ("127.0.0.1", 10022)


def handle(client: socket.socket) -> None:
    try:
        upstream = socket.create_connection(PROXY, 10)
        upstream.sendall(
            f"CONNECT {TARGET[0]}:{TARGET[1]} HTTP/1.1\r\n"
            f"Host: {TARGET[0]}:{TARGET[1]}\r\n\r\n".encode()
        )
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = upstream.recv(1024)
            if not chunk:
                raise ConnectionError("proxy closed")
            head += chunk
        if b" 200 " not in head.split(b"\r\n")[0]:
            raise ConnectionError(head[:120])
    except Exception:
        client.close()
        return

    def pump(a: socket.socket, b: socket.socket) -> None:
        try:
            while True:
                data = a.recv(65536)
                if not data:
                    break
                b.sendall(data)
        except OSError:
            pass
        finally:
            try:
                b.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    threading.Thread(target=pump, args=(client, upstream), daemon=True).start()
    pump(upstream, client)
    client.close()
    upstream.close()


server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(LISTEN)
server.listen(16)
while True:
    conn, _ = server.accept()
    threading.Thread(target=handle, args=(conn,), daemon=True).start()

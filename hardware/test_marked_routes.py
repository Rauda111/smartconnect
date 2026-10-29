import socket
import subprocess

DESTINATION = "192.168.30.10"

PATHS = {
    "A": 101,
    "B": 102,
}


def test_path(path, mark):
    print(f"\nTesting Path {path} using mark {mark}")

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_RAW,
        socket.IPPROTO_ICMP
    )

    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_MARK, mark)

        result = subprocess.run(
            [
                "ip",
                "route",
                "get",
                DESTINATION,
                "mark",
                str(mark),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        print(result.stdout.strip())
        print("Socket mark applied successfully.")

    finally:
        sock.close()


def main():
    print("SmartConnect Marked Routing Test")
    print("--------------------------------")

    for path, mark in PATHS.items():
        test_path(path, mark)


if __name__ == "__main__":
    main()

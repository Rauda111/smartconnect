import subprocess

PC2_NETWORK = "192.168.30.0/24"
INTERFACE = "eno2"

ROUTERS = {
    "A": "192.168.10.1",
    "B": "192.168.10.2"
}


def switch_network(path):
    if path not in ROUTERS:
        raise ValueError("Invalid network path")

    gateway = ROUTERS[path]

    command = [
        "ip",
        "route",
        "replace",
        PC2_NETWORK,
        "via",
        gateway,
        "dev",
        INTERFACE
    ]

    subprocess.run(command, check=True)

    print(f"Switched to Path {path}")
    print(f"Gateway: {gateway}")


def show_current_route():
    subprocess.run(
        ["ip", "route", "get", "192.168.30.10"],
        check=True
    )


if __name__ == "__main__":
    print("SmartConnect Hardware Controller")

    print("1. Switch to Router 1")
    print("2. Switch to Router 2")
    print("3. Show current route")

    choice = input("Choose an option: ")

    if choice == "1":
        switch_network("A")
    elif choice == "2":
        switch_network("B")
    elif choice == "3":
        show_current_route()
    else:
        print("Invalid choice")

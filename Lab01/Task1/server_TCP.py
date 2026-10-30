import socket
import threading

from click import command

bind_ip = "0.0.0.0"
bind_port = 9001

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((bind_ip, bind_port))

server.listen(10)
server.settimeout(1.0)

print(f"[+] Listening on port {bind_ip} : {bind_port}")
dictionary = {}

commands = ["PING", "ECHO", "SET", "GET"]

def handle_client(client_socket):
    try:
        partial_data = ""
        while True:
            
            data = client_socket.recv(1024)

            # Client disconnected
            if not data:
                break

            data = data.decode()
            partial_data += data
            print(f"[+] Received data: {data.strip()}")

            if "\n" in partial_data:
                
                data = partial_data.strip().split("\n")
                partial_data = ""
                for command in data:
                    if command.split(" ")[0] in commands:

                        if command == "PING":
                            response = "PONG"

                        if command.startswith("ECHO"):
                            response = command.split(" ", 1)[1]

                        if command.startswith("SET"):
                            try:
                                key = command.split(" ")[1]
                                value = command.split(" ", 2)[2]

                                print(f"[+] Setting key: {key} to value: {value}")

                                dictionary[key] = value
                                response = "OK"
                            except IndexError:
                                response = "ERR"

                        if command.startswith("GET"):
                            try:
                                key = command.split(" ")[1]
                                if key in dictionary:
                                    value = dictionary[key]
                                else:
                                    value = "NOT_FOUND"
                                response = value
                            except IndexError:
                                response = "ERR"

                    else:
                        response = "ERR"

                    print(f"[+] Sending response: {response.strip()}")
                    response += "\n"
                    client_socket.send(response.encode())

    finally:
        client_socket.close()
        print("[+] Client connection closed.\n")


try:
    while True:
        try:
            client, addr = server.accept()
        except socket.timeout:
            continue

        print(f"[+] Accepted connection from: {addr[0]}:{addr[1]}")
        threading.Thread(target=handle_client, args=(client,), daemon=True).start()

except KeyboardInterrupt:
    print("\n[+] Shutting down the server.")
finally:
    server.close()

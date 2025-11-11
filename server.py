import socket, os, struct


def receive_file_size(sck: socket.socket):
    # This funcion makes sure that the bytes which indicate the size of the file that will be sent are received.
    # The file is packed by the client via struct.pack(), 
    # a function that generates a bytes sequence that represents the file size.
    fmt = "<Q"
    expected_bytes = struct.calcsize(fmt)
    received_bytes = 0
    stream = bytes()
    while received_bytes < expected_bytes:
        chunk = sck.recv(expected_bytes - received_bytes)
        stream += chunk
        received_bytes += len(chunk)
    filesize = struct.unpack(fmt, stream)[0]
    return filesize


def receive_file(sck: socket.socket, filename):
    filesize = receive_file_size(sck)
    with open(filename, "wb") as f:
        received_bytes = 0
        while received_bytes < filesize:
            bytes_to_receive = min(1024, filesize - received_bytes)
            chunk = sck.recv(bytes_to_receive)
            if not chunk:
                raise ConnectionError(f"Connection closed. Received {received_bytes}/{filesize} bytes")
            f.write(chunk)
            received_bytes += len(chunk)

download_folder = "./downloads"
os.makedirs(download_folder, exist_ok=True)

# Delete all files in downloads folder
for filename in os.listdir(download_folder):
        file_path = os.path.join(download_folder, filename)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                print(f"Error deleting {file_path}: {e}")

with socket.create_server(("localhost", 3000)) as server:
    print("Waiting for the client...")
    conn, address = server.accept()
    print(f"{address[0]}:{address[1]} connected.")
    
    num_files = receive_file_size(conn)
    for i in range(num_files):
        print(f"Receiving file {i}...")
        filepath = os.path.join(download_folder, f"received-file-{i}.bin")
        receive_file(conn, filepath)
        print(f"File {i} received.")

print("Connection closed.")

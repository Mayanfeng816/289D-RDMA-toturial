# RDMA Basic Read Example
This example demonstrates the essential control flow for performing a one-sided RDMA Read from a client into a memory region hosted on the server, using `librdmacm` and `libibverbs`.

On the server side, the program:

- Initializes an RDMA endpoint, listens on a TCP port, and accepts an incoming RDMA connection.
- Creates a Queue Pair and allocates a 4 KB buffer in host memory.
- Fills this buffer with an application-defined message (e.g., `"Hello RDMA READ (from server)"`).
- Registers this buffer as a memory region with IBV_ACCESS_REMOTE_READ, and sends its (addr, rkey, len) to the client via the RDMA connection manager’s private data field.
- Does not issue any RDMA work requests itself; it simply waits while the client pulls the data and then prints the buffer content.

On the client side, the program:

- Resolves the server’s address and route, creates a Queue Pair, and establishes the RDMA connection.
- Receives the server’s memory metadata (`addr, rkey, len`) through private data.
- Allocates and registers a local buffer as the destination of the RDMA Read.
- Posts a single `IBV_WR_RDMA_READ` work request that pulls data from the server’s buffer into its local memory and waits for completion by polling the send completion queue.
- After completion, prints the data that was fetched from the server.

The following are the actual implementations:

```
--8<-- "code/basic_read/client.c"
```

```
--8<-- "code/basic_read/server.c"
```
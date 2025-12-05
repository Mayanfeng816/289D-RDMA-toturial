# RDMA Basic Write Example
This example illustrates the essential control flow required to perform a one-sided RDMA Write between two machines using `librdmacm` and `libibverbs`. The server initializes an RDMA endpoint, creates a Queue Pair, and registers a memory region that is exposed to remote write operations. Its memory address and RKey are delivered to the client through the RDMA connection manager’s private-data field during connection establishment.

The client resolves the server’s address and route, creates its own Queue Pair, registers a local buffer, and then issues a single RDMA Write targeting the server-provided memory region. Completion is detected by polling the client’s send completion queue, while the server receives the data without posting any receive work requests or involving its CPU in the data path.

Overall, this example provides a minimal yet complete demonstration of the RDMA programming pipeline:
`connection setup` → `memory registration` → `capability exchange` → `one-sided write` → `completion handling`.

The following are the actual implementations:

```
--8<-- "code/basic_write/client.c"
```

```
--8<-- "code/basic_write/server.c"
```
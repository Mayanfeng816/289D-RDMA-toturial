# Introduction to RDMA
## RDMA
Remote Direct Memory Access (RDMA) is a networking technology that allows one machine to directly read or write the memory of another machine **without involving the remote CPU or operating system**. By bypassing the kernel and avoiding unnecessary memory copies, RDMA provides:

| Benefit | Effect |
|--------|--------|
| **Very low latency** | Data is transferred without kernel involvement |
| **Low CPU overhead** | Remote access does not require remote CPU work |
| **Zero-copy transfer** | No intermediate buffer copying is needed |
| **High throughput** | NIC hardware handles data movement efficiently |

Compared to traditional TCP/IP networking, RDMA reduces communication overhead significantly. It does not require multiple memory copies and kernel transitions. This makes RDMA especially valuable in **data centers, HPC clusters, and distributed AI training**, because these systems need to exchange large amounts of data efficiently.

---

## What This Tutorial Covers

This section focuses on **GPU-side RDMA fundamentals**:

- The **RDMA Verbs API** and how applications interact with RDMA hardware  
- **Memory Registration**, which grants permission for remote access  
- **Queue Pairs**, the core communication endpoints in RDMA programs  

---

## Learning Outcomes

After completing the RDMA Basics section, you will be able to:

- Understand the RDMA programming model and key objects (PD, MR, CQ, QP)
- Register memory regions and work with memory access keys
- Set up and configure Queue Pairs for communication
- Run and modify basic RDMA operations such as Write, Read, and Send/Recv

---

Next, we begin with the **RDMA Verbs API**.

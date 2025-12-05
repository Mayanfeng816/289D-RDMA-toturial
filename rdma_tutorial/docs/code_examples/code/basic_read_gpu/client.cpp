#include <rdma/rdma_cma.h>
#include <infiniband/verbs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <hip/hip_runtime.h>

struct Info {
  uint64_t addr;
  uint32_t rkey, len;
} __attribute__((packed));

static void die(const char *m) {
  perror(m);
  exit(1);
}

int main(int argc,char**argv){
  if(argc < 3){
    fprintf(stderr,"Usage: %s <server_ip> <port>\n", argv[0]);
    return 1;
  }
  const char* ip   = argv[1];
  int         port = atoi(argv[2]);

  struct rdma_event_channel *ec = rdma_create_event_channel();
  struct rdma_cm_id *id;
  struct rdma_cm_event *e;
  if (rdma_create_id(ec, &id, NULL, RDMA_PS_TCP))
    die("create_id");

  struct addrinfo *res;
  char ps[16];
  snprintf(ps, sizeof(ps), "%d", port);
  if (getaddrinfo(ip, ps, NULL, &res))
    die("getaddrinfo");

  if (rdma_resolve_addr(id, NULL, res->ai_addr, 2000))
    die("resolve_addr");
  if (rdma_get_cm_event(ec, &e))
    die("event1");
  rdma_ack_cm_event(e);

  if (rdma_resolve_route(id, 2000))
    die("resolve_route");
  if (rdma_get_cm_event(ec, &e))
    die("event2");
  rdma_ack_cm_event(e);

  struct ibv_qp_init_attr qa = {};
  qa.qp_type          = IBV_QPT_RC;
  qa.cap.max_send_wr  = qa.cap.max_recv_wr  = 8;
  qa.cap.max_send_sge = qa.cap.max_recv_sge = 1;
  qa.sq_sig_all       = 1;
  if (rdma_create_qp(id, id->pd, &qa))
    die("create_qp");

  struct rdma_conn_param p = {};
  if (rdma_connect(id, &p))
    die("connect");

  if (rdma_get_cm_event(ec, &e))
    die("event3");
  struct Info info;
  memcpy(&info, e->param.conn.private_data, sizeof(info));
  rdma_ack_cm_event(e);

  size_t len = info.len;
  if (len < 64) len = 64;

  char *d_buf = NULL;
  hipError_t herr;
  herr = hipMalloc((void**)&d_buf, len);
  if (herr != hipSuccess) {
    fprintf(stderr, "hipMalloc failed: %s\n", hipGetErrorString(herr));
    return 1;
  }

  herr = hipMemset(d_buf, 0, len);
  if (herr != hipSuccess) {
    fprintf(stderr, "hipMemset failed: %s\n", hipGetErrorString(herr));
    return 1;
  }

  struct ibv_mr *mr = ibv_reg_mr(
      id->pd,
      d_buf,
      len,
      IBV_ACCESS_LOCAL_WRITE
  );
  if (!mr) {
    perror("ibv_reg_mr GPU");
    return 1;
  }

  struct ibv_sge s = {
      .addr   = (uintptr_t)d_buf,
      .length = (uint32_t)len,
      .lkey   = mr->lkey
  };

  struct ibv_send_wr wr = {}, *bad = NULL;
  wr.opcode              = IBV_WR_RDMA_READ;
  wr.sg_list             = &s;
  wr.num_sge             = 1;
  wr.wr.rdma.remote_addr = info.addr;
  wr.wr.rdma.rkey        = info.rkey;

  if (ibv_post_send(id->qp, &wr, &bad)) {
    perror("ibv_post_send (READ)");
    return 1;
  }

  struct ibv_wc wc;
  while (ibv_poll_cq(id->qp->send_cq, 1, &wc) == 0) { /* busy wait */ }
  if (wc.status != IBV_WC_SUCCESS) {
    fprintf(stderr, "RDMA READ failed, wc.status=%d\n", wc.status);
    return 1;
  }

  char host_buf[64] = {0};
  herr = hipMemcpy(host_buf, d_buf, sizeof(host_buf), hipMemcpyDeviceToHost);
  if (herr != hipSuccess) {
    fprintf(stderr, "hipMemcpy D2H failed: %s\n", hipGetErrorString(herr));
    return 1;
  }

  printf("[client][GPU] RDMA read: '%.*s'\n", 64, host_buf);

  rdma_disconnect(id);
  ibv_dereg_mr(mr);
  hipFree(d_buf);

  rdma_destroy_qp(id);
  rdma_destroy_id(id);
  rdma_destroy_event_channel(ec);
  freeaddrinfo(res);

  return 0;
}

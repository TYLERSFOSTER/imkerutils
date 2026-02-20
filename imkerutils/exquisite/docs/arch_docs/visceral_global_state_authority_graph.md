# VISCERAL — Global State Reconstruction & Authority Binding
**Date:** 2026-02-20 (America/New_York)

This document provides two Mermaid diagrams of the **runtime system graph** described in
“Global State Reconstruction, Authority Binding, and Systems Failure Modes”:

1. A **high-level** abstract topology diagram (roles + authority uniqueness).
2. A **nitty-gritty** runtime graph diagram (processes, configs, identity stores, sockets, tunnels, clients, caches) showing where split-brain and referential ambiguity appear.

---

## Diagram 1 — High-level (Abstract Roles & Authorities)

```mermaid
flowchart LR
  subgraph Human
    H1[Engineer_Project_Owner]
    HM[State_Estimate_x_hat_t]
  end

  subgraph System
    SYS[Runtime_System_x_t]
    GWA[Gateway_Authority]
    CFA[Config_Authority]
    IDA[Identity_Authority]
    NTA[Network_Authority]
    CLA[Client_Authority]
    OBS[Observability_Authority]
  end

  subgraph Discipline
    GSR[Global_State_Reconstruction]
    AB[Authority_Binding]
    VG[Verification_Gate]
  end

  H1 --> OBS
  OBS --> HM
  HM --> SYS

  GSR --> SYS
  AB --> SYS
  VG --> SYS

  GWA --- CFA
  GWA --- IDA
  GWA --- NTA
  GWA --- CLA

  HM -.-> SYS
```

**Reading guide:**
- The system fails when the operator’s internal state model **x̂(t)** diverges from the real system **x(t)**, yet local checks continue to pass.
- The fix is not “debug a node”; it’s to **reconstruct the runtime graph**, then **bind authorities uniquely**.

---

## Diagram 2 — Nitty-gritty (Runtime Graph, Referents, and Split-Brain)

```mermaid
flowchart LR
  subgraph Server
    subgraph Processes
      GW[gateway_PID_X]
      PX[shadow_gateway_PID_Y]
      PR[reverse_proxy]
    end

    subgraph ConfigRoots
      CF1[etc_openclaw_config_json]
      CF2[home_foster_dot_openclaw_config_json]
      CF3[container_mounted_config]
    end

    subgraph IdentityStores
      ID1[home_foster_dot_openclaw_identities]
      ID2[container_identity_store]
      ID3[browser_token_cache]
    end

    subgraph NetworkEndpoints
      S4[ipv4_local_18789_ws_http]
      S6[ipv6_local_18789_ws_http]
      PUB[public_ingress]
    end

    subgraph Observability
      JL[journalctl]
      LS[lsof_netstat]
      PS[ps_systemd]
    end
  end

  subgraph Client
    subgraph UISurface
      BR[browser_ui]
      VS[vscode_helper]
      CLI[curl_ssh]
    end

    subgraph Tunnels
      SSH[ssh_local_forward]
      L4[local_ipv4_18789]
      L5[local_ipv4_18790]
      V6[local_ipv6_18789]
    end

    subgraph ClientCache
      KC[keychain]
      LS1[localstorage_indexeddb]
      CK[cookies]
    end
  end

  GW --> CF1
  GW --> CF2
  PX --> CF3

  GW --> ID1
  PX --> ID2
  BR --> LS1
  BR --> CK
  KC --> CLI

  GW --> S4
  GW --> S6
  PR --> PUB

  BR --> L4
  CLI --> L4
  L4 --> S4
  L5 --> S4
  V6 --> S6
  SSH --> L4
  SSH --> L5
  SSH --> V6

  JL --> CLI
  LS --> CLI
  PS --> CLI

  GW -.-> PX
  CF1 -.-> CF2
  CF2 -.-> CF3
  ID1 -.-> ID2
  ID3 -.-> ID1
  S4 -.-> S6
  L4 -.-> V6
  VS -.-> L4

  L4 --> BR
  S4 --> CLI
  CF2 --> CLI
  ID1 --> CLI
```

**Reading guide (nitty-gritty):**
- **Global State Reconstruction** means enumerating **exactly which nodes exist** (processes/configs/identity stores/sockets/tunnels/caches) and the **edges** (reads/listens/connects/validates).
- **Authority Binding** is the explicit act of selecting *one* referent per role:
  - *Gateway authority* = `openclaw-gateway (PID X)` (not “the gateway somewhere”)
  - *Config authority* = `/home/foster/.openclaw/config.json` (or whichever is proven loaded)
  - *Identity authority* = `/home/foster/.openclaw/identities/` (or whichever is proven used)
  - *Network authority* = `127.0.0.1:18789` (or whatever is proven reachable end-to-end)
- The **stable trap** is when multiple local checks are “green” while the *graph* is incoherent (split-brain, wrong referent, wrong tunnel, wrong cache).

---

## Minimal checklist (diagram-driven)
To exit “locally consistent / globally wrong,” bind these with evidence:

1. **Gateway authority** → exact PID + exact listener sockets.
2. **Config authority** → exact file path proven loaded by the gateway.
3. **Identity authority** → exact identity root path used for validation.
4. **Client path authority** → exact local listener → exact remote socket mapping.
5. **Client token authority** → exact token store (browser cache vs server) and its lifecycle.

End.

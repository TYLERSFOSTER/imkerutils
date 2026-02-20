# VISCERAL — Global State Reconstruction & Authority Binding
**Date:** 2026-02-20 (America/New_York)

This document provides two Mermaid diagrams of the **runtime system graph** described in
“Global State Reconstruction, Authority Binding, and Systems Failure Modes”:

1. A **high-level** abstract topology diagram (roles + authority uniqueness).
2. A **nitty-gritty** runtime graph diagram (processes, configs, identity stores, sockets, tunnels, clients, caches) showing where split-brain and referential ambiguity appear.

---

## Diagram 1 — High-level (Abstract Roles & Authorities)

```mermaid
flowchart TB
  %% High-level roles (authority uniqueness)
  subgraph Human[Human Operator]
    H1[Engineer / Project Owner]
    HM[State Model x̂(t)]
  end

  subgraph System[Runtime System (Reality x(t))]
    GWA[Gateway Authority]
    CFA[Config Authority]
    IDA[Identity Authority]
    NTA[Network Authority]
    CLA[Client Authority]
    OBS[Observability Authority]
  end

  subgraph Discipline[Corrective Discipline]
    GSR[Global State Reconstruction
(rebuild runtime graph)]
    AB[Authority Binding
(unique referents)]
    VG[Verification Gate
(invariants + tests)]
  end

  H1 -->|observes| OBS
  OBS -->|produces evidence| HM
  HM -->|controls actions u(t)=f(x̂(t))| System

  GSR -->|enumerate nodes+edges| System
  AB -->|bind unique authorities| System
  VG -->|validate coherency| System

  %% Authority uniqueness principle
  GWA --- CFA
  GWA --- IDA
  GWA --- NTA
  GWA --- CLA

  %% Failure mode: local consistency vs global incorrectness
  HM -. model drift .- System
```

**Reading guide:**
- The system fails when the operator’s internal state model **x̂(t)** diverges from the real system **x(t)**, yet local checks continue to pass.
- The fix is not “debug a node”; it’s to **reconstruct the runtime graph**, then **bind authorities uniquely**.

---

## Diagram 2 — Nitty-gritty (Runtime Graph, Referents, and Split-Brain)

```mermaid
flowchart LR
  %% Nitty-gritty runtime graph: processes, configs, identity stores, sockets, tunnels, clients, caches.

  %% --- Server side / Deployment ---
  subgraph S[Server / Deployment Reality]
    subgraph P[Processes]
      GW[openclaw-gateway (PID X)]
      PX[shadow gateway (PID Y)?]
      PR[reverse proxy?]
    end

    subgraph C[Config Roots]
      CF1[/etc/openclaw/config.json]
      CF2[/home/foster/.openclaw/config.json]
      CF3[container-mounted config?]
    end

    subgraph I[Identity Stores]
      ID1[/home/foster/.openclaw/identities/]
      ID2[container identity store?]
      ID3[browser-local token cache?]
    end

    subgraph N[Network Endpoints]
      S4[127.0.0.1:18789 (ws/http)]
      S6[[::1]:18789 (ws/http)]
      PUB[public ingress / load balancer]
    end

    subgraph O[Observability]
      JL[journalctl logs]
      LS[lsof / netstat]
      PS[ps / systemd status]
    end
  end

  %% --- Client side / Operator environment ---
  subgraph U[Client / Operator Reality]
    subgraph UI[UI Surface]
      BR[Browser UI]
      VS[VSCode / Code Helper]
      CLI[CLI (curl / ssh)]
    end

    subgraph T[Tunnels & Port Maps]
      SSH[ssh -L local:remote]
      L4[127.0.0.1:18789 local listener]
      L5[127.0.0.1:18790 local listener]
      V6[::1:18789 local v6 listener]
    end

    subgraph K[Client Identity / Cache]
      KC[Keychain / local secrets]
      LS1[LocalStorage / IndexedDB]
      CK[Cookies]
    end
  end

  %% --- Edges: what reads what; what connects to what ---
  %% Process config bindings
  GW -->|reads config| CF1
  GW -->|reads config| CF2
  PX -->|reads config| CF3

  %% Identity bindings
  GW -->|validates tokens against| ID1
  PX -->|validates tokens against| ID2
  BR -->|stores token in| LS1
  BR -->|stores session in| CK
  KC -->|stores ssh keys / creds| CLI

  %% Listening sockets
  GW -->|listens| S4
  GW -->|listens| S6
  PR -->|fronts| PUB

  %% Client connections (intended)
  BR -->|connects ws/http| L4
  CLI -->|curl/ws test| L4
  L4 -->|tunnels to| S4
  L5 -->|tunnels to| S4
  V6 -->|tunnels to| S6
  SSH -->|creates| L4
  SSH -->|creates| L5
  SSH -->|creates| V6

  %% Observability evidence feeding model
  JL -->|evidence| CLI
  LS -->|evidence| CLI
  PS -->|evidence| CLI

  %% --- Split-brain / Referential ambiguity hotspots ---
  %% Multiple authorities for "gateway"
  GW -. ambiguity: which PID is the gateway? .- PX

  %% Multiple config roots
  CF1 -. ambiguity: which config is loaded? .- CF2
  CF2 -. ambiguity .- CF3

  %% Multiple identity stores
  ID1 -. ambiguity: which identity store is authoritative? .- ID2
  ID3 -. ambiguity: browser cache vs server identity store .- ID1

  %% IPv4 vs IPv6 confusion
  S4 -. mismatch: IPv4 reachable .- S6
  L4 -. mismatch: local v4 listener differs .- V6
  VS -. may bind local port unexpectedly .- L4

  %% Normalization of deviance: local OK signals
  L4 -->|local OK: port open| BR
  S4 -->|server OK: listening| CLI
  CF2 -->|exists| CLI
  ID1 -->|exists| CLI
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

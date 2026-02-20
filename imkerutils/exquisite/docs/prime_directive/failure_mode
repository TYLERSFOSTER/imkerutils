# Global State Reconstruction, Authority Binding, and Systems Failure Modes

**Purpose:**\
This document consolidates the conceptual, theoretical, and engineering
foundations behind the failure mode known as *Local Consistency vs
Global Incorrectness*, and the corrective discipline known as **Global
State Reconstruction** and **Authority Binding**.

This document serves as a canonical systems‑engineering reference
artifact.

------------------------------------------------------------------------

# Part I --- Local Consistency vs Global Correctness

## 1. The canonical distinction

A system can be:

-   **Locally consistent:** Every component behaves correctly according
    to its own view.
-   **Globally inconsistent:** The overall system state is invalid or
    impossible.

This is a fundamental property of distributed systems.

Leslie Lamport's work on:

-   logical clocks
-   distributed state
-   consensus

exists precisely because **local correctness does not imply global
correctness**.

You can verify every individual component and still have a broken
system.

------------------------------------------------------------------------

## 2. Model Drift (Cognitive Systems Engineering)

**Definition:**

Model drift occurs when an operator's internal model of the system
diverges from the system's actual state, and subsequent actions
reinforce the incorrect model instead of correcting it.

Key property:

Observations are interpreted through the existing model, and evidence
that should invalidate the model instead gets reinterpreted to preserve
it.

This creates a **self‑sealing feedback loop**.

Documented extensively in:

-   NASA accident investigations
-   Nuclear plant incident analysis
-   Aviation automation failures

This is one of the primary causes of prolonged debugging failures.

------------------------------------------------------------------------

## 3. Split‑Brain with Referential Ambiguity

Split‑brain is not limited to two servers.

It refers to **multiple competing authorities existing simultaneously**,
without a canonical authority resolution.

Engineers unknowingly interact with different authorities at different
times.

Each interaction appears locally valid.

Globally, they interact with different realities.

Common causes:

-   container vs host conflicts
-   multiple config roots
-   stale identity stores
-   shadow processes
-   multiple service instances

------------------------------------------------------------------------

## 4. Observer Error (Control Theory)

Control law operates on a state estimate:

u(t) = f(x̂(t))

If:

x̂(t) ≠ x(t)

then control actions are correct relative to estimate, but incorrect
relative to reality.

This is an estimation failure, not a logic failure.

------------------------------------------------------------------------

## 5. Normalization of Deviance (Safety Engineering)

Definition:

Unexpected system behavior gradually becomes accepted as normal instead
of recognized as evidence of incorrect system models.

Identified in:

-   Challenger disaster investigation

This allows incorrect models to persist indefinitely.

------------------------------------------------------------------------

## 6. Debugging the Wrong System (Software Engineering)

Form:

Engineer believes system A is running.

System B is actually running.

Engineer debugs system A correctly.

Nothing changes.

Common causes:

-   wrong container
-   wrong binary
-   wrong config file
-   wrong process
-   wrong environment

------------------------------------------------------------------------

## 7. Self‑Consistent False Models (Epistemology / AI Alignment)

A model can be:

-   internally coherent
-   predictive of its own observations

and still be globally false.

Because referents are incorrectly bound.

------------------------------------------------------------------------

## 8. Why this trap is stable

Local verification produces positive feedback:

-   port is listening
-   service is running
-   config exists
-   logs look correct

This reinforces incorrect models.

Engineers can remain trapped indefinitely.

------------------------------------------------------------------------

# Part II --- The Corrective Discipline: Global State Reconstruction

## 9. Definition

Global State Reconstruction is the explicit reconstruction of the
runtime system graph before attempting repair.

Debugging is fundamentally a **state estimation problem**.

You must determine what system actually exists.

Not what documentation says should exist.

Not what configuration intends.

What exists now.

------------------------------------------------------------------------

## 10. Systems are graphs

Runtime system modeled as graph:

Nodes:

-   processes
-   config files
-   identity stores
-   sockets
-   containers
-   services
-   clients

Edges:

-   process reads config
-   process listens on socket
-   client connects to socket
-   process validates identity against store
-   tunnel maps ports

The runtime graph is the system.

Not code.

Not configuration.

Reality.

------------------------------------------------------------------------

## 11. Common debugging mistake

Engineers debug nodes, not graphs.

Node questions:

-   Is service running?
-   Is config correct?
-   Is port open?

Graph question:

-   Is the topology coherent?

Nodes can be correct.

Graph can still be wrong.

------------------------------------------------------------------------

## 12. Industry implementation

Known under multiple names:

Google: system topology reconstruction\
Amazon: dependency graph reconstruction\
Microsoft: service dependency mapping\
Cloudflare: topology tracing\
Netflix: causal tracing

Google SRE explicitly teaches topology reconstruction prior to repair.

------------------------------------------------------------------------

## 13. Authority uniqueness principle

For every role, there must be exactly one authority.

Examples:

Gateway authority\
Config authority\
Identity authority\
Network authority

Multiple authorities → ambiguity → nondeterministic behavior.

------------------------------------------------------------------------

## 14. Reconstruction procedure

Explicitly enumerate:

Which process is running?

Which config file was loaded?

Which identity store is used?

Which network path is used?

Which client connects?

This produces authoritative runtime graph.

------------------------------------------------------------------------

## 15. Referential binding requirement

Symbolic references must bind uniquely.

Example:

Correct:

gateway → PID 83685

Incorrect:

gateway → container OR systemd OR proxy

Ambiguity prevents convergence.

------------------------------------------------------------------------

## 16. Formal algorithm

Step 1: enumerate runtime entities\
Step 2: enumerate relationships\
Step 3: identify authority roles\
Step 4: verify uniqueness of authority\
Step 5: resolve authority conflicts\
Step 6: only then debug behavior

------------------------------------------------------------------------

## 17. Authority Binding

Explicit declaration:

This process PID X is gateway.

This identity path Y is identity authority.

This network path Z is client path.

Authority binding eliminates ambiguity.

------------------------------------------------------------------------

# Part III --- Modern Infrastructure Amplifies the Problem

Modern systems introduce many parallel authorities:

-   containers
-   systemd
-   SSH tunnels
-   browser storage
-   identity caches
-   cloud metadata

Referential ambiguity probability increases dramatically.

------------------------------------------------------------------------

# Part IV --- LLM and Human Operator Failure Modes

LLMs optimize for narrative consistency, not authority validation.

They:

-   update incrementally
-   preserve existing model
-   avoid discarding model

This stabilizes incorrect models.

Human operators exhibit similar cognitive biases.

------------------------------------------------------------------------

# Part V --- Summary

Failure mechanism:

Local consistency without global correctness due to incorrect authority
binding.

Corrective method:

Global State Reconstruction followed by Authority Binding.

Shortest definition:

Global State Reconstruction is the process of determining the exact
runtime authority graph of a system prior to attempting repair.

------------------------------------------------------------------------

# End of Document

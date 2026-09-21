# Hardened Evaluation and Canary Operations

## Goal

v0.8 adds an optional second boundary around evaluated self-improvement. Git worktrees/copies isolate repository state; the container provider additionally restricts the execution environment. A passing evaluation may then be exercised as a temporary service canary before promotion.

## Evaluation providers

### Host

Runs parsed argv directly as the current user with no shell. This is compatible and lightweight, but it is not an OS sandbox.

### Container

Requires Docker or Podman already installed and an image already present locally. The assistant does not pull images. The image is resolved to an immutable local ID and pinned for the evaluation.

Default restrictions: no network, no capabilities, no-new-privileges, read-only root filesystem, writable project bind mount, bounded tmpfs, PID limit, CPU limit, RAM limit, and no runtime socket mount. Evaluation/canary subprocesses also strip common token/password/credential environment variables and agent sockets before launch.

## Canary lifecycle

1. Require a completed passing evaluation.
2. Verify the evaluated candidate branch still points to the measured commit.
3. Ask for a separate canary approval.
4. Recreate exact baseline and candidate worktrees/copies.
5. Start baseline service, wait for readiness, observe health/resources, stop.
6. Start candidate service, wait for readiness, observe health/resources, stop.
7. Compare health success, median latency and peak RSS against configured budgets.
8. Persist PASS/FAIL evidence.
9. If the suite requires canary, promotion remains blocked until PASS.

## Container canary networking

A temporary internal container network is created for each service run. Only the explicit container service port is mapped to an ephemeral/selected host port on `127.0.0.1`. The network is deleted when the canary stops.

## Limits

Containers are not VMs. Kernel exploits or container-runtime vulnerabilities are outside this project's security boundary. Use a disposable VM for genuinely hostile/untrusted code.

# Claude + GPT parallel rollout

This repository is the clean upstream-based replacement for the customized
legacy deployment. The legacy service stays online until the final cutover.

## Production topology on Render

The Mac launchers in this repository are rehearsal tools, not the long-term
memory host. The production design uses independent Render web services and
independent persistent disks:

| Phase | Service | Data | State |
|---|---|---|---|
| current | existing Claude service | live legacy vault | untouched |
| migration | `ombre-brain-claude-next` | copied Claude vault | rehearsal only |
| permanent | `ombre-brain-gpt` | empty GPT vault | independent from day one |

Phase 1 of `render.dual-ai.yaml` creates only GPT. After GPT passes its platform
and Codex-connection checks, Phase 2 adds Claude-next to the same Blueprint.
During the actual migration all three services exist. The old Claude service is
retired only after Claude personally accepts the migrated copy. The Blueprint
intentionally never names or manages the existing Claude service.

Each Render service has its own hostname and one attached persistent disk.
`OMBRE_MCP_AUTH_MODE=hybrid` permits OAuth clients and a separate static token;
each service receives different generated Dashboard and MCP credentials.

The phase-1 Blueprint deliberately leaves compression and embedding provider
settings unset. This lets the empty GPT service deploy and pass `/health`
without copying Claude's provider secrets or locking provider values into
environment overrides. Configure and test GPT's two engines from its own
Dashboard after the service is healthy; memory-writing tools remain unavailable
until a compression provider key is saved, and semantic search remains in
standby until an embedding provider key is saved.

The GPT Blueprint sets `OMBRE_PUBLIC_URL` to its Render HTTPS origin. Render's
internal hop is HTTP, so this explicit external origin prevents OAuth discovery
from advertising unusable `http://` issuer and resource URLs.

## Local rehearsal topology

| Owner | Port | Default host vault | Dashboard password | MCP token |
|---|---:|---|---|---|
| Claude | 18001 | `data/claude` | separate | separate |
| GPT | 18002 | `data/gpt` | separate | separate |

The two owners share code and may share model-provider credentials. They do
not share Markdown buckets, `config.yaml`, vector databases, caches, Dashboard
sessions, or MCP credentials.

## Safety boundary

- Do not merge this branch into the legacy branch as an upgrade mechanism.
- Do not mount the live legacy vault into the new service during testing.
- Do not copy the legacy `embeddings.db`, dehydration cache, configuration, or
  authentication files. They are version-specific or secret-bearing.
- Stage only the legacy Markdown memory tree into the Claude test vault. Let
  the new release rebuild derived indexes.
- Leave the GPT vault empty so its memory starts independently.

## Local launcher

The checked-in `deploy/owners.yaml` can be used with the upstream launcher:

```bash
python deploy/multi_owner.py
```

This is convenient for a source-based smoke test. It requires the project
Python dependencies.

## Docker launcher

1. Copy `deploy/.env.dual-ai.example` to `deploy/.env`.
2. Replace all `CHANGE_ME` values. Claude and GPT must use different MCP
   tokens.
3. Start the isolated pair:

```bash
docker compose --env-file deploy/.env \
  -f deploy/docker-compose.dual-ai.yml up -d --build
```

4. Verify `http://127.0.0.1:18001/health` and
   `http://127.0.0.1:18002/health` independently.
5. Write a canary memory to each instance and confirm it is absent from the
   other instance's Dashboard and search results.

## Claude migration rehearsal

1. Obtain a read-only copy of the legacy persistent vault while the legacy
   service remains online.
2. Copy only Markdown memory files into a disposable Claude test vault.
3. Start the new Claude instance against that copy.
4. Run the built-in bucket diagnostics and rebuild embeddings.
5. Compare bucket counts and spot-check pinned, dynamic, feel, resolved, and
   archived memories.
6. Test `breath`, `breath_search`, `hold`, `grow(items=...)`, and `pulse`.

### Acceptance gate for the legacy vault

Claude reported 527 buckets at the start of planning. That number may increase
while the live service continues accepting writes, so the authoritative count
is the count recorded from each frozen snapshot.

Before any new-version tool writes to the rehearsal vault:

1. Record a SHA-256 manifest for every Markdown file in the source snapshot.
2. Require the destination Markdown count to equal the snapshot count exactly.
3. Require every Markdown body and frontmatter document to parse successfully.
4. Compare counts by bucket type and state, including permanent/pinned,
   dynamic, feel, resolved, digested, and archived.
5. Reject duplicate bucket IDs, missing IDs, path escapes, symlinks, and any
   source Markdown without a destination counterpart.
6. Rebuild embeddings only after the Markdown gate passes; vector rows are
   derived data and are not evidence that the memory text survived.
7. Let Claude run `pulse`, representative searches, pinned-memory checks, and
   recent-memory checks against the migrated service before cutover.

The final cutover needs a short write freeze: stop new legacy writes, take one
last consistent Markdown snapshot, repeat the exact verified import, and then
change Claude's MCP endpoint. Keep the old Render service and vault intact for
rollback until the new service has survived an agreed observation period.

## Customized legacy behavior

Most legacy fixes now exist upstream in a stronger form: verbatim reads,
write-first behavior when model or embedding services fail, structured
`grow(items=...)`, old environment-variable compatibility, and legacy Markdown
frontmatter support.

One intentional behavior does not match upstream: the legacy default `breath`
returns deterministic newest-first memories, while upstream ranks unresolved
memories by activity/importance and can sample or surface passive associations.
Decide whether to keep the upstream behavior or carry a small, isolated
recent-first policy patch only after migration tests.

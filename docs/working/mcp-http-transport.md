# Serving MARS over HTTP: ChatGPT and Claude as Remote MCP Hosts

**Status:** proposed, 2026-10-01. No phase has started. Its first step, H0, is
a maintainer decision, because this track reopens one that
[`../archive/mcp-tool-surface.md`](../archive/mcp-tool-surface.md) §3.3 closed.

**Prerequisites:** the MCP tool surface (archived 2026-09-25). This track
builds on `tools/mcp/` as it stands and changes nothing under `algorithms/`,
`tools/agent/`, `tools/llm/` or `tools/registry.py`.

**Unblocks:** using MARS from ChatGPT on the web, and from claude.ai, Claude
Desktop and Claude mobile as a **custom connector**. Today none of these can
reach `mars-mcp`.

Host requirements below were checked against vendor documentation on
2026-10-01 (sources in §8). They change often. H0 re-checks them, and so does
each phase that depends on one.

---

## 1. The problem

`mars-mcp` speaks MCP over **stdio**. A host starts it as a child process on
the user's own machine. That covers the coding-agent CLIs, the IDEs and Claude
Desktop's local `mcpServers` block (`../installing.md`, "Register the server
with a host").

Browser chat cannot work that way. ChatGPT's developer mode and Claude's custom
connectors take a **URL**. The connection then comes **from the vendor's
cloud**, not from the user's browser or computer:

| Host | Transport | Where requests come from | Auth it accepts |
| --- | --- | --- | --- |
| ChatGPT (web), developer mode / apps | Streamable HTTP (SSE also accepted) | OpenAI's servers; egress ranges published, "can change" | none, OAuth (CIMD preferred, DCR, static client), "mixed" |
| claude.ai, Claude Desktop, mobile: custom connector | Streamable HTTP (HTTP+SSE deprecated) | Anthropic's cloud, `160.79.104.0/21`, **Desktop included** | none, OAuth (DCR, CIMD), static client ID/secret; static headers in limited beta |

Two consequences follow, and the rest of this document comes from them:

- **`localhost` is unreachable.** Even a user running everything on one laptop
  needs a public HTTPS endpoint, usually a tunnel. Claude Desktop is no
  exception for *connectors*; only its local `mcpServers` config is local.
- **The caller does not share the filesystem.** This removes the premise of the
  stdio design. The archived plan's §3.1 kept the artifact-path contract
  *because* "the caller does share the filesystem".

## 2. The decision this reopens

The archived track carried three deployment shapes and **deleted** the
networked one:

> ~~(b) Detached — server over the network, operator-held data~~ — **Deleted.**
> No HTTP transport, no network authentication, no Kepler-operated service.

Four things were removed with it: the HTTP transport, the authentication
design, server-side ceilings a client cannot raise (its §4.1), and
credential isolation. This track brings back **all four**. They come back in a
narrower form than shape (b), because §3 offers a personal deployment first.
H0 asks the maintainer to reopen §3.3 explicitly. Adding a `--http` flag
without that decision would contradict a recorded one.

## 3. Two deployment shapes, built in order

| Shape | Who runs the server | Whose data and keys | Who can call it |
| --- | --- | --- | --- |
| **(P) Personal** | The user, on their own machine, behind a tunnel | The user's own, as with stdio | The user's own ChatGPT or Claude account, through OAuth, or a secret held by the user |
| **(O) Operated** | An operator (for example, Skynet) on a server | The operator's | Many users, each authenticated, under limits the operator sets |

**(P) is the target. (O) is a later decision this document prices but does not
schedule.** Shape (P) keeps almost everything the stdio decision bought: the
keys and disk are the user's, so an expensive call lands on the person who
asked for it. What it adds is an internet-facing endpoint, so authentication is
not optional even for one user. A tunnel URL is public, and a server that
writes FITS headers and downloads MAST products must not be callable by
whoever finds the URL.

Shape (O) is shape (b) again. It needs everything (P) needs plus per-user
isolation of artifacts and scratch space, per-argument cost ceilings,
operator-held credentials that are never echoed to users, and capacity
planning for `numba` and plate-solving workloads. Each of those was priced in
the archive and deleted with it.

## 4. Architecture

### 4.1 One server, one more transport

`tools/mcp/server.py` already builds a low-level `mcp.server.Server` from the
registry, and `serve_stdio` hands it to the stdio transport. HTTP is a second
way of serving **the same `Server` object**: `mars-mcp serve-http`, a new
subcommand beside `fetch-data` and `self-test`. Tools, schemas, validation,
groups, annotations, icons and media are unchanged. Anything that differs
between transports is decided in `tools/mcp/surface.py`, which already owns
"what only the server knows".

The `mcp` 2.2 SDK ships what is needed: `StreamableHTTPSessionManager`
(stateful or `stateless`, SSE or `json_response`), a Starlette app factory,
`uvicorn`, and resource-server auth (`AuthSettings`, a `TokenVerifier`
protocol, RFC 9728 protected-resource metadata, and a `401` with
`WWW-Authenticate`). All of it is already a dependency of the `mcp` extra:
**no new dependency**. `mcp` is still imported only by `server.py` (and
`selftest.py`), and the extra stays optional.

Two SDK behaviours need deliberate settings:

- **DNS-rebinding protection** turns on automatically for a localhost bind and
  rejects any other `Host`. Behind a tunnel, the public hostname must be
  allowed explicitly, or every vendor request gets a `403`.
- **Protocol version.** MCP 2026-07-28 removes the `initialize` handshake and
  session IDs. Claude's connector documentation names only the 2025 specs. The
  SDK serves both, routing by the `MCP-Protocol-Version` header. H1 records
  which version each host actually negotiates.

### 4.2 The result contract over a wire

Measured on 2026-10-01 against `tools/registry.py`:

- **36 of 55 tools return an `ArtifactRef`**, a local path (archive C0 figure).
- **20 of 55 take a filesystem path as input**: `path`, `fits_path`,
  `csv_path`, `members_csv_path`, `directory` or `index_path`. Examples include
  the whole pulsar and variable-star chains, `solve_astrometry`,
  `calibrate_zeropoint`, `identify_radio_sources` and `describe_artifact`.

**Outputs.** A remote model can read neither a path nor the artifact directory.
The archive priced the answer in §4.3: *"an `ArtifactRef` gains a URI beside
its `path`, and nothing about the existing contract changes."* Over HTTP:

- each `ArtifactRef` in a result also carries a `mars://artifact/...` resource
  link, served by `on_read_resource` under the same containment check
  `inline_media` already applies (`within(path, artifact_root)`, regular files
  only);
- PNG and WAV keep arriving inline (C4). Media is the part of the contract that
  already works without a filesystem;
- the **instructions change**: "Artifacts are local files … read them
  directly" (`tools/mcp/install.py`) is false over HTTP. `surface.py` replaces
  it, as it already replaces sentences the server makes false;
- whether each host **shows** resources to the model is unverified for both
  vendors (§7). If one does not, the fallback is a short-lived signed HTTPS
  download URL in the result. H2 decides from what H1 measures.

**Inputs.** A remote user cannot hand the server a file. Path arguments still
work on what is **already on the server**: the bundled pulsar scans, the
optical library, MAST and CASDA downloads, and earlier artifacts. That is most
real use, because the local tools' first rule is "list or resolve first".
Uploading a user's own FITS or CSV is **out of scope** here. If it is wanted, it
is its own phase with its own size limits and its own write area.

### 4.3 Concurrency

`server.py` dispatches every call under **one lock**, because every MARS tool
was written to be called sequentially and stdio has one client
(archive §3.2). `tools/artifacts.py`'s `scoped_artifacts` is a `ContextVar`, the
one piece of implicit state on the surface.

Shape (P) **keeps the lock.** One user's chat issues calls one at a time
anyway, and a second client queueing behind the first is correct, not slow.
Stateless HTTP mode fits MARS's "no state between calls" rule
(`CLAUDE.md`, "One public tool call is MARS's execution boundary"). Shape (O)
cannot keep a global lock; that is one of the costs in §3.

### 4.4 Authentication

The server is an OAuth **resource server**, never its own authorization server.
It verifies tokens issued elsewhere:

- **(P), first choice: an existing identity provider** (GitHub, Google, or an
  OAuth service such as Auth0 or WorkOS), with the token's `aud` bound to the
  server URL and a single allowed subject: the user's own identity. Both
  vendors complete this flow unaided. They need RFC 9728 metadata, a `401`
  with `resource_metadata`, PKCE S256, and a form-encoded token endpoint.
  Claude also needs refresh failures to return `invalid_grant`.
- **(P), development only: no auth**, bound behind the tunnel with an
  unguessable path and the vendor's egress ranges allowlisted. Both vendors
  accept an authless server, so it is the quickest way to try H1. It is never
  the documented configuration, because egress ranges are shared by every
  customer of the vendor.
- Claude's **static headers** (bearer token) would be the simplest correct
  option for (P), but it is a limited beta. Revisit at H3.

Keys stay where they are. `ADS_DEV_KEY` and `CASDA_OPAL_USERNAME` are read from
the server's own environment, never sent by a client and never echoed. The
install facts already report only whether a key is set.

### 4.5 Approvals and the annotations

Both vendors gate calls on the annotations `tools/mcp/groups.py` generates from
`tools/bench/plane.py`:

- ChatGPT treats **any tool without `readOnlyHint`** as a write and asks for
  confirmation.
- Claude lets `readOnlyHint` tools run without per-call approval, and always
  prompts for `destructiveHint` tools.

That makes the annotations a security control rather than a hint. H4 audits
the generated values against what each tool actually writes. For example,
`solve_astrometry(write_header=true)` writes into a FITS file, and
`search_mast(download=true)` fills a disk. Any tool that writes but is
annotated read-only is a defect in this track.

`--tools` groups apply unchanged. The recommended remote configuration
starts with the read-mostly groups (`databases`, `timeseries`) and adds
`optical` deliberately.

### 4.6 Limits that are not MARS's

| Limit | ChatGPT | claude.ai / Desktop connector | MARS today |
| --- | --- | --- | --- |
| Per-call timeout | not documented | 240 s | `solve_astrometry` all-sky ~285 s; bounded ~14 s |
| Result size | not documented | ~150,000 characters | previews bounded by `PREVIEW_ROWS` and the `MARS_MAX_*` caps |

An all-sky plate solve does not fit Claude's 240 s window. The skill already
steers toward explicit bounds. H4 decides whether the remote surface refuses
an unbounded solve or only documents the limit.

### 4.7 Deep research and "company knowledge"

ChatGPT's deep research and company-knowledge modes call only two read-only
tools with fixed shapes, `search(query)` and `fetch(id)`. MARS has neither.
Adding them would be a registry change (two tools classified in
`tools/bench/plane.py` in the same commit, per `CLAUDE.md`), not a transport
change. **Out of scope**; developer mode calls the full tool set.

### 4.8 What does not change

- Nothing under `algorithms/`, `tools/agent/`, `tools/llm/` or
  `tools/registry.py`; `tools/mcp/` still imports nothing from the agent or
  model port.
- Undeclared arguments still never reach a tool (`additionalProperties: false`).
- The fixture-write guard and download-root containment hold unchanged; HTTP
  adds callers, not paths.
- **Default tests open no socket.** HTTP tests drive the Starlette app
  in-process (an ASGI transport), the way `tests/test_mcp_surface.py` drives
  stdio with the SDK's in-process client. A real bound port and a real tunnel
  are `network`-marked, gated by `MARS_TEST_NETWORK=1`.

## 5. A local-first alternative: a Claude Desktop extension

For Claude Desktop alone, a **`.mcpb` desktop extension** (a zip of a manifest
plus the server, installed by double-click) gives a one-click install with
**no HTTP, no tunnel and no auth**: it is still stdio. The cost is packaging.
The format favours Node. A Python server with `numba`, `scipy` and `astropy`
would need its environment bundled per platform or created at first run, and
the connectors directory no longer accepts `.mcpb` submissions. This is
independent of the HTTP track and can be weighed separately. It does nothing
for ChatGPT or claude.ai on the web.

## 6. Rollout

Each phase is one PR. No phase begins before the one before it has landed.

### Phase H0: Decide, and re-check the hosts

- The maintainer reopens archive §3.3 for shape (P), and says whether (O) is
  in view at all.
- Re-verify §1's table and §4.6's limits against the vendors' current pages
  (§8). Record the date.
- Decide (P)'s auth provider (§4.4).
- **Exit:** this document's Status updated with the answers.

### Phase H1: Transport, on localhost

- `mars-mcp serve-http --host --port --path` serves the existing `Server` over
  Streamable HTTP, with the same root pinning, `.env` order, groups and
  startup log as stdio. It binds `127.0.0.1` by default, rebinding protection
  stays on, and allowed hosts are a flag.
- Verified with the MCP Inspector and with Claude Code's
  `claude mcp add --transport http`, both on localhost.
- In-process tests: initialize, list tools, call one local tool, read one skill
  resource, and confirm the result equals the stdio result for the same call.
- **Exit:** the stdio suite unchanged and green; the HTTP results identical.

### Phase H2: The result contract over a wire

- Artifact resource URIs beside paths (§4.2), served with the existing
  containment check.
- HTTP-specific instructions and install facts in `surface.py`, under
  `BRIEF_LIMIT`, keeping ChatGPT's "first 512 characters self-contained" advice
  in mind.
- A test that no served sentence tells a remote model to read a local path.
- **Exit:** a remote client with no filesystem can obtain every artifact a
  result names.

### Phase H3: Authentication

- Resource-server auth through the SDK (`AuthSettings`, a `TokenVerifier` for
  the chosen provider), with audience validation on and a single allowed
  subject for (P).
- The server refuses to bind a non-loopback address without auth configured.
  Authless remote use requires an explicit, loudly logged flag.
- **Exit:** an unauthenticated request gets a `401` with `resource_metadata`;
  a token for another audience or subject is refused.

### Phase H4: Annotations and limits for unattended approval

- Audit `readOnlyHint` and `destructiveHint` on all 55 tools against what each
  tool writes (§4.5).
- Decide the unbounded-solve policy against the 240 s window (§4.6).
- **Exit:** a test pins every write-capable tool as non-read-only.

### Phase H5: The hosts, end to end

- A tunnel recipe (`cloudflared` or `ngrok`) in `../installing.md`.
- ChatGPT developer mode and a claude.ai custom connector, each connected to a
  (P) deployment, each run through the five-step pulsar detection that
  `mars-mcp self-test` checks.
- Record what each host does with instructions, resources and inline audio
  (§7).
- **Exit:** both hosts complete the pulsar detection; findings recorded here.

### Phase H6: Documentation outcome and archive

- Fold the outcome into `../installing.md` (remote hosts), `../tool-architecture.md`
  §10.3, and `CLAUDE.md`'s `tools/mcp/` rules (the transport and auth rules).
- Archive this document per [`README.md`](README.md)'s lifecycle.

## 7. Open questions, each answered inside a phase

- Does claude.ai pass the server's `instructions` to the model? Does ChatGPT
  surface non-UI resources? (H1/H5; neither vendor documents it.)
- Which protocol version does each host negotiate, the 2025 handshake or
  2026-07-28 stateless? (H1)
- ChatGPT's per-call timeout and result-size limits. (H5; undocumented.)
- ChatGPT plan gating: full MCP with write actions is reported as Business,
  Enterprise and Edu only, with Pro limited to read and fetch. That would put
  a read-only surface on Pro. The OpenAI help article was not readable when
  this was written. (H0)
- Whether shape (O) is ever wanted. (H0; a separate track if so.)

## 8. Sources, checked 2026-10-01

- OpenAI developer mode: <https://developers.openai.com/api/docs/guides/developer-mode>
- OpenAI Apps SDK, connecting and auth: <https://developers.openai.com/apps-sdk/deploy/connect-chatgpt>, <https://developers.openai.com/apps-sdk/build/auth>
- OpenAI MCP and deep research (`search`/`fetch`): <https://developers.openai.com/api/docs/mcp>
- OpenAI egress ranges: <https://developers.openai.com/api/docs/guides/ip-addresses>
- Claude custom connectors: <https://claude.com/docs/connectors/custom/remote-mcp>
- Claude connector building, auth, testing, review criteria: <https://claude.com/docs/connectors/building>, <https://claude.com/docs/connectors/building/authentication>, <https://claude.com/docs/connectors/building/testing>, <https://claude.com/docs/connectors/building/review-criteria>
- Anthropic IP ranges: <https://platform.claude.com/docs/en/api/ip-addresses>
- Claude desktop extensions: <https://claude.com/docs/connectors/building/mcpb>
- MCP 2026-07-28 changelog: <https://modelcontextprotocol.io/specification/2026-07-28/changelog>
- `mcp` Python SDK 2.2.0: `mcp/server/streamable_http_manager.py` and
  `mcp/server/lowlevel/server.py` in the locked environment;
  <https://py.sdk.modelcontextprotocol.io/v2/migration/>

# Warmtrace Website — Agent Instructions

## Scope and fail-closed rule

This repository is the local static source lead for the Warmtrace product
website. It is not evidence that any GitHub, hosting, DNS, certificate,
redirect, public-content, Apple, account, submission, or release state changed.

Nothing is committed, pushed, deployed, published, or represented as current
public evidence unless every applicable gate has current `PASS` evidence.
Missing, stale, conflicting, or `UNKNOWN` evidence keeps the action `BLOCKED`.

## Governing identity contract

- `Warmtrace` is the product name; the D-016 migration is not a product rename.
- Ashraya Studio is not approved as provider, operator, seller, or owner.
- The founder's legal name is omitted by default and may appear only when a
  current exact-surface requirement and founder decision support it.
- The `ashrayastudio` GitHub owner and repository URL are internal technical
  infrastructure. Neither those values nor an Ashraya-branded domain may
  appear in rendered website content, HTML attributes, or customer contact
  links.
- The founder-approved public support email is exactly
  `appportfolio.contact@gmail.com`; no other Gmail address or alias is allowed.
  Prefer role-based support wording and omit personal-name copyright footers.

The central governing source is
`/Users/hermes/Developer/personal-digital-products-ops`, especially D-016,
D-027, and MIG-004 in `docs/DECISION-LOG.md`, `docs/CURRENT-STATE.md`, and
`docs/PUBLIC-SURFACE-CORRECTION-PLAN.md`.

## Responsibility routing

- Codex owns exactly authorized local source/docs edits, validators, diffs,
  local Git, and ordinary GitHub network work for `ashrayastudio/warmtrace` at
  `https://github.com/ashrayastudio/warmtrace.git` through the installed
  `gh` CLI and HTTPS Git using the macOS-keyring-backed credential helper.
- Every GitHub operation must name the exact repository/URL, Git HTTPS transport,
  read-only or mutation class, exact permitted operation, prohibited
  operations, and required sanitized before/after evidence. Revalidate
  `gh auth status`, account `ashrayastudio`, credential-free origin,
  branch/ref, index, and worktree; never retrieve or print the token.
- Hermes is a bounded backup only after the exact direct Codex/`gh` route fails
  for a non-sandbox reason or the founder explicitly requests Hermes. Use its
  maintained handoff and existing configured `gh`/keyring access; never pass a
  token in a prompt or file. A sandbox denial requires narrow escalation, not
  an operator change.
- The founder alone authorizes commits, GitHub mutations, deployment,
  publication, DNS/hosting/certificate/redirect changes, Apple/account work,
  legal attestations, submission, and release. Neither Codex nor Hermes
  supplies authorization.

## Local validation and mutation boundaries

Run both before proposing a commit:

```text
python3 -B scripts/validate_site.py
python3 -B scripts/validate_site.py --self-test
```

Also require a reviewed exact diff, `git diff --check HEAD`, a clean index, a
scoped sensitive-pattern scan, and preservation of all unrelated owner work.
Local source, a Git commit, a Hermes push, hosting configuration, and the
published result are separate states and require separate evidence and
authority. Never access protected credential/configuration paths or place
credentials, protected contact values, financial records, or account secrets
in this repository.

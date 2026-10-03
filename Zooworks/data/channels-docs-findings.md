# ZooWork channels docs — saved findings (fetched live 2026-10-03)

Source: https://zoowork.ai/docs/en/build/channels (live public docs page, fetched directly —
not the cached copy bundled in the installed skill)

## Exact quoted text
> "Managed channel bindings and guided setup are currently unavailable with Platform API keys."

> "Platform API keys created in ZooWork Platform cannot list, create, update, or remove managed
> channel bindings, or run QR setup."

## What this means
- This blocks iMessage, WhatsApp, and Slack channel binding for ANY Platform API key — not a
  tier/upgrade issue, not something a dashboard setting changes, not something the FDE table can
  unlock for a hackathon key.
- There is no `createChannel`/`bindChannel` method in the installed `@zoowork-ai/sdk` (0.10.2)
  either — nothing exists to call to confirm this with a live 404; the docs text itself is the
  authoritative, current source.
- The docs' own recommended alternative: receive messages through the chat platform's own API
  (e.g. Twilio) and route them into ZooWork Sessions yourself, rather than a managed channel.
  This is exactly plan.md's own recommended default (Twilio SMS + fake-phone panel fallback).

## Action
Do not spend booth time asking about iMessage/WhatsApp access for this hackathon. Build messaging
via Twilio SMS from the start, per plan.md decision #1.

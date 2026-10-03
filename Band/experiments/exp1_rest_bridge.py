"""Experiment 1: REST-only bridge.

Posts into a BAND room *as an agent* (Tom) using only its API key over REST,
with no Tom process running. This is the pattern a ZooWork custom tool
(ask_customer_occasions / request_vouch) would use to talk to customer agents.

Also tests mention-scoped visibility: an un-mentioned message is posted first,
then a mentioned one; we record what Jerry reacts to.

Run from Band/tom-jerry-agents:  uv run python ../experiments/exp1_rest_bridge.py
"""

from __future__ import annotations

import time
from pathlib import Path

import yaml
from band.client.rest import ChatMessageRequest, ChatMessageRequestMentionsItem, RestClient
from band_rest import ChatRoomRequest, ParticipantRequest

cfg = yaml.safe_load((Path(__file__).parent.parent / "tom-jerry-agents/agent_config.yaml").read_text())
TOM_ID, TOM_KEY = cfg["tom_agent"]["agent_id"], cfg["tom_agent"]["api_key"]
JERRY_ID = cfg["jerry_agent"]["agent_id"]

bridge = RestClient(api_key=TOM_KEY, base_url="https://app.band.ai")


def jerry_messages(room_id: str) -> list:
    msgs = bridge.agent_api_messages.list_agent_messages(room_id, status="all", sort_order="asc", limit=50).data
    return msgs


def wait_for_jerry(room_id: str, seen: int, timeout: float) -> list:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(2)
        ctx = bridge.agent_api_context.get_agent_chat_context(room_id, limit=50).data
        replies = [m for m in ctx if getattr(m, "sender_id", None) == JERRY_ID]
        if len(replies) > seen:
            return replies
    return []


t0 = time.monotonic()
room = bridge.agent_api_chats.create_agent_chat(chat=ChatRoomRequest(title="exp1 bridge test"))
room_id = room.data.id
print(f"room created as Tom via REST: {room_id} ({time.monotonic() - t0:.1f}s)")

bridge.agent_api_participants.add_agent_chat_participant(room_id, participant=ParticipantRequest(participant_id=JERRY_ID))
print("Jerry added")

# A. No mention: the platform rejects it (422, mentions minItems 1), so agents cannot broadcast.
r = []

# B. With mention
t1 = time.monotonic()
bridge.agent_api_messages.create_agent_chat_message(
    room_id,
    message=ChatMessageRequest(
        content="@Jerry quick question: do you already own a cheese grater? Answer yes/no and a confidence 0-1.",
        mentions=[ChatMessageRequestMentionsItem(id=JERRY_ID, name="Jerry")],
    ),
)
r = wait_for_jerry(room_id, len(r), 90)
print(f"B (@mention): Jerry replied={bool(r)} after {time.monotonic() - t1:.1f}s")
for m in r:
    print("   Jerry:", (m.content or "")[:300])

print("\nFull room context as seen by Tom's key:")
for m in bridge.agent_api_context.get_agent_chat_context(room_id, limit=50).data:
    print(f"  [{getattr(m, 'message_type', '?')}] {getattr(m, 'sender_name', getattr(m, 'sender_id', '?'))}: {(m.content or '')[:160]}")
print("ROOM_ID", room_id)

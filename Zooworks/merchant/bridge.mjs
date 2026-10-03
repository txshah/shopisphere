// ZooWork bridge: runs the real merchant agent's custom tool calls against our backend.
//   cd Zooworks && node merchant/bridge.mjs          (after setup.mjs; listens on :8788)
//
// - POST /run  fires the "weekly-gifting" schedule (Outcome rubric applies). If the trigger fails,
//              it opens a plain session with the same message instead (no rubric on sessions).
// - Every second it lists the agent's pending custom tool calls, POSTs each input to
//   {BACKEND}/api/tools/<name> (X-Source: zoowork) and resolves the call with the JSON result.
// - It follows each session the agent works in and mirrors the Outcome rubric's verdicts and the
//   run result to the dashboard event log.
import http from 'node:http';
import { assistantText } from '@zoowork-ai/sdk';
import { BACKEND, RUN_MESSAGE, SCHEDULE_ID, postEvent, readState, zc } from './common.mjs';

const { agent_id: agentId } = readState();
if (!agentId) throw new Error('No agent yet: run `node merchant/setup.mjs` first');
const PORT = Number(process.env.ZOOWORK_BRIDGE_PORT || 8788);

const inFlight = new Set();
const watched = new Set();

async function runTool(call) {
  inFlight.add(call.call_id);
  const started = Date.now();
  try {
    const res = await fetch(`${BACKEND}/api/tools/${call.name}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Source': 'zoowork' },
      body: JSON.stringify(call.input ?? {}),
    });
    const value = await res.json();
    await zc.resolveCustomToolCall(agentId, call.call_id, {
      content: [{ type: 'json', value }], isError: !res.ok, resolvedBy: 'shopisphere-backend',
    });
    console.log(`tool ${call.name} → ${res.status} (${Date.now() - started} ms)`);
  } catch (e) {
    console.error(`tool ${call.name} failed:`, e?.message ?? e);
    try {
      await zc.resolveCustomToolCall(agentId, call.call_id, {
        content: [{ type: 'text', text: `backend error: ${e?.message ?? e}` }], isError: true, resolvedBy: 'shopisphere-backend',
      });
    } catch { /* already resolved or timed out */ }
  } finally {
    inFlight.delete(call.call_id);
  }
}

// Outcome rubric verdicts arrive as agent.lifecycle events; mirror them so the grade shows on the dashboard.
const OUTCOME_LABEL = {
  'outcome-started': 'Outcome rubric: grading the run',
  'outcome-revision': 'Outcome rubric: not yet, revising',
  'outcome-satisfied': 'Outcome rubric: satisfied',
  'outcome-unsatisfied': 'Outcome rubric: not satisfied',
};

async function watchSession(sessionId) {
  if (watched.has(sessionId)) return;
  watched.add(sessionId);
  await postEvent('session', `ZooWork merchant agent working (session ${sessionId.slice(0, 24)}…)`);
  let lastSeq = -1;
  const deadline = Date.now() + 15 * 60 * 1000;
  while (Date.now() < deadline) {
    try {
      const events = await zc.listAllEvents(agentId, sessionId);
      for (const ev of events) {
        if (ev.seq <= lastSeq) continue;
        lastSeq = ev.seq;
        const phase = ev.payload?.phase;
        if (ev.eventType === 'agent.lifecycle' && OUTCOME_LABEL[phase]) {
          const why = ev.payload.explanation ? `: ${ev.payload.explanation}` : '';
          await postEvent(phase, `${OUTCOME_LABEL[phase]}${why}`.slice(0, 900), { iteration: ev.payload.iteration });
          console.log(OUTCOME_LABEL[phase]);
        }
        const text = assistantText(ev);
        if (text?.trim()) await postEvent('report', text.trim().slice(0, 1200));
        if (ev.eventType === 'run.finished') {
          const status = ev.payload?.status ?? 'finished';
          await postEvent('run.finished', `ZooWork run ${status}`, { session_id: sessionId });
          console.log(`run finished: ${status}`);
          return;
        }
      }
    } catch (e) {
      console.error('event poll error:', e?.message ?? e);
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
}

async function poll() {
  try {
    const pending = await zc.listCustomToolCalls(agentId, { status: 'pending' });
    for (const call of pending) {
      if (call.session_id) watchSession(call.session_id);
      if (!inFlight.has(call.call_id)) runTool(call);
    }
  } catch (e) {
    console.error('poll error:', e?.status, e?.message ?? e);
  }
  setTimeout(poll, 1000);
}

async function fireRun() {
  try {
    const r = await zc.triggerSchedule(agentId, SCHEDULE_ID);
    await postEvent('schedule.triggered', `ZooWork schedule "${SCHEDULE_ID}" fired (Outcome rubric on)`, r);
    return { ok: true, via: 'zoowork schedule', ...r };
  } catch (e) {
    console.error('triggerSchedule failed, opening a session instead:', e?.status, e?.message);
    const s = await zc.createSession(agentId, { initial_events: [{ type: 'user.message', content: RUN_MESSAGE }] });
    watchSession(s.session_id);
    await postEvent('session.created', 'ZooWork session started (schedule trigger failed; no Outcome rubric)');
    return { ok: true, via: 'zoowork session', session_id: s.session_id };
  }
}

http.createServer(async (req, res) => {
  const send = (code, obj) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(obj)); };
  try {
    if (req.method === 'POST' && req.url === '/run') return send(200, await fireRun());
    if (req.method === 'GET') return send(200, { ok: true, agent_id: agentId, schedule: SCHEDULE_ID });
    send(404, { error: 'not found' });
  } catch (e) {
    send(502, { error: e?.message ?? String(e) });
  }
}).listen(PORT, () => console.log(`ZooWork bridge on http://localhost:${PORT} for agent ${agentId}`));

poll();

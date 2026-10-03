// One-off Composio check: does a ZooWork agent's built-in composio_* tooling reach Gmail?
// Reads ZOOWORKS from ../.env, never prints it, logs every event to data/, cleans up the Agent.
import fs from 'node:fs';
import { createZooworkClient, assistantText, isRunFinished } from '@zoowork-ai/sdk';

const env = fs.readFileSync('../.env', 'utf8');
process.env.ZOOWORK_API_KEY = env.match(/^ZOOWORKS=(.*)$/m)[1].trim();
const zc = createZooworkClient();
const log = [];
let agentId;

async function turn(sessionId, text) {
  if (sessionId) await zc.postEvents(agentId, sessionId, [{ type: 'user.message', content: text }]);
  const s = sessionId ? { session_id: sessionId }
    : await zc.createSession(agentId, { initial_events: [{ type: 'user.message', content: text }] });
  let reply = '';
  for await (const ev of zc.streamEvents(agentId, s.session_id, log.length ? { cursor: log[log.length-1].cursor } : {})) {
    log.push(ev);
    reply += assistantText(ev) ?? '';
    if (isRunFinished(ev)) break;
  }
  return { sid: s.session_id, reply };
}

async function main() {
  const models = await zc.listModels();
  const model = models.find((r) => r.selectable !== false && r.default_for?.includes('model'))?.model;
  const created = await zc.createAgent({ resource: { name: 'composio-check', model: { primary: model } } }, 'composio-check-v1');
  agentId = created.agent_id;
  await zc.startAgent(agentId);
  await zc.waitUntilRunning(agentId, { timeoutMs: 60000 });
  console.log('agent running:', agentId);

  const t1 = await turn(null,
    'Call your composio_tools tool now and paste its raw output verbatim. Then, using composio_tools/composio_execute, ' +
    'try to find a Gmail integration and start connecting a Gmail account (e.g. initiate an OAuth connection or get a connect link). ' +
    'Report exactly what each call returned, including any errors, verbatim. Do not invent results.');
  console.log('--- turn 1 ---\n' + t1.reply);

  const t2 = await turn(t1.sid,
    'If any Gmail send action is available, call it to send an email to tveshashah13@gmail.com with subject "composio-check" and body "test". ' +
    'If not, say exactly why. Paste raw tool output verbatim.');
  console.log('--- turn 2 ---\n' + t2.reply);
}

main()
  .catch((e) => { console.error('ERROR:', e?.status, e?.type, e?.message ?? e); process.exitCode = 1; })
  .finally(async () => {
    fs.writeFileSync('data/composio-check-events-2026-10-03.json', JSON.stringify(log, null, 2));
    if (agentId) {
      try { await zc.stopAgent(agentId); } catch (e) { console.log('stop warn:', e?.message); }
      try { await zc.deleteAgent(agentId); } catch (e) { console.log('delete warn:', e?.message); }
      console.log('cleaned up', agentId);
    }
  });

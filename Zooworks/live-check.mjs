// One-off live connectivity check for the ZOOWORKS key. Confined to this folder.
// Reads ZOOWORKS from ../.env, never prints the value, cleans up any created Agent.
import fs from 'node:fs';
import {
  createZooworkClient,
  assistantText,
  isRunFinished,
} from '@zoowork-ai/sdk';

function loadEnvKey(path, name) {
  const text = fs.readFileSync(path, 'utf8');
  for (const line of text.split('\n')) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m && m[1] === name) return m[2].trim();
  }
  throw new Error(`${name} not found in ${path}`);
}

const apiKey = loadEnvKey('../.env', 'ZOOWORKS');
process.env.ZOOWORK_API_KEY = apiKey;

const zc = createZooworkClient();
let agentId;

async function main() {
  console.log('[1/4] listModels (cheap credential check)...');
  const models = await zc.listModels();
  console.log(`  -> ok, ${models.length} models returned`);
  const model = models.find(
    (row) => row.selectable !== false && row.default_for?.includes('model'),
  )?.model;
  console.log(`  -> primary default model: ${model ?? 'NONE FOUND'}`);

  console.log('[2/4] createAgent + startAgent + waitUntilRunning...');
  const created = await zc.createAgent(
    { resource: { name: 'zooworks-live-check', model: { primary: model } } },
    'zooworks-live-check-v1',
  );
  agentId = created.agent_id;
  console.log(`  -> agent_id: ${agentId}`);
  await zc.startAgent(agentId);
  await zc.waitUntilRunning(agentId, { timeoutMs: 60000 });
  console.log('  -> running');

  console.log('[3/4] listAgentSkills (checking for a global ZooData skill attached by default)...');
  try {
    const skills = await zc.listAgentSkills(agentId);
    console.log('  -> skills:', JSON.stringify(skills, null, 2));
  } catch (e) {
    console.log('  -> listAgentSkills failed:', e?.status, e?.type ?? e?.message);
  }

  console.log('[4/4] minimal session: ask the agent what tools/skills it has for TikTok Shop or Amazon data...');
  const session = await zc.createSession(agentId, {
    initial_events: [{
      type: 'user.message',
      content: 'List every tool and skill you currently have access to, verbatim by name, with one line on what each does. Do not invent any.',
    }],
  });
  let reply = '';
  for await (const event of zc.streamEvents(agentId, session.session_id)) {
    reply += assistantText(event) ?? '';
    if (isRunFinished(event)) break;
  }
  console.log('  -> assistant reply:\n' + reply);
}

main()
  .catch((e) => {
    console.error('ERROR:', e?.status, e?.type, e?.message ?? e);
    process.exitCode = 1;
  })
  .finally(async () => {
    if (agentId) {
      console.log('Cleaning up: stopAgent + deleteAgent...');
      try { await zc.stopAgent(agentId); } catch (e) { console.log('stopAgent warn:', e?.message); }
      try { await zc.deleteAgent(agentId); } catch (e) { console.log('deleteAgent warn:', e?.message); }
      console.log('Done.');
    }
  });

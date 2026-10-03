// One-time setup of the real ZooWork merchant agent. Safe to re-run: it reuses saved ids.
//   cd Zooworks && node merchant/setup.mjs        (backend must be running: tools come from GET /api/tools)
// Creates: the "trailhead-merchant" Agent with our 13 custom tools, the trailhead-gifting Skill,
// and the "weekly-gifting" schedule (Mondays 9:00 Pacific) carrying the Outcome rubric.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { AGENT_NAME, BACKEND, HERE, OUTCOME, RUN_MESSAGE, SCHEDULE_ID, readState, writeState, zc } from './common.mjs';

const state = readState();

// 1. Model: the platform's primary chat default.
const models = await zc.listModels();
const model = state.model || models.find((r) => r.selectable !== false && r.default_for?.includes('model'))?.model;
if (!model) throw new Error('No selectable default ZooWork model');

// 2. Tools: the backend's ZooWork-ready declarations.
const customTools = await (await fetch(`${BACKEND}/api/tools`)).json();
console.log(`tools from backend: ${customTools.map((t) => t.name).join(', ')}`);

const persona = {
  docs: [{
    name: 'trailhead.md',
    content: 'You are the merchant agent for Trailhead, an outdoor gear boutique (fictional, for this demo). '
      + 'Your job is the weekly gifting run in the trailhead-gifting skill. Use only the custom tools for data and actions. '
      + 'Agents narrow the options; people make every choice: never place an order yourself.',
  }],
};

// 3. Agent: create once, then keep tools/persona current.
if (!state.agent_id) {
  const created = await zc.createAgent(
    { resource: { name: AGENT_NAME, model: { primary: model }, persona, custom_tools: customTools, include_global_skills: false } },
    'trailhead-merchant-v1',
  );
  state.agent_id = created.agent_id;
  state.model = model;
  writeState(state);
  console.log(`agent created: ${state.agent_id}`);
} else {
  await zc.updateAgent(state.agent_id, { custom_tools: customTools, persona });
  console.log(`agent updated: ${state.agent_id}`);
}
await zc.startAgent(state.agent_id);
await zc.waitUntilRunning(state.agent_id, { timeoutMs: 120000 });
console.log('agent running');

// 4. Skill: upload the gifting playbook (project scope, else org) and attach it.
//    On a re-run, publish SKILL.md as a new version (identical content is deduplicated).
const zipPath = path.join(HERE, 'trailhead-gifting.zip');
fs.rmSync(zipPath, { force: true });
execFileSync('zip', ['-qr', zipPath, 'trailhead-gifting'], { cwd: path.join(HERE, 'skill') });
const zip = fs.readFileSync(zipPath);
fs.rmSync(zipPath, { force: true });
if (state.skill_id) {
  try {
    const v = await zc.uploadSkillVersion(state.skill_id, zip, { fileName: 'trailhead-gifting.zip' });
    console.log(`skill version ${v.version}: ${v.state}`);
  } catch (e) {
    console.log(`skill version upload: ${e?.status} ${e?.type ?? e?.message}`);
  }
} else {
  for (const scope of ['project', 'org']) {
    try {
      const skill = await zc.uploadSkill(zip, { scope, fileName: 'trailhead-gifting.zip' });
      state.skill_id = skill.skill_id;
      console.log(`skill uploaded (${scope}): ${state.skill_id}`);
      break;
    } catch (e) {
      if (e?.status === 409) {
        const found = (await zc.listSkills()).find?.((s) => s.name === 'trailhead-gifting')
          ?? (await zc.listSkills()).skills?.find((s) => s.name === 'trailhead-gifting');
        if (found) { state.skill_id = found.skill_id; console.log(`skill exists: ${state.skill_id}`); break; }
      }
      console.log(`skill upload (${scope}) failed: ${e?.status} ${e?.type ?? e?.message}`);
    }
  }
  writeState(state);
}
if (state.skill_id) {
  await zc.putAgentSkill(state.agent_id, state.skill_id, { enabled: true });
  const skills = await zc.listAgentSkills(state.agent_id);
  console.log('attached skills:', JSON.stringify(skills).slice(0, 300));
} else {
  console.log('WARNING: no Skill attached; the run message and persona still carry the playbook.');
}

// 5. Schedule: Mondays 9:00 Pacific, with the Outcome rubric. Enabled so a manual trigger runs it.
if (!state.schedule_id) {
  await zc.createSchedule(state.agent_id, {
    schedule_id: SCHEDULE_ID,
    schedule: { kind: 'cron', expr: '0 9 * * 1', tz: 'America/Los_Angeles' },
    payload: { kind: 'agentTurn', message: RUN_MESSAGE, outcome: OUTCOME },
    delivery: { mode: 'none' },
    enabled: true,
  }, 'weekly-gifting-v1');
  state.schedule_id = SCHEDULE_ID;
  writeState(state);
  console.log(`schedule created: ${SCHEDULE_ID} (Mondays 09:00 America/Los_Angeles, Outcome rubric)`);
} else {
  await zc.updateSchedule(state.agent_id, SCHEDULE_ID, {
    schedule: { kind: 'cron', expr: '0 9 * * 1', tz: 'America/Los_Angeles' },
    payload: { kind: 'agentTurn', message: RUN_MESSAGE, outcome: OUTCOME },
    enabled: true,
  });
  console.log(`schedule updated: ${SCHEDULE_ID}`);
}
console.log('ready:', JSON.stringify(state));

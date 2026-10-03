// Shared config for the Trailhead merchant agent scripts. Reads ZOOWORKS from ../../.env (never printed).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createZooworkClient } from '@zoowork-ai/sdk';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const STATE_FILE = path.join(HERE, 'state.json');   // agent/skill/schedule ids (gitignored)
export const BACKEND = (process.env.BACKEND_URL || 'http://localhost:8787').replace(/\/$/, '');
export const AGENT_NAME = 'trailhead-merchant';
export const SCHEDULE_ID = 'weekly-gifting';

function loadEnv(name) {
  const text = fs.readFileSync(path.join(HERE, '..', '..', '.env'), 'utf8');
  for (const line of text.split('\n')) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m && m[1] === name) return m[2].trim().replace(/^"|"$/g, '');
  }
  throw new Error(`${name} not found in .env`);
}

process.env.ZOOWORK_API_KEY ||= loadEnv('ZOOWORKS');
export const zc = createZooworkClient();

export const readState = () => (fs.existsSync(STATE_FILE) ? JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) : {});
export const writeState = (s) => fs.writeFileSync(STATE_FILE, JSON.stringify(s, null, 2));

// The message the weekly schedule (and the fallback session) sends the agent.
export const RUN_MESSAGE = `Weekly gifting run for Trailhead. Follow the trailhead-gifting skill step by step:
top customer → verify their agent → consent room for occasions → match catalog → vouch room → competitor price
→ one offer through the Outcome rubric → text the customer (do not place the order; their YES does) →
restock purchase orders from anonymous vouches. Use only the custom tools. End with the short final report.`;

// Outcome rubric on the scheduled run (cron fires only; see Zooworks/Rules.md).
export const OUTCOME = {
  description: 'One verified, vouched-when-possible gift offer was drafted and texted, and the final report explains it.',
  evaluator: {
    type: 'rubric',
    rubric: {
      type: 'text',
      text: [
        'Pass only if ALL are true, judged from the tool results in this run and the final report:',
        "1. Trust: score_agent_trust returned verified=true for the customer's agent before make_offer.",
        '2. Stock: make_offer returned ok=true (the backend checks the item and size are in stock).',
        '3. Budget: the final price is within the occasion budget (+10%), or no budget was shared.',
        '4. Margin: the discount came from check_competitor_price (or 0% unvouched) and make_offer accepted it, so it is above the margin floor.',
        '5. Reason: the report has a one-line reason for the offer (vouch result and competitor price).',
        '6. Human gate: place_order was NOT called by the agent; the customer was texted and asked to reply YES.',
      ].join('\n'),
    },
  },
  maxIterations: 3,
  publish: 'after_satisfied',
};

export async function postEvent(kind, summary, payload) {
  try {
    await fetch(`${BACKEND}/api/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: 'zoowork', kind, summary, payload }),
    });
  } catch { /* dashboard log only */ }
}

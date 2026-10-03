// Remove the ZooWork merchant agent after the hackathon, so the Monday schedule stops firing.
//   cd Zooworks && node merchant/teardown.mjs
// Order matters: schedules outlive their agent, and a deleted agent can't be stopped.
import fs from 'node:fs';
import { STATE_FILE, readState, zc } from './common.mjs';

const s = readState();
if (!s.agent_id) { console.log('nothing to tear down'); process.exit(0); }
if (s.schedule_id) {
  try { await zc.deleteSchedule(s.agent_id, s.schedule_id); console.log('schedule deleted'); } catch (e) { console.log('deleteSchedule:', e?.status, e?.message); }
}
try { await zc.stopAgent(s.agent_id); console.log('agent stopped'); } catch (e) { console.log('stopAgent:', e?.status, e?.message); }
try { await zc.deleteAgent(s.agent_id); console.log('agent deleted'); } catch (e) { console.log('deleteAgent:', e?.status, e?.message); }
fs.rmSync(STATE_FILE, { force: true });

// One-off: dump the full listModels() response to disk so it survives context loss.
// Cheap, read-only, no agent created.
import fs from 'node:fs';
import { createZooworkClient } from '@zoowork-ai/sdk';

function loadEnvKey(path, name) {
  const text = fs.readFileSync(path, 'utf8');
  for (const line of text.split('\n')) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m && m[1] === name) return m[2].trim();
  }
  throw new Error(`${name} not found in ${path}`);
}

process.env.ZOOWORK_API_KEY = loadEnvKey('../.env', 'ZOOWORKS');
const zc = createZooworkClient();
const models = await zc.listModels();
fs.writeFileSync('data/zoowork-models.json', JSON.stringify(models, null, 2));
console.log(`Saved ${models.length} models to data/zoowork-models.json`);

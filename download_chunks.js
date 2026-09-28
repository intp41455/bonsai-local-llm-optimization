// Chunked GitHub release downloader
// Downloads large files in parallel chunks to work around proxy instability
const https = require('https');
const fs = require('fs');
const path = require('path');

const ASSET_ID = process.argv[2] || '589066601';
const OUTPUT = process.argv[3] || 'output.zip';
const CHUNK_SIZE = 1024 * 1024; // 1MB chunks

function getFileInfo(assetId) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.github.com',
      path: `/repos/PrismML-Eng/llama.cpp/releases/assets/${assetId}`,
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0'
      },
      rejectUnauthorized: false
    };
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve({ size: json.size, url: json.url });
        } catch(e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function downloadChunk(url, start, end) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.github.com',
      path: url.replace('https://api.github.com', ''),
      method: 'GET',
      headers: {
        'Accept': 'application/octet-stream',
        'Range': `bytes=${start}-${end}`,
        'User-Agent': 'Mozilla/5.0'
      },
      rejectUnauthorized: false
    };
    const chunks = [];
    const req = https.request(options, (res) => {
      if (res.statusCode !== 206 && res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode} for bytes ${start}-${end}`));
        return;
      }
      res.on('data', d => chunks.push(d));
      res.on('end', () => resolve(Buffer.concat(chunks)));
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error('timeout')); });
    req.end();
  });
}

async function downloadWithRetry(url, start, end, retries = 5) {
  for (let i = 0; i < retries; i++) {
    try {
      return await downloadChunk(url, start, end);
    } catch(e) {
      if (i === retries - 1) throw e;
      await new Promise(r => setTimeout(r, 2000 * (i + 1)));
    }
  }
}

async function main() {
  console.log(`Getting file info for asset ${ASSET_ID}...`);
  const info = await getFileInfo(ASSET_ID);
  const totalSize = info.size;
  console.log(`Total size: ${(totalSize / 1024 / 1024).toFixed(1)} MB`);

  const numChunks = Math.ceil(totalSize / CHUNK_SIZE);
  const fd = fs.openSync(OUTPUT, 'w');

  // Download in parallel batches of 4
  const BATCH = 4;
  for (let batch = 0; batch < numChunks; batch += BATCH) {
    const promises = [];
    for (let i = batch; i < Math.min(batch + BATCH, numChunks); i++) {
      const start = i * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE - 1, totalSize - 1);
      promises.push(
        downloadWithRetry(info.url, start, end)
          .then(buf => {
            fs.writeSync(fd, buf, 0, buf.length, start);
            process.stdout.write('.');
          })
      );
    }
    await Promise.all(promises);
    const pct = ((Math.min(batch + BATCH, numChunks)) / numChunks * 100).toFixed(1);
    process.stdout.write(` ${pct}%\n`);
  }

  fs.closeSync(fd);
  console.log(`\nDone! ${OUTPUT} (${totalSize} bytes)`);
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });

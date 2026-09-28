// Robust GitHub release downloader with redirect following
// Uses curl under the hood for each chunk (curl handles redirects + SSL)
const { execSync } = require('child_process');
const fs = require('fs');

const ASSET_ID = process.argv[2];
const OUTPUT = process.argv[3];
const CHUNK_SIZE = 2 * 1024 * 1024; // 2MB chunks
const PARALLEL = 1; // sequential to avoid proxy contention

function getAssetSize(assetId) {
  const cmd = `curl -sL --ssl-no-revoke -H "Accept: application/json" -H "User-Agent: Mozilla/5.0" "https://api.github.com/repos/PrismML-Eng/llama.cpp/releases/assets/${assetId}"`;
  const out = execSync(cmd, { encoding: 'utf-8', timeout: 30000 });
  const json = JSON.parse(out);
  return { size: json.size, browserUrl: json.browser_download_url };
}

function downloadRange(url, start, end, outputFile, offset) {
  // Use curl with Range header, follow redirects, write to specific offset
  const tmpFile = `/tmp/chunk_${Date.now()}_${start}`;
  const cmd = `curl -sL --ssl-no-revoke --retry 3 --retry-delay 2 -H "Range: bytes=${start}-${end}" -o "${tmpFile}" "${url}"`;
  try {
    execSync(cmd, { timeout: 60000 });
    const data = fs.readFileSync(tmpFile);
    // Write to specific offset in output file
    const fd = fs.openSync(outputFile, 'r+');
    fs.writeSync(fd, data, 0, data.length, offset);
    fs.closeSync(fd);
    fs.unlinkSync(tmpFile);
    return data.length;
  } catch(e) {
    try { fs.unlinkSync(tmpFile); } catch(_) {}
    return -1;
  }
}

function main() {
  console.log(`Getting info for asset ${ASSET_ID}...`);
  const info = getAssetSize(ASSET_ID);
  const totalSize = info.size;
  const url = info.browserUrl;
  console.log(`Total size: ${(totalSize/1024/1024).toFixed(1)} MB, URL: ${url.substring(0,80)}...`);

  // Create sparse file
  const fd = fs.openSync(OUTPUT, 'w');
  fs.closeSync(fd);

  let downloaded = 0;
  let chunkIdx = 0;
  const numChunks = Math.ceil(totalSize / CHUNK_SIZE);

  while (downloaded < totalSize) {
    const end = Math.min(downloaded + CHUNK_SIZE - 1, totalSize - 1);
    const expectedSize = end - downloaded + 1;

    let attempts = 0;
    let success = false;
    while (attempts < 5 && !success) {
      attempts++;
      const len = downloadRange(url, downloaded, end, OUTPUT, downloaded);
      if (len > 0) {
        downloaded += len;
        success = true;
      } else {
        console.log(`  retry ${attempts} for chunk ${chunkIdx}...`);
      }
    }
    if (!success) {
      console.error(`Failed to download chunk ${chunkIdx} after 5 attempts`);
      process.exit(1);
    }
    chunkIdx++;
    if (chunkIdx % 10 === 0) {
      const pct = (downloaded / totalSize * 100).toFixed(1);
      console.log(`  ${pct}% (${(downloaded/1024/1024).toFixed(1)}/${(totalSize/1024/1024).toFixed(1)} MB)`);
    }
  }
  console.log(`Done! ${OUTPUT} (${downloaded} bytes)`);
}

main();

// 从 codebuddy-headless.js 里精确切出与技能清单预算相关的函数原文
const fs = require('fs');
const P = 'D:/下载的/WorkBuddy/resources/app.asar.unpacked/cli/dist/codebuddy-headless.js';
const s = fs.readFileSync(P, 'utf8');

const anchors = [
  'truncateSkillsByCharBudget',
  'skillCharBudget',
  'SKILL_TOOL_CHAR_BUDGET',
  'SKILL_DESC_MAX_OVERRIDES',
  'resolveSkillDescCap',
  'skillsOverview',
];

for (const a of anchors) {
  const i = s.indexOf(a);
  console.log('\n' + '='.repeat(70));
  console.log('ANCHOR: ' + a + '   firstIndex=' + i + '  totalLen=' + s.length);
  console.log('='.repeat(70));
  if (i < 0) { console.log('(not found)'); continue; }
  // 打印锚点附近原文（前后各一段）
  const st = Math.max(0, i - 900);
  console.log(s.slice(st, i + 2200));
}

# MCP 与技能「重复度」盘点 · 2026-09-27

> 目的：压 WorkBuddy 每次请求的 prompt 体积（上次实测 **48,937 token**）。
> 口径：`~/.workbuddy/mcp-tool-list.json`（现场实测快照）+ `connector-states.json`（开关状态）+ `.skill-list-cache.json`（技能清单）。

---

## 一、结论摘要

| 项 | 实测 | 判断 |
|---|---|---|
| MCP 条目 | **12 条 / 154 个工具 / 78,330 字符 ≈ 22,320 token** | 真重复只有 **1 个** |
| 其中最大头 ardot | 26 工具 ≈ **10,985 token（占 MCP 总量 49%）** | **已经是关闭状态** ✅ |
| 技能总数 | 909（缓存实时增长中） | — |
| 可注入技能 | **740 个 ≈ 216,712 字符 ≈ 82,630 token** | **这才是真正的大头** |
| 已排除注入 | 157 个（`disableModelInvocation`） | 历史已做过的精简 |
| 真·重复技能簇 | **10 组 / 涉及 27 个技能** | 但其中 3 组不可合并（见四） |

**一句话**：MCP 侧基本没有冗余可砍（最大的 ardot 已关）；**冗余集中在技能清单**，但"看起来重复"的几组实际是不同目标模型的提示包，不能盲砍。

### 已执行（2026-09-27 04:19）

按陛下决策「只去真重复 + 留国产/免费那侧」，**已关闭 8 个重复技能**：

| 动作 | 对象 | 方式 | 省下 |
|---|---|---|---|
| 关闭 | `computer-use-linux`（你是 Windows） | settings.json | 72 tok |
| 关闭 | `kimi-websearch`（留豆包） | settings.json | 82 tok |
| 关闭 | `chrome-bridge-automation`（留基础版） | settings.json | 279 tok |
| 关闭 | `ppt-beautify`（留 PPT设计） | settings.json | 83 tok |
| 关闭 | `stagehand-browser-cli`（留 playwright-cli） | settings.json | 88 tok |
| 关闭 | `workbuddy-dev-dashen`（留 WorkBuddy 大神） | settings.json | 189 tok |
| 关闭 | `agent-earth` 嵌套副本 | SKILL.md | 68 tok |
| 关闭 | `neodata-financial-search` 用户级副本 | SKILL.md | 187 tok |
| | | **合计** | **≈ 1,048 tok** |

**未动**：图像生成 9 连（分属 GPT-Image-2 / Nano-Banana-2 / Image-2 三个目标模型）、tencent-docs 个人版/企业版——这两组看着像重复，实为不同能力。

**MCP 侧待你手点**（配置改不了，见第二节说明）：关 `miora`（省 3,200）+ `agent-earth`（省 273）= **3,473 tok**，收益比技能去重还大。

---

## 二、MCP 12 条台账（按占用降序）

| # | 服务 | 工具数 | ≈token | 实质用途 | 是否真重复 |
|---|---|---|---|---|---|
| 1 | **ardot**（设计画布） | 26 | **10,985** | 画布/设计稿读写、导出 | ⛔ **已关闭**；且是最大冗余 |
| 2 | **miora**（多模态生成） | 8 | **3,200** | 文生图/改图/文生视频/画布 | ⚠️ **与内置 ImageGen + VideoGen 重复** |
| 3 | github | 45 | 2,476 | 仓库/PR/Issue | 否，你推送依赖它 |
| 4 | sheetagent | 9 | 1,480 | Excel 读写/公式 | 否 |
| 5 | agent-mail | 11 | 968 | 收件箱/收发信 | 否，独一份 |
| 6 | 腾讯文档 tdrive | 10 | 938 | 云盘文件增删改查 | 与百度网盘**部分重叠** |
| 7 | genie-baas（云服务） | 9 | 672 | 云数据库/存储/RLS | 否 |
| 8 | EdgeOne Pages | 2 | 551 | 部署上线 | 否，且是你指定的部署首选 |
| 9 | 百度网盘 | 16 | 362 | 网盘文件/视频列表 | 否，OCR 项目依赖 |
| 10 | agent-earth | 5 | 273 | 第三方工具市场 | ⚠️ 疑未使用 |
| 11 | weixinpay | 4 | 208 | 支付绑定 | 否 |
| 12 | ima（知识库） | 9 | 207 | 知识库检索/导入 | 否，你的 KB 依赖 |

**关键提示**：MCP 的开关**不能靠改配置文件**（`connectors/default/mcp.json` 是只读目录，178 条全是 `disabled:true`；真实状态在加密的 `connector-states.json`）。
→ 只能走 **WorkBuddy 左侧「连接器」管理页** 手动点。

---

## 三、MCP 真重复判定

| 判定 | 条目 | 理由 | 建议 |
|---|---|---|---|
| 🔴 真重复 | **miora** | 8 个工具全是文生图/图生图/文生视频，与内置 `ImageGen`、`VideoGen` 完全同功能（且内置无 token 成本） | **可关**，省 3,200 token |
| 🟡 疑似无用 | **agent-earth** | 工具市场代理（RecommendTools/ExecuteTool），近 30 天无使用痕迹 | 可关，省 273 token |
| 🟡 部分重叠 | 腾讯文档 tdrive ↔ 百度网盘 | 都是云存储文件操作；但腾讯文档与你文档线相关，百度网盘与 OCR 线相关 | **建议都留** |
| ✅ 保留 | 其余 8 条 | 各自独占用途，且绑定你正在跑的项目线 | 不动 |

---

## 四、技能侧：740 个可注入 ≈ 82,630 token

### 4.1 已检测出的 10 组近重复（27 个技能）

| 组 | 成员 | 能否合并 |
|---|---|---|
| A | `AgentEarth` / `agent-earth` | ✅ **同一技能装了两份**，可去一 |
| B | `NeoData金融搜索服务` / `neodata-financial-search` | ✅ 同上，可去一 |
| C | `Computer Use Linux` / `Computer Use Windows` | ✅ 你是 Windows，可去 Linux |
| D | `PPT美化` / `PPT设计` | ✅ 可留一个 |
| E | `Midscene…for Browser` / `Midscene…with Browser Bridge` | ✅ 可留基础版 |
| F | `Stagehand Browser CLI` / `playwright-cli` | 🟡 留 `playwright-cli`（插件自带） |
| G | `豆包 WebSearch` / `Kimi WebSearch` | 🟡 留哪个看你习惯 |
| H | `WorkBuddy 大神` / `AI开发大神` | 🟡 留一个 |
| I | `tencent-docs` / `tencent-saas-docs` | ❌ **不可合并**：个人版 vs 企业版 |
| J | 图像生成 9 连：`精准文字图片`/`GPT Image 2 角色一致性`/`GPT Image 2 多参考图`/`GPT Image 2 商品精修`/`Image2 图生图`/`Image2 海报生成`/`Nano Banana 2 精准文字图片`/`Nano Banana 2 海报生成`/`商品详情页` | ❌ **不可合并**：分属 GPT-Image-2 / Nano-Banana-2 / Image-2 三个不同目标模型，砍掉即失去对应模型能力 |

**可安全去重：A~H 共 8 组，约 14 个技能。**

### 4.2 但真正的账在这里

740 个可注入技能里，重复只占 27 个。**剩下 713 个才是 8 万 token 的来源。**

这 713 个里绝大多数是与你不相关的通用技能（例：`eRoad JD智能生成`、`药品说明书检索`、`周易通识`、`中国财税政策助手`、`复星财富AI`、`游戏发行策略矩阵`…）。
WorkBuddy 的注入有 token 上限（实测本会话只展示了 **201/816**），所以：
- 关掉重复 → 省约 1~2 千 token（杯水车薪）
- **精简整个清单 → 才是万级 token 的收益**

### 4.3 开关机制（已确认可程序化操作）

- 位置：`~/.workbuddy/settings.json` → `skillOverrides`，**键名是 `overrideKey` 而非技能名**
- 值：`"user-invocable-only"` = 不再自动注入，但手动 `/技能名` 仍可调用
- 另一条路：直接改各技能 `SKILL.md` frontmatter 的 `disable: true`（你已装的 `ybl-skill-switch` 技能走的就是这条）
- 现状：已有 **136** 个被设为不注入，**740** 个仍在注入

---

## 五、剩余可选动作

| 路线 | 动作 | 预计省下 | 状态 |
|---|---|---|---|
| **① 只去真重复** | 关 A~H 8 组中重复的那 8 个 + 连接器关 miora / agent-earth | ≈ 1,048（技能）+ 3,473（MCP） | ✅ 技能侧**已完成**；MCP 侧待手点 |
| **② 去重 + 精简清单** | 在①基础上，把 740 个按"你是否真会用"分批设为不注入 | ≈ 40,000~60,000 tok | ⬜ 未开始（需逐个确认） |
| **③ 只关连接器** | 仅关 miora / agent-earth / zsxq 等 | ≈ 3,473 tok | ⬜ 未开始 |

**手点路径**：WorkBuddy 左侧 **「连接器」** 页 → 找到 *miora*（多模态生成）、*agent-earth* → 关闭。

---

## 六、本次改动清单（可回滚）

```
C:\Users\intpj\.workbuddy\settings.json
    skillOverrides: 136 条 → 142 条（新增 6 条 "user-invocable-only"）
    备份：settings.json.bak-dedup-20260927-041758   （改动前 · 干净）
          settings.json.bak-dedup2-20260927-041938  （改动前 · 含 pluginConfigs）

C:\Users\intpj\.workbuddy\skills\agent-earth\skills\SKILL.md
    插入 disable: true       备份：同名 .bak-dedup-20260927-041938

C:\Users\intpj\.workbuddy\skills\neodata-financial-search\SKILL.md
    插入 disable: true       备份：同名 .bak-dedup-20260927-041938
```

**语义说明**：走 `skillOverrides` 的 6 个是**软关闭**——不再自动注入 prompt，但你手动输入 `/技能名` 仍可调用；走 `SKILL.md` 的 2 个是**硬关闭**（因其 overrideKey 与保留的那份撞车，无法单独软关）。

**生效时机**：技能列表在下一轮对话刷新时重载；若未生效请重启 WorkBuddy。

---

## 附：回滚

```bash
# 1. 还原设置
cp "C:/Users/intpj/.workbuddy/settings.json.bak-dedup-20260927-041758" \
   "C:/Users/intpj/.workbuddy/settings.json"

# 2. 还原两个 SKILL.md
cd "C:/Users/intpj/.workbuddy/skills"
cp "agent-earth/skills/SKILL.md.bak-dedup-20260927-041938" "agent-earth/skills/SKILL.md"
cp "neodata-financial-search/SKILL.md.bak-dedup-20260927-041938" "neodata-financial-search/SKILL.md"

# 3. 连接器：WorkBuddy 左侧「连接器」页重新打开即可（凭据不会丢）
```

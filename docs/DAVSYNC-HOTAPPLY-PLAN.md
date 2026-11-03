# DavSync 下一轮：热应用（不重启）实施计划

> 目标：拉取云端数据后**不关闭设置页**，在线应用；仅当高级设置有差异时才重启。
> 状态：**已落地，v1.75.1.122（2026-11-03）**。实施与验收记录见
> `DAVSYNC-TESTING.md` §18；验收/脚手架脚本在 `_tmp/acceptance.py`、
> `_tmp/case8-firefox.py`、`_tmp/scaffold.py`。以下为历史计划，仅存档。

---

## 一、为什么至今没做成

两轮都卡在「应用之后本地指纹与远端指纹对不上」，表现为**紧接着一次多余上传**（把刚拉下来的数据推回云端、顶掉远端版本），状态栏变成「已上传」。

根因链：

1. 同步判定依赖 `fingerprintLocalData()`（`src/js/davsync.js`），它直接 `JSON.stringify` 各字段。
2. 两侧数据形态不同：
   - uBO `collectLocalData()` 只上报**与默认值不同**的设置；云端 payload 可能带 `importedLists: []` 这类默认项；
   - 白名单一边是数组、一边是换行字符串；
   - 列表/规则行序可能不同。
3. 于是同一份内容算出两个指纹 → 被判成「两边都改了」或「本地有改动」。
4. 老路（清库 + 重启）靠「应用后重新读一次」勉强对齐，但那一次读到的常是**应用前的内存态**
   （118 的真凶：`whitelist` 还是默认的 `chrome-extension-scheme,moz-extension-scheme`）。

---

## 二、设计（已写过一版，逻辑如下）

### 1. 指纹归一化（先做这个）

改 `fingerprintLocalData()`：

- `userSettings`：剔除等于 `userSettingsDefault` 的项（**深比较**，`[] === []` 恒假），按 key 排序后 stringify。
- `selectedFilterLists` / `whitelist` / 动态规则 / URL 规则 / 主机名开关：归一成「trim + 去空行」的行数组，**排序**。
- `userFilters`：同样 trim + 去空行，但**保留顺序**（顺序不影响语义，但改了顺序算一次真实改动）。
- 比较前必须先 `await ensureUserSettingsDefaults()`（默认值表要通过 `import('./background.js')` 取到）。

### 2. 热应用（归一化之后再接）

`applyRemoteDataHot(data)`，返回 `true` 表示已应用、无需重启：

```js
const µb = (await import('./background.js')).default;
const { permanentFirewall, permanentSwitches, permanentURLFiltering } =
    await import('./filtering-engines.js');

// 高级设置只能重启生效：对比「与默认值不同的键」的差值，有差异 return false
// 设置：远程没有的键回默认值
for (const key of Object.keys(µb.userSettingsDefault)) { ... await µb.changeUserSettings(key, target); }
µb.trustedSites.fromLines(data.whitelist || []); µb.saveWhitelist();
permanentFirewall.fromString(data.dynamicFilteringString || ''); µb.savePermanentFirewallRules();
permanentURLFiltering.fromString(data.urlFilteringString || ''); µb.savePermanentURLFilteringRules();
permanentSwitches.fromString(data.hostnameSwitchesString || ''); µb.saveHostnameSwitches();
await µb.saveUserFilters((data.userFilters || []).join('\n'));
await µb.saveSelectedFilterLists(data.selectedFilterLists || []);
await µb.loadFilterLists();
```

### 3. 调用方必须一起改（第一轮的坑）

`runSyncOnce()` 的返回值被**三处**判断：`syncNow()`、闹钟、启动同步，都是 `if (status === 'pulled') restart()`。
热应用必须返回新值 `'pulled-hot'`，否则「明明走新路径却仍被重启」，页面照样关。

---

## 三、测试脚手架（**这一轮的第一件事**）

上一轮失败不在产品代码，在脚手架：

- `ui.ensure_page()` 会 attach 到 `about:blank`，导致 `#davSync` 为 null，**配置根本没保存**；
- 于是扩展从不 PUT，脚本自己 PUT 时 WebDAV 因集合未建返回 **409**。

### 必须满足的四条

1. **显式开页面**：`Target.createTarget({url:'chrome-extension://<id>/settings.html'})`，用返回的 `targetId` 锁定页面，不要模糊匹配 URL。
2. **每步断言**：配置后先断言 `davSyncGetStatus().enabled === true`；云端先断言文件存在（GET 200），再改。
3. **干净的实例**：每次测试用**新建 profile 目录**，dev-mode 用 Preferences 打补丁后重启一次；结束时整目录删除。
4. **WebDAV 也要干净**：每次 `rm -rf davroot` 再起服务，避免残留 lock（曾出现 `locked-by-other-device`）。

### 验收清单（全绿才算过）

| # | 用例 | 期望 |
|---|---|---|
| 1 | 远端改动（含 `importedLists: []` 等默认项）→ 立即同步 | 页面**不消失**；状态「已从云端应用」 |
| 2 | 同上之后等 20 秒再同步一次 | 不出现「已上传」；云端 `deviceName` 保持对端值 |
| 3 | 我的过滤 / 白名单 / 设置项 | 与远端一致（`readUserFilters`、`getWhitelist`） |
| 4 | 过滤引擎 | `getLists.netFilterCount` 有变化（证明真的重建了） |
| 5 | 本地改动 → 同步 | 「已上传」，不误判冲突 |
| 6 | 双端都改 → 同步 | 冲突横幅出现 |
| 7 | 远端改 `hiddenSettings` → 同步 | 走重启路径（页面会关并重开），数据仍正确 |
| 8 | Firefox：pull → 重启 → 再同步 | `dir=none`，云端未被回写 |

---

## 四、环境准备（每次重来都照这个做）

```bash
# 本地 WebDAV（仓库外脚本 _tmp/webdav.py，监听 8088，账号 davtest/davtest123）
rm -rf _tmp/davroot && mkdir -p _tmp/davroot
python _tmp/webdav.py &

# 百分/Chromium 测试实例
mkdir -p _tmp/p1
chrome.exe --user-data-dir=.../_tmp/p1 --remote-debugging-port=9447 \
           --load-extension=.../dist/build/uBlock0.chromium about:blank
# 停掉 → 改 Preferences（extensions.ui.developer_mode=true, settings[id].state=1）→ 重启

# Firefox（正式版只接受临时附加组件）
npx web-ext run --source-dir dist/build/uBlock0.firefox \
  --firefox <ff.exe> --firefox-profile <空目录> --keep-profile-changes --no-input --no-reload \
  --args=--remote-debugging-port=9223
# 详见 docs/DAVSYNC-TESTING.md §17
```

---

## 五、新开一轮怎么起

1. 打开新会话（上下文干净），用这句话开始：
   > 按 `docs/DAVSYNC-HOTAPPLY-PLAN.md` 做热应用，先把测试脚手架按第三节修好并自检通过，再改代码。
2. 我会先跑「脚手架自检」：能显式打开设置页、能保存配置、能确认云端文件存在——这三条不通就不动同步逻辑。
3. 通过后再实现归一化 → 热应用 → 跑第三节验收表 → 全绿才发版（1.75.1.122）。

## 六、不要做的事

- 不要在脚手架不可靠时改 `runSyncOnce` 的判定逻辑（上一轮就是这么翻车的）。
- 不要把「多余上传」当成小事：它会顶掉云端版本，让其他设备白拉一次，正是 118/119 花两版修掉的问题。
- 不要在没跑完验收表的情况下发版。

[![Badge Commits]][Commit Rate]
[![Badge Issues]][Issues]
[![Badge Localization]][Crowdin]
[![Badge License]][License]
[![Badge NPM]][NPM]
[![Badge Mozilla]][Mozilla]
![Badge Chrome]
[![Badge Edge]][Edge]

***

<h1 align="center">
<sub>
<img src="https://github.com/gorhill/uBlock/blob/master/src/img/ublock.svg" height="38" width="38">
</sub>
uBlock Origin — DAV-Sync Edition
</h1>

> **本仓库是 [gorhill/uBlock](https://github.com/gorhill/uBlock) 的私有 fork，不向上游推送。**
> 上游作者已明确 uBO 不做设置自动同步；本 fork 为自用目的添加了该能力。

## 这个 fork 加了什么：DAV-Sync

uBO 原版的设置（过滤规则、自定义规则、白名单等）只存在本机，换设备/换浏览器要手动导出导入。**DAV-Sync 让任意多个浏览器实例通过任意标准 WebDAV 服务（坚果云、InfiniCLOUD、Nextcloud 等）自动保持 uBO 设置一致**：

- **自动同步**：设置变更后自动推送到 WebDAV，其他设备定时拉取合并，无需人工干预；
- **跨浏览器**：基于 uBO 官方云存储通道（`vAPI.cloud`）实现，任何能装 uBO 的浏览器都适用，不绑定单一内核；
- **快照合并**：带设备名标识与数据快照，多端同时修改可合并而非盲目覆盖；
- **零外部依赖**：直接用扩展自身的 `fetch` 访问 WebDAV，无需本地代理或额外服务端。

### 快速开始

1. 从 `artifacts` 分支 `build/`（或自行按 `ARTIFACTS.md` 重建）获取构建包，解压；
2. 浏览器扩展管理 → 开发者模式 → 加载已解压的扩展程序（**需仍支持 MV2 的浏览器**——Chrome 137+ 已移除 MV2，推荐百分浏览器 / 360 极速 / Firefox）；
3. uBO 设置页 → 底部「DAV-Sync」区块 → 填 WebDAV 地址、账号、应用密码、设备名 → 保存；
4. 其余设备装同款 fork，填**同一个 WebDAV 目录**、不同的设备名即可。

### 关键文件

| 文件 | 作用 |
|---|---|
| `src/js/davsync.js` | WebDAV 客户端、自动同步调度、快照生成/应用 |
| `src/js/dav-cloud.js` | 把 uBO 云存储路由接到 WebDAV |
| `src/js/settings.js` / `src/settings.html` | 设置页 DAV-Sync 配置 UI |
| `docs/DAVSYNC-HOST-COMPATIBILITY-AND-SIDELOAD.md` | 载体兼容性验证 + Chrome 侧载方法（持续迭代） |
| `ARTIFACTS.md` | 产物索引与换机重建指南 |

### 已知限制

- 基于 uBO **1.75.1.16（Manifest V2）**。Chrome 137+ 已禁用 MV2，需选用保留 MV2 的内核；未来计划向 uBOL（MV3）移植，见兼容性文档第 5 节；
- Android 端未验证（x86 模拟器无法运行带扩展的浏览器，需 ARM 真机）；
- WebDAV 服务端需支持 MKCOL/PUT/GET（坚果云已验证全通，PUT 前须先建父目录，fork 已内置处理）。

---

## 以下为上游 uBlock Origin 原始说明

| Browser   | Install from ... | Status |
| :-------: | ---------------- | ------ |
| <img src="https://github.com/user-attachments/assets/b0136512-56a5-4856-8c50-4971c957a24f" alt="Get uBlock Origin for Firefox"> | <a href="https://addons.mozilla.org/addon/ublock-origin/">Firefox Add-ons</a> | [uBO works best on Firefox](https://github.com/gorhill/uBlock/wiki/uBlock-Origin-works-best-on-Firefox) |
| <img src="https://github.com/user-attachments/assets/3a7569f8-688b-4eb1-a643-8d0fe173aefe" alt="Get uBlock Origin for Microsoft Edge"> | <a href="https://microsoftedge.microsoft.com/addons/detail/ublock-origin/odfafepnkmbhccpbejgmiehpchacaeak">Edge Add-ons</a> | <a href="https://blogs.windows.com/msedgedev/2026/08/07/moving-the-microsoft-edge-extensions-ecosystem-forward-with-manifest-version-3/">"Moving the Microsoft Edge extensions ecosystem forward with Manifest Version 3"</a>: "Beginning in August 2026, Microsoft Edge will start the consumer transition away from Manifest Version 2 (MV2) extensions and toward MV3. Our goal is to complete the consumer transition by the end of 2026, with enterprise deprecation following in early 2027." |
| <img src="https://github.com/user-attachments/assets/938f080c-fe64-4e48-8b89-4bfceabb56e6" alt="Get uBlock Origin for Opera"> | <a href="https://addons.opera.com/extensions/details/ublock/">Opera Add-ons</a> |
| <img src="https://github.com/user-attachments/assets/5463ef88-873b-4516-8514-5277664cfde7" alt="Get uBlock Origin for Chromium"> | Removed | <a href="https://developer.chrome.com/docs/extensions/develop/migrate/mv2-deprecation-timeline#aug_31st_2026_all_remaining_manifest_v2_extensions_removed_from_the_chrome_web_store">"Manifest V2 support timeline"</a>: "Aug 31st 2026: All remaining Manifest V2 extensions removed from the Chrome Web Store"<br><a href="https://github.com/uBlockOrigin/uBlock-issues/wiki/About-Google-Chrome's-%22This-extension-may-soon-no-longer-be-supported%22">About Google Chrome's "This extension may soon no longer be supported"</a> |
| <img src="https://github.com/user-attachments/assets/2e9037c4-836d-44c1-a716-ba96e89daaff" alt="Get uBlock Origin for Thunderbird"> | <a href="https://addons.thunderbird.net/thunderbird/addon/ublock-origin/">Thunderbird Add-ons</a> | [No longer updated and stuck at 1.49.2.](https://github.com/uBlockOrigin/uBlock-issues/issues/2928) Later versions require "GitHub - Releases". |
| <img src="https://upload.wikimedia.org/wikipedia/commons/c/c2/GitHub_Invertocat_Logo.svg" height="50" alt="Get uBlock Origin through GitHub"> | <a href="https://github.com/gorhill/uBlock/releases">GitHub - Releases</a> | Stable and development versions on Firefox, Chromium MV2, and Thunderbird. Must be placed manually into web browsers; the Chromium and Thunderbird versions usually won't auto-update.

<h3> Related: 
<sub>
<img src="https://github.com/gorhill/uBlock/blob/master/platform/mv3/extension/img/ublock.svg" height="24" width="24">
</sub>
<a href="https://github.com/uBlockOrigin/uBOL-home">uBlock Origin Lite</a>
</h3>


***

uBlock Origin (uBO) is a CPU and memory-efficient [wide-spectrum content blocker][Blocking] for Chromium and Firefox. It blocks ads, trackers, coin miners, popups, annoying anti-blockers, malware sites, etc., by default using [EasyList][EasyList], [EasyPrivacy][EasyPrivacy], [Peter Lowe's Blocklist][Peter Lowe's Blocklist], [Online Malicious URL Blocklist][Malicious Blocklist], and uBO [filter lists][uBO Filters]. There are many other lists available to block even more. Hosts files are also supported. uBO uses the EasyList filter syntax and [extends][Extended Syntax] the syntax to work with custom rules and filters.

You may easily unselect any preselected filter lists if you think uBO blocks too much. For reference, Adblock Plus installs with only EasyList, ABP filters, and Acceptable Ads enabled by default.

It is important to note that using a blocker is **NOT** [theft]. Do not fall for this creepy idea. The _ultimate_ logical consequence of `blocking = theft` is the criminalization of the inalienable right to privacy.

Ads, "unintrusive" or not, are just the visible portion of the privacy-invading means entering your browser when you visit most sites. **uBO's primary goal is to help users neutralize these privacy-invading methods** in a way that welcomes those users who do not wish to use more technical means.

***

* [Documentation](#documentation)
* [Installation](#installation)
  * [Firefox](#firefox)
  * [Chromium](#chromium)
  * [Thunderbird](#thunderbird)
  * [All Programs](#all-programs)
  * [Enterprise Deployment](#enterprise-deployment)
* [Release History](#release-history)
* [Translations](#translations)
* [About](#about)

## Documentation

<table>
    <thead>
        <tr>
            <th>Basic Mode</th>
            <th>Advanced Mode</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>The <a href="https://github.com/gorhill/uBlock/wiki/Quick-guide:-popup-user-interface">simple popup user interface</a> for an install-it-and-forget-it type of installation that is configured optimally by default.</td>
            <td>The <a href="https://github.com/gorhill/uBlock/wiki/Dynamic-filtering:-quick-guide">advanced popup user interface</a> includes a point-and-click firewall that is configurable on a per-site basis.</td>
        </tr>
        <tr>
            <td align="center" valign="top"><a href="https://github.com/gorhill/uBlock/wiki/Quick-guide:-popup-user-interface"><img src="https://user-images.githubusercontent.com/585534/232531044-c4ac4dd5-0b60-4c1e-aabb-914be04b846c.png"/></a></td>
            <td align="center" valign="top"><a href="https://github.com/gorhill/uBlock/wiki/Dynamic-filtering:-quick-guide"><img src="https://user-images.githubusercontent.com/585534/232531439-a8f81cc3-6622-45c4-8b32-7348cecf6e98.png"/></a></td>
        </tr>
    </tbody>
</table>

Visit the [Wiki][Wiki] for documentation.

For support, questions, or help, visit [/r/uBlockOrigin][Reddit].

## Installation

[Required Permissions][Permissions]

#### Firefox

[Firefox Add-ons][Mozilla]

[Development Builds][Beta]

uBO [works best][Works Best] on Firefox and is available for desktop and Android versions.

#### Chromium

Chrome Web Store: Removed on 2026-08-31

[Microsoft Edge Add-ons][Edge] (Published by [Nicole Rolls][Nicole Rolls] until version 1.62. Ownership transfer at version 1.64.)

[Opera Add-ons][Opera]

uBO should be compatible with any Chromium-based browser.

#### Thunderbird

[Thunderbird Add-ons][Thunderbird]

In Thunderbird, uBlock Origin does not affect emails, just feeds.

#### All Programs

Do **NOT** use uBO with any other content blocker. uBO [performs][Performance] as well as or better than most popular blockers. Other blockers can prevent uBO's privacy or anti-blocker-defusing features from working correctly.

[Manual Installation][Manual Installation]

#### Enterprise Deployment

[Deploying uBO][Deployment]

## Release History

[Releases Page][Releases]

## Translations

Help translate uBO via [Crowdin][Crowdin].

## About

[Manifesto][Manifesto]

[Privacy Policy][Privacy Policy]

[GPLv3 License][License]

Free. Open-source. For users by users. No donations sought.

If you ever want to contribute something, think about the people working hard to maintain the filter lists you are using, which are available to use by all for free.


<!----------------------------------------------------------------------------->

[Peter Lowe's Blocklist]: https://pgl.yoyo.org/adservers/
[Malicious Blocklist]: https://gitlab.com/malware-filter/urlhaus-filter#malicious-url-blocklist
[Performance]: https://www.debugbear.com/blog/chrome-extensions-website-performance#the-impact-of-ad-blocking-on-website-performance
[EasyPrivacy]: https://easylist.to/#easyprivacy
[Thunderbird]: https://addons.thunderbird.net/thunderbird/addon/ublock-origin/
[EasyList]: https://easylist.to/#easylist
[Mozilla]: https://addons.mozilla.org/addon/ublock-origin/
[Crowdin]: https://crowdin.com/project/ublock
[Reddit]: https://www.reddit.com/r/uBlockOrigin/
[Theft]: https://x.com/LeaVerou/status/518154828166725632
[Opera]: https://addons.opera.com/extensions/details/ublock/
[Edge]: https://microsoftedge.microsoft.com/addons/detail/ublock-origin/odfafepnkmbhccpbejgmiehpchacaeak
[NPM]: https://www.npmjs.com/package/@gorhill/ubo-core

[Manifesto]: MANIFESTO.md
[License]: LICENSE.txt

[Nicole Rolls]: https://github.com/nicole-ashley

<!---------------------------------[ Internal ]-------------------------------->

[Manual Installation]: https://github.com/gorhill/uBlock/tree/master/dist#install
[Extended Syntax]: https://github.com/gorhill/uBlock/wiki/Static-filter-syntax#extended-syntax
[Privacy Policy]: https://github.com/gorhill/uBlock/wiki/Privacy-policy
[uBO Filters]: https://github.com/uBlockOrigin/uAssets/tree/master/filters
[Permissions]: https://github.com/gorhill/uBlock/wiki/Permissions
[Commit Rate]: https://github.com/gorhill/uBlock/commits/master
[Works Best]: https://github.com/gorhill/uBlock/wiki/uBlock-Origin-works-best-on-Firefox
[Deployment]: https://github.com/gorhill/uBlock/wiki/Deploying-uBlock-Origin
[Blocking]: https://github.com/gorhill/uBlock/wiki/Blocking-mode
[Releases]: https://github.com/gorhill/uBlock/releases
[Issues]: https://github.com/uBlockOrigin/uBlock-issues/issues
[Beta]: https://github.com/gorhill/uBlock/blob/master/dist/README.md#for-beta-version
[Wiki]: https://github.com/gorhill/uBlock/wiki

<!----------------------------------[ Badges ]--------------------------------->

[Badge Localization]: https://d322cqt584bo4o.cloudfront.net/ublock/localized.svg
[Badge Commits]: https://img.shields.io/github/commit-activity/m/gorhill/ublock?label=Commits
[Badge Mozilla]: https://img.shields.io/amo/rating/ublock-origin?label=Firefox
[Badge License]: https://img.shields.io/badge/License-GPLv3-blue.svg
[Badge Chrome]: https://img.shields.io/chrome-web-store/rating/cjpalhdlnbpafiamejdnhcphjbkeiagm?label=Chrome
[Badge Edge]: https://img.shields.io/badge/dynamic/json?label=Edge&color=brightgreen&query=%24.averageRating&suffix=%2F%35&url=https%3A%2F%2Fmicrosoftedge.microsoft.com%2Faddons%2Fgetproductdetailsbycrxid%2Fodfafepnkmbhccpbejgmiehpchacaeak
[Badge Issues]: https://img.shields.io/github/issues/uBlockOrigin/uBlock-issues
[Badge NPM]: https://img.shields.io/npm/v/@gorhill/ubo-core

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

- **自动同步**：启动后自动同步一次；之后定时同步 + 本地变更稍后自动推送，无需人工干预；
- **多端可靠**：锁文件防多端并发冲突，双端同时修改时不会静默覆盖，会明确提示让你选择保留哪边；
- **跨浏览器**：基于 uBO 官方云存储通道实现，任何能装 uBO 的浏览器都适用。

### 适用浏览器

| 平台 | 浏览器 |
|---|---|
| Windows 桌面 | **Turbo**、**百分（Cent）**、**Firefox** |
| Android | **Quetta**（真机）、**Kiwi**（x86 设备/模拟器） |

> Chrome/Edge 等官方商店渠道已移除 MV2 支持，无法使用。各浏览器的详细安装方法与兼容性实测记录见[测试文档](docs/DAVSYNC-TESTING.md)。

### 下载安装

到 [Releases](https://github.com/leoshone/ublock-davsync/releases) 下载最新版（Assets 里三个包，按浏览器选择）：

| 包 | 适用 | 安装方式 |
|---|---|---|
| **`.crx`** | 百分等支持 crx 安装的 Chromium 壳 | 扩展页开启「开发者模式」→ 拖入 crx → 确认。安装后持久生效 |
| **`.zip`** | Kiwi（Android） | push 到设备 → 扩展页「+ (from .zip)」选择 |
| 解包目录 | Turbo 等不支持 crx 安装的壳 | `--load-extension=<解包目录>` 启动 |
| **`.firefox.xpi`** | Firefox（桌面） | 临时加载（web-ext），日常使用建议等待正式签名方案 |

### 配置同步

1. 扩展安装后打开 uBO 设置页 → 底部「DAV-Sync」区块
2. 填 WebDAV 地址（如 `https://dav.jianguoyun.com/dav/`）、账号、**应用密码**（坚果云用授权密码而非登录密码）、设备名
3. 开启开关 → 立即首推；其余设备填**同一 WebDAV 目录**、**不同设备名**即可自动互相同步

> 遇到同步连接错误时：个别 Android 网络环境可能无法直连坚果云 WebDAV（桌面端不受影响），切换网络/使用代理通常可解决，或改用其他标准 WebDAV 服务商（InfiniCLOUD/TeraCLOUD/自建 Nextcloud 均可）。

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

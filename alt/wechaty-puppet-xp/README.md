# Legacy engine: Wechaty + puppet-xp / 旧版引擎

> [!CAUTION]
> **Legacy / experimental. Largely unusable today.** wechaty-puppet-xp 2.1.1 only supports WeChat **3.9.10.27**, which Tencent now blocks at login. Use the main engine (wxauto4 + WeChat 4.x) in the [project root](../../README.md) instead.
>
> **旧版 / 实验性，目前基本无法使用。** wechaty-puppet-xp 2.1.1 只支持微信 **3.9.10.27**，该版本已被腾讯在登录时拦截。请使用[项目根目录](../../README.zh-CN.md)的主引擎（wxauto4 + 微信 4.x）。

Kept for reference: Node.js, Wechaty 1.20.2, puppet-xp 2.1.1 (Apache-2.0), group memory with BM25 search over Chinese bigrams, proactive chat. Version spoofing (e.g. [FakeWechatVersion](https://github.com/ThinkerWen/FakeWechatVersion), no license, linked only) is unreliable and not included.

保留供参考：Node.js、Wechaty 1.20.2、puppet-xp 2.1.1（Apache-2.0）、基于中文二元词 BM25 检索的群记忆、主动聊天。改版本号方案（如 FakeWechatVersion，无许可证，仅链接）不可靠，本仓库不包含。

## Usage / 使用

Requirements / 要求: Windows x64, **Node.js 18 LTS**, WeChat **3.9.10.27** logged in / 已登录.

1. `install.bat` (in this folder / 本目录) runs `npm install` and creates `.env` from `.env.example`.
2. Fill in `.env` in **this folder** (`OPENAI_API_KEY`, `BOT_NAME`, ...). Comments are bilingual. 在**本目录**的 `.env` 里填写配置，注释中英双语。
3. `start.bat` checks the config (`node scripts/check-config.js`) and starts `src/index.js`.

The persona is shared with the main engine: `../../persona/`. Runtime data goes to `kb/` and `logs/` inside this folder (git-ignored).
人设与主引擎共用 `../../persona/`；运行数据写入本目录下的 `kb/`、`logs/`（已被 git 忽略）。

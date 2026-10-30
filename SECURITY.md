# Security & Disclaimer / 安全与免责声明

## Disclaimer / 免责声明

**English.** This project is for learning and personal research only. It is not affiliated with or endorsed by Tencent or WeChat. It relies on unofficial third-party techniques (UI automation via wxauto4 in the main engine; process injection via wechaty-puppet-xp in the legacy engine) that violate WeChat's terms of service and may lead to your account being restricted or permanently banned. Use a secondary account. Do not use it for spam, marketing, fraud, harassment, or collecting other people's data. You are solely responsible for how you use it.

**中文。** 本项目仅供学习和个人研究，与腾讯 / 微信无关，也未获其认可。项目依赖非官方的第三方技术（主引擎使用 wxauto4 界面自动化；旧版引擎使用 wechaty-puppet-xp 进程注入），违反微信使用条款，可能导致账号被限制或永久封禁。请使用小号。禁止用于群发营销、诈骗、骚扰或收集他人数据。使用后果由使用者自行承担。

## Protecting your data / 保护你的数据

- Keep `.env` private. It is git-ignored; never paste your API key into issues or screenshots.
  `.env` 不要外传；它已被 git 忽略，不要把 API Key 贴到 Issue 或截图里。
- `kb/` and `logs/` (also under `alt/wechaty-puppet-xp/`) contain real chat content and are git-ignored. Do not share them.
  `kb/` 和 `logs/` 含真实聊天内容，已被 git 忽略，请勿分享。
- Messages are sent to the AI provider you configure. Choose one you trust and tell group members.
  消息会发送给你配置的 AI 服务商，请选择可信的服务商并告知群成员。
- Group messages are untrusted input. The default persona tells the model not to follow instructions inside them, but prompt injection cannot be fully prevented; the bot has no tools besides replying.
  群消息属于不可信输入。默认人设要求模型不照做其中的指令，但无法完全防止提示词注入；机器人除了回复消息外没有其他能力。

## Reporting a vulnerability / 报告漏洞

Please open a private security advisory on GitHub (Security > Report a vulnerability) instead of a public issue.
请通过 GitHub 的私密安全通告（Security > Report a vulnerability）报告，不要公开提 Issue。

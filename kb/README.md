# kb/ - local knowledge base / 本地知识库

Generated at runtime. Everything here except this file is git-ignored.
运行时自动生成；除本文件外全部被 git 忽略，不会提交。

```
kb/shared.md                      facts for all chats (hand-written)    所有会话共用的事实（手写）
kb/handled.jsonl                  dedup records                         去重记录
kb/proactive.json                 proactive chat state                  主动聊天状态
kb/chats/<chat>/chat.jsonl        this chat's exchanges (scrubbed)      本会话问答（已脱敏）
kb/chats/<chat>/knowledge.md      notes for this chat only (hand-written) 只属于本会话的知识（手写）
kb/chats/<chat>/memory.md         AI-maintained memory                  AI 整理的长期记忆
```

Example `kb/chats/<chat>/knowledge.md` (fictional) / 示例（虚构）:

```markdown
# 周末徒步小队
- 每月第一个周六活动，集合地点在地铁站 A 口
- 阿明负责拍照，问照片找他
```

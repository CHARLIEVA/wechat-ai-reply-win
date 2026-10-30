'use strict'
// Runtime strings in both languages / 运行时文案（中英双语）
const { config } = require('./config')

const S = {
  'zh-CN': {
    missingKey: '没有设置 OPENAI_API_KEY，请复制 .env.example 为 .env 并填写。',
    started: '机器人已启动，等待 puppet-xp 连接已登录的微信……',
    login: '已登录',
    logout: '已退出登录',
    scan: '需要扫码登录，打开下面的链接显示二维码：',
    inGroup: (topic) => `当前群名：${topic}。`,
    proactiveTask: '群里已经安静一阵子了，你要主动打破沉默。只说一句简短自然的话，像普通群友随口一说：可以接着最近聊过的话题，或问个轻松的问题。不要打招呼，不要说自己是 AI，不要 @ 任何人，不要夸人，直接输出这句话。',
    noRecentCtx: '（群里最近没有可参考的聊天记录）',
    bgHeader: '以下是你私下掌握的背景（仅供参考，自然地用，不要逐条复述，不要提“记录/日志/记忆”）：',
    memRoom: '【你对这个群的长期记忆】',
    memPeople: '【相关成员记忆】',
    memHits: '【可能相关的过往聊天片段】',
    mentionedYou: '（@了你）',
    someone: '某人',
  },
  en: {
    missingKey: 'OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in.',
    started: 'Bot started, waiting for puppet-xp to attach to the logged-in WeChat...',
    login: 'Logged in',
    logout: 'Logged out',
    scan: 'Login QR needed, open this link to display it:',
    inGroup: (topic) => `Current group: ${topic}.`,
    proactiveTask: 'The group has been quiet for a while. Break the silence with ONE short, natural line, like a normal member would: follow up on a recent topic or ask a light question. No greetings, do not say you are an AI, do not @ anyone, no flattery. Output only that line.',
    noRecentCtx: '(No recent messages in this group.)',
    bgHeader: 'Private background you know (use it naturally; do not list it or mention "records/logs/memory"):',
    memRoom: '[Long-term memory of this group]',
    memPeople: '[Relevant members]',
    memHits: '[Possibly related past messages]',
    mentionedYou: '(mentioned you)',
    someone: 'someone',
  },
}

module.exports = S[config.LANGUAGE] || S['zh-CN']

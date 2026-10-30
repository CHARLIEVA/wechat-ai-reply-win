'use strict'
/**
 * wechat-ai-reply-win: Wechaty + wechaty-puppet-xp + OpenAI-compatible AI auto-reply.
 * Wechaty + puppet-xp + OpenAI 兼容接口的微信 AI 自动回复。
 *
 * Flow / 流程:
 *   WeChat PC (logged in) -> puppet-xp hook -> Wechaty "message" event
 *   -> trigger check (@ / name / private) -> persona + memory + context -> AI -> reply
 */
const { WechatyBuilder } = require('wechaty')
const { PuppetXp } = require('wechaty-puppet-xp')
const { config, loadPersona } = require('./config')
const { log } = require('./logger')
const ai = require('./ai')
const memory = require('./memory')
const proactive = require('./proactive')
const T = require('./i18n')

if (!config.OPENAI_API_KEY) { log('[ERROR] ' + T.missingKey); process.exit(1) }

const bot = WechatyBuilder.build({ name: 'wechat-ai-reply-win', puppet: new PuppetXp() })

// ---------- helpers / 工具函数 ----------
const ctx = new Map() // chatId -> [{role, content}] short-term context / 短期上下文
const lastReply = new Map()
const busy = new Set()
const pending = new Map()

function pushCtx (id, item) {
  const a = ctx.get(id) || []
  a.push(item)
  while (a.length > config.CONTEXT_MESSAGES) a.shift()
  ctx.set(id, a)
}
function roomAllowed (topic) {
  if (config.ROOM_BLOCKLIST.includes(topic)) return false
  if (config.ROOM_ALLOWLIST.length) return config.ROOM_ALLOWLIST.includes(topic)
  return true
}
function trimReply (s) {
  s = (s || '').trim()
  return s.length > config.MAX_REPLY_CHARS ? s.slice(0, config.MAX_REPLY_CHARS) + '…' : s
}
// Persona is re-read on every reply, so edits apply without restart.
// 每次回复都重新读取人设文件，改人设无需重启。
function systemPrompt (topic, extra = '') {
  return loadPersona() + (topic ? '\n' + T.inGroup(topic) : '') + extra
}

// ---------- group reply / 群聊回复 ----------
async function replyInRoom (room, talker, senderName, text, queued = false) {
  const id = room.id
  let topic = ''; try { topic = await room.topic() } catch (e) {}
  const gap = Date.now() - (lastReply.get(id) || 0)
  if (busy.has(id) || gap < config.MIN_GAP_MS) {
    // Only the latest trigger per group is answered after a burst.  连发时只答最新一条
    if (!queued) pushCtx(id, { role: 'user', content: senderName + ': ' + text.slice(0, 500) })
    pending.set(id, { room, talker, senderName, text })
    if (!busy.has(id)) setTimeout(() => drain(id), Math.max(50, config.MIN_GAP_MS - gap + 50))
    return
  }
  busy.add(id); lastReply.set(id, Date.now())
  try {
    if (!queued) pushCtx(id, { role: 'user', content: senderName + ': ' + text.slice(0, 1500) })
    let bg = ''
    try {
      const recent = memory.readRaw(id, Date.now() - 3 * 3600e3, 1).slice(-15)
      const pids = [talker && talker.id, senderName, ...recent.map(r => r.senderId), ...recent.map(r => r.sender)].filter(Boolean)
      bg = memory.contextBlock(id, { query: text, participantIds: pids })
    } catch (e) { log('memory context error', e) }
    const reply = trimReply(await ai.chat([{ role: 'system', content: systemPrompt(topic, bg) }, ...(ctx.get(id) || [])]))
    if (!reply) return log('AI empty reply')
    pushCtx(id, { role: 'assistant', content: reply })
    // @ the asker so the answer is clearly attached to the question.  回复时 @ 提问的人
    try { await room.say(reply, talker) } catch (e) { await room.say(reply) }
    memory.archive({ roomId: id, topic, senderId: 'self', senderName: config.BOT_NAME, text: reply, self: true })
    log(`replied room=${topic} len=${reply.length}`)
  } catch (e) {
    log('AI error', e)
  } finally {
    busy.delete(id); lastReply.set(id, Date.now())
    if (pending.has(id)) setTimeout(() => drain(id), config.MIN_GAP_MS)
  }
}
function drain (id) {
  const p = pending.get(id)
  if (!p || busy.has(id)) return
  pending.delete(id)
  replyInRoom(p.room, p.talker, p.senderName, p.text, true).catch(e => log('drain error', e))
}

// ---------- private reply / 私聊回复 ----------
async function replyPrivate (msg, talker, text) {
  const id = 'dm:' + talker.id
  pushCtx(id, { role: 'user', content: text.slice(0, 1500) })
  const reply = trimReply(await ai.chat([{ role: 'system', content: systemPrompt('') }, ...(ctx.get(id) || [])]))
  if (!reply) return
  pushCtx(id, { role: 'assistant', content: reply })
  await msg.say(reply)
  log('replied private len=' + reply.length)
}

// ---------- events / 事件 ----------
bot.on('scan', (qrcode, status) => {
  log(`scan status=${status}`)
  log(T.scan + ' https://wechaty.js.org/qrcode/' + encodeURIComponent(qrcode))
})
bot.on('login', user => log(`${T.login}: ${user.name()}`))
bot.on('logout', user => log(`${T.logout}: ${user.name()}`))
bot.on('error', e => log('bot error', e))

bot.on('message', async msg => {
  try {
    if (msg.type() !== bot.Message.Type.Text) return
    const room = msg.room()
    const talker = msg.talker()
    const text = (msg.text() || '').trim()
    let senderName = T.someone; try { senderName = talker.name() || T.someone } catch (e) {}

    // Archive group messages for memory.  群消息写入本地知识库
    if (room) {
      let topic = ''; try { topic = await room.topic() } catch (e) {}
      proactive.note(room.id, !msg.self())
      if (!roomAllowed(topic)) return
      if (!msg.self()) memory.archive({ roomId: room.id, topic, senderId: talker.id, senderName, text, ts: msg.date().getTime() })
    }
    if (msg.self() || !text) return

    // Ignore old messages replayed after (re)login.  忽略重新登录后补推的旧消息
    if (Date.now() - msg.date().getTime() > config.STALE_MESSAGE_MIN * 60e3) return

    const names = [config.BOT_NAME, ...config.BOT_ALIASES]
    try { const me = bot.currentUser.name(); if (me) names.push(me) } catch (e) {}
    const named = names.some(n => n && text.includes(n))

    if (!room) {
      if (!config.REPLY_IN_PRIVATE) return
      if (config.PRIVATE_REQUIRE_TRIGGER && !named) return
      return await replyPrivate(msg, talker, text)
    }

    if (!config.REPLY_IN_GROUPS) return
    let mentioned = false
    try { mentioned = await msg.mentionSelf() } catch (e) {}
    if (!mentioned && !named) {
      pushCtx(room.id, { role: 'user', content: senderName + ': ' + text.slice(0, 500) }) // light context / 轻量上下文
      return
    }
    let clean = text
    try { if (mentioned) clean = (await msg.mentionText()) || text } catch (e) {}
    for (const n of names) if (n) clean = clean.split('@' + n).join('')
    clean = clean.replace(/\u2005/g, ' ').trim() || T.mentionedYou
    await replyInRoom(room, talker, senderName, clean)
  } catch (e) { log('message error', e) }
})

// ---------- background jobs / 后台任务 ----------
memory.start(ai.chat, log)
proactive.start({
  bot,
  log,
  isBusy: id => busy.has(id),
  allowed: roomAllowed,
  generate: async (room, topic) => {
    const recent = ctx.get(room.id) || []
    const bg = memory.contextBlock(room.id, { query: recent.slice(-6).map(c => c.content).join(' ') })
    const messages = [{ role: 'system', content: systemPrompt(topic, bg) + '\n' + T.proactiveTask }, ...recent.slice(-10)]
    if (!recent.length) messages.push({ role: 'user', content: T.noRecentCtx })
    const line = await ai.chat(messages, 200)
    return (line || '').replace(/^["“”']+|["“”']+$/g, '').replace(/@\S+/g, '').trim().split('\n')[0].slice(0, 120)
  },
})

process.on('unhandledRejection', e => log('unhandledRejection', e))
bot.start().then(() => log(T.started)).catch(e => { log('start failed', e); process.exit(1) })

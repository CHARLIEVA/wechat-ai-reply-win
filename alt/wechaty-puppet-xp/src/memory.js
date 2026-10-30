'use strict'
/**
 * Local knowledge base + long-term memory.  本地知识库 + 长期记忆
 *
 * kb/raw/<chatId>/<YYYY-MM-DD>.jsonl  raw messages (scrubbed)      原始消息（已脱敏）
 * kb/memory/<chatId>.md               per-group long-term memory   每个群的长期记忆
 * kb/memory/people.md                 cross-group member notes     跨群成员档案
 * kb/state.json                       bookkeeping                  内部状态
 *
 * Retrieval: BM25 over Chinese char bigrams + ASCII words, no vector DB needed.
 * 检索：中文二元组 + 英文单词的 BM25，不依赖向量数据库。
 * Everything stays on your disk. 所有数据只保存在本机。
 */
const fs = require('fs')
const path = require('path')
const { config } = require('./config')
const T = require('./i18n')

const KB = config.KB_DIR
const RAW = path.join(KB, 'raw')
const MEM = path.join(KB, 'memory')
const STATE = path.join(KB, 'state.json')
const PEOPLE = path.join(MEM, 'people.md')
fs.mkdirSync(RAW, { recursive: true }); fs.mkdirSync(MEM, { recursive: true })

const CFG = {
  enabled: config.MEMORY_ENABLED,
  intervalMin: config.MEMORY_INTERVAL_MIN,
  minNew: config.MEMORY_MIN_NEW,
  searchDays: config.MEMORY_SEARCH_DAYS,
  roomCap: 2000, peopleCap: 6000, topK: 5,
}
let state = {}
try { state = JSON.parse(fs.readFileSync(STATE, 'utf8')) || {} } catch (e) { state = {} }
const saveState = () => { try { fs.writeFileSync(STATE, JSON.stringify(state, null, 1)) } catch (e) {} }
const rst = id => (state[id] = state[id] || { newCount: 0, lastTs: 0, topic: '' })
const safeId = id => String(id).replace(/[^A-Za-z0-9:_@.-]/g, '_')
const day = ts => new Intl.DateTimeFormat('en-CA', { timeZone: config.TIMEZONE }).format(new Date(ts))

// Redact obviously sensitive data BEFORE anything is stored.  落盘前先脱敏
function scrub (t) {
  return String(t || '')
    .replace(/sk-[A-Za-z0-9_-]{8,}/g, '[key]')
    .replace(/\b\d{17}[\dXx]\b/g, '[id-number]')
    .replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, '[phone]')
    .replace(/\b\d{16,19}\b/g, '[card]')
}

const cache = new Map()

function archive ({ roomId, topic, senderId, senderName, text, type, ts, self }) {
  ts = ts || Date.now()
  const dir = path.join(RAW, safeId(roomId)); fs.mkdirSync(dir, { recursive: true })
  const rec = { ts, topic: topic || '', senderId: senderId || '', sender: senderName || '', self: !!self }
  if (type && type !== 'Text') rec.type = type; else rec.text = scrub(text).slice(0, 2000)
  fs.appendFileSync(path.join(dir, day(ts) + '.jsonl'), JSON.stringify(rec) + '\n')
  const s = rst(roomId); if (rec.text) s.newCount++; if (topic) s.topic = topic; saveState()
  cache.delete(roomId)
}

function readRaw (roomId, sinceTs = 0, days = CFG.searchDays) {
  const dir = path.join(RAW, safeId(roomId)); if (!fs.existsSync(dir)) return []
  const cutoff = day(Date.now() - days * 86400e3)
  const out = []
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.jsonl') && f.slice(0, 10) >= cutoff).sort()) {
    for (const l of fs.readFileSync(path.join(dir, f), 'utf8').split('\n')) {
      if (!l) continue; try { const r = JSON.parse(l); if (r.ts > sinceTs) out.push(r) } catch (e) {}
    }
  }
  return out.sort((a, b) => a.ts - b.ts)
}

// ---- retrieval: BM25 ----
const STOP = new Set(['哈哈', '什么', '怎么', '这个', '那个', '一下', '你们', '我们', '不是', '就是', '可以', '没有'])
function toks (t) {
  t = String(t || '').toLowerCase().replace(/@\S+/g, ' ')
  const out = (t.match(/[a-z0-9]{2,}/g) || [])
  const han = t.replace(/[^\u4e00-\u9fff]/g, ' ').split(/\s+/).filter(Boolean)
  for (const h of han) for (let i = 0; i < h.length - 1; i++) { const b = h.slice(i, i + 2); if (!STOP.has(b)) out.push(b) }
  return out
}
function index (roomId) {
  if (cache.has(roomId)) return cache.get(roomId)
  const docs = readRaw(roomId).filter(r => r.text)
  const tf = []; const df = new Map(); const lens = []
  for (const d of docs) {
    const m = new Map(); for (const w of toks(d.text)) m.set(w, (m.get(w) || 0) + 1)
    tf.push(m); lens.push([...m.values()].reduce((a, b) => a + b, 0))
    for (const w of m.keys()) df.set(w, (df.get(w) || 0) + 1)
  }
  const avg = lens.reduce((a, b) => a + b, 0) / (lens.length || 1)
  const ix = { docs, tf, df, lens, avg }; cache.set(roomId, ix); return ix
}
function search (roomId, query, { k = CFG.topK, excludeLast = 20 } = {}) {
  const ix = index(roomId); const q = [...new Set(toks(query))]; if (!q.length || !ix.docs.length) return []
  const N = ix.docs.length; const lim = Math.max(0, N - excludeLast); const res = []
  for (let i = 0; i < lim; i++) {
    let s = 0; const m = ix.tf[i]
    for (const t of q) {
      const f = m.get(t); if (!f) continue
      const idf = Math.log(1 + (N - ix.df.get(t) + 0.5) / (ix.df.get(t) + 0.5))
      s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * ix.lens[i] / ix.avg))
    }
    if (s > 0) res.push([s, ix.docs[i]])
  }
  return res.sort((a, b) => b[0] - a[0]).slice(0, k).map(x => x[1]).sort((a, b) => a.ts - b.ts)
}

function readMem (roomId) { try { return fs.readFileSync(path.join(MEM, safeId(roomId) + '.md'), 'utf8') } catch (e) { return '' } }
function readPeople () { try { return fs.readFileSync(PEOPLE, 'utf8') } catch (e) { return '' } }
function peopleFor (ids) {
  const txt = readPeople(); if (!txt || !ids.length) return ''
  return txt.split(/\n(?=## )/).filter(sec => {
    const h = sec.split('\n')[0]
    return ids.some(id => id && id !== 'self' && (h.startsWith('## ' + id + ' ') || h.split(' ').slice(1).includes(id)))
  }).join('\n').slice(0, 1200)
}

/** Context block appended to the system prompt (~3.5k chars max). 拼进系统提示词的背景块 */
function contextBlock (roomId, { query = '', participantIds = [] } = {}) {
  if (!CFG.enabled) return ''
  const parts = []
  const mem = readMem(roomId).slice(0, 2000); if (mem) parts.push(T.memRoom + '\n' + mem)
  const ppl = peopleFor([...new Set(participantIds)]); if (ppl) parts.push(T.memPeople + '\n' + ppl)
  const hits = query ? search(roomId, query) : []
  if (hits.length) parts.push(T.memHits + '\n' + hits.map(h => day(h.ts) + ' ' + (h.self ? config.BOT_NAME : h.sender) + ': ' + h.text.slice(0, 150)).join('\n'))
  if (!parts.length) return ''
  return '\n\n' + T.bgHeader + '\n' + parts.join('\n\n').slice(0, 3500)
}

// ---- periodic summarization into long-term memory / 定期把聊天整理成长期记忆 ----
const PROMPTS = {
  'zh-CN': {
    rules: '严禁记录敏感信息：身份证号、手机号、住址/定位、密码、验证码、银行卡/支付信息、密钥 token、健康病历等，遇到就忽略。只记真正说过或明显可推断的内容，不要编造。',
    room: (cap) => `你是群聊记忆整理员，为群助手“${config.BOT_NAME}”维护某个群的长期记忆。把【已有记忆】和【新聊天记录】合并成更新后的记忆，Markdown，简体中文，总长度不超过 ${cap} 字。结构固定：\n# 群：<群名>\n## 成员（昵称｜喜欢被怎么叫｜稳定偏好/兴趣｜性格特点，带 id）\n## 进行中的话题\n## 计划/约定/日期（写清绝对日期）\n## 梗与内部笑话\n## 群里提到的事实\n要求：去重；新旧矛盾以新为准；删除过期内容；每条一行、简短；不要记机器人自己的客套话。`,
    people: (cap) => `你维护跨群的人物档案 people.md（Markdown，简体中文，总长度不超过 ${cap} 字）。每人一节，标题格式严格为“## <id> <最常用昵称>”，下面用短条目记：别名、喜欢被怎么叫、稳定偏好兴趣、性格特点、所在群。合并去重、矛盾以新为准、不记一次性闲聊。不要为机器人自己建档。`,
    only: '只输出正文。', self: '(机器人自己)', none: '（无）',
    u: (topic, today, old, lines) => `群名：${topic}\n今天日期：${today}\n\n【已有记忆】\n${old}\n\n【新聊天记录】\n${lines}`,
    up: (old, topic, lines) => `【已有档案】\n${old}\n\n【新聊天记录（群：${topic}）】\n${lines}`,
  },
  en: {
    rules: 'Never record sensitive data: ID numbers, phone numbers, addresses/locations, passwords, verification codes, bank/payment info, API keys/tokens, medical info. Only record what was actually said or clearly implied; never invent.',
    room: (cap) => `You maintain the long-term memory of one WeChat group for the assistant "${config.BOT_NAME}". Merge [Existing memory] and [New messages] into an updated memory in Markdown, at most ${cap} characters. Fixed sections:\n# Group: <name>\n## Members (nickname | preferred name | stable interests | personality, with id)\n## Ongoing topics\n## Plans / dates (absolute dates)\n## Running jokes\n## Facts mentioned\nRules: dedupe; newer wins on conflict; drop expired items; one short line per item; skip the bot's own small talk.`,
    people: (cap) => `You maintain people.md, cross-group member notes (Markdown, max ${cap} characters). One section per person, heading exactly "## <id> <most used nickname>", short bullets: aliases, preferred name, stable interests, personality, groups. Merge and dedupe, newer wins, skip one-off chatter. Do not create a profile for the bot itself.`,
    only: 'Output only the content.', self: '(the bot itself)', none: '(none)',
    u: (topic, today, old, lines) => `Group: ${topic}\nToday: ${today}\n\n[Existing memory]\n${old}\n\n[New messages]\n${lines}`,
    up: (old, topic, lines) => `[Existing profiles]\n${old}\n\n[New messages (group: ${topic})]\n${lines}`,
  },
}
const P = PROMPTS[config.LANGUAGE] || PROMPTS['zh-CN']

let running = false
async function updateRoom (roomId, ask, log, { force = false } = {}) {
  const s = rst(roomId)
  const msgs = readRaw(roomId, s.lastTs).filter(r => r.text || r.type)
  if (!msgs.length || (!force && s.newCount < CFG.minNew)) return false
  const topic = s.topic || msgs[msgs.length - 1].topic || roomId
  const lines = msgs.slice(-400).map(r => `[${new Date(r.ts).toLocaleString('sv-SE', { timeZone: config.TIMEZONE })}] ${r.self ? config.BOT_NAME + P.self : r.sender + '(id:' + r.senderId + ')'}: ${r.text || '[' + r.type + ']'}`).join('\n').slice(-12000)
  const old = readMem(roomId)
  const roomMd = await ask([{ role: 'system', content: P.room(CFG.roomCap) + P.rules + P.only }, { role: 'user', content: P.u(topic, day(Date.now()), old || P.none, lines) }], 4000)
  if (!roomMd || roomMd.length < 20) throw new Error('empty room memory from model')
  fs.writeFileSync(path.join(MEM, safeId(roomId) + '.md'), scrub(roomMd).slice(0, CFG.roomCap + 300) + '\n')
  const peopleMd = await ask([{ role: 'system', content: P.people(CFG.peopleCap) + P.rules + P.only }, { role: 'user', content: P.up(readPeople() || P.none, topic, lines) }], 5000)
  if (peopleMd && peopleMd.includes('## ')) fs.writeFileSync(PEOPLE, scrub(peopleMd).slice(0, CFG.peopleCap + 500) + '\n')
  else log('memory: people.md update skipped (bad output)')
  s.lastTs = msgs[msgs.length - 1].ts; s.newCount = 0; s.lastRun = Date.now(); saveState()
  log(`memory updated room=${topic} from ${msgs.length} msgs`)
  return true
}
async function runAll (ask, log, opts = {}) {
  if (running) return; running = true
  try {
    for (const id of Object.keys(state)) {
      try { await updateRoom(id, ask, log, opts) } catch (e) { log('memory update error room=' + id, e) }
    }
  } finally { running = false }
}
function start (ask, log) {
  log('memory config ' + JSON.stringify({ enabled: CFG.enabled, intervalMin: CFG.intervalMin, minNew: CFG.minNew }))
  if (!CFG.enabled) return
  setInterval(() => runAll(ask, log), CFG.intervalMin * 60e3)
  // Touch kb/update-now.txt to force a memory update.  创建 kb/update-now.txt 可立即整理一次记忆
  setInterval(() => {
    const f = path.join(KB, 'update-now.txt'); if (!fs.existsSync(f)) return
    try { fs.unlinkSync(f) } catch (e) {}
    log('memory: forced update requested')
    runAll(ask, log, { force: true }).then(() => log('memory: forced update done'))
  }, 3000)
}

module.exports = { archive, readRaw, search, contextBlock, start, runAll, scrub }

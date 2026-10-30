'use strict'
/**
 * Proactive chat: when a group has been quiet for a while, occasionally say one line.
 * 主动聊天：群里安静一段时间后，偶尔主动说一句。默认关闭。
 * Guard rails: active hours, quiet time, cooldown, daily cap, probability.
 * 限制条件：活跃时段、安静时长、冷却时间、每日上限、触发概率。
 */
const fs = require('fs')
const path = require('path')
const { config } = require('./config')

const STATE_FILE = path.join(config.KB_DIR, 'proactive-state.json')
let st = {}
try { st = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) || {} } catch (e) { st = {} }
const save = () => { try { fs.writeFileSync(STATE_FILE, JSON.stringify(st, null, 1)) } catch (e) {} }
const rs = id => (st[id] = st[id] || { lastMsg: 0, lastHuman: 0, lastPro: 0, day: '', count: 0 })

function today () { return new Intl.DateTimeFormat('en-CA', { timeZone: config.TIMEZONE }).format(new Date()) }
function minutesNow () {
  const p = new Intl.DateTimeFormat('en-GB', { timeZone: config.TIMEZONE, hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date())
  const [h, m] = p.split(':').map(Number); return (h % 24) * 60 + m
}
function inHours () {
  const [a, b] = config.PROACTIVE_HOURS.split('-').map(x => { const [h, m] = x.split(':').map(Number); return h * 60 + (m || 0) })
  const t = minutesNow(); return t >= a && t <= b
}

/** Call on every group message. 每条群消息都调用 */
function note (roomId, isHuman) {
  const s = rs(roomId); const now = Date.now()
  s.lastMsg = now; if (isHuman) s.lastHuman = now
  save()
}

/**
 * @param {object} deps { bot, log, isBusy(roomId), generate(room) -> Promise<string>, allowed(topic) }
 */
function start ({ bot, log, isBusy, generate, allowed }) {
  log('proactive config ' + JSON.stringify({
    enabled: config.PROACTIVE_ENABLED, hours: config.PROACTIVE_HOURS, quietMin: config.PROACTIVE_QUIET_MIN,
    cooldownMin: config.PROACTIVE_COOLDOWN_MIN, maxPerDay: config.PROACTIVE_MAX_PER_DAY, prob: config.PROACTIVE_PROB,
  }))
  if (!config.PROACTIVE_ENABLED) return
  let running = false
  setInterval(async () => {
    if (running || !bot.isLoggedIn || !inHours()) return
    running = true
    try {
      const now = Date.now(); const d = today()
      for (const room of await bot.Room.findAll()) {
        const s = rs(room.id)
        if (s.day !== d) { s.day = d; s.count = 0 }
        let topic = room.id; try { topic = (await room.topic()) || room.id } catch (e) {}
        if (!allowed(topic)) continue
        if (!s.lastHuman || now - s.lastHuman > 24 * 3600e3) continue // dead group / 一天没人说话的群不打扰
        if (now - s.lastMsg < config.PROACTIVE_QUIET_MIN * 60e3) continue
        if (now - s.lastPro < config.PROACTIVE_COOLDOWN_MIN * 60e3) continue
        if (s.count >= config.PROACTIVE_MAX_PER_DAY || isBusy(room.id)) continue
        if (Math.random() >= config.PROACTIVE_PROB) continue
        try {
          const line = await generate(room, topic)
          if (!line) continue
          await room.say(line)
          s.lastPro = Date.now(); s.lastMsg = s.lastPro; s.count++
          save()
          log(`proactive sent room=${topic} (${s.count}/${config.PROACTIVE_MAX_PER_DAY} today)`)
        } catch (e) { log('proactive send error room=' + topic, e) }
      }
    } catch (e) { log('proactive check error', e) } finally { running = false }
  }, config.PROACTIVE_CHECK_MIN * 60e3)
}

module.exports = { start, note }

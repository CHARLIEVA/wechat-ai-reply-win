'use strict'
// Load and normalize all settings from .env  /  从 .env 读取并整理全部配置
const fs = require('fs')
const path = require('path')

const ROOT = path.resolve(__dirname, '..')
require('dotenv').config({ path: path.join(ROOT, '.env') })

const env = (k, d = '') => (process.env[k] ?? d).toString().trim()
const bool = (k, d) => ['1', 'true', 'yes', 'on'].includes(env(k, String(d)).toLowerCase())
const num = (k, d) => { const n = Number(env(k, String(d))); return Number.isFinite(n) ? n : d }
const list = (k, d = '') => env(k, d).replace(/，/g, ',').split(',').map(s => s.trim()).filter(Boolean)

const LANGUAGE = env('LANGUAGE', 'zh-CN').toLowerCase().startsWith('en') ? 'en' : 'zh-CN'

function resolvePersonaFile () {
  const p = env('PERSONA_FILE')
  if (p) return path.isAbsolute(p) ? p : path.join(ROOT, p)
  // Shared persona files live in the repo root: ../../persona/  共用仓库根目录的人设文件
  return path.join(ROOT, '..', '..', 'persona', LANGUAGE === 'en' ? 'persona.en.md' : 'persona.zh-CN.md')
}

const config = {
  ROOT,
  LANGUAGE,
  TIMEZONE: env('TIMEZONE', 'Asia/Shanghai'),

  // AI (any OpenAI-compatible API)
  OPENAI_API_KEY: env('OPENAI_API_KEY'),
  OPENAI_BASE_URL: env('OPENAI_BASE_URL', 'https://api.openai.com/v1').replace(/\/+$/, ''),
  OPENAI_MODEL: env('OPENAI_MODEL', 'gpt-4o-mini'),
  OPENAI_MAX_TOKENS: num('OPENAI_MAX_TOKENS', 800),
  OPENAI_TIMEOUT_MS: num('OPENAI_TIMEOUT_MS', 60000),

  // Bot identity / triggers
  BOT_NAME: env('BOT_NAME', LANGUAGE === 'en' ? 'Nova' : '小星'),
  BOT_ALIASES: list('BOT_ALIASES'),
  PERSONA_FILE: resolvePersonaFile(),

  // Reply scope
  REPLY_IN_GROUPS: bool('REPLY_IN_GROUPS', true),
  REPLY_IN_PRIVATE: bool('REPLY_IN_PRIVATE', false),
  PRIVATE_REQUIRE_TRIGGER: bool('PRIVATE_REQUIRE_TRIGGER', true),
  ROOM_ALLOWLIST: list('ROOM_ALLOWLIST'),
  ROOM_BLOCKLIST: list('ROOM_BLOCKLIST'),
  CONTEXT_MESSAGES: num('CONTEXT_MESSAGES', 10),
  MIN_GAP_MS: num('MIN_GAP_MS', 3000),
  MAX_REPLY_CHARS: num('MAX_REPLY_CHARS', 300),
  STALE_MESSAGE_MIN: num('STALE_MESSAGE_MIN', 10),

  // Proactive chat
  PROACTIVE_ENABLED: bool('PROACTIVE_ENABLED', false),
  PROACTIVE_QUIET_MIN: num('PROACTIVE_QUIET_MIN', 45),
  PROACTIVE_COOLDOWN_MIN: num('PROACTIVE_COOLDOWN_MIN', 180),
  PROACTIVE_MAX_PER_DAY: num('PROACTIVE_MAX_PER_DAY', 3),
  PROACTIVE_PROB: num('PROACTIVE_PROB', 0.3),
  PROACTIVE_HOURS: env('PROACTIVE_HOURS', '09:00-22:30'),
  PROACTIVE_CHECK_MIN: num('PROACTIVE_CHECK_MIN', 10),

  // Memory / knowledge base
  MEMORY_ENABLED: bool('MEMORY_ENABLED', true),
  MEMORY_INTERVAL_MIN: num('MEMORY_INTERVAL_MIN', 30),
  MEMORY_MIN_NEW: num('MEMORY_MIN_NEW', 10),
  MEMORY_SEARCH_DAYS: num('MEMORY_SEARCH_DAYS', 30),
  KB_DIR: path.join(ROOT, env('KB_DIR', 'kb')),

  LOG_FILE: path.join(ROOT, env('LOG_FILE', 'logs/bot.log')),
}

function loadPersona () {
  try {
    const raw = fs.readFileSync(config.PERSONA_FILE, 'utf8')
    // strip HTML comments (used for bilingual notes) / 去掉 <!-- --> 注释
    const text = raw.replace(/<!--[\s\S]*?-->/g, '').trim()
    return text.split('{{BOT_NAME}}').join(config.BOT_NAME)
  } catch (e) {
    return config.LANGUAGE === 'en'
      ? `You are "${config.BOT_NAME}", a member of a WeChat group. Reply briefly and plainly.`
      : `你是“${config.BOT_NAME}”，微信群里的一员。用简体中文简短、直接地回复。`
  }
}

module.exports = { config, loadPersona }

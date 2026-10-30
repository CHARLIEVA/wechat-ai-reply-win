'use strict'
// Console + file logger with secret redaction / 带脱敏的日志
const fs = require('fs')
const path = require('path')
const { config } = require('./config')

fs.mkdirSync(path.dirname(config.LOG_FILE), { recursive: true })
const KEY = config.OPENAI_API_KEY

function redact (s) {
  let out = String(s)
  if (KEY) out = out.split(KEY).join('<redacted>')
  return out.replace(/sk-[A-Za-z0-9_-]{8,}/g, 'sk-<redacted>')
}

function log (...args) {
  const body = args.map(x => x instanceof Error ? (x.stack || x.message) : (typeof x === 'string' ? x : JSON.stringify(x))).join(' ')
  const line = `[${new Date().toISOString()}] ` + redact(body)
  console.log(line)
  try { fs.appendFileSync(config.LOG_FILE, line + '\n') } catch (e) {}
}

module.exports = { log, redact }

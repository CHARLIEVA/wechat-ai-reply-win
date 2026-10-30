'use strict'
// Minimal OpenAI-compatible chat client (no SDK) / 极简 OpenAI 兼容接口客户端
const { config } = require('./config')

async function chat (messages, maxTokens = config.OPENAI_MAX_TOKENS) {
  if (!config.OPENAI_API_KEY) throw new Error('OPENAI_API_KEY missing')
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), config.OPENAI_TIMEOUT_MS)
  try {
    const r = await fetch(config.OPENAI_BASE_URL + '/chat/completions', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + config.OPENAI_API_KEY, 'Content-Type': 'application/json' },
      // max_tokens is the most widely supported field across compatible providers
      body: JSON.stringify({ model: config.OPENAI_MODEL, messages, max_tokens: maxTokens }),
      signal: ctl.signal,
    })
    const body = await r.text()
    if (!r.ok) throw new Error(`AI HTTP ${r.status}: ${body.slice(0, 300)}`)
    const d = JSON.parse(body)
    return ((d.choices && d.choices[0] && d.choices[0].message && d.choices[0].message.content) || '').trim()
  } finally { clearTimeout(timer) }
}

module.exports = { chat }

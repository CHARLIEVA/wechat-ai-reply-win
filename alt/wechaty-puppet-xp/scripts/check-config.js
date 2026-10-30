'use strict'
// Quick sanity check of .env and persona without connecting to WeChat.
// 不连接微信，快速检查 .env 和人设文件是否就绪。
const fs = require('fs')
const { config, loadPersona } = require('../src/config')

let ok = true
const line = (good, msg) => { console.log((good ? '[ OK ] ' : '[FAIL] ') + msg); if (!good) ok = false }

line(Number(process.versions.node.split('.')[0]) >= 18, 'Node.js ' + process.version + ' (need >= 18, 18 LTS recommended / 建议 18 LTS)')
line(fs.existsSync(config.ROOT + '/.env'), '.env exists / .env 文件存在')
line(!!config.OPENAI_API_KEY, 'OPENAI_API_KEY set / 已填写 OPENAI_API_KEY')
line(/^https?:\/\//.test(config.OPENAI_BASE_URL), 'OPENAI_BASE_URL = ' + config.OPENAI_BASE_URL)
line(fs.existsSync(config.PERSONA_FILE), 'persona file / 人设文件: ' + config.PERSONA_FILE)
console.log('       LANGUAGE=' + config.LANGUAGE + '  BOT_NAME=' + config.BOT_NAME + '  MODEL=' + config.OPENAI_MODEL)
console.log('       groups=' + config.REPLY_IN_GROUPS + ' private=' + config.REPLY_IN_PRIVATE + ' proactive=' + config.PROACTIVE_ENABLED + ' memory=' + config.MEMORY_ENABLED)
console.log('\n--- persona preview / 人设预览 ---\n' + loadPersona().slice(0, 200) + '...\n')

if (process.argv.includes('--ping')) {
  require('../src/ai').chat([{ role: 'user', content: 'ping' }], 20)
    .then(r => { console.log('[ OK ] AI reply / AI 接口可用: ' + r) })
    .catch(e => { console.log('[FAIL] AI call / AI 接口调用失败: ' + e.message); process.exitCode = 1 })
} else if (!ok) process.exitCode = 1

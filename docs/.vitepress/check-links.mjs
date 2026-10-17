import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import config from './config.mjs'

const root = resolve(import.meta.dirname, '../..')
const docs = join(root, 'docs')
const failures = []
const markdownFiles = []
const collect = (directory) => {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue
    const path = join(directory, entry.name)
    if (entry.isDirectory()) collect(path)
    else if (entry.name.endsWith('.md')) markdownFiles.push(path)
  }
}
collect(docs)
markdownFiles.push(join(root, 'README.md'), join(root, 'README.ja.md'), join(root, 'brand/README.md'))

const resolves = (path) => [path, `${path}.md`, join(path, 'index.md')].some((candidate) => existsSync(candidate) && statSync(candidate).isFile())
const check = (source, raw) => {
  const url = raw.replace(/&amp;/g, '&')
  let target
  const repositoryPrefix = 'https://github.com/Sunwood-ai-labs/SECCA/'
  if (url.startsWith(`${repositoryPrefix}blob/main/`) || url.startsWith(`${repositoryPrefix}tree/main/`)) {
    target = join(root, url.slice(repositoryPrefix.length).replace(/^(blob|tree)\/main\//, '').split(/[?#]/)[0])
    if (existsSync(target)) return
  } else {
    if (/^(https?:|mailto:|data:|#)/.test(url)) return
    const pathname = decodeURIComponent(url.split(/[?#]/)[0])
    if (!pathname) return
    if (pathname.startsWith('/')) {
      const route = pathname.replace(/^\/SECCA\//, '/')
      target = join(docs, route)
      if (resolves(join(docs, 'public', route))) return
    } else target = resolve(dirname(source), pathname)
  }
  if (!resolves(target)) failures.push(`${relative(root, source)}: ${raw}`)
}

let linkCount = 0
for (const file of markdownFiles) {
  const content = readFileSync(file, 'utf8').replace(/```[\s\S]*?```/g, '')
  const links = [...content.matchAll(/\]\(([^\s)]+)(?:\s+"[^"]*")?\)|(?:href|src)="([^"]+)"|^\s+(?:link|src):\s*(\S+)/gm)]
  for (const match of links) {
    check(file, match[1] || match[2] || match[3])
    linkCount++
  }
}

const visit = (value) => {
  if (!value || typeof value !== 'object') return
  if (typeof value.link === 'string') check(join(docs, 'index.md'), value.link)
  for (const item of Object.values(value)) visit(item)
}
visit(config.locales)
check(join(docs, 'index.md'), config.themeConfig.logo.src)
check(join(docs, 'index.md'), config.head[0][1].href)

const english = readdirSync(join(docs, 'guide')).filter((file) => file.endsWith('.md')).sort()
const japanese = readdirSync(join(docs, 'ja/guide')).filter((file) => file.endsWith('.md')).sort()
if (JSON.stringify(english) !== JSON.stringify(japanese)) failures.push('English and Japanese guide filenames differ')
if (config.base !== '/SECCA/') failures.push('Expected /SECCA/ base')
for (const [locale, pages] of [['en', english], ['ja', japanese]]) {
  for (const page of pages) {
    const source = join(docs, locale === 'ja' ? 'ja/guide' : 'guide', page)
    if ((readFileSync(source, 'utf8').match(/^# /gm) || []).length !== 1) failures.push(`${relative(root, source)}: expected one h1`)
  }
}
if (failures.length) {
  process.stderr.write(`${failures.join('\n')}\n`)
  process.exitCode = 1
} else process.stdout.write(`Checked ${markdownFiles.length} Markdown files, ${linkCount} links, navigation, assets, /SECCA/ base, and ${english.length} matching guide routes per locale.\n`)

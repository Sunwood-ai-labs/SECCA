import { defineConfig } from 'vitepress'

const repository = 'https://github.com/Sunwood-ai-labs/SECCA'
const pages = ['getting-started', 'run', 'protocol', 'scoring', 'isolation', 'results', 'troubleshooting', 'provenance']
const labels = {
  en: ['Get started', 'Run a trial', 'Fixed protocol', 'Score a result', 'Isolation', 'Results', 'Troubleshooting', 'Provenance'],
  ja: ['はじめに', '試行を実行する', '固定プロトコル', '再現度を採点する', '隔離', '実験結果', 'トラブル対応', '来歴と権利']
}
const sidebar = (locale) => [{
  text: locale === 'ja' ? 'ガイド' : 'Guide',
  items: pages.map((page, index) => ({ text: labels[locale][index], link: `${locale === 'ja' ? '/ja' : ''}/guide/${page}` }))
}]

export default defineConfig({
  title: 'SECCA',
  description: 'Solid-model Evaluation of CAD Construction Agents. A fixed CAD task with inspectable artifacts and evidence.',
  base: '/SECCA/',
  cleanUrls: true,
  appearance: false,
  lastUpdated: false,
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/SECCA/secca-mark.svg' }],
    ['meta', { name: 'theme-color', content: '#087f8c' }],
    ['meta', { property: 'og:type', content: 'website' }]
  ],
  locales: {
    root: { label: 'English', lang: 'en', themeConfig: {
      nav: [{ text: 'Guide', link: '/guide/getting-started' }, { text: 'Results', link: '/guide/results' }, { text: 'GitHub', link: repository }],
      sidebar: sidebar('en'),
      footer: { message: 'Code and original artwork: MIT. Benchmark image rights are separately documented.', copyright: 'SECCA · Sunwood AI Labs' }
    } },
    ja: { label: '日本語', lang: 'ja', title: 'SECCA · 雪華', description: '固定入力と保存CAD、根拠を確認できるCAD構築エージェント評価。', themeConfig: {
      nav: [{ text: 'ガイド', link: '/ja/guide/getting-started' }, { text: '実験結果', link: '/ja/guide/results' }, { text: 'GitHub', link: repository }],
      sidebar: sidebar('ja'),
      outlineTitle: 'このページ',
      docFooter: { prev: '前のページ', next: '次のページ' },
      returnToTopLabel: '先頭に戻る',
      sidebarMenuLabel: 'メニュー',
      darkModeSwitchLabel: '表示テーマ',
      footer: { message: 'コードとオリジナルロゴはMIT。参照画像の権利は別途記載しています。', copyright: 'SECCA · Sunwood AI Labs' }
    } }
  },
  themeConfig: {
    logo: { src: '/secca-mark.svg', alt: 'SECCA snow crystal and CAD cube' },
    siteTitle: 'SECCA',
    socialLinks: [{ icon: 'github', link: repository }],
    search: { provider: 'local' },
    outline: [2, 3],
    editLink: { pattern: `${repository}/edit/main/docs/:path`, text: 'Edit this page on GitHub' }
  },
  sitemap: { hostname: 'https://sunwood-ai-labs.github.io/SECCA/' }
})

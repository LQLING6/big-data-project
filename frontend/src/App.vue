<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { request, sessionToken } from './api'
import CompetitionCard from './components/CompetitionCard.vue'
import ProfileView from './views/ProfileView.vue'
import type { Competition, Notification, Profile, Recommendation, Source, Subscription, User } from './types'

const view = ref('discover')
const user = ref<User | null>(null)
const competitions = ref<Competition[]>([])
const subscriptions = ref<Subscription[]>([])
const notifications = ref<Notification[]>([])
const recommendations = ref<Recommendation[]>([])
const profile = ref<Profile | null>(null)
const sources = ref<Source[]>([])
const status = ref<Record<string, string | number>>({})
const demoMode = ref(false)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const toast = ref('')
const query = ref('')
const category = ref('全部')
const selected = ref<Competition | null>(null)
const loginOpen = ref(false)
const loginName = ref('')
const loginPassword = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined

const navItems = computed(() => [
  { key: 'discover', icon: '◈', title: '赛事广场' },
  { key: 'recommend', icon: '✦', title: '为你推荐' },
  { key: 'saved', icon: '▧', title: '我的订阅' },
  { key: 'notifications', icon: '◷', title: '通知中心' },
  { key: 'profile', icon: '◉', title: '我的画像' },
  ...(user.value?.role === 'admin' ? [{ key: 'admin', icon: '▤', title: '来源与运行' }] : []),
])
const categories = computed(() => ['全部', ...new Set(competitions.value.map(item => item.category))])
const visible = computed(() => competitions.value.filter(item =>
  (category.value === '全部' || item.category === category.value)
  && `${item.title}${item.summary}${item.tags.join('')}`.toLowerCase().includes(query.value.toLowerCase()),
))
const unread = computed(() => notifications.value.filter(item => !item.read).length)
const pageTitle = computed(() => navItems.value.find(item => item.key === view.value)?.title ?? '赛事广场')
const isSubscribed = (id: number) => subscriptions.value.some(item => item.competition.id === id)

function showToast(message: string) {
  clearTimeout(toastTimer)
  toast.value = message
  toastTimer = setTimeout(() => { toast.value = '' }, 4500)
}
async function perform(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try { await action() } catch (problem) { error.value = problem instanceof Error ? problem.message : '操作失败，请稍后重试' }
  finally { busy.value = false }
}
async function refreshPrivate() {
  if (!user.value) return
  const [p, subs, notes, recs] = await Promise.all([
    request<Profile>('/me/profile'), request<Subscription[]>('/me/subscriptions'),
    request<Notification[]>('/me/notifications'), request<{ items: Recommendation[] }>('/me/recommendations'),
  ])
  profile.value = p; subscriptions.value = subs; notifications.value = notes; recommendations.value = recs.items
  if (user.value.role === 'admin') {
    ;[sources.value, status.value] = await Promise.all([request<Source[]>('/admin/sources'), request<Record<string, string | number>>('/admin/status')])
  }
}
async function refreshPublic() { competitions.value = await request<Competition[]>('/competitions') }
async function signIn(username: string, password: string) {
  const result = await request<{ access_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
  sessionToken.set(result.access_token); user.value = result.user
  if (view.value === 'admin' && user.value.role !== 'admin') view.value = 'discover'
  await refreshPrivate()
  loginOpen.value = false
  loginPassword.value = ''
  showToast(`已进入${user.value.role === 'admin' ? '管理员' : '学生'}账号`)
}
function demoLogin(role: 'student' | 'admin') {
  perform(() => signIn(role, role === 'student' ? 'CampusComp-demo-2026!' : 'CampusComp-admin-2026!'))
}
async function logout() {
  await perform(async () => {
    try { await request('/auth/logout', { method: 'POST' }) }
    finally {
      sessionToken.clear(); user.value = null; profile.value = null; subscriptions.value = []
      notifications.value = []; recommendations.value = []; sources.value = []; status.value = {}; view.value = 'discover'
    }
  })
}
function subscribe(item: Competition) {
  if (!user.value) { loginOpen.value = true; return }
  perform(async () => {
    const result = await request<{ reminder_scheduled: boolean }>('/me/subscriptions', { method: 'POST', body: JSON.stringify({ competition_id: item.id, lead_hours: 24 }) })
    await refreshPrivate()
    showToast(result.reminder_scheduled ? '已订阅，将在截止前24小时生成站内提醒' : '订阅已保存；暂无可安排的未来精确提醒')
  })
}
function unsubscribe(id: number) {
  perform(async () => { await request(`/me/subscriptions/${id}`, { method: 'DELETE' }); await refreshPrivate(); showToast('已取消订阅和未发送的提醒') })
}
function saveProfile(value: Omit<Profile, 'version'>) {
  perform(async () => { await request('/me/profile', { method: 'PUT', body: JSON.stringify(value) }); await refreshPrivate(); view.value = 'recommend'; showToast('画像已保存，推荐已更新') })
}
function readNote(id: number) {
  perform(async () => { await request(`/me/notifications/${id}/read`, { method: 'POST' }); await refreshPrivate() })
}
function adminAction(path: string) {
  perform(async () => { const result = await request<Record<string, unknown>>(`/admin/${path}`, { method: 'POST' }); await refreshPublic(); await refreshPrivate(); showToast(`处理完成：${JSON.stringify(result)}`) })
}
function precisionLabel(value: string): string {
  return ({ datetime: '精确时间', date: '仅日期，不推测具体时刻', unknown: '未知，不生成精确提醒' } as Record<string, string>)[value] ?? '未知'
}
onMounted(async () => {
  try {
    const health = await request<{ demo_mode: boolean }>('/health')
    demoMode.value = health.demo_mode
    await refreshPublic()
    if (sessionToken.get()) {
      try { user.value = await request<User>('/me'); await refreshPrivate() }
      catch { sessionToken.clear(); user.value = null; error.value = '登录已失效，请重新登录' }
    }
  } catch (problem) { error.value = `未能连接服务。请先启动后端。${problem instanceof Error ? problem.message : ''}` }
  finally { loading.value = false }
})
</script>

<template>
  <div class="app-layout">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="view = 'discover'"><img src="/favicon.svg" alt="" /><div><strong>赛知<span> AI</span></strong><small>CAMPUSCOMP</small></div></a>
      <div class="workspace-label">你的校园竞赛助手</div>
      <nav aria-label="主导航"><button v-for="item in navItems" :key="item.key" :class="['nav-item', { active: view === item.key }]" @click="view = item.key"><span class="nav-icon">{{ item.icon }}</span>{{ item.title }}<b v-if="item.key === 'notifications' && unread">{{ unread }}</b></button></nav>
      <div class="sidebar-note"><span class="tiny-star">✦</span><strong>机会，与你有关。</strong><p>从了解一场比赛，<br />到认真迈出下一步。</p><button @click="view = 'profile'">完善我的画像 <span>↗</span></button></div>
      <div class="sidebar-bottom"><span class="status-dot"></span> 本地基础框架 <span>v0.1</span></div>
    </aside>

    <main class="main-area">
      <header class="topbar"><div class="breadcrumb">工作台 <span>/</span> <strong>{{ pageTitle }}</strong></div><div class="account-actions"><template v-if="user"><span class="avatar">{{ user.role === 'admin' ? '管' : '学' }}</span><span>{{ user.username }}</span><button class="text-button" :disabled="busy" @click="logout">退出</button></template><template v-else><span class="guest-hint">先浏览，再找到适合你的方向</span><button class="button button-outline" @click="loginOpen = true">登录</button></template></div></header>
      <div class="page-content">
        <div v-if="demoMode" class="demo-banner"><span>演示模式</span> 全部赛事为合成数据，用于团队开发与验收，不提供真实报名。<div class="demo-links"><button :disabled="busy" @click="demoLogin('student')">学生体验</button><button :disabled="busy" @click="demoLogin('admin')">管理员体验</button></div></div>
        <div v-if="error" class="error-banner" role="alert">{{ error }}<button aria-label="关闭错误提示" @click="error = ''">×</button></div>
        <div v-if="loading" class="empty-panel">正在准备赛事信息…</div>

        <template v-else-if="view === 'discover'">
          <section class="hero"><div class="hero-copy"><span class="eyebrow">MAKE YOUR NEXT MOVE</span><h1>下一场比赛，<br />找到与你有关的机会。</h1><p>看清报名要求，了解匹配理由，<br class="mobile-only" />让重要的截止时间有迹可循。</p><button class="button button-primary" @click="view = user ? 'recommend' : 'profile'">探索我的推荐 <span>↗</span></button></div><div class="hero-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="art-spark">✦</div><div class="art-card art-card-one"><span>YOUR NEXT</span><strong>possibility.</strong><i>↗</i></div><div class="art-card art-card-two"><span>⌁</span> 为兴趣找到方向</div><div class="art-dot"></div></div></section>
          <section class="stats-row" aria-label="概览"><div><span>可浏览赛事</span><strong>{{ competitions.length }}<small>场</small></strong><p>已发布的演示赛事</p></div><div><span>我的订阅</span><strong>{{ subscriptions.length }}<small>场</small></strong><p>主动关注，不错过更新</p></div><div><span>未读通知</span><strong>{{ unread }}<small>条</small></strong><p>站内记录，可追踪处理</p></div><div class="stats-tip"><span class="tip-icon">⌁</span><p>先看条件，再看热度。<br /><strong>适合你，才值得投入。</strong></p></div></section>
          <div class="section-heading"><div><span class="eyebrow">EXPLORE COMPETITIONS</span><h2>值得了解的赛事</h2></div><label class="search-box"><span>⌕</span><input v-model="query" aria-label="搜索赛事" placeholder="搜索赛事、方向或关键词" /><kbd>⌕</kbd></label></div>
          <div class="filter-row"><button v-for="item in categories" :key="item" :class="{ selected: category === item }" @click="category = item">{{ item }}</button><span>{{ visible.length }} 场赛事</span></div>
          <div class="card-grid"><CompetitionCard v-for="item in visible" :key="item.id" :competition="item" :subscribed="isSubscribed(item.id)" @detail="selected = $event" @subscribe="subscribe" /></div><div v-if="!visible.length" class="empty-panel">没有符合当前筛选的赛事，试试其他关键词。</div>
        </template>

        <template v-else-if="!user && view !== 'admin'"><section class="empty-panel auth-empty"><span>✦</span><h2>从一份简单画像开始</h2><p>登录后保存技能与兴趣，查看推荐、订阅和站内通知。</p><button v-if="demoMode" class="button button-primary" :disabled="busy" @click="demoLogin('student')">使用学生演示账号</button><button v-else class="button button-primary" @click="loginOpen = true">登录账号</button></section></template>

        <template v-else-if="view === 'recommend'"><div class="section-heading"><div><span class="eyebrow">CURATED FOR YOU</span><h1>为你推荐</h1><p>当前使用可解释规则排序。AI接口预留，尚未调用外部模型。</p></div><button class="button button-outline" @click="view = 'profile'">调整画像 ↗</button></div><div class="info-banner">匹配分用于排序参考；资格信息缺失会单独提示，不代表官方审核通过。</div><div class="card-grid"><div v-for="item in recommendations" :key="item.competition.id" class="recommendation-wrap"><CompetitionCard :competition="item.competition" :score="item.score" :reason="item.reasons.map(reason => reason.text).join('；')" :subscribed="isSubscribed(item.competition.id)" @detail="selected = $event" @subscribe="subscribe" /><div class="recommendation-notes"><strong>{{ item.qualification }}</strong><span>{{ item.warnings[0] }}</span></div></div></div><div v-if="!recommendations.length" class="empty-panel">暂无推荐。请检查画像，或等待新的已核验赛事。</div></template>

        <template v-else-if="view === 'saved'"><div class="section-heading"><div><span class="eyebrow">YOUR WATCHLIST</span><h1>我的订阅</h1><p>精确截止时间可生成提前提醒；日期不明确时保留订阅，等待更新。</p></div></div><div v-if="!subscriptions.length" class="empty-panel">还没有订阅赛事。去赛事广场关注一个方向吧。</div><div class="subscription-list"><article v-for="item in subscriptions" :key="item.id" class="panel subscription-row"><div><span class="eyebrow">{{ item.competition.category }}</span><h3><button class="title-button" @click="selected = item.competition">{{ item.competition.title }}</button></h3><p>{{ item.competition.deadline_precision === 'datetime' ? `截止前${item.lead_hours}小时 · 站内提醒` : '截止时间不明确 · 暂无精确提醒' }}</p></div><button class="button button-outline" :disabled="busy" @click="unsubscribe(item.id)">取消订阅</button></article></div></template>

        <template v-else-if="view === 'notifications'"><div class="section-heading"><div><span class="eyebrow">STAY IN THE LOOP</span><h1>通知中心</h1><p>这里的“已记录”表示站内消息已保存，不表示邮件已送达。</p></div><button class="button button-outline" :disabled="busy" @click="perform(refreshPrivate)">刷新</button></div><div v-if="!notifications.length" class="empty-panel">暂无通知。订阅确认和后续提醒会保存在这里。</div><article v-for="item in notifications" :key="item.id" :class="['panel', 'notification-row', { unread: !item.read }]"><div class="notification-symbol">{{ item.kind === 'change' ? '↻' : '◷' }}</div><div><h3>{{ item.title }} <span>{{ item.read ? '已读' : '未读' }}</span></h3><p>{{ item.body }}</p><small>站内已记录 · {{ new Date(item.created_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) }}</small></div><button v-if="!item.read" class="text-button" :disabled="busy" @click="readNote(item.id)">标为已读</button></article></template>

        <ProfileView v-else-if="view === 'profile' && profile" :key="`${user?.id}-${profile.version}`" :profile="profile" :saving="busy" @save="saveProfile" />

        <template v-else-if="view === 'admin' && user?.role === 'admin'"><div class="section-heading"><div><span class="eyebrow">SOURCE & OPERATIONS</span><h1>来源与运行</h1><p>真实网络采集默认关闭；合成数据仅从本地文件导入。</p></div></div><div class="admin-actions"><button class="button button-primary" :disabled="busy" @click="adminAction('import-fixtures')">重新导入演示通知</button><button class="button button-outline" :disabled="busy" @click="adminAction('run-cycle')">处理到期提醒</button><button v-if="demoMode" class="button button-outline" :disabled="busy" @click="adminAction('demo-trigger')">提前处理一条演示提醒</button></div><div class="panel source-panel" v-for="source in sources" :key="source.id"><span class="source-state">{{ source.network_enabled ? '网络已启用' : '网络采集关闭' }}</span><h3>{{ source.name }}</h3><p>{{ source.base_url }}</p><small>策略：{{ source.policy_status }} · 调度间隔：{{ source.interval_seconds }}秒</small></div><div class="panel system-status"><h3>运行状态</h3><dl><template v-for="(value, key) in status" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></template></dl></div><div class="info-banner">演示流程：学生账号订阅 → 管理员提前处理一条演示提醒 → 切回学生账号查看通知。</div></template>

        <footer class="page-footer"><span>赛知 CampusComp AI</span><span>来源可追溯 · 推荐有依据 · 提醒有记录</span></footer>
      </div>
    </main>

    <div v-if="selected" class="modal-backdrop" @click.self="selected = null" @keydown.esc="selected = null"><section class="modal detail-modal" role="dialog" aria-modal="true" aria-labelledby="detail-title" tabindex="-1"><button class="modal-close" aria-label="关闭赛事详情" @click="selected = null">×</button><span class="eyebrow">{{ selected.category }} · {{ selected.is_demo ? '合成演示' : '已核验赛事' }}</span><h2 id="detail-title">{{ selected.title }}</h2><p>{{ selected.summary }}</p><dl class="detail-facts"><dt>主办方</dt><dd>{{ selected.organizer }}</dd><dt>培养层次</dt><dd>{{ selected.allowed_levels.join('、') || '待确认' }}</dd><dt>专业限制</dt><dd>{{ selected.allowed_majors.join('、') || '未列出限制，请核对原文' }}</dd><dt>截止信息</dt><dd>{{ selected.deadline_at ? new Date(selected.deadline_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) + '（北京时间）' : selected.deadline_date || '未公布' }}</dd><dt>时间精度</dt><dd>{{ precisionLabel(selected.deadline_precision) }}</dd></dl><h3>来源证据</h3><div v-for="(evidence, key) in selected.evidence" :key="key" class="evidence-block"><span>{{ key }} · {{ evidence.origin }}</span><blockquote>{{ evidence.quote }}</blockquote></div><p class="source-url">{{ selected.is_demo ? '演示占位地址（非报名入口）' : '来源地址' }}<br /><code v-if="selected.is_demo">{{ selected.source_url }}</code><a v-else :href="selected.source_url" target="_blank" rel="noopener noreferrer">查看原始通知 ↗</a></p><button class="button button-primary" :disabled="isSubscribed(selected.id) || busy" @click="subscribe(selected)">{{ isSubscribed(selected.id) ? '已订阅' : '订阅此赛事提醒' }}</button></section></div>

    <div v-if="loginOpen" class="modal-backdrop" @click.self="loginOpen = false"><section class="modal login-modal" role="dialog" aria-modal="true" aria-labelledby="login-title"><button class="modal-close" aria-label="关闭登录" @click="loginOpen = false">×</button><span class="eyebrow">WELCOME TO CAMPUSCOMP</span><h2 id="login-title">登录赛知</h2><form class="login-form" @submit.prevent="perform(() => signIn(loginName, loginPassword))"><label>用户名<input v-model="loginName" autocomplete="username" required /></label><label>密码<input v-model="loginPassword" type="password" autocomplete="current-password" required /></label><button class="button button-primary" :disabled="busy">{{ busy ? '登录中…' : '登录' }}</button></form><p v-if="demoMode" class="login-demo-hint">先体验：<button class="text-button" :disabled="busy" @click="demoLogin('student')">学生演示账号 ↗</button></p><p v-if="error" class="login-error" role="alert">{{ error }}</p></section></div>
    <div v-if="toast" class="toast" role="status">✓ {{ toast }}</div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const loggedIn = ref(false)
const loading = ref(true)
const credentials = ref({ username: 'admin', password: '' })
const error = ref('')
const tab = ref('overview')
const overview = ref({})
const users = ref([])
const events = ref([])
const eventKind = ref('parse')
const search = ref('')

function csrf() {
  const match = document.cookie.match(/(?:^|; )admin_csrf=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function api(path, method = 'GET', body) {
  const response = await fetch('/admin/api/' + path, {
    method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf() },
    ...(body === undefined ? {} : { body: JSON.stringify(body) })
  })
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.error || '操作失败')
  return payload
}

async function signIn() {
  error.value = ''
  try { await api('login', 'POST', credentials.value); loggedIn.value = true; credentials.value.password = ''; await load() }
  catch (e) { error.value = e.message }
}

async function signOut() {
  try { await api('logout', 'POST', {}) }
  catch (e) { error.value = e.message }
  finally { loggedIn.value = false; users.value = []; events.value = [] }
}

async function load() {
  error.value = ''
  try {
    if (tab.value === 'overview') overview.value = await api('overview')
    if (tab.value === 'users') users.value = (await api('users?q=' + encodeURIComponent(search.value))).items
    if (tab.value === 'events') events.value = (await api('events?kind=' + eventKind.value + '&user_id=' + encodeURIComponent(search.value))).items
  } catch (e) {
    error.value = e.message
    if (/登录/.test(e.message)) loggedIn.value = false
  }
}

function selectTab(name) { tab.value = name; search.value = ''; load() }

async function toggleUser(user) {
  const action = user.disabled ? '启用' : '停用'
  if (!window.confirm(`确认${action}用户 #${user.id}？`)) return
  try { await api(`users/${user.id}/status`, 'POST', { disabled: !user.disabled }); await load() }
  catch (e) { error.value = e.message }
}

function time(value) { return value ? new Date(value * 1000).toLocaleString('zh-CN', { hour12: false }) : '—' }

onMounted(async () => {
  try { await api('session'); loggedIn.value = true; await load() }
  catch (e) { if (e.message?.includes('登录')) loggedIn.value = false; else error.value = e.message }
  finally { loading.value = false }
})
</script>

<template>
  <main v-if="loading" class="center">正在加载…</main>
  <main v-else-if="!loggedIn" class="login-wrap">
    <form class="login-card" @submit.prevent="signIn">
      <div class="brand">保存助手 <span>管理端</span></div>
      <h1>欢迎回来</h1><p class="muted">登录后查看用户和使用情况</p>
      <label>管理员账号<input v-model.trim="credentials.username" autocomplete="username" required></label>
      <label>密码<input v-model="credentials.password" type="password" autocomplete="current-password" required></label>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="primary" type="submit">登 录</button>
    </form>
  </main>
  <main v-else class="shell">
    <aside class="sidebar">
      <div class="brand">保存助手 <span>管理端</span></div>
      <nav><button :class="{ active: tab === 'overview' }" @click="selectTab('overview')">总览</button><button :class="{ active: tab === 'users' }" @click="selectTab('users')">用户管理</button><button :class="{ active: tab === 'events' }" @click="selectTab('events')">使用记录</button></nav>
      <button class="logout" @click="signOut">退出登录</button>
    </aside>
    <section class="workspace">
      <header><div><small>运营工作台</small><h1>{{ { overview: '数据总览', users: '用户管理', events: '使用记录' }[tab] }}</h1></div><button class="outline" @click="load">刷新数据</button></header>
      <p v-if="error" class="error panel">{{ error }}</p>
      <template v-if="tab === 'overview'">
        <div class="metrics"><div v-for="item in [['累计用户', overview.users], ['今日登录用户', overview.today_logins], ['今日解析请求', overview.today_parses], ['今日解析成功', overview.today_parse_success], ['今日保存成功', overview.today_saves]]" :key="item[0]" class="metric"><span>{{ item[0] }}</span><strong>{{ item[1] ?? '—' }}</strong></div></div>
        <div class="panel note"><h2>数据说明</h2><p>今日统计采用北京时间。保存成功数来自小程序相册保存接口回报；媒体文件没有存进数据库。解析记录保留 30 天。</p></div>
      </template>
      <template v-if="tab === 'users'">
        <div class="toolbar"><input v-model.trim="search" placeholder="按用户 ID 查询，留空显示最近 100 位" @keyup.enter="load"><button class="primary" @click="load">查询</button></div>
        <div class="panel table-wrap"><table><thead><tr><th>用户 ID</th><th>创建时间</th><th>最近登录</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="user in users" :key="user.id"><td>#{{ user.id }}</td><td>{{ time(user.created_at) }}</td><td>{{ time(user.last_login_at) }}</td><td><span :class="user.disabled ? 'tag off' : 'tag'">{{ user.disabled ? '已停用' : '正常' }}</span></td><td><button class="link" @click="toggleUser(user)">{{ user.disabled ? '启用' : '停用' }}</button></td></tr><tr v-if="!users.length"><td colspan="5" class="empty">暂无用户</td></tr></tbody></table></div>
      </template>
      <template v-if="tab === 'events'">
        <div class="toolbar"><select v-model="eventKind" @change="load"><option value="parse">解析记录</option><option value="save">保存记录</option></select><input v-model.trim="search" placeholder="按用户 ID 筛选，留空显示最近 100 条" @keyup.enter="load"><button class="primary" @click="load">查询</button></div>
        <div class="panel table-wrap"><table><thead><tr><th>时间</th><th>用户 ID</th><th>{{ eventKind === 'parse' ? '作品 ID' : '记录 ID' }}</th><th>结果</th><th>详情</th></tr></thead><tbody><tr v-for="event in events" :key="event.id"><td>{{ time(event.created_at) }}</td><td>#{{ event.user_id }}</td><td>{{ eventKind === 'parse' ? event.aweme_id || '—' : '#' + event.history_id }}</td><td><span :class="event.success ? 'tag' : 'tag off'">{{ event.success ? '成功' : '失败' }}</span></td><td>{{ eventKind === 'save' ? (event.media_kind === 'video' ? '视频' : '图片') + ' · 第' + (event.item_index + 1) + '项' : '' }} {{ event.message }}</td></tr><tr v-if="!events.length"><td colspan="5" class="empty">暂无记录</td></tr></tbody></table></div>
      </template>
    </section>
  </main>
</template>

import { API_BASE_URL, DEV_LOGIN } from '../config'

let token = uni.getStorageSync('user_token') || ''
let loginPromise = null

function consent() {
  return new Promise(resolve => {
    uni.showModal({ title: '隐私说明', content: '登录将使用微信用户标识；解析时分享链接会发往服务端。解析和保存记录保留 30 天，可在“我的”页面注销账号。', confirmText: '同意并继续', cancelText: '暂不使用', success: ({ confirm }) => resolve(Boolean(confirm)), fail: () => resolve(false) })
  })
}

function loginCode() {
  if (DEV_LOGIN) return Promise.resolve('dev-test')
  return new Promise((resolve, reject) => {
    uni.login({ provider: 'weixin', success: (res) => res.code ? resolve(res.code) : reject(new Error('未获得微信登录凭证')), fail: () => reject(new Error('微信登录失败，请重试')) })
  })
}

function rawRequest(path, method, data, auth) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: API_BASE_URL + path, method, data,
      header: { 'Content-Type': 'application/json', ...(auth && token ? { Authorization: 'Bearer ' + token } : {}) },
      success: (res) => res.statusCode >= 200 && res.statusCode < 300 ? resolve(res.data) : reject(Object.assign(new Error(res.data?.error || '请求失败，请稍后再试'), { status: res.statusCode })),
      fail: () => reject(new Error('网络连接失败，请检查网络后重试'))
    })
  })
}

export async function ensureLogin(force = false) {
  if (token && !force) return token
  if (loginPromise) return loginPromise
  loginPromise = (async () => {
    if (!DEV_LOGIN && !uni.getStorageSync('privacy_agreed')) {
      const agreed = await consent()
      if (!agreed) throw new Error('同意隐私说明后才能使用登录与解析功能')
      uni.setStorageSync('privacy_agreed', true)
    }
    const code = await loginCode()
    const response = await rawRequest('/api/auth/wechat', 'POST', { code }, false)
    token = response.token
    uni.setStorageSync('user_token', token)
    uni.setStorageSync('user_id', response.user.id)
    return token
  })().finally(() => { loginPromise = null })
  return loginPromise
}

export async function api(path, method = 'GET', data) {
  await ensureLogin()
  try { return await rawRequest(path, method, data, true) }
  catch (error) {
    if (error.status !== 401) throw error
    token = ''
    uni.removeStorageSync('user_token')
    await ensureLogin(true)
    return rawRequest(path, method, data, true)
  }
}

export function clearLogin() {
  token = ''
  uni.removeStorageSync('user_token')
  uni.removeStorageSync('user_id')
}

// 只在当前运行期间保留结果；历史记录打开时从服务器重新解析。
let currentResult = null
export function setResult(value) { currentResult = value }
export function getResult() { return currentResult }

export function mediaUrl(path) { return API_BASE_URL + path }

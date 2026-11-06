<script setup>
import { ref } from 'vue'
import { api, setResult } from '../../utils/api'

const text = ref('')
const busy = ref(false)

function paste() {
  uni.getClipboardData({ success: ({ data }) => { text.value = data || ''; uni.showToast({ title: '已粘贴', icon: 'none' }) }, fail: () => uni.showToast({ title: '读取剪贴板失败', icon: 'none' }) })
}

async function parse() {
  if (!text.value.trim()) return uni.showToast({ title: '请先粘贴分享链接', icon: 'none' })
  if (busy.value) return
  busy.value = true
  uni.showLoading({ title: '正在解析…', mask: true })
  try {
    const result = await api('/api/parse', 'POST', { text: text.value.trim() })
    setResult(result)
    uni.navigateTo({ url: '/pages/result/result' })
  } catch (e) { uni.showToast({ title: e.message || '解析失败', icon: 'none', duration: 2500 }) }
  finally { busy.value = false; uni.hideLoading() }
}
</script>

<template>
  <view class="page">
    <view class="hero"><view class="eyebrow">VIDEO · IMAGE · LIVE</view><view class="hero-title">保存喜欢的</view><view class="hero-title">每个瞬间</view><text class="hero-sub">粘贴抖音分享链接，解析作品中的视频、图片与实况内容。</text></view>
    <view class="card"><view class="card-heading"><text>分享链接</text><text class="hint">支持完整分享文案</text></view><textarea v-model="text" class="input" maxlength="3000" placeholder="在这里粘贴抖音分享链接或分享文案…" placeholder-class="placeholder" /><view class="actions"><button class="paste" @click="paste">粘贴内容</button><button class="submit" :disabled="busy" @click="parse">{{ busy ? '解析中…' : '开始解析  →' }}</button></view></view>
    <view class="steps"><view class="step"><text class="number">01</text><text>粘贴链接</text></view><view class="line"></view><view class="step"><text class="number">02</text><text>查看内容</text></view><view class="line"></view><view class="step"><text class="number">03</text><text>保存相册</text></view></view>
    <view class="note">仅用于保存本人创作或已获授权的内容。实况内容以图片和视频分别保存。</view>
  </view>
</template>

<style scoped>
.page{padding:34rpx 34rpx 70rpx}.hero{padding:66rpx 14rpx 66rpx}.eyebrow{font-size:21rpx;letter-spacing:5rpx;color:#219476;font-weight:700;margin-bottom:24rpx}.hero-title{display:block;white-space:pre-line;font-size:73rpx;line-height:1.15;letter-spacing:2rpx;font-weight:800;color:#193e32}.hero-sub{display:block;margin-top:26rpx;color:#6f8980;font-size:27rpx;line-height:1.8}.card{background:white;border-radius:32rpx;padding:32rpx;box-shadow:0 18rpx 55rpx #224c3212}.card-heading{display:flex;justify-content:space-between;align-items:center;font-size:30rpx;font-weight:700;margin-bottom:24rpx}.hint{font-size:22rpx;color:#9aaa9f;font-weight:400}.input{height:210rpx;width:100%;box-sizing:border-box;background:#f6f8f6;border-radius:20rpx;padding:26rpx;font-size:27rpx;line-height:1.6;color:#263f36}.placeholder{color:#a3afa9}.actions{display:flex;gap:18rpx;margin-top:26rpx}.actions button{font-size:26rpx;border-radius:18rpx;line-height:92rpx;height:92rpx}.paste{background:#e9f3ee;color:#268266;width:210rpx}.submit{background:#177b5d;color:white;flex:1;font-weight:700}.submit[disabled]{opacity:.6}.steps{display:flex;align-items:center;justify-content:center;margin:58rpx 10rpx 0}.step{display:flex;flex-direction:column;align-items:center;font-size:23rpx;color:#5b7468;gap:10rpx;white-space:nowrap}.number{background:#e4f4ea;color:#268762;width:66rpx;height:66rpx;line-height:66rpx;border-radius:50%;text-align:center;font-weight:700}.line{height:2rpx;background:#d8e9dc;flex:1;margin:0 10rpx 27rpx}.note{color:#9aaa9f;font-size:23rpx;line-height:1.7;padding:40rpx 10rpx;text-align:center}
</style>

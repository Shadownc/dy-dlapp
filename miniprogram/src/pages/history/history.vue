<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { api, ensureLogin } from '../../utils/api'

const records = ref([])
const loading = ref(false)
const date = (time) => new Date(time * 1000).toLocaleDateString('zh-CN')
onShow(async () => {
  loading.value = true
  try { await ensureLogin(); records.value = (await api('/api/history')).items }
  catch (e) { records.value = []; uni.showToast({ title: e.message || '加载失败', icon: 'none' }) }
  finally { loading.value = false }
})

function open(item) { uni.navigateTo({ url: '/pages/result/result?id=' + item.id }) }
</script>

<template>
  <view class="page"><view class="heading"><text class="title">最近记录</text><text class="subtitle">保存最近 30 天的解析记录，重新打开会刷新媒体链接</text></view><view v-if="!loading && !records.length" class="empty"><text class="empty-icon">◷</text><text>还没有解析记录</text><text class="empty-sub">去解析你有权保存的作品吧</text><button @click="uni.switchTab({ url: '/pages/index/index' })">去解析</button></view><view v-for="item in records" :key="item.id" class="record" @click="open(item)"><view class="icon">{{ item.kind === 'video' ? '▶' : '▧' }}</view><view class="details"><text class="name">{{ item.title }}</text><text class="meta">{{ item.kind === 'video' ? '视频' : '图片图集' }} · {{ item.item_count }} 项 · {{ date(item.created_at) }}</text></view><text class="arrow">›</text></view></view>
</template>

<style scoped>
.page{padding:50rpx 30rpx}.heading{padding:0 6rpx 36rpx}.title{display:block;font-size:47rpx;font-weight:800;color:#183a2e}.subtitle{display:block;color:#8b9c92;font-size:24rpx;margin-top:12rpx}.record{background:#fff;border-radius:22rpx;padding:24rpx;margin-bottom:17rpx;display:flex;align-items:center;gap:22rpx;box-shadow:0 8rpx 26rpx #2d49360a}.icon{width:87rpx;height:87rpx;line-height:87rpx;text-align:center;background:#e4f3e8;border-radius:20rpx;color:#198668;font-size:31rpx}.details{flex:1;min-width:0}.name{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:27rpx;font-weight:600}.meta{display:block;color:#96a79c;font-size:21rpx;margin-top:12rpx}.arrow{color:#9aac9f;font-size:40rpx}.empty{margin-top:170rpx;display:flex;align-items:center;flex-direction:column;color:#536b5b;font-size:30rpx}.empty-icon{font-size:90rpx;color:#84ae96;margin-bottom:20rpx}.empty-sub{font-size:24rpx;color:#a1b0a4;margin:16rpx 0 30rpx}.empty button{font-size:25rpx;background:#158465;color:#fff;border-radius:15rpx;padding:0 36rpx}
</style>

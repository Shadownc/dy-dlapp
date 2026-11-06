<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { api, clearLogin, ensureLogin, setResult } from '../../utils/api'

const user = ref(null)
onShow(async () => {
  try { await ensureLogin(); user.value = (await api('/api/me')).user }
  catch (e) { user.value = null; uni.showToast({ title: e.message || '无法获取账号信息', icon: 'none' }) }
})

function erase() {
  uni.showModal({ title: '注销账号', content: '将删除账号、解析记录与保存记录。此操作不可恢复，确认继续吗？', confirmText: '确认注销', confirmColor: '#ba4a4a', success: async ({ confirm }) => {
    if (!confirm) return
    try { await api('/api/me', 'DELETE'); clearLogin(); setResult(null); user.value = null; uni.showToast({ title: '已注销' }); uni.switchTab({ url: '/pages/index/index' }) }
    catch (e) { uni.showToast({ title: e.message || '注销失败', icon: 'none' }) }
  } })
}
</script>

<template>
  <view class="page"><text class="heading">我的</text><view class="profile"><view class="avatar">我</view><view><text class="name">微信用户</text><text class="id">用户编号 {{ user?.id || '登录中…' }}</text></view></view><view class="group"><view class="row" @click="uni.switchTab({ url: '/pages/history/history' })"><text>最近解析记录</text><text class="arrow">›</text></view><view class="row" @click="uni.openSetting({})"><text>相册权限设置</text><text class="arrow">›</text></view><view class="row" @click="uni.navigateTo({ url: '/pages/privacy/privacy' })"><text>隐私说明</text><text class="arrow">›</text></view></view><view class="group description"><text class="subtitle">使用说明</text><text>本工具用于保存本人创作或已获授权的内容。使用记录保留 30 天。实况内容可分别保存静态图片和视频文件。</text></view><button class="delete" @click="erase">注销账号并删除个人记录</button></view>
</template>

<style scoped>
.page{padding:50rpx 30rpx}.heading{font-size:47rpx;font-weight:800;color:#183a2e}.profile{background:#e5f4ea;padding:43rpx 31rpx;border-radius:24rpx;margin:36rpx 0;display:flex;align-items:center;gap:26rpx}.avatar{background:#168564;color:#fff;border-radius:50%;height:90rpx;width:90rpx;line-height:90rpx;text-align:center;font-size:35rpx}.name,.id{display:block}.name{font-size:29rpx;font-weight:700}.id{font-size:24rpx;color:#759281;margin-top:9rpx}.group{background:#fff;border-radius:22rpx;margin-bottom:24rpx;padding:0 27rpx}.row{display:flex;justify-content:space-between;align-items:center;min-height:105rpx;border-bottom:1rpx solid #f1f3f0;font-size:27rpx}.row:last-child{border-bottom:0}.arrow{font-size:40rpx;color:#9aada0}.description{padding:26rpx 27rpx;color:#7d9185;font-size:24rpx;line-height:1.8}.subtitle{display:block;font-size:25rpx;color:#234f3c;font-weight:700;margin-bottom:9rpx}.delete{color:#ba5b55;background:#fff;font-size:26rpx;margin-top:48rpx;border-radius:15rpx}
</style>

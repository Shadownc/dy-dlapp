<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api, getResult, mediaUrl, setResult } from '../../utils/api'
import { saveMedia } from '../../utils/save'

const result = ref(null)
const busy = ref(false)
const selected = ref([])
const media = (path) => path ? mediaUrl(path) : ''
const isVideo = computed(() => result.value?.type === 'video')

onLoad(async (query) => {
  const cached = getResult()
  if (cached && !query.id) { result.value = cached; return }
  if (!query.id || !/^\d+$/.test(query.id)) return
  uni.showLoading({ title: '获取最新内容…', mask: true })
  try { result.value = await api(`/api/history/${query.id}/refresh`, 'POST'); selected.value = []; setResult(result.value) }
  catch (e) { uni.showModal({ title: '无法打开记录', content: e.message || '请稍后重试', showCancel: false, success: () => uni.navigateBack() }) }
  finally { uni.hideLoading() }
})

async function refreshMedia() {
  if (!result.value || busy.value) return
  busy.value = true
  uni.showLoading({ title: '更新媒体链接…', mask: true })
  try { result.value = await api(`/api/history/${result.value.id}/refresh`, 'POST'); selected.value = []; setResult(result.value); uni.showToast({ title: '链接已更新', icon: 'none' }) }
  catch (e) { uni.showModal({ title: '更新失败', content: e.message || '请稍后重试', showCancel: false }) }
  finally { busy.value = false; uni.hideLoading() }
}

function toggle(index) {
  selected.value = selected.value.includes(index) ? selected.value.filter(x => x !== index) : [...selected.value, index]
}

function preview(index) {
  if (!result.value || isVideo.value) return
  uni.previewImage({ current: media(result.value.content[index].url), urls: result.value.content.map(item => media(item.url)) })
}

async function save(index, kind) {
  if (busy.value || !result.value) return
  const item = result.value.content[index]
  const path = kind === 'image' ? item.url : (isVideo.value ? item.url : item.video)
  if (!path) return
  busy.value = true
  try { await saveMedia(result.value, index, kind, path); uni.showToast({ title: '已保存到相册', icon: 'success' }) }
  catch (e) { uni.showModal({ title: '保存失败', content: e.message || '请稍后重试', showCancel: false }) }
  finally { busy.value = false }
}

async function saveSelected() {
  if (busy.value || !result.value) return
  const indexes = selected.value.length ? selected.value : result.value.content.map((_, index) => index)
  busy.value = true
  let saved = 0
  try {
    for (const index of indexes) {
      try { await saveMedia(result.value, index, 'image', result.value.content[index].url); saved++ }
      catch (e) { uni.showModal({ title: '部分图片保存失败', content: `已保存 ${saved} 张。${e.message || ''}`, showCancel: false }); return }
    }
    uni.showToast({ title: `已保存 ${saved} 张图片`, icon: 'none' })
  } finally { busy.value = false }
}

</script>

<template>
  <view v-if="result" class="page">
    <view class="header"><view class="tag">{{ isVideo ? '视频作品' : result.content.some(item => item.video) ? '图片 · 含实况' : '图片作品' }}</view><text class="title">{{ result.title }}</text><text class="meta">作品 ID {{ result.aweme_id }} · {{ result.content.length }} 个内容</text><view class="refresh" @click="refreshMedia">链接失效？点此刷新</view></view>
    <template v-if="isVideo"><view class="video-card"><video class="player" :src="media(result.content[0].url)" :poster="media(result.content[0].thumbnail)" controls object-fit="contain" /><view class="card-body"><text>高清视频</text><button class="save" :disabled="busy" @click="save(0, 'video')">保存视频到相册</button></view></view></template>
    <template v-else><view class="tip">选择图片后可以批量保存。带「实况」标记的内容可以分别保存图片和对应视频。</view><view v-for="(item, index) in result.content" :key="index" class="item"><view class="picture"><image class="photo" :src="media(item.url)" mode="aspectFill" @click="preview(index)" /><view v-if="item.video" class="live-badge">▶ 实况</view><view class="select" :class="{ checked: selected.includes(index) }" @click="toggle(index)">{{ selected.includes(index) ? '✓' : '+' }}</view></view><view class="item-footer"><text>第 {{ index + 1 }} 张 {{ item.video ? '· 实况' : '' }}</text><view class="buttons"><button :disabled="busy" @click="save(index, 'image')">存图片</button><button v-if="item.video" :disabled="busy" class="soft" @click="save(index, 'video')">存实况视频</button></view></view><video v-if="item.video" class="live-player" :src="media(item.video)" :poster="media(item.thumbnail || item.url)" controls object-fit="contain" /></view><view class="bottom-space"></view><view class="batch"><button :disabled="busy" @click="saveSelected">保存{{ selected.length ? `选中的 ${selected.length} 张` : '全部图片' }}</button></view></template>
  </view>
</template>

<style scoped>
.page{padding:30rpx 30rpx 60rpx}.header{padding:20rpx 8rpx 40rpx}.tag{display:inline-block;background:#e2f4e8;color:#168061;font-size:21rpx;border-radius:40rpx;padding:10rpx 20rpx;font-weight:700}.title{display:block;margin:20rpx 0 13rpx;font-size:37rpx;font-weight:750;line-height:1.45;color:#193e32}.meta{font-size:22rpx;color:#9ba99e}.refresh{display:inline-block;margin-top:18rpx;color:#198466;font-size:23rpx;text-decoration:underline}.video-card,.item{background:white;border-radius:25rpx;overflow:hidden;margin-bottom:22rpx;box-shadow:0 8rpx 28rpx #2647360c}.player{width:100%;height:690rpx;background:#161e1a}.card-body{padding:26rpx;display:flex;align-items:center;justify-content:space-between;font-size:26rpx}.save,.batch button{background:#168062;color:white;font-size:26rpx;padding:0 26rpx;border-radius:14rpx;height:78rpx;line-height:78rpx}.tip{font-size:24rpx;color:#6f8a7d;line-height:1.6;padding:0 8rpx 25rpx}.picture{height:630rpx;position:relative;background:#edf1ed}.photo{width:100%;height:100%}.live-badge{position:absolute;left:20rpx;top:20rpx;background:#16372ed9;color:white;border-radius:25rpx;padding:9rpx 17rpx;font-size:22rpx}.select{position:absolute;right:20rpx;top:20rpx;width:62rpx;height:62rpx;line-height:60rpx;text-align:center;border-radius:50%;background:#fff;color:#299a73;font-size:36rpx}.select.checked{background:#1b926c;color:#fff}.item-footer{display:flex;align-items:center;justify-content:space-between;padding:20rpx;gap:8rpx;font-size:25rpx;color:#526c5b}.buttons{display:flex;gap:8rpx}.buttons button{background:#198262;color:white;font-size:22rpx;padding:0 18rpx;border-radius:12rpx;height:65rpx;line-height:65rpx}.buttons button.soft{background:#e7f3e9;color:#167356}.live-player{width:100%;height:410rpx;background:#16241d}.bottom-space{height:115rpx}.batch{position:fixed;bottom:0;left:0;right:0;background:#fffe;padding:18rpx 30rpx calc(20rpx + env(safe-area-inset-bottom));box-shadow:0 -5rpx 20rpx #27443612}.batch button{width:100%}
</style>

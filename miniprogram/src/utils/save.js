import { api, mediaUrl } from './api'

function download(url) {
  return new Promise((resolve, reject) => {
    uni.downloadFile({
      url: mediaUrl(url),
      success: (res) => res.statusCode === 200 ? resolve(res.tempFilePath) : reject(new Error('媒体链接已失效，请点击结果页的“链接失效？点此刷新”')),
      fail: () => reject(new Error('下载失败，请检查网络连接'))
    })
  })
}

function saveToAlbum(path, kind) {
  return new Promise((resolve, reject) => {
    const options = { filePath: path, success: resolve, fail: reject }
    if (kind === 'video') uni.saveVideoToPhotosAlbum(options)
    else uni.saveImageToPhotosAlbum(options)
  })
}

export async function saveMedia(result, index, kind, path) {
  uni.showLoading({ title: '准备下载…', mask: true })
  try {
    const localPath = await download(path)
    uni.showLoading({ title: '保存到相册…', mask: true })
    await saveToAlbum(localPath, kind)
    await api('/api/saves', 'POST', { history_id: result.id, item_index: index, media_kind: kind, success: true }).catch(() => {})
    return true
  } catch (error) {
    const detail = String(error?.errMsg || error?.message || '')
    await api('/api/saves', 'POST', { history_id: result.id, item_index: index, media_kind: kind, success: false, message: detail }).catch(() => {})
    if (/auth deny|authorize|permission|scope\.writePhotosAlbum/i.test(detail)) throw new Error('相册权限未开启，请到小程序设置中允许保存到相册')
    throw error instanceof Error && error.message && !error.errMsg ? error : new Error('保存失败，请稍后再试')
  } finally { uni.hideLoading() }
}

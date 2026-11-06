<template>
  <view class="page"><view class="card"><text class="heading">隐私说明</text><text class="intro">使用保存助手前，请了解以下信息处理方式。正式发布前，运营者还需要在微信小程序后台配置与实际服务一致的隐私保护指引。</text></view><view class="card"><text class="title">登录与用户身份</text><text>使用微信登录获得当前小程序中的用户标识，生成内部用户编号，以提供解析记录和账号功能。不要求手机号、昵称或头像。</text></view><view class="card"><text class="title">解析与保存记录</text><text>将你提交的抖音分享链接发送至服务端及运营者配置的解析接口，记录解析结果、时间、作品 ID 和保存操作的结果，用于最近记录、故障排查和使用统计。媒体链接短时有效，需重新解析时会使用保存的原始分享链接。</text></view><view class="card"><text class="title">相册权限与保存期限</text><text>只有点击保存时，才调用设备相册保存能力。解析和保存操作记录最多保留 30 天；用户标识与账号保留至账号注销。你可以在“我的”页面注销账号并删除对应记录。</text></view></view>
</template>

<style scoped>
.page{padding:30rpx 28rpx 80rpx}.card{background:white;border-radius:22rpx;padding:31rpx;margin-bottom:18rpx;color:#5c7666;font-size:25rpx;line-height:1.85;box-shadow:0 7rpx 26rpx #1939250b}.heading{display:block;font-size:43rpx;font-weight:800;color:#1a4230;margin-bottom:15rpx}.intro{color:#8ba091}.title{display:block;color:#1a5136;font-size:29rpx;font-weight:700;margin-bottom:10rpx}
</style>

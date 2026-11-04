<script setup lang="ts">
import { computed } from 'vue'
import type { AvatarType } from '@/types/assistant'

/** 助理头像：字符头像或上传图片，尺寸沿用列表 36 / 详情 52 / 小尺寸 28 */
const props = withDefaults(
  defineProps<{
    type?: AvatarType
    char?: string | null
    url?: string | null
    color?: string
    size?: number
    name?: string
  }>(),
  { type: 'char', char: null, url: null, color: '#3685F2', size: 36, name: '' }
)

const text = computed(() => props.char || props.name.slice(0, 1) || '助')
const isImage = computed(() => props.type === 'image' && !!props.url)
</script>

<template>
  <span
    class="assistant-avatar"
    :style="{ width: `${size}px`, height: `${size}px`, fontSize: `${Math.round(size * 0.42)}px`, background: isImage ? 'transparent' : color }"
  >
    <img v-if="isImage" :src="url as string" alt="" />
    <template v-else>{{ text }}</template>
  </span>
</template>

<style scoped>
.assistant-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 10px;
  color: #fff;
  font-weight: 500;
  overflow: hidden;
  user-select: none;
}

.assistant-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>

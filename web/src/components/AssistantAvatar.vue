<script setup lang="ts">
import { computed } from 'vue'
import type { AvatarType } from '@/types/assistant'
import { presetSrc, presetColor, resolvePresetKey } from '@/utils/avatar'

/** 助理头像：上传图片优先，其余按 6 款卡通人像稳定展示（助理 = 人） */
const props = withDefaults(
  defineProps<{
    type?: AvatarType
    char?: string | null
    url?: string | null
    color?: string
    size?: number
    name?: string
    /** 稳定分配头像的种子，缺省用 char / name */
    seed?: string | number | null
  }>(),
  { type: 'char', char: null, url: null, color: '#3685F2', size: 36, name: '', seed: null }
)

const isImage = computed(() => props.type === 'image' && !!props.url)
const presetKey = computed(() => resolvePresetKey(props.char, props.seed ?? props.char ?? props.name))
const src = computed(() => presetSrc(presetKey.value, props.seed ?? props.name))
const bg = computed(() => (props.char && /^P[1-6]$/.test(props.char) ? presetColor(props.char) : props.color))
</script>

<template>
  <span
    class="assistant-avatar"
    :class="{ 'is-image': isImage }"
    :style="{ width: `${size}px`, height: `${size}px`, background: isImage ? 'transparent' : bg }"
  >
    <img v-if="isImage" :src="url as string" alt="" />
    <img v-else :src="src" alt="" />
  </span>
</template>

<style scoped>
.assistant-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 50%;
  color: #fff;
  font-weight: 500;
  overflow: hidden;
  user-select: none;
}

.assistant-avatar.is-image {
  border-radius: 50%;
}

.assistant-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
</style>

/** 助理默认头像（卡通人像，6 款）。
 *
 * 与原型 prototype/js/common.js 的 __personAvatar 保持一致：
 * - 创建时选定默认头像存 `avatarChar = 'P1' ~ 'P6'`（avatarType = 'char'）；
 * - 历史字符头像（如「招」「薪」）按名称/ID 稳定映射到同一套人像，保证同一助理头像不变；
 * - 上传图片仍以 avatarType = 'image' + avatarUrl 优先。
 */

export const PRESET_AVATARS = [
  { key: 'P1', color: '#3685F2', src: '/avatars/avatar-01.png' },
  { key: 'P2', color: '#00B780', src: '/avatars/avatar-02.png' },
  { key: 'P3', color: '#FF813B', src: '/avatars/avatar-03.png' },
  { key: 'P4', color: '#2468F2', src: '/avatars/avatar-04.png' },
  { key: 'P5', color: '#7B61FF', src: '/avatars/avatar-05.png' },
  { key: 'P6', color: '#FF4D5D', src: '/avatars/avatar-06.png' }
]

/** 预设头像键：'P1' ~ 'P6' */
export type PresetAvatarKey = (typeof PRESET_AVATARS)[number]['key']

export function isPresetKey(value: string | null | undefined): value is PresetAvatarKey {
  return /^P[1-6]$/.test(String(value ?? ''))
}

/** 按种子（助理 ID 或名称）稳定取人像序号 0~5 */
export function presetIndex(seed: string | number | null | undefined): number {
  const text = String(seed ?? '')
  let n = 0
  for (let i = 0; i < text.length; i += 1) n = (n * 31 + text.charCodeAt(i)) % 99991
  return n % PRESET_AVATARS.length
}

/** 默认头像键：优先取已存的 P#，否则按种子稳定分配 */
export function resolvePresetKey(
  avatarChar: string | null | undefined,
  seed: string | number | null | undefined
): PresetAvatarKey {
  if (isPresetKey(avatarChar)) return avatarChar
  return PRESET_AVATARS[presetIndex(seed)].key
}

export function presetSrc(key: string | null | undefined, seed?: string | number): string {
  const resolved = resolvePresetKey(key, seed)
  return PRESET_AVATARS.find((v) => v.key === resolved)?.src ?? PRESET_AVATARS[0].src
}

export function presetColor(key: string | null | undefined): string {
  const hit = PRESET_AVATARS.find((v) => v.key === key)
  return hit?.color ?? PRESET_AVATARS[0].color
}

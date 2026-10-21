<script setup lang="ts">
import type { Competition } from '../types'
defineProps<{ competition: Competition; subscribed?: boolean; score?: number; reason?: string }>()
defineEmits<{ detail: [competition: Competition]; subscribe: [competition: Competition] }>()
function deadline(item: Competition) {
  if (item.deadline_precision === 'datetime' && item.deadline_at) {
    return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(item.deadline_at))
  }
  return item.deadline_date ? `${item.deadline_date.slice(5)} · 时间待确认` : '截止时间待公布'
}
const categoryMark: Record<string, string> = { '数据与AI': 'DA', '创意设计': 'DE', '数理建模': 'MA', '软件开发': 'CO', '学术研究': 'RE', '社会实践': 'SE' }
</script>

<template>
  <article class="competition-card">
    <div class="card-top">
      <span class="category-icon" :class="`tone-${competition.id % 4}`">{{ categoryMark[competition.category] ?? 'CC' }}</span>
      <span class="card-category">{{ competition.category }}</span>
      <span v-if="score !== undefined" class="match-badge">{{ score }} 匹配分</span>
      <span v-else class="subtle-badge">{{ competition.edition }} 届</span>
    </div>
    <h3><button class="title-button" @click="$emit('detail', competition)">{{ competition.title }}</button></h3>
    <p class="card-summary">{{ competition.summary }}</p>
    <div class="tag-row"><span v-for="tag in competition.tags" :key="tag">{{ tag }}</span></div>
    <p v-if="reason" class="match-reason"><span>✦</span> {{ reason }}</p>
    <div class="card-facts">
      <span>◷ <strong>{{ deadline(competition) }}</strong><small>报名截止 · 北京时间</small></span>
      <span>⌁ <strong>{{ competition.allowed_levels.join(' / ') || '条件待确认' }}</strong><small>培养层次要求</small></span>
    </div>
    <div class="card-footer">
      <span class="source-label"><i></i>{{ competition.is_demo ? '合成演示 · 可查证据' : '已核验 · 可查来源' }}</span>
      <button :class="['button', subscribed ? 'button-saved' : 'button-outline']" :disabled="subscribed" @click="$emit('subscribe', competition)">{{ subscribed ? '✓ 已订阅' : '＋ 订阅提醒' }}</button>
    </div>
  </article>
</template>

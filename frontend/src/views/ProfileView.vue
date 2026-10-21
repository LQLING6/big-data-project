<script setup lang="ts">
import { reactive } from 'vue'
import type { Profile } from '../types'
const props = defineProps<{ profile: Profile; saving: boolean }>()
const emit = defineEmits<{ save: [profile: Omit<Profile, 'version'>] }>()
const form = reactive({
  major: props.profile.major, school: props.profile.school, level: props.profile.level,
  grade: props.profile.grade, weekly_hours: props.profile.weekly_hours,
  skills: props.profile.skills.join('，'), interests: props.profile.interests.join('，'),
  unavailable_dates: props.profile.unavailable_dates.join('，'),
})
const split = (value: string) => value.split(/[,，\n]/).map(item => item.trim()).filter(Boolean)
function save() {
  emit('save', {
    ...form, grade: form.grade === null || (form.grade as unknown) === '' ? null : Number(form.grade),
    weekly_hours: form.weekly_hours === null || (form.weekly_hours as unknown) === '' ? null : Number(form.weekly_hours),
    skills: split(form.skills), interests: split(form.interests), unavailable_dates: split(form.unavailable_dates),
  })
}
</script>

<template>
  <section class="panel profile-panel">
    <div class="section-intro"><span class="eyebrow">YOUR PROFILE</span><h2>让推荐更了解你</h2><p>只填写必要信息。画像用于匹配参考，不代表官方资格审核。</p></div>
    <form class="profile-form" @submit.prevent="save">
      <label>专业<input v-model="form.major" maxlength="100" placeholder="例如：计算机科学与技术" /></label>
      <label>学校<input v-model="form.school" maxlength="100" placeholder="用于判断仅限本校的赛事" /></label>
      <label>培养层次<select v-model="form.level"><option>本科</option><option>专科</option><option>硕士</option><option>博士</option></select></label>
      <label>当前年级<input v-model.number="form.grade" type="number" min="1" max="8" placeholder="例如：2" /></label>
      <label class="wide">技能标签<input v-model="form.skills" placeholder="python，sql，vue" /><small>多个标签用逗号分隔。技能标签会自动转为小写。</small></label>
      <label class="wide">兴趣标签<input v-model="form.interests" placeholder="数据分析，人工智能，设计" /></label>
      <label>每周可投入小时<input v-model.number="form.weekly_hours" type="number" min="0" max="100" step="0.5" /><small>赛事没有官方工作量时，不据此猜测是否来得及。</small></label>
      <label>不可用日期<input v-model="form.unavailable_dates" placeholder="2026-11-01，2026-11-02" /><small>使用 YYYY-MM-DD 格式，多个日期用逗号分隔。</small></label>
      <div class="wide form-actions"><button class="button button-primary" :disabled="saving">{{ saving ? '保存中…' : '保存并更新推荐' }}</button><span>不需要学号、身份证或完整课表</span></div>
    </form>
  </section>
</template>

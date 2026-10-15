<script setup lang="ts">
import type {Analysis} from '../types';
defineProps<{analysis:Analysis}>();
const steps=[['queued','대기'],['validating','파일 검사'],['transcribing','음성 전사'],['extracting','주장 추출'],['retrieving','근거 검색'],['validating_evidence','원문 검증'],['completed','보고서']];
</script>
<template><section class="progress-card" aria-live="polite"><div class="section-label">분석 진행 <span>AUDIO ANALYSIS</span></div><h2>음성의 주장을 확인하고 있습니다.</h2><p class="muted">단계별 상태를 표시합니다. 완료 시간은 파일과 근거 접근 상태에 따라 달라집니다.</p><ol class="steps"><li v-for="([key,label],i) in steps" :key="key" :class="{current:analysis.status===key,done:steps.findIndex(s=>s[0]===analysis.status)>i}"><span>{{i+1}}</span>{{label}}</li></ol></section></template>

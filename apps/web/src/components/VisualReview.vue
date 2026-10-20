<script setup lang="ts">
import type {Analysis} from '../types';
import {time} from '../types';
defineProps<{analysis:Analysis}>();
defineEmits<{seek:[seconds:number]}>();
const statusLabels:Record<string,string>={complete:'표본 추출 완료',partial:'부분 추출',unavailable:'추출 불가',not_applicable:'해당 없음'};
const subtitleLabels:Record<string,string>={extracted:'추출됨',not_present:'없음',unsupported:'지원하지 않는 형식',failed:'추출 실패',truncated:'일부 누락'};
const ocrLabels:Record<string,string>={complete:'표본 추출됨',partial:'일부 추출',unavailable:'사용 불가',no_video:'영상 없음'};
const checkLabels:Record<string,string>={matching_record:'같은 수치 기록 · 사실성 미검증',possible_mismatch:'불일치 후보 · 검토 필요',review_required:'맥락 검토 필요'};
const overallLabels:Record<string,string>={review_required:'검토 필요',insufficient:'검증 불충분',mixed:'확인·반박 혼재',supported_claims:'선택 주장 근거로 확인됨',refuted_claims:'선택 주장 반박됨',no_checkable_claims:'검증 대상 주장 없음'};
const reasonLabels:Record<string,string>={DIRECT_REVIEWED_EVIDENCE:'검토된 비교 정의와 직접 인용에 한정한 평가입니다.',INDEPENDENCE_UNVERIFIED:'출처 독립성은 확인되지 않았습니다.',UNRESOLVED_CLAIMS:'선택 범위에 미해결 또는 의미 검토가 없는 주장이 있습니다.',MODAL_UNCERTAINTY:'음성·자막·화면 비교에 별도 불확실성이 있습니다.',SHARED_OR_DUPLICATE_ORIGIN:'같은 문서 또는 출처 관계 그룹은 중복 근거로 세지 않습니다.'};
</script>
<template>
<section v-if="analysis.visual && analysis.visual.status!=='not_applicable'" class="visual-review">
 <h3>자막·화면 관측</h3>
 <p>{{statusLabels[analysis.visual.status]}} · 자막 {{subtitleLabels[analysis.visual.subtitleStatus]??'상태 확인 필요'}} · OCR {{ocrLabels[analysis.visual.ocrStatus]??'상태 확인 필요'}}</p>
 <p>표본 화면의 관측입니다. OCR 오인식과 표본 사이의 누락이 가능하며, 내부 일치 여부는 외부 사실성과 별개입니다.</p>
 <ul><li v-for="(record,i) in analysis.visual.records" :key="i">
  <button type="button" @click="$emit('seek',record.startSeconds)" :aria-label="`${time(record.startSeconds)} 관측 구간 재생`">{{time(record.startSeconds)}}–{{time(record.endSeconds)}}</button>
  <span>{{record.source==='ocr'?'화면 OCR':'내장 자막'}} · {{record.text}}</span>
 </li></ul>
 <p v-if="!analysis.visual.records.length">읽을 수 있는 자막·화면 텍스트를 확보하지 못했습니다. 일치로 판단하지 않습니다.</p>
 <h4 v-if="analysis.modalChecks?.length">음성 주장과의 비교</h4>
 <ul><li v-for="(check,i) in analysis.modalChecks" :key="i">
  <strong>{{checkLabels[check.status]}}</strong>
  <p>{{analysis.claims.find(c=>c.id===check.claimId)?.text}}</p>
  <p>{{check.observedText}}</p>
  <small>{{check.reasons.join(' · ')}}</small>
 </li></ul>
 <ul><li v-for="item in analysis.visual.limitations" :key="item">{{item}}</li></ul>
</section>
<section v-if="analysis.summary" class="visual-review">
 <h3>주장 집계</h3>
 <p>집계 결과: {{overallLabels[analysis.summary.overall]??analysis.summary.overall}}</p>
 <p v-if="analysis.summary.crossModalReviewRequired">자막·화면 비교 결과에 검토가 필요한 항목이 있습니다.</p>
 <template v-if="analysis.summary.reviewedEvidence">
  <p>선택한 주장 {{analysis.summary.reviewedEvidence.claimIds.length}}개를 집계했습니다.</p>
  <p>검토 근거 강도: {{analysis.summary.reviewedEvidence.strength==='moderate'?'보통':'낮음'}}</p>
  <p>문서 {{analysis.summary.reviewedEvidence.documentCount}}개 · 가능한 공통 출처 그룹 {{analysis.summary.reviewedEvidence.originGroupCount}}개</p>
  <p>같은 문서 해시 또는 출처 관계 그룹을 묶은 수이며 독립 출처 수가 아닙니다.</p>
  <ul><li v-for="reason in analysis.summary.reviewedEvidence.reasons" :key="reason">{{reasonLabels[reason]??reason}}</li></ul>
  <p>보통은 선택 주장에 직접 검토 근거가 있다는 뜻이고, 낮음은 미해결 주장이나 모달 불확실성이 남았다는 뜻입니다. 진실 확률이나 전체 영상의 신뢰도를 뜻하지 않습니다.</p>
 </template>
 <p v-else>전체 영상의 진실 판정이 아닙니다. 근거 강도와 출처 독립성은 평가하지 않았습니다.</p>
</section>
</template>
<style scoped>
.visual-review{padding:1.2rem;border-top:1px solid #dce3e8;overflow-wrap:anywhere}.visual-review li{margin:.7rem 0}.visual-review button{margin-right:.6rem;cursor:pointer}.visual-review small{overflow-wrap:anywhere}
</style>

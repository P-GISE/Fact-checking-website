<script setup lang="ts">
import {ref,onMounted,onUnmounted} from 'vue';
import UploadPanel from './components/UploadPanel.vue';
import AnalysisProgress from './components/AnalysisProgress.vue';
import AnalysisReport from './components/AnalysisReport.vue';
import {upload,createAnalysis,getAnalysis,listAnalyses,deleteAnalysis} from './api';
import type {Analysis} from './types';
import {example} from './example';
const analysis=ref<Analysis|null>(null),history=ref<Analysis[]>([]),busy=ref(false),error=ref(''),notice=ref('');
let timer:ReturnType<typeof setTimeout>|undefined;
let generation=0;
const messages:Record<string,string>={BUDGET_EXCEEDED:'분석 1건 또는 월 예산 한도에 도달했습니다.',BILLING_REVIEW_REQUIRED:'사용량 정산을 확인해야 합니다. 추가 유료 호출을 중단했습니다.',PROVIDER_AUTH_FAILED:'AI 또는 검색 API 인증 정보를 확인해 주세요.',PROVIDER_RATE_LIMITED:'제공자 호출 제한에 도달했습니다. 자동으로 재시도하지 않습니다.',PROVIDER_MODEL_UNAVAILABLE:'선택한 모델을 이 계정에서 사용할 수 없습니다.',PROVIDER_INPUT_LIMIT:'제공자 입력 제한을 초과해 추가 전송을 중단했습니다.',PROVIDER_RESPONSE_INVALID:'제공자 응답을 검증하지 못해 판정을 만들지 않았습니다.',PROVIDER_REQUEST_FAILED:'제공자 연결에 실패했습니다. 네트워크 허용 정책과 연결 상태를 확인해 주세요.',PROVIDER_SEARCH_LIMIT:'분석당 검색 횟수 제한에 도달했습니다.',PROVIDER_NOT_CONFIGURED:'AI 제공자 연결이 필요합니다.',SIZE_LIMIT:'100 MiB 이하 파일을 선택해 주세요.',DURATION_LIMIT:'3분 이하 파일을 선택해 주세요.',INVALID_MEDIA:'파일이 손상됐거나 지원하지 않는 미디어입니다.',FORMAT_MISMATCH:'파일 확장자와 실제 형식이 다릅니다.',NO_AUDIO:'분석할 음성 트랙이 없습니다.',TIMEOUT:'작업 제한 시간을 초과했습니다.',NETWORK_ERROR:'연결을 확인한 뒤 다시 시도해 주세요.'};
function message(code:string){return messages[code]??'처리를 완료하지 못했습니다. 파일과 연결 상태를 확인해 주세요.';}
async function refreshHistory(){try{history.value=await listAnalyses();}catch{error.value='분석 이력에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요.';}}
function clearPoll(){generation++;if(timer)clearTimeout(timer);}
async function open(id:string){
 clearPoll();const token=generation;error.value='';
 try{
  const result=await getAnalysis(id);
  if(token!==generation)return;
  analysis.value=result;
  if(!['completed','failed','cancelled','deleted'].includes(result.status))timer=setTimeout(()=>open(id),1200);
 }catch(e){if(token===generation)error.value=message((e as Error).message);}
}
async function start(file:File,consent:boolean){
 clearPoll();const token=generation;busy.value=true;error.value='';notice.value='';
 try{const m=await upload(file);const job=await createAnalysis(m.mediaId,consent);if(token===generation)await open(job.id);await refreshHistory();}
 catch(e){if(token===generation)error.value=message((e as Error).message);}
 finally{busy.value=false;}
}
function showExample(){clearPoll();analysis.value=example;error.value='';notice.value='';}
async function remove(){
 if(!analysis.value||analysis.value.demo)return;
 const id=analysis.value.id;clearPoll();const token=generation;
 try{await deleteAnalysis(id);if(token===generation){analysis.value=null;notice.value='분석과 미디어를 삭제했습니다.';}await refreshHistory();}
 catch(e){if(token===generation)error.value=message((e as Error).message);}
}
function home(){clearPoll();analysis.value=null;notice.value='';}
onMounted(refreshHistory);onUnmounted(clearPoll);
</script>
<template><div class="app-shell"><aside class="sidebar"><button class="brand" @click="home"><span class="brand-icon" aria-hidden="true">◉</span>FactLens<span class="ai-tag">AI</span></button><span class="workspace-label">WORKSPACE</span><button class="nav-item" :class="{active:!analysis}" @click="home"><span aria-hidden="true">＋</span>새 분석</button><div class="nav-heading">분석 이력 <span>{{history.length}}</span></div><button v-for="item in history" :key="item.id" class="history-item" :class="{active:analysis?.id===item.id}" @click="open(item.id)"><span aria-hidden="true">▤</span><span>{{new Date(item.createdAt).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})}}<small>{{item.status==='completed'?'분석 완료':item.status==='failed'?'처리 확인 필요':'분석 진행'}}</small></span></button><p v-if="!history.length" class="history-empty">분석한 파일이 여기에<br>표시됩니다.</p><a class="nav-item" href="/admin">운영 관리</a><div class="sidebar-bottom"><span class="status-dot"></span>비공개 개발 환경<small>FactLens AI · Audio PoC</small></div></aside><div class="main-shell"><header class="topbar"><span>워크스페이스 <span class="breadcrumb">/ {{analysis?'분석 보고서':'새 분석'}}</span></span><span class="version">EARLY ACCESS <i>v0.1</i></span></header><main><div class="page-intro"><div class="eyebrow"><span></span>EVIDENCE BEFORE VERDICT</div><h1>{{analysis?'판정의 이유까지, 투명하게.':'영상 속 주장, 근거로 다시 보기.'}}</h1><p>음성의 주장을 하나씩 살펴보고, 확인 가능한 원문과 대조합니다.<br>무엇을 확인했고 무엇을 알 수 없는지 함께 보여드립니다.</p></div><div v-if="error" class="error-note" role="alert">{{error}} <button class="text-button" @click="refreshHistory">연결 다시 확인</button></div><p v-if="notice" class="success-note" role="status">{{notice}}</p><template v-if="!analysis"><div class="start-grid"><UploadPanel :busy="busy" @start="start" @example="showExample"/><aside class="guide-card"><span class="section-label">HOW IT WORKS</span><h2>결론보다,<br>근거가 먼저입니다.</h2><ol><li><span>01</span><div><strong>주장과 시간 구간 추출</strong><p>음성을 전사하고 확인할 수 있는<br>개별 주장을 구분합니다.</p></div></li><li><span>02</span><div><strong>외부 근거와 원문 대조</strong><p>인용·기간·대상·수치를 확인하고<br>근거의 적합성을 검토합니다.</p></div></li><li><span>03</span><div><strong>이유와 한계를 담은 보고서</strong><p>자료가 부족하면 판정을 유보하고<br>확인한 범위를 설명합니다.</p></div></li></ol><div class="scope-note"><span aria-hidden="true">ⓘ</span>현재 버전은 음성만 분석합니다.<br>자막·영상 맥락 분석은 준비 중입니다.</div></aside></div><div class="principles"><div><span aria-hidden="true">↗</span><strong>원문까지 이어지는 근거</strong><p>주장과 인용 위치를 함께 확인</p></div><div><span aria-hidden="true">◇</span><strong>불확실성을 숨기지 않는 판정</strong><p>부족·충돌·처리 오류를 구분</p></div><div><span aria-hidden="true">◷</span><strong>파일은 필요한 만큼만</strong><p>비공개 보관 · 삭제 요청 지원</p></div></div></template><template v-else><div class="analysis-toolbar"><button class="text-button" @click="home">← 새 분석으로</button><button v-if="!analysis.demo" class="danger-button" @click="remove">분석 삭제</button><button v-else class="text-button" @click="home">예시 닫기</button></div><div v-if="analysis.status==='failed'" class="failure-card" role="status"><span class="upload-icon">!</span><h2>{{message(analysis.error?.code??'')}}</h2><p>이 작업의 실제 AI 분석은 완료되지 않았습니다.</p><p class="muted">제공자·모델·예산과 외부 전송 정책을 설정한 후 새 분석을 시작할 수 있습니다.</p><small>오류 코드: {{analysis.error?.code}}</small></div><AnalysisReport v-else-if="analysis.status==='completed'" :analysis="analysis"/><AnalysisProgress v-else :analysis="analysis"/></template><footer class="page-footer"><span>FactLens AI</span>근거 기반 의사결정 지원 · 모든 사실의 진실을 보증하지 않습니다.</footer></main></div></div></template>

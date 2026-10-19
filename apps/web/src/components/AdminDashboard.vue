<script setup lang="ts">
import {ref,computed,onMounted,onUnmounted} from 'vue';
import AccountPanel from './AccountPanel.vue';
import {getSession,logout,type Session} from '../api';
type Overview={pagination:{page:number;pageSize:number;total:number;hasNext:boolean};observedAt:string;windowStart:string;statusCounts:Record<string,number>;recentJobs:{id:string;status:string;createdAt:string;errorCode:string|null}[];usage:{month:string;settledMicros:string;reservedMicros:string;effectiveMicros:string;pendingReservations:string}};
const session=ref<Session|null>(null),overview=ref<Overview|null>(null),error=ref(''),busy=ref(false);
const search=ref(''),statusFilter=ref('');
const totals=computed(()=>{
 const counts=overview.value?.statusCounts??{};
 return {all:Object.values(counts).reduce((a,b)=>a+b,0),active:['validating','transcribing','extracting','retrieving','validating_evidence'].reduce((n,key)=>n+(counts[key]??0),0),completed:counts.completed??0,failed:counts.failed??0};
});
const errorLabels:Record<string,string>={PROVIDER_NOT_CONFIGURED:'AI 연결 미설정',PROVIDER_RATE_LIMITED:'제공자 호출 제한',PROVIDER_AUTH_FAILED:'제공자 인증 실패',BUDGET_EXCEEDED:'예산 한도 도달',BILLING_REVIEW_REQUIRED:'사용량 정산 확인 필요',INVALID_MEDIA:'미디어 확인 필요',TIMEOUT:'처리 시간 초과'};
function resetFilters(){search.value='';statusFilter.value='';return applyFilters();}
let appliedSearch='',appliedStatus='';
function applyFilters(){appliedSearch=search.value;appliedStatus=statusFilter.value;return load(1);}
let generation=0,controller:AbortController|undefined;
const statusLabels:Record<string,string>={queued:'대기',validating:'미디어 검사',transcribing:'전사',extracting:'주장 추출',retrieving:'근거 수집',validating_evidence:'근거 검증',completed:'완료',failed:'실패',cancelled:'취소',deleted:'삭제'};
function money(value:string){const micros=BigInt(value);return `$${micros/1000000n}.${(micros%1000000n).toString().padStart(6,'0')}`;}
function date(value:string){return new Date(value).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'});}
function disconnect(){generation++;controller?.abort();controller=undefined;overview.value=null;busy.value=false;}
async function initialize(){error.value='';try{session.value=await getSession();if(session.value.user?.role==='admin')await load();}catch{error.value='로그인 상태를 확인하지 못했습니다. 다시 시도해 주세요.';}}
async function authenticated(value:Session){session.value=value;if(value.user?.role==='admin')await load();}
async function signOut(){try{await logout();disconnect();session.value=null;await initialize();}catch{error.value='로그아웃하지 못했습니다. 다시 시도해 주세요.';}}
async function load(page=overview.value?.pagination.page??1){
 const current=++generation;controller?.abort();controller=new AbortController();busy.value=true;error.value='';
 try{
  const response=await fetch('/api/admin/overview?'+new URLSearchParams({page:String(page),pageSize:'20',...(appliedSearch?{q:appliedSearch}:{}),...(appliedStatus?{status:appliedStatus}:{})}),{cache:'no-store',credentials:'same-origin',signal:controller.signal});
  if(current!==generation)return;
  if(!response.ok){if(response.status===401||response.status===403){overview.value=null;await initializeSession();}throw new Error('REQUEST_FAILED');}
  const data:Overview=await response.json();if(current!==generation)return;overview.value=data;
 }catch{if(current===generation){overview.value=null;error.value='관리 정보를 조회하지 못했습니다. 로그인 상태와 연결을 확인해 주세요.';}}
 finally{if(current===generation)busy.value=false;}
}
async function initializeSession(){session.value=await getSession();}
onMounted(initialize);onUnmounted(disconnect);

</script>
<template>
 <main class="admin-page">
  <header class="dashboard-header"><div><a class="brand-link" href="/">← FactLens AI</a><p class="eyebrow">ADMIN WORKSPACE</p><h1>운영 대시보드</h1><p>최근 작업과 오류, 이번 달 비용을 한눈에 확인하세요.</p></div><div class="header-tools"><span v-if="session?.user" class="operator">{{session.user.username}}</span><button v-if="session?.user" class="secondary" @click="signOut">로그아웃</button></div></header>
  <p class="muted">원본 미디어·전사·근거 본문은 표시하지 않습니다. 시간은 한국 표준시입니다.</p>
  <p v-if="!session&&!error" role="status">로그인 상태 확인 중…</p>
  <AccountPanel v-if="session&&!session.user&&session.mode==='accounts'" @authenticated="authenticated"/>
  <p v-if="session&&(session.mode==='local'||(session.user&&session.user.role!=='admin'))" role="alert">관리자 계정으로 로그인해야 접근할 수 있습니다.</p>
  <button v-if="error" :disabled="busy" @click="initialize">다시 연결</button>
  <p v-if="error" role="alert" class="error-note">{{error}}</p>
  <template v-if="overview">
   <div class="refresh-bar"><p class="muted">마지막 조회 <strong>{{date(overview.observedAt)}}</strong> · 자동 갱신 아님</p><button :disabled="busy" @click="load()">{{busy?'조회 중…':'새로 조회'}}</button></div>
   <dl class="summary-grid" aria-label="최근 24시간 작업 요약">
    <div><dt>전체 작업</dt><dd>{{totals.all}}<small>건</small></dd><p>최근 24시간 생성 기준</p></div>
    <div><dt>진행 중</dt><dd>{{totals.active}}<small>건</small></dd><p>대기 {{overview.statusCounts.queued??0}}건 별도</p></div>
    <div class="success-card"><dt>완료</dt><dd>{{totals.completed}}<small>건</small></dd><p>처리가 완료된 작업</p></div>
    <div class="failure-card"><dt>실패</dt><dd>{{totals.failed}}<small>건</small></dd><p>실패 원인은 아래 목록에서 확인</p></div>
   </dl>
   <section class="status-section"><h2>상태별 상세</h2><p>생성 시각 기준 · {{date(overview.windowStart)}}부터</p>
    <dl class="admin-counts"><div v-for="(count,status) in overview.statusCounts" :key="status"><dt>{{statusLabels[status]??status}}</dt><dd>{{count}}건</dd></div></dl>
    <p v-if="!Object.keys(overview.statusCounts).length">해당 기간에 생성된 작업이 없습니다.</p>
   </section>
   <section class="cost-section"><h2>월 사용량 기록</h2><p>{{overview.usage.month}} · UTC 기준 · USD</p>
    <dl class="admin-counts"><div><dt>정산 기록액</dt><dd>{{money(overview.usage.settledMicros)}}</dd></div><div><dt>미정산 예약액</dt><dd>{{money(overview.usage.reservedMicros)}}</dd></div><div><dt>예산 반영액</dt><dd>{{money(overview.usage.effectiveMicros)}}</dd></div></dl>
    <p>미정산 예약 {{overview.usage.pendingReservations}}건</p><p class="muted">애플리케이션의 비용 기록입니다. 제공자의 실제 청구액·잔액·호출 한도를 확인한 값이 아닙니다.</p>
   </section>
   <section class="jobs-section" :aria-busy="busy"><h2>최근 작업과 오류</h2><p>최근 24시간 · 최신 생성 순 · 요약과 월 비용은 필터와 관계없이 전체 기준입니다.</p>
    <form class="admin-filters" @submit.prevent="applyFilters">
     <label>작업 ID 검색<input v-model="search" type="search" maxlength="36" pattern="[a-fA-F0-9-]{0,36}" placeholder="작업 ID 또는 앞부분" :disabled="busy"></label>
     <label>작업 상태<select v-model="statusFilter" :disabled="busy"><option value="">전체 상태</option><option v-for="(label,key) in statusLabels" :key="key" :value="key">{{label}}</option></select></label>
     <button type="submit" :disabled="busy">검색 적용</button><button type="button" class="secondary" :disabled="busy" @click="resetFilters">초기화</button>
    </form>
    <p role="status">검색 결과 {{overview.pagination.total}}건 · {{overview.pagination.page}}페이지{{busy?' · 조회 중…':''}}</p>
    <p v-if="!overview.recentJobs.length">조건에 맞는 작업이 없습니다. 검색 조건을 바꾸거나 이전 페이지로 이동하세요.</p><div class="admin-table"><table><thead><tr><th scope="col">작업 ID</th><th scope="col">상태</th><th scope="col">생성 시각</th><th scope="col">오류 코드</th></tr></thead><tbody><tr v-for="job in overview.recentJobs" :key="job.id"><td class="job-id">{{job.id}}</td><td><span class="status-badge" :class="job.status">{{statusLabels[job.status]??job.status}}</span></td><td>{{date(job.createdAt)}}</td><td><span v-if="job.errorCode" class="error-detail">{{errorLabels[job.errorCode]??'상세 코드 확인 필요'}}<code>{{job.errorCode}}</code></span><span v-else class="muted">없음</span></td></tr></tbody></table></div><nav class="admin-actions" aria-label="작업 목록 페이지"><button :disabled="busy||overview.pagination.page<=1" @click="load(overview.pagination.page-1)">이전 페이지</button><button :disabled="busy||!overview.pagination.hasNext||overview.pagination.page>=1000" @click="load(overview.pagination.page+1)">다음 페이지</button></nav></section>
  </template>
 </main>
</template>
<style scoped>
.admin-page{box-sizing:border-box;max-width:1240px;margin:0 auto;padding:2.5rem 2rem 4rem;color:#172b4d;font-size:15px;line-height:1.6}.dashboard-header{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;padding-bottom:1.5rem;border-bottom:1px solid #cdd7e3}.brand-link{font-weight:700;text-decoration:none}.eyebrow{font-size:.72rem;letter-spacing:.14em;color:#526477;margin:1.5rem 0 .25rem}.dashboard-header h1{font-size:2rem;margin:0;letter-spacing:-.04em}.dashboard-header p{color:#526477}.header-tools,.refresh-bar,.admin-actions{display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}.operator{font-weight:600}.refresh-bar{justify-content:space-between;margin:1.5rem 0 1rem}.refresh-bar p{margin:0}.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;margin:0 0 1.5rem}.summary-grid>div{background:#fff;padding:1.25rem;border:1px solid #dce3eb;border-radius:12px;border-top:4px solid #5980ae}.summary-grid dt{font-weight:600;color:#526477}.summary-grid dd{margin:.35rem 0;font-size:2.25rem;font-weight:750;font-variant-numeric:tabular-nums}.summary-grid small{margin-left:.4rem;font-size:.9rem;font-weight:400}.summary-grid p{margin:0;color:#526477;font-size:.8rem}.summary-grid .success-card{border-top-color:#23845a}.summary-grid .failure-card{border-top-color:#be4350;background:#fff;box-shadow:none;text-align:left;display:block}.admin-page section{margin-block:1.5rem;padding:1.5rem;border:1px solid #dce3eb;border-radius:12px;background:#fff}.admin-page h2{font-size:1.15rem;margin:0 0 .4rem}.admin-page section>p{color:#526477;margin:.25rem 0 1rem}.admin-page button,.admin-page input,.admin-page select{box-sizing:border-box;padding:.65rem .9rem;border:1px solid #8b9bae;border-radius:7px;font:inherit;min-height:42px}.admin-page button{cursor:pointer;background:#2459a9;color:#fff;border-color:#2459a9;font-weight:600}.admin-page .secondary{background:#fff;color:#2459a9;border-color:#b4c5db}.admin-page button:disabled{opacity:.5;cursor:wait}.admin-counts{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:0}.admin-counts>div{padding:.75rem 1rem;background:#f3f6fa;border-radius:8px;min-width:100px}.admin-counts dt{color:#526477;font-size:.85rem}.admin-counts dd{margin:.3rem 0;font-size:1.3rem;font-weight:650;font-variant-numeric:tabular-nums}.cost-section .admin-counts>div{flex:1;min-width:170px}.admin-table{overflow-x:auto;margin:1rem 0}.admin-table table{width:100%;border-collapse:collapse}.admin-table th{background:#f3f6fa;color:#526477;font-size:.8rem}.admin-table th,.admin-table td{text-align:left;padding:.9rem .75rem;border-bottom:1px solid #e2e8f0;white-space:nowrap}.admin-table tbody tr:hover{background:#f7faff}.job-id{font-family:ui-monospace,monospace;font-size:.78rem}.status-badge{display:inline-block;padding:.2rem .6rem;border-radius:6px;background:#edf2f8;color:#37516e;font-size:.8rem;font-weight:600}.status-badge.completed{background:#e5f5ec;color:#176340}.status-badge.failed{background:#ffebed;color:#a42b38}.status-badge.queued{background:#fff2d7;color:#805600}.error-detail{display:grid;color:#9b2934;font-size:.82rem}.error-detail code{font-size:.7rem;color:#526477}.admin-filters{display:flex;gap:.75rem;flex-wrap:wrap;align-items:end;padding:1rem;background:#f3f6fa;border-radius:8px}.admin-filters label{display:grid;gap:.35rem;font-size:.85rem;font-weight:600}.admin-filters label:first-child{flex:1;min-width:180px}.admin-filters input,.admin-filters select{width:100%;background:white}.muted{color:#526477;font-size:.85rem}.error-note{padding:1rem;background:#ffebed;color:#9b2934;border-radius:8px}.admin-page :focus-visible{outline:3px solid #3276cc;outline-offset:3px}.admin-page a{color:#2459a9}@media(max-width:800px){.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.admin-page{padding:1.25rem 1rem}.dashboard-header h1{font-size:1.6rem}.header-tools{justify-content:flex-end}.admin-page section{padding:1rem}}@media(max-width:420px){.summary-grid{gap:.5rem}.summary-grid>div{padding:.8rem}.summary-grid dd{font-size:1.8rem}.dashboard-header{flex-direction:column}.admin-filters label{width:100%}.admin-filters button{flex:1}}
</style>

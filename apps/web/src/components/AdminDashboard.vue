<script setup lang="ts">
import {ref,onMounted,onUnmounted} from 'vue';
import AccountPanel from './AccountPanel.vue';
import {getSession,logout,type Session} from '../api';
type Overview={pagination:{page:number;pageSize:number;total:number;hasNext:boolean};observedAt:string;windowStart:string;statusCounts:Record<string,number>;recentJobs:{id:string;status:string;createdAt:string;errorCode:string|null}[];usage:{month:string;settledMicros:string;reservedMicros:string;effectiveMicros:string;pendingReservations:string}};
const session=ref<Session|null>(null),overview=ref<Overview|null>(null),error=ref(''),busy=ref(false);
const search=ref(''),statusFilter=ref('');
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
  <header><a href="/">← FactLens AI</a><h1>운영 관리</h1><p>작업·오류·사용량을 읽기 전용으로 확인합니다.</p></header>
  <p class="muted">원본 미디어·전사·근거 본문은 표시하지 않습니다. 시간은 한국 표준시입니다.</p>
  <p v-if="!session&&!error" role="status">로그인 상태 확인 중…</p>
  <AccountPanel v-if="session&&!session.user&&session.mode==='accounts'" @authenticated="authenticated"/>
  <p v-if="session&&(session.mode==='local'||(session.user&&session.user.role!=='admin'))" role="alert">관리자 계정으로 로그인해야 접근할 수 있습니다.</p>
  <button v-if="session?.user" @click="signOut">로그아웃</button>
  <button v-if="error" :disabled="busy" @click="initialize">다시 연결</button>
  <p v-if="error" role="alert" class="error-note">{{error}}</p>
  <template v-if="overview">
   <div class="admin-actions"><button :disabled="busy" @click="load()">{{busy?'조회 중…':'새로 조회'}}</button></div>
   <p class="muted">조회 시각: {{date(overview.observedAt)}}</p>
   <section><h2>최근 24시간 작업</h2><p>생성 시각 기준 · {{date(overview.windowStart)}}부터</p>
    <dl class="admin-counts"><div v-for="(count,status) in overview.statusCounts" :key="status"><dt>{{statusLabels[status]??status}}</dt><dd>{{count}}건</dd></div></dl>
    <p v-if="!Object.keys(overview.statusCounts).length">해당 기간에 생성된 작업이 없습니다.</p>
   </section>
   <section><h2>월 사용량 기록</h2><p>{{overview.usage.month}} · UTC 기준 · USD</p>
    <dl class="admin-counts"><div><dt>정산 기록액</dt><dd>{{money(overview.usage.settledMicros)}}</dd></div><div><dt>미정산 예약액</dt><dd>{{money(overview.usage.reservedMicros)}}</dd></div><div><dt>예산 반영액</dt><dd>{{money(overview.usage.effectiveMicros)}}</dd></div></dl>
    <p>미정산 예약 {{overview.usage.pendingReservations}}건</p><p class="muted">애플리케이션의 비용 기록입니다. 제공자의 실제 청구액·잔액·호출 한도를 확인한 값이 아닙니다.</p>
   </section>
   <section :aria-busy="busy"><h2>최근 작업과 오류</h2><p>최근 24시간 · 최신 생성 순 · 요약과 월 비용은 필터와 관계없이 전체 기준입니다.</p>
    <form class="admin-filters" @submit.prevent="applyFilters">
     <label>작업 ID 검색<input v-model="search" type="search" maxlength="36" pattern="[a-fA-F0-9-]{0,36}" placeholder="작업 ID 또는 앞부분" :disabled="busy"></label>
     <label>작업 상태<select v-model="statusFilter" :disabled="busy"><option value="">전체 상태</option><option v-for="(label,key) in statusLabels" :key="key" :value="key">{{label}}</option></select></label>
     <button type="submit" :disabled="busy">검색 적용</button>
    </form>
    <p role="status">검색 결과 {{overview.pagination.total}}건 · {{overview.pagination.page}}페이지{{busy?' · 조회 중…':''}}</p>
    <p v-if="!overview.recentJobs.length">조건에 맞는 작업이 없습니다. 검색 조건을 바꾸거나 이전 페이지로 이동하세요.</p><div class="admin-table"><table><thead><tr><th scope="col">작업 ID</th><th scope="col">상태</th><th scope="col">생성 시각</th><th scope="col">오류 코드</th></tr></thead><tbody><tr v-for="job in overview.recentJobs" :key="job.id"><td>{{job.id}}</td><td>{{statusLabels[job.status]??job.status}}</td><td>{{date(job.createdAt)}}</td><td>{{job.errorCode??'없음'}}</td></tr></tbody></table></div><nav class="admin-actions" aria-label="작업 목록 페이지"><button :disabled="busy||overview.pagination.page<=1" @click="load(overview.pagination.page-1)">이전 페이지</button><button :disabled="busy||!overview.pagination.hasNext||overview.pagination.page>=1000" @click="load(overview.pagination.page+1)">다음 페이지</button></nav></section>
  </template>
 </main>
</template>
<style scoped>
.admin-page{max-width:1100px;margin:0 auto;padding:2rem 1rem}.admin-page section,.admin-login{margin-block:1.5rem;padding:1.25rem;border:1px solid #cbd5e1;border-radius:12px;background:#fff}.admin-login{max-width:560px;display:grid;gap:.75rem}.admin-page button,.admin-page input{padding:.7rem 1rem;border:1px solid #64748b;border-radius:6px;font:inherit}.admin-page button{cursor:pointer;background:#163b35;color:white}.admin-page button:disabled{opacity:.6;cursor:wait}.admin-actions{display:flex;gap:1rem}.admin-counts{display:flex;gap:2rem;flex-wrap:wrap}.admin-counts dd{margin:.5rem 0;font-size:1.2rem}.admin-table{overflow-x:auto}.admin-table table{width:100%;border-collapse:collapse}.admin-table th,.admin-table td{text-align:left;padding:.75rem;border-bottom:1px solid #e2e8f0;white-space:nowrap}.admin-filters{display:flex;gap:1rem;flex-wrap:wrap;align-items:end}.admin-filters label{display:grid;gap:.4rem}.admin-filters select{padding:.7rem;font:inherit;max-width:100%}.admin-page :focus-visible{outline:3px solid #3276cc;outline-offset:3px}.admin-page a{color:#163b35}
</style>

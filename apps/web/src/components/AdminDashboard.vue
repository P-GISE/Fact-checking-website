<script setup lang="ts">
import {ref,onUnmounted} from 'vue';
type Overview={observedAt:string;windowStart:string;statusCounts:Record<string,number>;recentJobs:{id:string;status:string;createdAt:string;errorCode:string|null}[];usage:{month:string;settledMicros:string;reservedMicros:string;effectiveMicros:string;pendingReservations:string}};
const enteredToken=ref(''),overview=ref<Overview|null>(null),error=ref(''),busy=ref(false);
let activeToken='',generation=0,controller:AbortController|undefined;
const statusLabels:Record<string,string>={queued:'대기',validating:'미디어 검사',transcribing:'전사',extracting:'주장 추출',retrieving:'근거 수집',validating_evidence:'근거 검증',completed:'완료',failed:'실패',cancelled:'취소',deleted:'삭제'};
function money(value:string){const micros=BigInt(value);return `$${micros/1000000n}.${(micros%1000000n).toString().padStart(6,'0')}`;}
function date(value:string){return new Date(value).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'});}
function disconnect(){generation++;controller?.abort();controller=undefined;activeToken='';enteredToken.value='';overview.value=null;busy.value=false;error.value='';}
async function load(connect=false){
 const candidate=connect?enteredToken.value:activeToken;enteredToken.value='';
 if(!candidate){error.value='관리자 접근 토큰을 입력해 주세요.';return;}
 const current=++generation;controller?.abort();controller=new AbortController();busy.value=true;error.value='';
 try{
  const response=await fetch('/api/admin/overview',{headers:{Authorization:`Bearer ${candidate}`},cache:'no-store',credentials:'omit',signal:controller.signal});
  if(!response.ok)throw new Error(response.status===503?'ADMIN_NOT_CONFIGURED':response.status===401?'ADMIN_UNAUTHORIZED':'REQUEST_FAILED');
  const data:Overview=await response.json();
  if(current!==generation)return;
  activeToken=candidate;overview.value=data;
 }catch(cause){
  if(current!==generation)return;
  activeToken='';overview.value=null;
  error.value=(cause as Error).message==='ADMIN_NOT_CONFIGURED'?'서버에 관리자 접근이 설정되지 않았습니다.':(cause as Error).message==='ADMIN_UNAUTHORIZED'?'관리자 인증 정보를 확인해 주세요.':'관리 정보에 연결하지 못했습니다. 서버 상태를 확인해 주세요.';
 }finally{if(current===generation)busy.value=false;}
}
onUnmounted(disconnect);
</script>
<template>
 <main class="admin-page">
  <header><a href="/">← FactLens AI</a><h1>운영 관리</h1><p>작업·오류·사용량을 읽기 전용으로 확인합니다.</p></header>
  <p class="muted">원본 미디어·전사·근거 본문은 표시하지 않습니다. 시간은 한국 표준시입니다.</p>
  <form v-if="!overview" @submit.prevent="load(true)" class="admin-login">
   <label for="admin-token">관리자 접근 토큰</label>
   <input id="admin-token" v-model="enteredToken" type="password" autocomplete="off" spellcheck="false" maxlength="256" :disabled="busy" required>
   <button type="submit" :disabled="busy">{{busy?'연결 중…':'관리자 연결'}}</button>
   <p class="muted">토큰은 이 페이지의 메모리에만 보관하며 새로고침·연결 종료 시 지웁니다.</p>
  </form>
  <p v-if="error" role="alert" class="error-note">{{error}}</p>
  <template v-if="overview">
   <div class="admin-actions"><button :disabled="busy" @click="load()">{{busy?'조회 중…':'새로 조회'}}</button><button @click="disconnect">연결 종료</button></div>
   <p class="muted">조회 시각: {{date(overview.observedAt)}}</p>
   <section><h2>최근 24시간 작업</h2><p>생성 시각 기준 · {{date(overview.windowStart)}}부터</p>
    <dl class="admin-counts"><div v-for="(count,status) in overview.statusCounts" :key="status"><dt>{{statusLabels[status]??status}}</dt><dd>{{count}}건</dd></div></dl>
    <p v-if="!Object.keys(overview.statusCounts).length">해당 기간에 생성된 작업이 없습니다.</p>
   </section>
   <section><h2>월 사용량 기록</h2><p>{{overview.usage.month}} · UTC 기준 · USD</p>
    <dl class="admin-counts"><div><dt>정산 기록액</dt><dd>{{money(overview.usage.settledMicros)}}</dd></div><div><dt>미정산 예약액</dt><dd>{{money(overview.usage.reservedMicros)}}</dd></div><div><dt>예산 반영액</dt><dd>{{money(overview.usage.effectiveMicros)}}</dd></div></dl>
    <p>미정산 예약 {{overview.usage.pendingReservations}}건</p><p class="muted">애플리케이션의 비용 기록입니다. 제공자의 실제 청구액·잔액·호출 한도를 확인한 값이 아닙니다.</p>
   </section>
   <section><h2>최근 작업과 오류</h2><p>최근 24시간에 생성된 작업 중 최대 20건</p><div class="admin-table"><table><thead><tr><th scope="col">작업 ID</th><th scope="col">상태</th><th scope="col">생성 시각</th><th scope="col">오류 코드</th></tr></thead><tbody><tr v-for="job in overview.recentJobs" :key="job.id"><td>{{job.id}}</td><td>{{statusLabels[job.status]??job.status}}</td><td>{{date(job.createdAt)}}</td><td>{{job.errorCode??'없음'}}</td></tr></tbody></table></div></section>
  </template>
 </main>
</template>
<style scoped>
.admin-page{max-width:1100px;margin:0 auto;padding:2rem 1rem}.admin-page section,.admin-login{margin-block:1.5rem;padding:1.25rem;border:1px solid #cbd5e1;border-radius:12px;background:#fff}.admin-login{max-width:560px;display:grid;gap:.75rem}.admin-page button,.admin-page input{padding:.7rem 1rem;border:1px solid #64748b;border-radius:6px;font:inherit}.admin-page button{cursor:pointer;background:#163b35;color:white}.admin-page button:disabled{opacity:.6;cursor:wait}.admin-actions{display:flex;gap:1rem}.admin-counts{display:flex;gap:2rem;flex-wrap:wrap}.admin-counts dd{margin:.5rem 0;font-size:1.2rem}.admin-table{overflow-x:auto}.admin-table table{width:100%;border-collapse:collapse}.admin-table th,.admin-table td{text-align:left;padding:.75rem;border-bottom:1px solid #e2e8f0;white-space:nowrap}.admin-page a{color:#163b35}
</style>

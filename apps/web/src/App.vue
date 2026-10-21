<script setup lang="ts">
import {ref,computed,nextTick,onMounted,onUnmounted} from 'vue';
import AccountSettings from './components/AccountSettings.vue';
import AccountPanel from './components/AccountPanel.vue';
import {getSession,logout,type Session} from './api';
import UploadPanel from './components/UploadPanel.vue';
import AnalysisProgress from './components/AnalysisProgress.vue';
import AnalysisReport from './components/AnalysisReport.vue';
import {upload,createAnalysis,getAnalysis,listAnalyses,deleteAnalysis} from './api';
import type {Analysis} from './types';
import {example} from './example';
const analysis=ref<Analysis|null>(null),history=ref<Analysis[]>([]),busy=ref(false),error=ref(''),notice=ref('');
type Page='home'|'new'|'history'|'settings'|'login'|'register';
const page=ref<Page>('home'),mobileMenu=ref(false),accountMenu=ref(false);
const accountBusy=ref(false),signingOut=ref(false);
const navigationBusy=computed(()=>busy.value||accountBusy.value||signingOut.value);
const authorized=computed(()=>session.value?.mode==='local'||Boolean(session.value?.user));
const accountTrigger=ref<HTMLButtonElement|null>(null),mobileTrigger=ref<HTMLButtonElement|null>(null);
const mainContent=ref<HTMLElement|null>(null);
function focusMain(){void nextTick(()=>mainContent.value?.focus());}
function navigate(target:Page){
 if(navigationBusy.value)return;
 clearPoll();analysis.value=null;error.value='';notice.value='';
 page.value=!authorized.value&&['new','history','settings'].includes(target)?'login':target;
 mobileMenu.value=false;accountMenu.value=false;
 if(target==='history'&&authorized.value)void refreshHistory();
 focusMain();
}
const accountMessage=ref('');
function accountClosed(pending:boolean){accountUpdated();accountMessage.value=pending?'회원 탈퇴가 처리됐습니다. 파일 정리를 재시도 중이며 계정 접근은 차단됐습니다.':'회원 탈퇴가 완료됐습니다.';}
function accountUpdated(){accountBusy.value=false;page.value='login';accountMenu.value=false;clearPoll();analysis.value=null;history.value=[];error.value='';notice.value='';session.value={mode:'accounts',user:null};accountMessage.value='계정이 변경됐습니다. 변경한 정보로 다시 로그인하세요.';focusMain();}
const session=ref<Session|null>(null),sessionError=ref(false);
async function initialize(){sessionError.value=false;try{session.value=await getSession();if(authorized.value){await refreshHistory();if(session.value.mode==='local')page.value='new';}}catch{sessionError.value=true;}}
async function authenticated(value:Session){accountBusy.value=false;accountMessage.value='';session.value=value;page.value='new';focusMain();await refreshHistory();}
async function signOut(){if(navigationBusy.value)return;signingOut.value=true;try{await logout();clearPoll();analysis.value=null;history.value=[];error.value='';notice.value='';session.value={mode:'accounts',user:null};page.value='home';accountMenu.value=false;mobileMenu.value=false;focusMain();}catch{error.value='로그아웃을 완료하지 못했습니다. 다시 시도해 주세요.';}finally{signingOut.value=false;}}
let timer:ReturnType<typeof setTimeout>|undefined;
let generation=0;
const messages:Record<string,string>={BUDGET_EXCEEDED:'분석 1건 또는 월 예산 한도에 도달했습니다.',BILLING_REVIEW_REQUIRED:'사용량 정산을 확인해야 합니다. 추가 유료 호출을 중단했습니다.',PROVIDER_AUTH_FAILED:'AI 또는 검색 API 인증 정보를 확인해 주세요.',PROVIDER_RATE_LIMITED:'제공자 호출 제한에 도달했습니다. 자동으로 재시도하지 않습니다.',PROVIDER_MODEL_UNAVAILABLE:'선택한 모델을 이 계정에서 사용할 수 없습니다.',PROVIDER_INPUT_LIMIT:'제공자 입력 제한을 초과해 추가 전송을 중단했습니다.',PROVIDER_RESPONSE_INVALID:'제공자 응답을 검증하지 못해 판정을 만들지 않았습니다.',PROVIDER_REQUEST_FAILED:'제공자 연결에 실패했습니다. 네트워크 허용 정책과 연결 상태를 확인해 주세요.',PROVIDER_SEARCH_LIMIT:'분석당 검색 횟수 제한에 도달했습니다.',PROVIDER_NOT_CONFIGURED:'AI 제공자 연결이 필요합니다.',SIZE_LIMIT:'100 MiB 이하 파일을 선택해 주세요.',DURATION_LIMIT:'3분 이하 파일을 선택해 주세요.',INVALID_MEDIA:'파일이 손상됐거나 지원하지 않는 미디어입니다.',FORMAT_MISMATCH:'파일 확장자와 실제 형식이 다릅니다.',NO_AUDIO:'분석할 음성 트랙이 없습니다.',TIMEOUT:'작업 제한 시간을 초과했습니다.',NETWORK_ERROR:'연결을 확인한 뒤 다시 시도해 주세요.'};
messages.PROVIDER_QUOTA_EXCEEDED='OpenAI API 사용 가능 잔액 또는 프로젝트 할당량을 확인해야 합니다. 자동으로 재시도하지 않습니다.';
function message(code:string){return messages[code]??'처리를 완료하지 못했습니다. 파일과 연결 상태를 확인해 주세요.';}
async function refreshHistory(){const token=generation;try{const result=await listAnalyses();if(token===generation)history.value=result;}catch{if(token===generation)error.value='분석 이력에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요.';}}
function clearPoll(){generation++;if(timer)clearTimeout(timer);}
async function open(id:string,userInitiated=true){
 clearPoll();const token=generation;error.value='';
 try{
  const result=await getAnalysis(id);
  if(token!==generation)return;
  analysis.value=result;page.value='new';if(userInitiated)focusMain();
  if(!['completed','failed','cancelled','deleted'].includes(result.status))timer=setTimeout(()=>open(id,false),1200);
 }catch(e){if(token===generation)error.value=message((e as Error).message);}
}
async function start(file:File,consent:boolean){
 clearPoll();const token=generation;busy.value=true;error.value='';notice.value='';
 try{const m=await upload(file);const job=await createAnalysis(m.mediaId,consent);if(token===generation)await open(job.id);await refreshHistory();}
 catch(e){if(token===generation)error.value=message((e as Error).message);}
 finally{busy.value=false;}
}
function showExample(){if(navigationBusy.value)return;clearPoll();analysis.value=example;error.value='';notice.value='';focusMain();}
async function remove(){
 if(!analysis.value||analysis.value.demo)return;
 const id=analysis.value.id;clearPoll();const token=generation;
 try{await deleteAnalysis(id);if(token===generation){analysis.value=null;notice.value='분석과 미디어를 삭제했습니다.';}await refreshHistory();}
 catch(e){if(token===generation)error.value=message((e as Error).message);}
}
function home(){navigate('home');}
function closeMenus(event:KeyboardEvent){if(event.key==='Escape'){if(accountMenu.value)accountTrigger.value?.focus();else if(mobileMenu.value)mobileTrigger.value?.focus();accountMenu.value=false;mobileMenu.value=false;}}
onMounted(()=>{initialize();document.addEventListener('keydown',closeMenus);});onUnmounted(()=>{clearPoll();document.removeEventListener('keydown',closeMenus);});
</script>
<template>
 <div class="site-shell" @click="accountMenu=false">
  <a class="skip-link" href="#main-content">본문으로 건너뛰기</a>
  <header class="site-header">
   <div class="header-inner">
    <button class="brand" aria-label="FactLens AI 홈" :disabled="navigationBusy" @click="home"><span class="brand-icon" aria-hidden="true">◉</span>FactLens <span class="ai-tag">AI</span></button>
    <button ref="mobileTrigger" class="mobile-toggle" aria-label="메뉴 열기" :aria-expanded="mobileMenu" aria-controls="primary-navigation" :disabled="navigationBusy" @click="mobileMenu=!mobileMenu">☰</button>
    <nav id="primary-navigation" class="primary-navigation" :class="{expanded:mobileMenu}" aria-label="주 메뉴">
     <button v-for="item in [{id:'home',label:'홈'},{id:'new',label:'새 분석'},{id:'history',label:'분석 이력'}]" :key="item.id" :aria-current="page===item.id?'page':undefined" :disabled="navigationBusy||!session||sessionError" @click="navigate(item.id as Page)">{{item.label}}</button>
    </nav>
    <div class="header-account">
     <template v-if="session?.user">
      <button ref="accountTrigger" class="profile-trigger"  :aria-expanded="accountMenu" aria-controls="account-dropdown" :disabled="navigationBusy" @click.stop="accountMenu=!accountMenu"><span class="avatar" aria-hidden="true">{{session.user.username.slice(0,1).toUpperCase()}}</span><span class="profile-name">{{session.user.username}}</span><span aria-hidden="true">⌄</span><span class="sr-only"> 계정 메뉴</span></button>
      <div v-if="accountMenu" id="account-dropdown" class="account-dropdown" @click.stop>
       <p>내 계정<strong>{{session.user.username}}</strong></p>
       <button @click="navigate('settings')">계정 설정 <span aria-hidden="true">↗</span></button>
       <a v-if="session.user.role==='admin'" href="/admin">운영 관리 <span aria-hidden="true">↗</span></a>
       <button class="logout-action" @click="signOut">로그아웃</button>
      </div>
     </template>
     <template v-else-if="session?.mode==='accounts'">
      <button class="header-login" :disabled="navigationBusy" @click="navigate('login')">로그인</button>
      <button class="primary header-register" :disabled="navigationBusy" @click="navigate('register')">회원가입 <span aria-hidden="true">↗</span></button>
     </template>
     <span v-else class="local-badge">비공개 작업 공간</span>
    </div>
   </div>
  </header>
  <main id="main-content" ref="mainContent" tabindex="-1" class="site-main" :class="{'landing-main':page==='home'&&!analysis}">
   <p v-if="accountMessage" class="success-note" role="status">{{accountMessage}}</p>
   <div v-if="sessionError" class="error-note" role="alert">로그인 상태를 확인할 수 없습니다. <button @click="initialize">다시 연결</button></div>
   <p v-else-if="!session" class="loading-note" role="status">로그인 상태 확인 중</p>
   <div v-if="error" class="error-note" role="alert">{{error}}</div>
   <p v-if="notice" class="success-note" role="status">{{notice}}</p>
   <template v-if="page==='home'&&!analysis">
    <section class="hero">
     <div class="hero-copy"><div class="eyebrow"><span></span>근거로 살펴보는 새로운 관점</div><h1>영상 속 주장,<br><em>근거로 다시 보기.</em></h1><p>넘쳐나는 정보 속, 확인할 수 있는 것부터.<br>영상의 주장을 원문 근거와 대조하고<br class="desktop-break"> 판단에 필요한 이유와 한계를 함께 살펴보세요.</p>
      <div class="hero-actions"><button class="primary" :disabled="navigationBusy||!session||sessionError" @click="navigate('new')">분석 시작하기 <span aria-hidden="true">↗</span></button><button class="secondary" :disabled="navigationBusy" @click="showExample">예시 보고서 보기 <span aria-hidden="true">→</span></button></div>
      <div class="hero-meta"><span>MP4 · MP3 · WAV</span><span>최대 3분</span><span>계정별 비공개</span></div>
     </div>
     <div class="hero-visual" aria-label="분석 보고서 구성 안내 — 실제 분석 결과가 아닙니다">
      <div class="visual-label"><span class="status-dot"></span>CLAIM → EVIDENCE → INSIGHT</div>
      <div class="preview-window"><div class="preview-top"><span class="preview-dots">● ● ●</span><span>보고서 구성 미리보기</span><span>↗</span></div><div class="preview-body"><div class="preview-media"><span class="preview-play">▶</span><div><span>영상 속 한 문장</span><strong>확인할 주장을 찾습니다.</strong></div><span class="preview-time">00:12</span></div><div class="preview-connector"></div><div class="preview-evidence"><span class="preview-icon">≡</span><div><span>원문 근거</span><strong>주장과 출처를 나란히.</strong><p>인용 · 기간 · 대상 · 수치 대조</p></div></div><div class="preview-result"><span>판단의 이유까지 투명하게</span><span>근거와 한계 확인 →</span></div></div></div>
      <div class="visual-footnote">화면 구성 예시 · 실제 분석 결과가 아닙니다</div>
     </div>
    </section>
    <section class="home-process" aria-labelledby="process-title"><div class="process-heading"><span class="section-label">HOW FACTLENS WORKS</span><h2 id="process-title">결론에 앞서, 확인하는 과정.</h2><p>파일 하나에서 시작해, 근거를 살피는 보고서까지.</p></div><div class="process-grid"><article><span class="process-number">01 / UPLOAD</span><h3>확인할 파일을 올리고</h3><p>한국어 영상이나 음성을 선택하세요.<br>외부 AI 처리에 동의한 뒤 분석합니다.</p></article><article><span class="process-number">02 / CROSS-CHECK</span><h3>주장을 원문과 대조하고</h3><p>음성 속 개별 주장을 추출하고<br>확인 가능한 외부 자료를 살펴봅니다.</p></article><article><span class="process-number">03 / UNDERSTAND</span><h3>근거와 한계를 함께 읽어요</h3><p>자료가 부족하면 판정을 유보합니다.<br>확인한 범위와 불확실성을 설명합니다.</p></article></div></section>
   </template>
   <section v-else-if="page==='login'||page==='register'" class="auth-layout"><div class="auth-intro"><div class="eyebrow"><span></span>YOUR PRIVATE WORKSPACE</div><h2>확인한 근거가,<br>나의 기록이 되도록.</h2><p>내 분석과 보고서를 한곳에서 관리하세요.<br>파일과 이력은 로그인한 계정에서만 볼 수 있습니다.</p><button class="text-button" @click="home">← 홈으로 돌아가기</button></div><AccountPanel :key="page" :initial-mode="page==='register'?'register':'login'" @pending="accountBusy=$event" @authenticated="authenticated"/></section>
   <section v-else-if="page==='settings'&&session?.user" class="settings-page"><div class="page-intro"><div class="eyebrow"><span></span>ACCOUNT SETTINGS</div><h1>계정 설정</h1><p>내 계정 정보와 보안 설정을 관리하세요.</p></div><AccountSettings :user="session.user" @pending="accountBusy=$event" @changed="accountUpdated" @closed="accountClosed"/></section>
   <section v-else-if="page==='history'&&authorized" class="history-page"><div class="page-intro"><div class="eyebrow"><span></span>YOUR LIBRARY</div><h1>분석 이력</h1><p>이전에 확인한 주장과 근거를 다시 살펴보세요.</p></div><div class="history-list"><button v-for="item in history" :key="item.id" class="history-item" @click="open(item.id)"><span class="history-file" aria-hidden="true">▤</span><span><strong>{{new Date(item.createdAt).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})}}</strong><small>{{item.status==='completed'?'분석 완료':item.status==='failed'?'처리 확인 필요':'분석 진행'}}</small></span><span aria-hidden="true">→</span></button><div v-if="!history.length" class="empty-library"><span aria-hidden="true">▤</span><h2>첫 번째 분석을 시작해 보세요.</h2><p>분석한 파일과 보고서가 이곳에 모입니다.</p><button class="primary" @click="navigate('new')">새 분석 시작</button></div></div></section>
   <template v-else>
    <div class="page-intro"><div class="eyebrow"><span></span>{{analysis?'ANALYSIS REPORT':'NEW ANALYSIS'}}</div><h1>{{analysis?'판정의 이유까지, 투명하게.':'영상 속 주장, 근거로 다시 보기.'}}</h1><p>{{analysis?'주장별 근거와 확인한 범위를 살펴보세요.':'확인하고 싶은 파일을 선택하면, 주장과 근거를 하나씩 살펴봅니다.'}}</p></div>
    <div v-if="!analysis&&authorized" class="start-grid"><UploadPanel :busy="busy" @start="start" @example="showExample"/><aside class="guide-card"><span class="section-label">BEFORE YOU START</span><h2>알아두면 좋은<br>분석의 범위.</h2><ol><li><span>01</span><div><strong>개별 주장을 살펴봅니다</strong><p>영상 전체의 진실을 보증하거나<br>딥페이크 여부를 판별하지 않습니다.</p></div></li><li><span>02</span><div><strong>근거가 부족하면 유보합니다</strong><p>자료가 없다는 이유만으로<br>거짓이라고 판단하지 않습니다.</p></div></li><li><span>03</span><div><strong>화면 분석에는 한계가 있습니다</strong><p>내장 자막과 표본 화면을 살피며<br>OCR 오류·표본 누락이 있을 수 있습니다.</p></div></li></ol></aside></div>
    <template v-else-if="analysis"><div class="analysis-toolbar"><button class="text-button" @click="navigate('new')">← 새 분석으로</button><button v-if="!analysis.demo" class="danger-button" @click="remove">분석 삭제</button><button v-else class="text-button" @click="home">예시 닫기</button></div><div v-if="analysis.status==='failed'" class="failure-card" role="status"><span class="upload-icon">!</span><h2>{{message(analysis.error?.code??'')}}</h2><p>이 작업의 실제 AI 분석은 완료되지 않았습니다.</p><small>오류 코드: {{analysis.error?.code}}</small></div><AnalysisReport v-else-if="analysis.status==='completed'" :analysis="analysis"/><AnalysisProgress v-else :analysis="analysis"/></template>
   </template>
   <footer class="page-footer"><span>FactLens AI</span><span>근거 기반 의사결정 지원 · 모든 사실의 진실을 보증하지 않습니다.</span><span class="footer-motto">A clearer view, with evidence.</span></footer>
  </main>
 </div>
</template>

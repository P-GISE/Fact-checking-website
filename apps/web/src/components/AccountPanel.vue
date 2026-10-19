<script setup lang="ts">
import {ref} from 'vue';
import {authenticate,type Session} from '../api';
const emit=defineEmits<{authenticated:[session:Session]}>();
const mode=ref<'login'|'register'>('login');
const username=ref(''),password=ref(''),confirmation=ref('');
const busy=ref(false),visible=ref(false),error=ref('');
function switchMode(){
 mode.value=mode.value==='login'?'register':'login';
 password.value='';confirmation.value='';error.value='';visible.value=false;
}
async function submit(){
 if(busy.value)return;
 error.value='';
 if(mode.value==='register'&&password.value!==confirmation.value){error.value='비밀번호 확인이 일치하지 않습니다.';return;}
 busy.value=true;
 try{const session=await authenticate(mode.value,username.value,password.value);emit('authenticated',session);}
 catch(e){
  const code=(e as Error).message;
  error.value=code==='AUTH_RATE_LIMITED'?'시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.':
   code==='USERNAME_UNAVAILABLE'?'이미 사용 중인 사용자 이름입니다. 다른 이름을 입력해 주세요.':
   code==='AUTH_FAILED'?'사용자 이름 또는 비밀번호가 올바르지 않습니다.':
   '요청을 완료하지 못했습니다. 연결 상태와 입력 내용을 확인하고 다시 시도해 주세요.';
 }
 finally{password.value='';confirmation.value='';busy.value=false;}
}
</script>
<template>
 <section class="account-panel" aria-labelledby="account-title">
  <p class="brand">FactLens AI</p>
  <h1 id="account-title">{{mode==='login'?'로그인':'회원가입'}}</h1>
  <p class="intro">{{mode==='login'?'내 분석과 이력을 이어서 확인하세요.':'나만의 계정으로 분석 파일과 이력을 관리하세요.'}}</p>
  <form @submit.prevent="submit" :aria-busy="busy">
   <label for="account-username">사용자 이름</label>
   <input id="account-username" v-model="username" name="username" autocomplete="username" pattern="[a-z0-9_-]{3,32}" minlength="3" maxlength="32" required :disabled="busy" aria-describedby="username-help" autocapitalize="none" :spellcheck="false">
   <small id="username-help">영문 소문자·숫자·밑줄·하이픈 3~32자</small>
   <div class="password-label"><label for="account-password">비밀번호</label><button type="button" class="text-button" :disabled="busy" :aria-pressed="visible" aria-controls="account-password" @click="visible=!visible">{{visible?'비밀번호 숨기기':'비밀번호 표시'}}</button></div>
   <input id="account-password" v-model="password" name="password" :type="visible?'text':'password'" :autocomplete="mode==='register'?'new-password':'current-password'" minlength="12" maxlength="128" required :disabled="busy" aria-describedby="password-help">
   <small id="password-help">12~128자</small>
   <template v-if="mode==='register'">
    <label for="account-confirmation">비밀번호 확인</label>
    <input id="account-confirmation" v-model="confirmation" name="confirmation" :type="visible?'text':'password'" autocomplete="new-password" minlength="12" maxlength="128" required :disabled="busy">
   </template>
   <p v-if="error" class="error" role="alert">{{error}}</p>
   <button class="primary" type="submit" :disabled="busy">{{busy?'처리 중…':mode==='login'?'로그인':'계정 만들기'}}</button>
  </form>
  <p class="switch">{{mode==='login'?'아직 계정이 없으신가요?':'이미 계정이 있으신가요?'}} <button type="button" class="text-button" :disabled="busy" @click="switchMode">{{mode==='login'?'회원가입':'로그인으로 돌아가기'}}</button></p>
  <p class="notice">분석 파일과 이력은 로그인한 계정에서만 접근할 수 있습니다. 비밀번호 분실 시 재설정 기능은 아직 제공하지 않습니다.</p>
 </section>
</template>
<style scoped>
.account-panel{box-sizing:border-box;max-width:460px;margin:6vh auto;padding:2rem;background:#fff;border:1px solid #dce3eb;border-radius:16px;box-shadow:0 12px 36px #172b4d0a;color:#172b4d}.brand{font-weight:700;color:#2459a9;margin:0 0 1rem}.account-panel h1{margin:0;font-size:1.8rem}.intro{color:#526477;line-height:1.6}.account-panel label{display:block;font-weight:600;margin:1.1rem 0 .4rem}.account-panel input{box-sizing:border-box;display:block;width:100%;padding:.8rem;border:1px solid #8b9bae;border-radius:8px;font:inherit}.account-panel small{display:block;color:#526477;margin-top:.4rem}.password-label{display:flex;align-items:baseline;justify-content:space-between;gap:.5rem}.text-button{border:0;background:none;color:#2459a9;padding:.3rem;cursor:pointer;font:inherit;text-decoration:underline}.primary{width:100%;padding:.85rem;margin-top:1.5rem;border:0;border-radius:8px;background:#2459a9;color:white;font:inherit;font-weight:600;cursor:pointer}.account-panel button:disabled{opacity:.6;cursor:wait}.account-panel :focus-visible{outline:3px solid #3276cc;outline-offset:3px}.error{background:#fff1f0;color:#9b2020;padding:.75rem;border-radius:8px;line-height:1.5}.switch{text-align:center;line-height:1.6}.notice{border-top:1px solid #dce3eb;padding-top:1rem;font-size:.85rem;color:#526477;line-height:1.6}@media(max-width:520px){.account-panel{margin:1rem;padding:1.25rem}.password-label{flex-wrap:wrap}}
</style>

<script setup lang="ts">
import {ref} from 'vue';
import {authenticate,type Session} from '../api';
const emit=defineEmits<{authenticated:[session:Session]}>();
const username=ref(''),password=ref(''),busy=ref(false),error=ref('');
async function submit(action:'login'|'register'){
 if(busy.value)return;busy.value=true;error.value='';
 try{const session=await authenticate(action,username.value,password.value);password.value='';emit('authenticated',session);}
 catch(e){const code=(e as Error).message;error.value=code==='AUTH_RATE_LIMITED'?'잠시 후 다시 시도해 주세요.':code==='USERNAME_UNAVAILABLE'?'다른 사용자 이름을 선택해 주세요.':'사용자 이름과 비밀번호를 확인해 주세요.';}
 finally{password.value='';busy.value=false;}
}
</script>
<template><section class="account-panel"><h1>계정으로 시작하기</h1><p>분석 파일과 이력은 로그인한 계정에서만 접근할 수 있습니다.</p><form @submit.prevent="submit('login')"><label>사용자 이름<input v-model="username" name="username" autocomplete="username" pattern="[a-z0-9_-]{3,32}" minlength="3" maxlength="32" required></label><small>소문자·숫자·밑줄·하이픈 3~32자</small><label>비밀번호<input v-model="password" name="password" type="password" autocomplete="current-password" minlength="12" maxlength="128" required></label><small>12~128자. 비밀번호 재설정은 아직 제공하지 않습니다.</small><p v-if="error" role="alert">{{error}}</p><div><button type="submit" :disabled="busy">로그인</button><button type="submit" :disabled="busy" @click.prevent="submit('register')">계정 만들기</button></div></form></section></template>
<style scoped>
.account-panel{max-width:480px;margin:10vh auto;padding:1.5rem}.account-panel label{display:block;margin:1rem 0 .3rem}.account-panel input{display:block;width:100%;padding:.7rem;border:1px solid #aab7c4;border-radius:6px}.account-panel button{padding:.7rem 1rem;margin:1rem .6rem 0 0;cursor:pointer}.account-panel small{color:#526477}
</style>

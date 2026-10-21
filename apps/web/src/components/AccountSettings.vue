<script setup lang="ts">
import {ref} from 'vue';
import {closeAccount,updateAccount,type Session} from '../api';
const props=defineProps<{user:NonNullable<Session['user']>}>();
const emit=defineEmits<{pending:[value:boolean];changed:[];closed:[pending:boolean]}>();
const username=ref(props.user.username),currentPassword=ref(''),newPassword=ref(''),confirmation=ref('');
const busy=ref(false),error=ref(''),closePassword=ref(''),consent=ref(false);
async function remove(){
 if(busy.value||!consent.value)return;busy.value=true;emit('pending',true);error.value='';
 try{const result=await closeAccount(closePassword.value);emit('closed',Boolean(result?.cleanupPending));}
 catch(cause){const code=(cause as Error).message;error.value=code==='ACCOUNT_BUSY'?'진행 중인 분석이나 업로드가 있습니다. 완료 후 다시 시도해 주세요.':code==='ADMIN_CLOSURE_BLOCKED'?'관리자 계정은 여기서 탈퇴할 수 없습니다.':code==='AUTH_FAILED'||code==='AUTH_REQUIRED'?'현재 비밀번호 또는 로그인 상태를 확인해 주세요.':'탈퇴를 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.';}
 finally{closePassword.value='';busy.value=false;emit('pending',false);}
}
async function save(){
 if(busy.value)return;error.value='';
 if(newPassword.value!==confirmation.value){error.value='새 비밀번호 확인이 일치하지 않습니다.';return;}
 busy.value=true;emit('pending',true);
 try{await updateAccount(username.value,currentPassword.value,newPassword.value||undefined);emit('changed');}
 catch(cause){const code=(cause as Error).message;error.value=code==='USERNAME_UNAVAILABLE'?'이미 사용 중인 사용자 이름입니다.':code==='AUTH_FAILED'||code==='AUTH_REQUIRED'?'현재 비밀번호 또는 로그인 상태를 확인해 주세요.':code==='AUTH_RATE_LIMITED'?'시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.':'변경하지 못했습니다. 연결 상태와 입력 내용을 확인해 주세요.';}
 finally{currentPassword.value='';newPassword.value='';confirmation.value='';busy.value=false;emit('pending',false);}
}
</script>
<template>
 <section class="account-settings">
  <h2>내 계정 관리</h2>
  <p>사용자 이름: {{user.username}} · {{user.role==='admin'?'관리자':'일반 회원'}}</p>
  <p>변경하면 모든 기기에서 로그아웃됩니다. 변경한 정보로 다시 로그인하세요.</p>
  <form @submit.prevent="save" :aria-busy="busy">
   <label for="settings-username">변경할 사용자 이름</label><input id="settings-username" v-model="username" autocomplete="username" pattern="[a-z0-9_-]{3,32}" minlength="3" maxlength="32" required :disabled="busy" aria-describedby="settings-name-help"><small id="settings-name-help">영문 소문자·숫자·밑줄·하이픈 3~32자</small>
   <label for="settings-current">현재 비밀번호</label><input id="settings-current" v-model="currentPassword" type="password" autocomplete="current-password" minlength="12" maxlength="128" required :disabled="busy">
   <label for="settings-new">새 비밀번호 (선택)</label><input id="settings-new" v-model="newPassword" type="password" autocomplete="new-password" minlength="12" maxlength="128" :disabled="busy" aria-describedby="settings-password-help"><small id="settings-password-help">12~128자. 바꾸지 않으려면 비워두세요.</small>
   <label for="settings-confirm">새 비밀번호 확인</label><input id="settings-confirm" v-model="confirmation" type="password" autocomplete="new-password" minlength="12" maxlength="128" :required="Boolean(newPassword)" :disabled="busy">
   <p v-if="error" role="alert">{{error}}</p><button type="submit" :disabled="busy">{{busy?'변경 중…':'계정 변경 저장'}}</button>
  </form>
  <details v-if="user.role!=='admin'" class="closure">
   <summary>회원 탈퇴</summary>
   <p>로그인 정보와 분석 내용·파일을 삭제합니다. 비용 기록과 개인 식별정보를 제거한 연결 ID는 운영 정산을 위해 보존합니다. 이 작업은 되돌릴 수 없습니다.</p>
   <p>진행 중인 분석·업로드가 있으면 완료 후 다시 시도하세요. 대기 작업은 폐기됩니다.</p>
   <form @submit.prevent="remove">
    <label for="closure-password">탈퇴 확인 비밀번호</label><input id="closure-password" v-model="closePassword" type="password" autocomplete="current-password" minlength="12" maxlength="128" required :disabled="busy">
    <label><input v-model="consent" type="checkbox" required :disabled="busy">삭제 범위와 비용 기록 보존을 확인했으며 회원 탈퇴에 동의합니다.</label>
    <button type="submit" :disabled="busy||!consent">{{busy?'처리 중…':'회원 탈퇴 확정'}}</button>
   </form>
  </details>
 </section>
</template>
<style scoped>
.account-settings{padding:32px;margin-bottom:1.5rem;border:1px solid #e2e8f0;border-radius:16px;background:white}.account-settings h2{font-size:20px}.account-settings>p{color:#64748b}.account-settings button{border-radius:8px;background:#2563eb;color:white;font-weight:600}.account-settings .closure button{background:#fff1f2;color:#b42338}.account-settings label{font-size:13px;font-weight:500}.account-settings form{max-width:560px}.account-settings input{background:#f8fafc}.closure summary{color:#b42338}.closure{margin-top:1.5rem;border-top:1px solid #ddd;padding-top:1rem}.account-settings input[type=checkbox]{display:inline;width:auto}.account-settings summary{cursor:pointer;font-weight:600}.account-settings form{max-width:440px;display:grid;gap:.5rem}.account-settings input{box-sizing:border-box;width:100%;padding:.7rem;font:inherit;border:1px solid #8b9bae;border-radius:6px}.account-settings label{margin-top:.5rem}.account-settings button{padding:.75rem;cursor:pointer}.account-settings small{color:#526477}.account-settings :focus-visible{outline:3px solid #3276cc;outline-offset:3px}
</style>

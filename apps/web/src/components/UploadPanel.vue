<script setup lang="ts">
import {ref} from 'vue';
const props=defineProps<{busy:boolean}>();
const emit=defineEmits<{start:[file:File,consent:boolean];example:[]}>();
const selected=ref<File|null>(null),consent=ref(false),error=ref('');
function choose(file?:File){error.value='';if(!file)return;if(!/\.(mp4|mp3|wav)$/i.test(file.name)){error.value='MP4, MP3 또는 WAV 파일을 선택해 주세요.';return;}if(file.size>104857600){error.value='100 MiB 이하 파일을 선택해 주세요.';return;}selected.value=file;}
function picked(event:Event){choose((event.target as HTMLInputElement).files?.[0]);}
function dropped(event:DragEvent){event.preventDefault();choose(event.dataTransfer?.files[0]);}
</script>
<template>
<section class="upload-card" aria-labelledby="upload-title">
 <div class="section-label">새로운 분석 <span>01 / UPLOAD</span></div>
 <h2 id="upload-title">확인하고 싶은 파일을 올려주세요.</h2><p class="muted">최대 3분의 한국어 뉴스형 영상·음성을 지원합니다.</p>
 <label class="drop-zone" @dragover.prevent @drop="dropped"><input type="file" accept=".mp4,.mp3,.wav" aria-label="분석할 파일" :disabled="busy" @change="picked"><span class="upload-icon" aria-hidden="true">↑</span><strong>{{selected?selected.name:'파일을 끌어 놓거나 선택하세요'}}</strong><span>MP4 · MP3 · WAV <i>최대 100 MiB</i></span></label>
 <p v-if="error" role="alert" class="error-note">{{error}}</p>
 <label class="consent"><input type="checkbox" v-model="consent" aria-label="외부 AI 처리 동의" :disabled="busy"><span>파일 사용 권한이 있으며, 음성·전사·주장 등 분석에 필요한 데이터의 외부 AI 전송에 동의합니다. 제공자 연결 전에는 외부로 전송하지 않습니다.</span></label>
 <button class="primary wide" :disabled="!selected||!consent||busy" @click="selected&&emit('start',selected,consent)">{{busy?'업로드하고 있습니다…':'분석 시작'}} <span aria-hidden="true">↗</span></button>
 <div class="upload-footer"><span>비공개 개발용 · 24시간 후 자동 삭제</span><button class="text-button" @click="emit('example')">예시 보고서 보기 <span aria-hidden="true">→</span></button></div>
</section>
</template>

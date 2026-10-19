import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';

test('explicit example report, evidence selection, keyboard and mobile',async({page})=>{
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'영상 속 주장, 근거로 다시 보기.'})).toBeVisible();
 await page.getByRole('button',{name:'예시 보고서 보기'}).click();
 await expect(page.getByText('가상 예시 · 실제 분석 결과가 아닙니다')).toBeVisible();
 await page.getByRole('button',{name:/통계 수치가 50%/}).click();
 await expect(page.getByRole('heading',{name:'근거 대조'})).toBeVisible();
 await expect(page.getByText('2025년 가상 지역의 예시 지표는 5%입니다.')).toBeVisible();
 await expect(page.getByText('자막·화면 맥락은 분석하지 않았습니다.')).toBeVisible();
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('real upload reaches explicit provider error and can be deleted',async({page})=>{
 const dir=mkdtempSync(path.join(tmpdir(),'factlens-e2e-'));const file=path.join(dir,'sample.wav');
 execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','sine=duration=1',file]);
 try{
  await page.goto('/');
  await page.getByLabel('분석할 파일').setInputFiles(file);
  await page.getByLabel('외부 AI 처리 동의').check();
  await page.getByRole('button',{name:'분석 시작',exact:true}).click();
  await expect(page.getByText('AI 제공자 연결이 필요합니다.')).toBeVisible({timeout:20000});
  await page.getByRole('button',{name:'분석 삭제',exact:true}).click();
  await expect(page.getByText('분석과 미디어를 삭제했습니다.')).toBeVisible();
 }finally{rmSync(dir,{recursive:true});}
});

test('persisted report links claim time to player and renders evidence as text',async({page,request})=>{
 const {default:pg}=await import('pg');
 const pool=new pg.Pool({connectionString:process.env.DATABASE_URL});
 const dir=mkdtempSync(path.join(tmpdir(),'factlens-report-')),file=path.join(dir,'report.wav');
 execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','sine=duration=30',file]);
 let id='';
 try{
  const {readFileSync}=await import('node:fs');
  const u=await request.post('/api/media/upload',{multipart:{file:{name:'report.wav',mimeType:'audio/wav',buffer:readFileSync(file)}}});
  const mediaId=(await u.json()).mediaId;
  const {randomUUID}=await import('node:crypto');id=randomUUID();
  const missing={state:'missing',value:null,candidates:[]};
  const sourceTrace={parserVersion:'static-text-v1',requestedUrl:'https://example.org/start',finalUrl:'https://example.org/report',retrievedAt:'2026-10-18T00:00:00+00:00',contentType:'text/html',bodySha256:'a'.repeat(64),textSha256:'b'.repeat(64),textLength:30,blocks:[{kind:'paragraph',position:0,length:30}],structureComplete:true,publication:{publisher:{state:'observed',value:'<img src=x onerror=window.traceInjected=true>',candidates:[{value:'<img src=x onerror=window.traceInjected=true>',locator:'meta[0]@content'}]},publishedAt:missing,modifiedAt:missing},quoteOccurrences:2,quoteBlockIndexes:[],extractionTruncated:false};
  const sourceReview={version:'source-review-v1',registryVersion:'browser-fixture-v1',identity:{status:'publisher_conflict',publisherId:'fixture-publisher',registeredName:'<img src=x onerror=window.registryInjected=true>'},independence:'unverified',groupId:'c'.repeat(64),groupSize:2,relatedUrls:['https://other.example/original'],signals:['DECLARED_SOURCE_LINK']};
  const result={scope:'audio_only',demo:false,claims:[{id:randomUUID(),text:'테스트 자료의 주장',contextText:'전사 원문 <img src=x onerror=window.contextInjected=true> 끝',startSeconds:12,endSeconds:18,subject:null,period:null,metric:null,value:null,unit:null,eligibility:'checkable',verdict:'INSUFFICIENT',evidence:[{url:'javascript:alert(1)',title:'테스트 자료',quote:'<img src=x onerror="window.injected=true">',position:0,publisher:null,publishedAt:null,relation:'INSUFFICIENT',usable:false,reasons:['QUOTE_NOT_VERIFIED'],lineage:'test',sourceTrace,sourceReview}]}],limitations:['테스트 전용 고정 출력. 실제 AI 추론 아님.'],usage:{}};
  await pool.query("INSERT INTO jobs(id,media_id,consent,status,result) VALUES($1,$2,true,'completed',$3)",[id,mediaId,JSON.stringify(result)]);
  await page.goto('/');
  await page.locator('.history-item').first().click();
  const player=page.locator('video');
  await expect(player).toBeVisible();
  await expect.poll(()=>player.evaluate((v:HTMLVideoElement)=>v.readyState)).toBeGreaterThan(0);
  await page.getByRole('button',{name:/테스트 자료의 주장/}).click();
  await expect.poll(()=>player.evaluate((v:HTMLVideoElement)=>Math.round(v.currentTime))).toBe(12);
  await expect(page.getByText('<img src=x onerror="window.injected=true">',{exact:true})).toBeVisible();
  await page.getByText('전사 원문 맥락',{exact:true}).click();
  await expect(page.getByText('전사 원문 <img src=x onerror=window.contextInjected=true> 끝',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>Object.hasOwn(window,'contextInjected'))).toBe(false);
  expect(await page.evaluate(()=>Object.hasOwn(window,'injected'))).toBe(false);
  await expect(page.getByText('원문 수집·발행 정보',{exact:true})).toBeVisible();
  await page.getByText('원문 수집·발행 정보',{exact:true}).click();
  await expect(page.getByText('페이지에서 관측한 정보이며 출처 인증이나 독립성 확인을 뜻하지 않습니다.')).toBeVisible();
  await expect(page.getByText('<img src=x onerror=window.traceInjected=true>',{exact:true})).toBeVisible();
  await expect(page.getByText('인용 위치 미확정 · 동일 인용 2곳',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>Object.hasOwn(window,'traceInjected'))).toBe(false);
  await expect(page.getByText('출처 등록·재인용 검토',{exact:true})).toBeVisible();
  await page.getByText('출처 등록·재인용 검토',{exact:true}).click();
  await expect(page.getByText('출처 독립성은 확인되지 않았습니다.',{exact:true})).toBeVisible();
  await expect(page.getByText('가능한 공통 출처 그룹 · 2개 근거',{exact:true})).toBeVisible();
  await expect(page.getByText('<img src=x onerror=window.registryInjected=true>',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>Object.hasOwn(window,'registryInjected'))).toBe(false);
  expect(await page.locator('a[href^="javascript:"]').count()).toBe(0);
 }finally{
  if(id)await request.delete(`/api/analyses/${id}`);
  await pool.end();rmSync(dir,{recursive:true});
 }
});

test('late polling response cannot replace a newly selected example',async({page})=>{
 const item={id:'late',status:'queued',stage:'queued',createdAt:'2026-10-16T00:00:00Z',expiresAt:'',scope:'audio_only',demo:false,error:null,claims:[],limitations:[],usage:{}};
 await page.route('**/api/analyses',route=>route.fulfill({json:[item]}));
 let pending:import('@playwright/test').Route|undefined;
 await page.route('**/api/analyses/late',async route=>{pending=route;});
 await page.goto('/');await page.locator('.history-item').first().click();
 await expect.poll(()=>Boolean(pending)).toBe(true);
 await page.getByRole('button',{name:'예시 보고서 보기'}).click();
 const response=page.waitForResponse(r=>r.url().endsWith('/api/analyses/late'));
 await pending!.fulfill({json:item});await response;
 await page.waitForTimeout(100);
 await expect(page.getByText('가상 예시 · 실제 분석 결과가 아닙니다')).toBeVisible();
});

test('budget rejection is explained without suggesting successful analysis',async({page})=>{
 const item={id:'budget',status:'failed',stage:'failed',createdAt:'2026-10-16T00:00:00Z',expiresAt:'',scope:'audio_only',demo:false,error:{code:'BUDGET_EXCEEDED',message:'BUDGET_EXCEEDED'},claims:[],limitations:[],usage:{}};
 await page.route('**/api/analyses',route=>route.fulfill({json:[item]}));
 await page.route('**/api/analyses/budget',route=>route.fulfill({json:item}));
 await page.goto('/');await page.locator('.history-item').first().click();
 await expect(page.getByRole('heading',{name:'분석 1건 또는 월 예산 한도에 도달했습니다.'})).toBeVisible();
 await expect(page.getByText('이 작업의 실제 AI 분석은 완료되지 않았습니다.')).toBeVisible();
});

test('admin access is explicit, read-only and forgotten on logout',async({page})=>{
 await page.goto('/admin');
 await expect(page.getByRole('heading',{name:'운영 관리'})).toBeVisible();
 await page.getByLabel('관리자 접근 토큰').fill('invalid-token');
 await page.getByRole('button',{name:'관리자 연결',exact:true}).click();
 const token=process.env.FACTLENS_ADMIN_TOKEN;
 if(!token){
  await expect(page.getByRole('alert')).toContainText('관리자 접근이 설정되지 않았습니다');
  return;
 }
 await expect(page.getByRole('alert')).toContainText('관리자 인증 정보를 확인');
 await page.getByLabel('관리자 접근 토큰').fill(token);
 await page.getByRole('button',{name:'관리자 연결',exact:true}).click();
 await expect(page.getByRole('heading',{name:'월 사용량 기록'})).toBeVisible();
 await expect(page.getByText('미정산 예약액', {exact:true})).toBeVisible();
 await page.getByRole('button',{name:'연결 종료',exact:true}).click();
 await expect(page.getByRole('heading',{name:'월 사용량 기록'})).toHaveCount(0);
 await expect(page.getByLabel('관리자 접근 토큰')).toHaveValue('');
 expect(await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length}))).toEqual({local:0,session:0});
});

test('table quote displays physical source location without claiming verified meaning',async({page,request})=>{
 const {default:pg}=await import('pg');const pool=new pg.Pool({connectionString:process.env.DATABASE_URL});
 const dir=mkdtempSync(path.join(tmpdir(),'factlens-table-')),file=path.join(dir,'table.wav');
 execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','sine=duration=1',file]);let id='';
 try{
  const {readFileSync}=await import('node:fs');const {randomUUID}=await import('node:crypto');
  const uploaded=await request.post('/api/media/upload',{multipart:{file:{name:'table.wav',mimeType:'audio/wav',buffer:readFileSync(file)}}});
  const mediaId=(await uploaded.json()).mediaId;id=randomUUID();const quote='2025년 한국 고용률 50%';
  const missing={state:'missing',value:null,candidates:[]};
  const sourceTrace={parserVersion:'static-text-v3',requestedUrl:'https://example.org/table',finalUrl:'https://example.org/table',retrievedAt:'2026-10-19T00:00:00Z',contentType:'text/html',bodySha256:'a'.repeat(64),textSha256:'b'.repeat(64),textLength:quote.length,blocks:[{kind:'table_cell',position:0,length:quote.length,tableLocation:{tableIndex:0,rowIndex:1,cellIndex:0,rowSpan:1,columnSpan:2}}],structureComplete:true,publication:{publisher:missing,publishedAt:missing,modifiedAt:missing},quoteOccurrences:1,quoteBlockIndexes:[0],extractionTruncated:false};
  const result={scope:'audio_only',demo:false,claims:[{id:randomUUID(),text:'표 위치 추적 테스트',startSeconds:0,endSeconds:1,verdict:'INSUFFICIENT',evidence:[{url:sourceTrace.finalUrl,title:'합성 표',quote,position:0,publisher:null,publishedAt:null,relation:'INSUFFICIENT',usable:false,reasons:['TABLE_CONTEXT_UNVERIFIED'],lineage:'example.org',sourceTrace}]}],limitations:['합성 고정 출력이며 실제 AI 분석이 아닙니다.'],usage:{}};
  await pool.query("INSERT INTO jobs(id,media_id,consent,status,result) VALUES($1,$2,true,'completed',$3)",[id,mediaId,JSON.stringify(result)]);
  await page.goto('/');await page.locator('.history-item').first().click();
  await page.getByText('원문 수집·발행 정보',{exact:true}).click();
  await expect(page.getByText('표 1 · 행 2 · 셀 1 (원문 순서)',{exact:true})).toBeVisible();
  await expect(page.getByText('행 병합 표기: 1 · 열 병합 표기: 2',{exact:true})).toBeVisible();
  await expect(page.getByText('행·셀 번호는 원문 태그 순서입니다. 단위·분모·주석의 의미는 검증되지 않았습니다.',{exact:true})).toBeVisible();
 }finally{if(id)await request.delete(`/api/analyses/${id}`);await pool.end();rmSync(dir,{recursive:true});}
});

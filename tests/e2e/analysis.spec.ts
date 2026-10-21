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
  await page.getByRole('button',{name:'분석 이력',exact:true}).click();await page.locator('.history-item').first().click();
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
 await page.goto('/');await page.getByRole('button',{name:'분석 이력',exact:true}).click();await page.locator('.history-item').first().click();
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
 await page.goto('/');await page.getByRole('button',{name:'분석 이력',exact:true}).click();await page.locator('.history-item').first().click();
 await expect(page.getByRole('heading',{name:'분석 1건 또는 월 예산 한도에 도달했습니다.'})).toBeVisible();
 await expect(page.getByText('이 작업의 실제 AI 분석은 완료되지 않았습니다.')).toBeVisible();
});

test('local development does not implicitly grant administrator access',async({page})=>{
 await page.goto('/admin');
 await expect(page.getByRole('heading',{name:'운영 대시보드'})).toBeVisible();
 await expect(page.getByRole('alert')).toContainText('관리자 계정으로 로그인해야');
 await expect(page.getByLabel('관리자 접근 토큰')).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'월 사용량 기록'})).toHaveCount(0);
});

test('table quote displays physical source location without claiming verified meaning',async({page,request})=>{
 const {default:pg}=await import('pg');const pool=new pg.Pool({connectionString:process.env.DATABASE_URL});
 const dir=mkdtempSync(path.join(tmpdir(),'factlens-table-')),file=path.join(dir,'table.wav');
 execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','sine=duration=1',file]);let id='';
 try{
  const {readFileSync}=await import('node:fs');const {randomUUID}=await import('node:crypto');
  const uploaded=await request.post('/api/media/upload',{multipart:{file:{name:'table.wav',mimeType:'audio/wav',buffer:readFileSync(file)}}});
  const mediaId=(await uploaded.json()).mediaId;id=randomUUID();const quote='2025년 한국 고용률 50%';
  const missing={state:'missing',value:null,candidates:[]};const header='15세 이상 잠정치 <img src=x onerror=window.tableContextInjected=true>';
  const sourceTrace={parserVersion:'static-text-v3',requestedUrl:'https://example.org/table',finalUrl:'https://example.org/table',retrievedAt:'2026-10-19T00:00:00Z',contentType:'text/html',bodySha256:'a'.repeat(64),textSha256:'b'.repeat(64),textLength:header.length+1+quote.length,blocks:[{kind:'table_header',position:0,length:header.length,tableLocation:{tableIndex:0,rowIndex:0,cellIndex:0,rowSpan:1,columnSpan:1}},{kind:'table_cell',position:header.length+1,length:quote.length,tableLocation:{tableIndex:0,rowIndex:1,cellIndex:0,rowSpan:1,columnSpan:2}}],structureComplete:true,publication:{publisher:missing,publishedAt:missing,modifiedAt:missing},quoteOccurrences:1,quoteBlockIndexes:[1],extractionTruncated:false,tableReferenceAudit:{version:'table-reference-audit-v1',meaningVerified:false,complete:true,references:[{cellBlockIndex:1,declaredId:'rate',status:'resolved_same_table_header',headerBlockIndex:0}]},tableContext:{version:'table-context-v1',tableIndex:0,association:'same_table_only',meaningVerified:false,complete:true,fragments:[{blockIndex:0,kind:'table_header',text:header,truncated:false}],cueAudit:{version:'table-cue-audit-v1',meaningVerified:false,complete:true,cues:[{blockIndex:0,kind:'denominator',offset:0,text:'15세 이상'}]}}};
  const result={scope:'audio_only',demo:false,claims:[{id:randomUUID(),text:'표 위치 추적 테스트',startSeconds:0,endSeconds:1,verdict:'INSUFFICIENT',evidence:[{url:sourceTrace.finalUrl,title:'합성 표',quote,position:header.length+1,publisher:null,publishedAt:null,relation:'INSUFFICIENT',usable:false,reasons:['TABLE_CONTEXT_UNVERIFIED'],lineage:'example.org',sourceTrace}]}],limitations:['합성 고정 출력이며 실제 AI 분석이 아닙니다.'],usage:{}};
  await pool.query("INSERT INTO jobs(id,media_id,consent,status,result) VALUES($1,$2,true,'completed',$3)",[id,mediaId,JSON.stringify(result)]);
  await page.goto('/');await page.getByRole('button',{name:'분석 이력',exact:true}).click();await page.locator('.history-item').first().click();
  await page.getByText('원문 수집·발행 정보',{exact:true}).click();
  await expect(page.getByText('표 1 · 행 2 · 셀 1 (원문 순서)',{exact:true})).toBeVisible();
  await expect(page.getByText('행 병합 표기: 1 · 열 병합 표기: 2',{exact:true})).toBeVisible();
  await expect(page.getByText('행·셀 번호는 원문 태그 순서입니다. 단위·분모·주석의 의미는 검증되지 않았습니다.',{exact:true})).toBeVisible();
  await expect(page.getByText(header,{exact:true})).toBeVisible();
  await expect(page.getByText('같은 표의 설명 후보이며 해당 수치와의 의미 관계는 검증되지 않았습니다.',{exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'표 헤더 참조 관측'})).toBeVisible();
  await expect(page.getByText('같은 표의 헤더를 구조상 찾음 · 의미 미검증',{exact:true})).toBeVisible();
  await expect(page.getByText('분모 관련 표기 · 15세 이상',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>Object.hasOwn(window,'tableContextInjected'))).toBe(false);
 }finally{if(id)await request.delete(`/api/analyses/${id}`);await pool.end();rmSync(dir,{recursive:true});}
});

test('visual observations remain separate from external verdicts and escape OCR text',async({page})=>{
 await page.route('**/api/auth/session',route=>route.fulfill({json:{mode:'local',user:null}}));
 const text='<img src=x onerror=window.ocrInjected=true> 화면 40%';
 const item={id:'visual',status:'completed',stage:'completed',createdAt:'2026-10-19T00:00:00Z',expiresAt:'',scope:'audio_visual',demo:false,error:null,claims:[{id:'claim',text:'음성 50%',startSeconds:0,endSeconds:1,verdict:'INSUFFICIENT',evidence:[]}],limitations:['15초 간격 표본 추출'],usage:{},visual:{version:'visual-sampled-v1',status:'partial',durationSeconds:2,subtitleStatus:'not_present',ocrStatus:'partial',frames:[{frameId:'frame',timeSeconds:0}],records:[{source:'ocr',startSeconds:0,endSeconds:2,text,frameId:'frame'}],limitations:['OCR 오인식 가능']},modalChecks:[{claimId:'claim',source:'ocr',startSeconds:0,endSeconds:2,observedText:text,status:'possible_mismatch',reasons:['OCR_UNCERTAIN'],frameId:'frame'}],summary:{overall:'review_required',counts:{CONFIRMED:0,REFUTED:0,INSUFFICIENT:1,REVIEW_REQUIRED:0,EXCLUDED:0},strength:'not_assessed',independenceVerified:false,crossModalReviewRequired:true}};
 await page.route('**/api/analyses',route=>route.fulfill({json:[item]}));
 await page.route('**/api/analyses/visual',route=>route.fulfill({json:item}));
 await page.goto('/');await page.getByRole('button',{name:'분석 이력',exact:true}).click();await page.locator('.history-item').first().click();
 await expect(page.getByRole('heading',{name:'자막·화면 관측'})).toBeVisible();
 await expect(page.getByText('불일치 후보 · 검토 필요',{exact:true})).toBeVisible();
 await expect(page.getByText(text,{exact:true}).first()).toBeVisible();
 await expect(page.getByText('전체 영상의 진실 판정이 아닙니다. 근거 강도와 출처 독립성은 평가하지 않았습니다.',{exact:true})).toBeVisible();
 await expect(page.locator('.claim-card .verdict')).toHaveText('검증 불충분');
 expect(await page.evaluate(()=>Object.hasOwn(window,'ocrInjected'))).toBe(false);
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

for(const reviewed of [false,true])test(`reviewed report audit and legacy summary ${reviewed?'reviewed':'legacy'}`,async({page},testInfo)=>{
 const errors:string[]=[];
 page.on('pageerror',error=>errors.push(error.message));
 page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
 const definition='15세 이상 고용률 <img src=x onerror=window.meaningInjected=true>';
 const evidence={url:'https://example.org/report',title:'검토 원문',quote:'2025년 한국 고용률 50%',position:7,publisher:null,publishedAt:null,relation:'SUPPORTED',usable:true,reasons:[],lineage:'example.org',...(reviewed?{meaningReview:{version:'reviewed-meaning-v1',verified:true,policyId:'fixture-policy',sourceKind:'paragraph',documentHash:'a'.repeat(64),definition,quotePosition:7,quoteLength:16,relation:'SUPPORTED',reviewReference:'https://example.org/review',reviewedAt:'2026-10-21'}}:{})};
 const item={id:'reviewed-report',status:'completed',stage:'completed',createdAt:'2026-10-21T00:00:00Z',expiresAt:'',scope:'audio_only',demo:false,error:null,claims:[{id:'c1',text:'선택 주장',startSeconds:0,endSeconds:1,verdict:'CONFIRMED',evidence:[evidence]},{id:'c2',text:'미확인 주장',startSeconds:1,endSeconds:2,verdict:'INSUFFICIENT',evidence:[]}],limitations:['합성 보고서 UI 검증'],usage:{},summary:{version:'claim-summary-v1',scope:'claim_summary',overall:'insufficient',counts:{CONFIRMED:1,REFUTED:0,INSUFFICIENT:1,REVIEW_REQUIRED:0,EXCLUDED:0},strength:'not_assessed',independenceVerified:false,crossModalReviewRequired:false,...(reviewed?{reviewedEvidence:{version:'reviewed-summary-v1',claimIds:['c1','c2'],documentCount:1,originGroupCount:1,strength:'low',reasons:['UNRESOLVED_CLAIMS','INDEPENDENCE_UNVERIFIED']}}:{})}};
 await page.route('**/api/auth/session',route=>route.fulfill({json:{mode:'local',user:null}}));
 await page.route('**/api/analyses',route=>route.fulfill({json:[item]}));
 await page.route('**/api/analyses/reviewed-report',route=>route.fulfill({json:item}));
 await page.goto('/');await page.getByRole('button',{name:'분석 이력',exact:true}).click();await page.locator('.history-item').first().click();
 await expect(page.getByText('집계 결과: 검증 불충분',{exact:true})).toBeVisible();
 if(reviewed){
  await expect(page.getByText('선택한 주장 2개를 집계했습니다.',{exact:true})).toBeVisible();
  await expect(page.getByText('검토 근거 강도: 낮음',{exact:true})).toBeVisible();
  await expect(page.getByText('문서 1개 · 가능한 공통 출처 그룹 1개',{exact:true})).toBeVisible();
  await page.getByText('검토된 비교 정의·인용 위치',{exact:true}).click();
  await expect(page.getByText(definition,{exact:true})).toBeVisible();
  await expect(page.getByText('시작 7 · 길이 16자 (정규화 원문 기준)',{exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'검토 참조 열기'})).toHaveAttribute('href','https://example.org/review');
  expect(await page.evaluate(()=>Object.hasOwn(window,'meaningInjected'))).toBe(false);
 }else{
  await expect(page.getByText('전체 영상의 진실 판정이 아닙니다. 근거 강도와 출처 독립성은 평가하지 않았습니다.',{exact:true})).toBeVisible();
  await expect(page.getByText('검토된 비교 정의·인용 위치',{exact:true})).toHaveCount(0);
 }
 await page.screenshot({path:testInfo.outputPath('desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:testInfo.outputPath('mobile.png'),fullPage:true});
 expect(errors).toEqual([]);
});

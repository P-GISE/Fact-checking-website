import { describe, it, expect } from 'vitest';
import { claimSchema } from '../src/contracts.js';
const claim = {id:'c1',text:'통계가 5% 증가했다',startSeconds:1,endSeconds:2,subject:'한국',period:'2025',metric:'통계',value:'5',unit:'%',eligibility:'checkable',verdict:'INSUFFICIENT',evidence:[]};
describe('claim boundary',()=>{
 it('rejects reversed time ranges',()=>expect(claimSchema.safeParse({...claim,startSeconds:3}).success).toBe(false));
 it('rejects unknown verdicts',()=>expect(claimSchema.safeParse({...claim,verdict:'TRUE'}).success).toBe(false));
 it('accepts an explicit insufficient claim',()=>expect(claimSchema.parse(claim).verdict).toBe('INSUFFICIENT'));
});

it('preserves new source context and rule versions without inventing legacy provenance',async()=>{
 const {resultSchema}=await import('../src/contracts.js');
 const source='원문 <img src=x onerror=alert(1)> 맥락';
 const current=resultSchema.parse({claims:[{...claim,contextText:source}],limitations:[],scope:'audio_only',versions:{ruleVersion:'audio-numeric-canonical-v2'}});
 expect(current.claims[0].contextText).toBe(source);
 expect(current.versions.ruleVersion).toBe('audio-numeric-canonical-v2');
 const legacy=resultSchema.parse({claims:[claim],limitations:[],scope:'audio_only'});
 expect(legacy.versions).toEqual({});expect(legacy.claims[0].contextText).toBeNull();
});

it('preserves bounded source observations while keeping legacy evidence untraced',async()=>{
 const {evidenceSchema}=await import('../src/contracts.js');
 const field={state:'missing',value:null,candidates:[]};
 const sourceTrace={parserVersion:'static-text-v1',requestedUrl:'https://example.org/start',finalUrl:'https://example.org/report',retrievedAt:'2026-10-18T00:00:00+00:00',contentType:'text/html',bodySha256:'a'.repeat(64),textSha256:'b'.repeat(64),textLength:20,blocks:[{kind:'paragraph',position:0,length:20}],structureComplete:true,publication:{publisher:field,publishedAt:field,modifiedAt:field},quoteOccurrences:2,quoteBlockIndexes:[],extractionTruncated:false};
 const evidence={url:sourceTrace.finalUrl,title:'자료',quote:'원문',position:0,publisher:null,publishedAt:null,relation:'INSUFFICIENT',usable:false,reasons:['QUOTE_AMBIGUOUS'],lineage:'example.org'};
 expect(evidenceSchema.parse({...evidence,sourceTrace})).toMatchObject({sourceTrace});
 expect(evidenceSchema.parse({...evidence,sourceTrace}).sourceTrace?.sourceLinksComplete).toBe(false);
 expect(evidenceSchema.parse(evidence)).toHaveProperty('sourceTrace',null);
 expect(evidenceSchema.safeParse({...evidence,sourceTrace:{...sourceTrace,bodySha256:'invalid'}}).success).toBe(false);
 expect(evidenceSchema.safeParse({...evidence,sourceTrace:{...sourceTrace,blocks:[{kind:'paragraph',position:19,length:2}]}}).success).toBe(false);
});

it('preserves source registration review without claiming independent evidence',async()=>{
 const {evidenceSchema}=await import('../src/contracts.js');
 const evidence={url:'https://example.org/report',title:'자료',quote:'원문',position:0,publisher:null,publishedAt:null,relation:'INSUFFICIENT',usable:false,reasons:[],lineage:'example.org'};
 const sourceReview={version:'source-review-v1',registryVersion:'source-registry-v1-empty',identity:{status:'unregistered',publisherId:null,registeredName:null},independence:'unverified',groupId:'a'.repeat(64),groupSize:2,relatedUrls:['https://other.example/copy'],signals:['SAME_TEXT_HASH']};
 expect(evidenceSchema.parse({...evidence,sourceReview})).toHaveProperty('sourceReview',sourceReview);
 expect(evidenceSchema.parse(evidence)).toHaveProperty('sourceReview',null);
 expect(evidenceSchema.safeParse({...evidence,sourceReview:{...sourceReview,independence:'verified'}}).success).toBe(false);
});

it('preserves physical table locations in v3 and accepts legacy blocks without them',async()=>{
 const {sourceTraceSchema}=await import('../src/contracts.js');const field={state:'missing',value:null,candidates:[]};
 const location={tableIndex:0,rowIndex:1,cellIndex:0,rowSpan:0,columnSpan:2};
 const trace={parserVersion:'static-text-v3',requestedUrl:'https://example.org/',finalUrl:'https://example.org/',retrievedAt:'2026-10-19T00:00:00Z',contentType:'text/html',bodySha256:'a'.repeat(64),textSha256:'b'.repeat(64),textLength:4,blocks:[{kind:'table_cell',position:0,length:4,tableLocation:location}],structureComplete:true,publication:{publisher:field,publishedAt:field,modifiedAt:field},quoteOccurrences:1,quoteBlockIndexes:[0],extractionTruncated:false};
 expect(sourceTraceSchema.parse(trace).blocks[0]).toHaveProperty('tableLocation',location);
 expect(sourceTraceSchema.parse({...trace,parserVersion:'static-text-v2',blocks:[{kind:'table_cell',position:0,length:4}]}).blocks[0]).toHaveProperty('tableLocation',null);
 expect(sourceTraceSchema.safeParse({...trace,blocks:[{...trace.blocks[0],tableLocation:{...location,columnSpan:0}}]}).success).toBe(false);
 expect(sourceTraceSchema.safeParse({...trace,blocks:[{...trace.blocks[0],tableLocation:{...location,tableIndex:-1}}]}).success).toBe(false);
});

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

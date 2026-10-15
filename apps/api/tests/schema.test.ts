import { describe, it, expect } from 'vitest';
import { claimSchema } from '../src/contracts.js';
const claim = {id:'c1',text:'통계가 5% 증가했다',startSeconds:1,endSeconds:2,subject:'한국',period:'2025',metric:'통계',value:'5',unit:'%',eligibility:'checkable',verdict:'INSUFFICIENT',evidence:[]};
describe('claim boundary',()=>{
 it('rejects reversed time ranges',()=>expect(claimSchema.safeParse({...claim,startSeconds:3}).success).toBe(false));
 it('rejects unknown verdicts',()=>expect(claimSchema.safeParse({...claim,verdict:'TRUE'}).success).toBe(false));
 it('accepts an explicit insufficient claim',()=>expect(claimSchema.parse(claim).verdict).toBe('INSUFFICIENT'));
});

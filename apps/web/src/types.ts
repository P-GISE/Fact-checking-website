export type Verdict='CONFIRMED'|'REFUTED'|'INSUFFICIENT'|'REVIEW_REQUIRED'|'EXCLUDED';
export interface Evidence{url:string;title:string;quote:string;position:number;publisher:string|null;publishedAt:string|null;relation:string;usable:boolean;reasons:string[];lineage:string;}
export interface Claim{id:string;text:string;startSeconds:number;endSeconds:number;verdict:Verdict;evidence:Evidence[];}
export interface Analysis{id:string;status:string;stage:string;createdAt:string;expiresAt:string;scope:'audio_only';demo:boolean;claims:Claim[];limitations:string[];mediaId?:string;error:{code:string;message:string}|null;usage:Record<string,unknown>;}
export const verdictLabel:Record<Verdict,string>={CONFIRMED:'근거로 확인됨',REFUTED:'반박됨',INSUFFICIENT:'검증 불충분',REVIEW_REQUIRED:'검토 필요',EXCLUDED:'검증 대상 제외'};
export function time(seconds:number){return `${Math.floor(seconds/60).toString().padStart(2,'0')}:${Math.floor(seconds%60).toString().padStart(2,'0')}`;}

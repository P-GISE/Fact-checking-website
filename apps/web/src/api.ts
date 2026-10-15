import type {Analysis} from './types';
async function call<T>(url:string,init?:RequestInit):Promise<T>{
 const response=await fetch(url,init);
 if(!response.ok){const body=await response.json().catch(()=>null);throw new Error(body?.error?.code??'NETWORK_ERROR');}
 return response.status===204?undefined as T:response.json();
}
export async function upload(file:File){const data=new FormData();data.append('file',file);return call<{mediaId:string}>('/api/media/upload',{method:'POST',body:data});}
export async function createAnalysis(mediaId:string,consent:boolean){return call<{id:string}>('/api/analyses',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':mediaId},body:JSON.stringify({mediaId,externalProcessingConsent:consent})});}
export const getAnalysis=(id:string)=>call<Analysis>(`/api/analyses/${id}`);
export const listAnalyses=()=>call<Analysis[]>('/api/analyses');
export const deleteAnalysis=(id:string)=>call<void>(`/api/analyses/${id}`,{method:'DELETE'});

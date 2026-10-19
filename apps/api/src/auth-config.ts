import type {AuthMode} from './auth.js';
export function authConfiguration(env:Record<string,string|undefined>){
 const local=env.FACTLENS_LOCAL_ONLY==='true';
 const mode=env.FACTLENS_AUTH_MODE??(local?'local':'accounts');
 if(!['local','accounts'].includes(mode)||(!local&&mode!=='accounts'))throw new Error('PUBLIC_AUTH_REQUIRED');
 if(!local){
  const origins=env.ALLOWED_ORIGINS?.split(',')??[];
  if(!origins.length||origins.some(value=>{try{const u=new URL(value);return u.protocol!=='https:'||u.origin!==value;}catch{return true;}}))throw new Error('PUBLIC_HTTPS_ORIGIN_REQUIRED');
 }
 return {authMode:mode as AuthMode,secureCookies:!local};
}

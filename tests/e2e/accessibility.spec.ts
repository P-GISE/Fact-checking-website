import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

async function audit(page:import('@playwright/test').Page){
 const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
 expect(result.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))).toEqual([]);
}
for(const width of [1280,390]){
 test(`home and account screens have no automated A/AA violations at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:900});
  await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:null}}));
  await page.goto('/');
  await page.getByRole('button',{name:'로그인',exact:true}).waitFor();
  await audit(page);
  await page.getByRole('button',{name:'로그인',exact:true}).click();
  await audit(page);
  await page.locator('.account-panel').getByRole('button',{name:'회원가입',exact:true}).click();
  await audit(page);
 });
 test(`private navigation screens have no automated A/AA violations at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:900});
  await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:{id:'fixture',username:'a11y_user',role:'user'}}}));
  await page.route('**/api/analyses',r=>r.fulfill({json:[]}));
  await page.goto('/');
  await page.getByRole('button',{name:'계정 메뉴'}).click();
  await audit(page);
  await page.getByRole('button',{name:'계정 설정',exact:true}).click();
  await audit(page);
  await page.getByText('회원 탈퇴',{exact:true}).click();
  await audit(page);
  if(width===390)await page.getByRole('button',{name:'메뉴 열기'}).click();
  await page.getByRole('button',{name:'새 분석',exact:true}).click();
  await audit(page);
  if(width===390)await page.getByRole('button',{name:'메뉴 열기'}).click();
  await page.getByRole('button',{name:'분석 이력',exact:true}).click();
  await audit(page);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 });
}

test('keyboard skips repeated navigation and restores focus after menus',async({page})=>{
 await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:{id:'fixture',username:'a11y_user',role:'user'}}}));
 await page.route('**/api/analyses',r=>r.fulfill({json:[]}));
 await page.goto('/');
 await page.keyboard.press('Tab');
 await expect(page.getByRole('link',{name:'본문으로 건너뛰기'})).toBeFocused();
 await page.keyboard.press('Enter');
 await expect(page.getByRole('main')).toBeFocused();
 const profile=page.getByRole('button',{name:'계정 메뉴'});
 await profile.focus();await page.keyboard.press('Enter');
 await page.keyboard.press('Tab');
 await expect(page.getByRole('button',{name:'계정 설정',exact:true})).toBeFocused();
 await page.keyboard.press('Escape');await expect(profile).toBeFocused();
 await page.keyboard.press('Enter');await page.keyboard.press('Tab');await page.keyboard.press('Enter');
 await expect(page.getByRole('heading',{name:'계정 설정',exact:true})).toBeVisible();
 await expect(page.getByRole('main')).toBeFocused();
});

for(const width of [1280,390]){
 test(`example report remains accessible at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:900});
  await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:null}}));
  await page.goto('/');
  await page.getByRole('button',{name:'예시 보고서 보기'}).click();
  await expect(page.getByRole('main')).toBeFocused();
  await audit(page);
 });
}

test('320px reflow and mobile keyboard menu keep every control reachable',async({page})=>{
 await page.setViewportSize({width:320,height:800});
 await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:{id:'fixture',username:'a11y_user',role:'user'}}}));
 await page.route('**/api/analyses',r=>r.fulfill({json:[]}));
 await page.goto('/');
 const toggle=page.getByRole('button',{name:'메뉴 열기'});
 await toggle.focus();await page.keyboard.press('Enter');
 await page.getByRole('button',{name:'분석 이력',exact:true}).focus();
 await page.keyboard.press('Escape');await expect(toggle).toBeFocused();
 await page.keyboard.press('Enter');
 await page.getByRole('button',{name:'새 분석',exact:true}).focus();await page.keyboard.press('Enter');
 await expect(page.getByLabel('분석할 파일')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await audit(page);
});

test('opening history moves focus once and polling preserves user focus',async({page})=>{
 await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:{id:'fixture',username:'a11y_user',role:'user'}}}));
 await page.route('**/api/analyses',r=>r.fulfill({json:[{id:'fixture',createdAt:'2026-10-21T00:00:00Z',status:'transcribing'}]}));
 let requests=0;
 await page.route('**/api/analyses/fixture',r=>{requests++;return r.fulfill({json:{id:'fixture',createdAt:'2026-10-21T00:00:00Z',status:'transcribing',stage:'transcribing',demo:false,claims:[],limitations:[],usage:{}}});});
 await page.goto('/');
 await page.getByRole('button',{name:'분석 이력',exact:true}).click();
 await page.locator('.history-item').focus();await page.keyboard.press('Enter');
 await expect(page.getByRole('main')).toBeFocused();
 const profile=page.getByRole('button',{name:'계정 메뉴'});
 await profile.focus();
 await expect.poll(()=>requests).toBeGreaterThan(1);
 await expect(profile).toBeFocused();
});

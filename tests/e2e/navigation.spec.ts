import {test,expect} from '@playwright/test';

for(const width of [1280,390]){
 test(`public home and private account navigation at ${width}px`,async({page},info)=>{
  await page.setViewportSize({width,height:900});
  let signedIn=false;
  await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:null}}));
  await page.route('**/api/analyses',r=>r.fulfill({json:[]}));
  await page.route('**/api/auth/login',r=>{signedIn=true;return r.fulfill({json:{mode:'accounts',user:{id:'fixture',username:'design_user',role:'user'}}});});
  await page.route('**/api/auth/logout',r=>{signedIn=false;return r.fulfill({json:{ok:true}});});
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'영상 속 주장, 근거로 다시 보기.'})).toBeVisible();
  await expect(page.getByLabel('분석할 파일')).toHaveCount(0);
  await page.screenshot({path:info.outputPath('home.png'),fullPage:true});
  await page.getByRole('button',{name:'로그인',exact:true}).click();
  await page.getByLabel('사용자 이름',{exact:true}).fill('design_user');
  await page.getByLabel('비밀번호',{exact:true}).fill('fixture-password-123!');
  await page.getByRole('button',{name:'로그인',exact:true}).last().click();
  await expect(page.getByLabel('분석할 파일')).toBeVisible();
  expect(signedIn).toBe(true);
  await expect(page.getByLabel('현재 비밀번호',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'계정 메뉴'}).click();
  await page.getByRole('button',{name:'계정 설정',exact:true}).click();
  await expect(page.getByLabel('현재 비밀번호',{exact:true})).toBeVisible();
  await page.screenshot({path:info.outputPath('settings.png'),fullPage:true});
  if(width===390)await page.getByRole('button',{name:'메뉴 열기'}).click();
  await page.getByRole('button',{name:'홈',exact:true}).click();
  await expect(page.getByLabel('현재 비밀번호',{exact:true})).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole('button',{name:'계정 메뉴'}).click();
  await page.getByRole('button',{name:'로그아웃',exact:true}).click();
  await expect(page.getByRole('heading',{name:'영상 속 주장, 근거로 다시 보기.'})).toBeVisible();
  await expect(page.getByLabel('분석할 파일')).toHaveCount(0);
  expect(signedIn).toBe(false);
 });
}

test('guest example stays public and private navigation requests login',async({page})=>{
 await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:null}}));
 let privateRequests=0;
 await page.route('**/api/analyses**',r=>{privateRequests++;return r.fulfill({json:[]});});
 await page.goto('/');
 await page.getByRole('button',{name:'예시 보고서 보기'}).click();
 await expect(page.getByText('가상 예시 · 실제 분석 결과가 아닙니다')).toBeVisible();
 await page.getByRole('button',{name:'예시 닫기'}).click();
 await page.getByRole('button',{name:'분석 이력',exact:true}).click();
 await expect(page.getByRole('heading',{name:'로그인',exact:true})).toBeVisible();
 expect(privateRequests).toBe(0);
});

test('failed logout preserves the private session and displays an error',async({page})=>{
 await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:{id:'fixture',username:'design_user',role:'user'}}}));
 await page.route('**/api/analyses',r=>r.fulfill({json:[]}));
 await page.route('**/api/auth/logout',r=>r.fulfill({status:500,json:{error:{code:'NETWORK_ERROR'}}}));
 await page.goto('/');
 await page.getByRole('button',{name:'계정 메뉴'}).click();
 await page.keyboard.press('Escape');
 await expect(page.getByRole('button',{name:'계정 설정',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'계정 메뉴'}).click();
 await page.getByRole('button',{name:'로그아웃',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('로그아웃을 완료하지 못했습니다.');
 await expect(page.getByRole('button',{name:'계정 메뉴'})).toBeVisible();
});

test('pending login cannot lose its completion through home navigation',async({page})=>{
 await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:null}}));
 await page.route('**/api/analyses',r=>r.fulfill({json:[]}));
 let finish!:()=>void;
 const pending=new Promise<void>(resolve=>{finish=resolve;});
 await page.route('**/api/auth/login',async r=>{await pending;return r.fulfill({json:{mode:'accounts',user:{id:'fixture',username:'design_user',role:'user'}}});});
 await page.goto('/');
 await page.getByRole('button',{name:'로그인',exact:true}).click();
 await page.getByLabel('사용자 이름',{exact:true}).fill('design_user');
 await page.getByLabel('비밀번호',{exact:true}).fill('fixture-password-123!');
 await page.locator('.account-panel').getByRole('button',{name:'로그인',exact:true}).click();
 await expect(page.getByRole('button',{name:'홈',exact:true})).toBeDisabled();
 await expect(page.getByRole('button',{name:'FactLens 홈',exact:true})).toBeDisabled();
 finish();
 await expect(page.getByLabel('분석할 파일')).toBeVisible();
 await expect(page.getByRole('button',{name:'홈',exact:true})).toBeEnabled();
});

test('pending account change stays visible and then requires reauthentication',async({page})=>{
 await page.route('**/api/auth/session',r=>r.fulfill({json:{mode:'accounts',user:{id:'fixture',username:'design_user',role:'user'}}}));
 await page.route('**/api/analyses',r=>r.fulfill({json:[]}));
 let finish!:()=>void;
 const pending=new Promise<void>(resolve=>{finish=resolve;});
 await page.route('**/api/auth/account',async r=>{await pending;return r.fulfill({status:204});});
 await page.goto('/');
 await page.getByRole('button',{name:'계정 메뉴'}).click();
 await page.getByRole('button',{name:'계정 설정',exact:true}).click();
 await page.getByLabel('현재 비밀번호',{exact:true}).fill('fixture-password-123!');
 await page.getByRole('button',{name:'계정 변경 저장'}).click();
 await expect(page.getByRole('button',{name:'홈',exact:true})).toBeDisabled();
 finish();
 await expect(page.getByRole('heading',{name:'로그인',exact:true})).toBeVisible();
 await expect(page.getByRole('status')).toContainText('계정이 변경됐습니다.');
 await expect(page.getByRole('button',{name:'홈',exact:true})).toBeEnabled();
});

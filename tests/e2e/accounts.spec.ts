import {test,expect} from '@playwright/test';
test('account login gates workspace and logout clears private history',async({page})=>{
 test.skip(process.env.FACTLENS_AUTH_MODE!=='accounts','Account-mode integration run required');
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'계정으로 시작하기'})).toBeVisible();
 await expect(page.getByLabel('분석할 파일')).toHaveCount(0);
 const username='user_'+Date.now();
 await page.getByLabel('사용자 이름').fill(username);await page.getByLabel('비밀번호',{exact:true}).fill('test-only-long-password-123!');
 await page.getByRole('button',{name:'계정 만들기',exact:true}).click();
 await expect(page.getByLabel('분석할 파일')).toBeVisible();
 await expect(page.getByText(username,{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'로그아웃',exact:true}).click();
 await expect(page.getByRole('heading',{name:'계정으로 시작하기'})).toBeVisible();
 await page.getByLabel('사용자 이름').fill(username);await page.getByLabel('비밀번호',{exact:true}).fill('test-only-long-password-123!');
 await page.getByRole('button',{name:'로그인',exact:true}).click();
 await expect(page.getByLabel('분석할 파일')).toBeVisible();
 expect(await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length}))).toEqual({local:0,session:0});
});

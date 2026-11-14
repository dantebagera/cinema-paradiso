const {defineConfig}=require('C:/Users/dante/Desktop/cinema paradiso/node_modules/@playwright/test');
const path=require('path');
const baseURL=process.env.CP_PASS3_BASE_URL;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(baseURL||''))throw Error('Owned baseURL required');
module.exports=defineConfig({
  testDir:path.join(__dirname,'pass3-specs'),workers:1,retries:0,timeout:30000,
  expect:{timeout:7000},outputDir:path.join(__dirname,'pass3-browser-results',process.env.CP_PASS3_GROUP),
  reporter:[['json',{outputFile:path.join(__dirname,`pass3-browser-${process.env.CP_PASS3_GROUP}.json`)}]],
  use:{baseURL,browserName:'chromium',headless:true,viewport:{width:1600,height:1000},
       serviceWorkers:'block',extraHTTPHeaders:{'X-Sandbox-Nonce':process.env.CP_PASS3_NONCE},screenshot:'only-on-failure'}
});

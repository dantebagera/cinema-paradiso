const base=require('C:/Users/dante/Desktop/cinema paradiso/node_modules/@playwright/test');
const origin=new URL(process.env.CP_PASS3_BASE_URL).origin;
const test=base.test.extend({
  isolationBoundary:[async({context},use)=>{
    await context.route('**/*',route=>new URL(route.request().url()).origin===origin
      ? route.fallback() : route.abort('blockedbyclient'));
    await use();
  },{auto:true}]
});
module.exports={test,expect:base.expect};

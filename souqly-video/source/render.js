const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path=require('path'), fs=require('fs');
(async()=>{
  const [,, outDir, from='0', to='465', step='1'] = process.argv;
  fs.mkdirSync(outDir,{recursive:true});
  const b=await chromium.launch();
  const p=await b.newPage({viewport:{width:1080,height:1080}});
  await p.goto('file://'+path.resolve(__dirname,'index.html'));
  await p.evaluate(()=>document.fonts.ready);
  await p.waitForTimeout(300);
  for(let f=+from; f<+to; f+=+step){
    await p.evaluate(t=>window.render(t), f/30);
    await p.screenshot({path:`${outDir}/f${String(f).padStart(4,'0')}.png`});
  }
  await b.close();
})();

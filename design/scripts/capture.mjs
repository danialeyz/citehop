import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(root,'screenshots');
await mkdir(output,{recursive:true});
const sources={};
for(const name of ['prototype/index.html','prototype/styles.css','prototype/app.js']) {
  sources[name]=createHash('sha256').update(await readFile(path.join(root,name))).digest('hex');
}
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml'};
const server=createServer(async(req,res)=>{
  try {
    const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    const file=path.resolve(root,'.'+pathname);
    if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
    const bytes=await readFile(file);
    res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'}).end(bytes);
  } catch {res.writeHead(404).end('Not found');}
});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
const url=`http://127.0.0.1:${server.address().port}/prototype/index.html`;
const core=['search','results','graph','paper-1','experiments','settings'];
const manifest={status:'running',created_at:new Date().toISOString(),sources,browser:null,device_scale_factor:1,reduced_motion:'reduce',captures:[],errors:[]};
let browser;
try {
  browser=await chromium.launch({headless:true});
  manifest.browser=browser.version();
  for(const [name,viewport,routes] of [['desktop',{width:1440,height:1050},[...core,'loading','empty','error','missing']],['mobile',{width:390,height:844},core]]) {
    const context=await browser.newContext({viewport,deviceScaleFactor:1,reducedMotion:'reduce',colorScheme:'dark',locale:'en-US'});
    for(const route of routes){
      const page=await context.newPage();
      page.on('pageerror',error=>manifest.errors.push(`${name}/${route}: ${error.message}`));
      await page.goto(`${url}#${route}`,{waitUntil:'load'});
      await page.locator('#main').waitFor({state:'visible'});
      await page.evaluate(()=>document.fonts.ready);
      const size=await page.evaluate(()=>({viewportWidth:innerWidth,documentWidth:document.documentElement.scrollWidth,height:Math.max(document.documentElement.scrollHeight,innerHeight)}));
      if(size.documentWidth>viewport.width)manifest.errors.push(`${name}/${route}: horizontal page overflow ${size.documentWidth}>${viewport.width}`);
      const filename=`${name}-${route}.png`;
      await page.screenshot({path:path.join(output,filename),fullPage:true});
      manifest.captures.push({file:filename,route,viewport,document:size});
      await page.close();
    }
    await context.close();
  }
  manifest.status=manifest.errors.length?'failed':'passed';
} catch(error){manifest.errors.push(error.message);manifest.status='failed';}
finally {
  if(browser)await browser.close();
  await new Promise(resolve=>server.close(resolve));
  await writeFile(path.join(output,'capture-manifest.json'),JSON.stringify(manifest,null,2)+'\n');
}
if(manifest.status!=='passed'){
  console.error(manifest.errors.join('\n'));
  process.exitCode=1;
}else console.log(`Captured ${manifest.captures.length} PNGs from canonical source. Inspect them before accepting visual parity.`);

// Actual compressed cast GLBs in a password-protected loopback-only Chrome preview.
// CAST_QA_BROWSER_DIR=<private local output> node assets/pipeline/cast/qa_browser.mjs [cast names...]
// Requires the web workspace Playwright dependency and installed Google Chrome. Never uploads assets or screenshots.
/* global window */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const webRequire = createRequire(path.join(root, "apps/web/package.json"));
const { chromium } = webRequire("@playwright/test");
const threeBase = path.dirname(path.dirname(webRequire.resolve("three")));
const output = process.env.CAST_QA_BROWSER_DIR;
if (!output)
  throw new Error(
    "Set CAST_QA_BROWSER_DIR to a private local directory outside assets/cast/build",
  );
if (path.resolve(output).startsWith(path.join(root, "assets/cast/build")))
  throw new Error("QA output must stay outside runtime assets");
const secret = crypto.randomBytes(20).toString("hex");
const names =
  process.argv.length > 2
    ? process.argv.slice(2)
    : Object.keys(
        JSON.parse(
          fs.readFileSync(path.join(root, "assets/cast/cast.json"), "utf8"),
        ).characters,
      );
if (!names.length || names.some((name) => !/^[a-z0-9-]+$/.test(name)))
  throw new Error("Expected at least one cast asset name");
const html = `<!doctype html><html><head><style>body{margin:0;background:#585f66;font:14px sans-serif}canvas{display:block}#label{position:fixed;top:20px;left:24px;color:white;font-size:22px}</style><script type="importmap">{"imports":{"three":"/three/build/three.module.js","three/addons/":"/three/examples/jsm/"}}</script></head><body><div id="label"></div><script type="module">
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {KTX2Loader} from 'three/addons/loaders/KTX2Loader.js';
import {MeshoptDecoder} from 'three/addons/libs/meshopt_decoder.module.js';
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});renderer.setSize(720,900);renderer.setPixelRatio(1);renderer.setClearColor(0x585f66);renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1;document.body.append(renderer.domElement);const scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xc9ddff,0xb49b7c,2));const key=new THREE.DirectionalLight(0xffe2be,3);key.position.set(3,5,4);scene.add(key);const fill=new THREE.DirectionalLight(0xcddfff,1);fill.position.set(-3,3,-2);scene.add(fill);const floor=new THREE.Mesh(new THREE.PlaneGeometry(100,100),new THREE.MeshStandardMaterial({color:0x585f66,roughness:1}));floor.rotation.x=-Math.PI/2;floor.position.y=-.02;scene.add(floor);const camera=new THREE.PerspectiveCamera(28,720/900,.01,100);camera.position.set(0,1.1,4.3);camera.lookAt(0,.88,0);const loader=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).setKTX2Loader(new KTX2Loader().detectSupport(renderer));let current,mixer;
window.show=async(name,tier='talk_std',clip='idle',angle=0,time=.4)=>{if(current){scene.remove(current);current.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.material){for(const m of (Array.isArray(o.material)?o.material:[o.material])){for(const v of Object.values(m))if(v?.isTexture)v.dispose();m.dispose()}}});mixer?.stopAllAction()};const [model,anims]=await Promise.all([loader.loadAsync('/cast/'+name+'/'+tier+'.glb'),loader.loadAsync('/cast/'+name+'/anims.glb')]);current=model.scene;scene.add(current);current.rotation.y=angle;current.traverse(o=>{if(o.morphTargetInfluences)o.morphTargetInfluences.fill(0)});mixer=new THREE.AnimationMixer(current);const action=mixer.clipAction(anims.animations.find(a=>a.name===clip));action.play();mixer.setTime(time);renderer.render(scene,camera);document.querySelector('#label').textContent=name+' / '+tier+' / '+clip;return {drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,clips:anims.animations.map(a=>a.name)}};
window.ready=true;
</script></body></html>`;
const server = http.createServer((req, res) => {
  res.setHeader("Cache-Control", "private, no-store");
  res.setHeader("Referrer-Policy", "no-referrer");
  if (
    req.headers.authorization !==
    "Basic " + Buffer.from("qa:" + secret).toString("base64")
  ) {
    res.writeHead(401, {
      "WWW-Authenticate": 'Basic realm="Private local QA"',
    });
    res.end();
    return;
  }
  let file, base;
  if (req.url === "/") {
    res.setHeader("content-type", "text/html");
    res.end(html);
    return;
  }
  if (req.url.startsWith("/three/")) {
    base = threeBase;
    file = path.resolve(base, req.url.slice(7));
  } else if (req.url.startsWith("/cast/") && req.url.endsWith(".glb")) {
    base = path.join(root, "assets/cast/build");
    file = path.resolve(base, req.url.slice(6));
  }
  if (!file || !file.startsWith(base + path.sep) || !fs.existsSync(file)) {
    res.writeHead(404);
    res.end();
    return;
  }
  res.setHeader(
    "content-type",
    file.endsWith(".js")
      ? "text/javascript"
      : file.endsWith(".wasm")
        ? "application/wasm"
        : "application/octet-stream",
  );
  fs.createReadStream(file).pipe(res);
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
let browser;
try {
  browser = await chromium.launch({ headless: true, channel: "chrome" });
  const context = await browser.newContext({
    httpCredentials: { username: "qa", password: secret },
    viewport: { width: 720, height: 900 },
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:" + server.address().port);
  await page.waitForFunction(() => window.ready);
  const out = path.resolve(output);
  fs.mkdirSync(out, { recursive: true });
  for (const name of names) {
    for (const [tier, clip, angle, time, label] of [
      ["talk_std", "idle", 0, 0.4, "front"],
      ["talk_std", "idle", Math.PI, 0.4, "back"],
      ["talk_std", "walk", Math.PI, 0.3, "walk-back-a"],
      ["talk_std", "walk", Math.PI, 0.95, "walk-back-b"],
      ["talk_std", "walk", 0.6, 0.4, "walk-front"],
      ["walk", "walk", Math.PI, 0.3, "walk-lod-back"],
      ["talk_high", "talk", 0, 0.5, "talk-high"],
    ]) {
      const metrics = await page.evaluate(
        async ([n, t, c, a, s]) => window.show(n, t, c, a, s),
        [name, tier, clip, angle, time],
      );
      await page.screenshot({
        path: path.join(out, name + "-" + label + ".png"),
      });
      console.log(name, label, JSON.stringify(metrics));
    }
  }
  if (errors.length) throw new Error(errors.join("\n"));
} finally {
  await browser?.close();
  await new Promise((resolve) => server.close(resolve));
}

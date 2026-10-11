import { useEffect, useRef, useState } from "react";
import {
  Color,
  DirectionalLight,
  HemisphereLight,
  Mesh,
  MeshBasicMaterial,
  NeutralToneMapping,
  PCFShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  PMREMGenerator,
  PointLight,
  Raycaster,
  Scene,
  SRGBColorSpace,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { GTAOPass } from "three/examples/jsm/postprocessing/GTAOPass.js";
import { makePost } from "../post";
import { buildRoom, type HomeTarget } from "./room";

export type HomeSceneProps = {
  onSelectBook: () => void;
  onOpenMemories: () => void;
  focus?: "room" | "books" | "memories";
};

// The house belongs to the reader, outside every book's state/time/voice connection.
// No network access: procedural architecture/materials are deterministic local code.
export default function HomeScene({
  onSelectBook,
  onOpenMemories,
  focus = "room",
}: HomeSceneProps) {
  const mount = useRef<HTMLDivElement>(null);
  const actions = useRef({ onSelectBook, onOpenMemories });
  const destination = useRef(focus);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    actions.current = { onSelectBook, onOpenMemories };
  }, [onSelectBook, onOpenMemories]);
  useEffect(() => {
    destination.current = focus;
  }, [focus]);

  useEffect(() => {
    const host = mount.current;
    if (!host) return;
    const releases: (() => void)[] = [];
    const cleanup = () => {
      for (const release of releases.reverse()) release();
      releases.length = 0;
    };
    try {
      let renderer: WebGLRenderer;
      try {
        renderer = new WebGLRenderer({
          antialias: false,
          alpha: false,
          powerPreference: "default",
        });
      } catch {
        setFailed(true);
        return;
      }
      releases.push(() => {
        renderer.dispose();
        renderer.forceContextLoss(); // Repeated book ↔ home navigation must release scarce mobile GL contexts.
        renderer.domElement.remove();
      });
      renderer.outputColorSpace = SRGBColorSpace;
      renderer.toneMapping = NeutralToneMapping;
      renderer.toneMappingExposure = 1.0;
      renderer.info.autoReset = false;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = PCFShadowMap;
      renderer.domElement.style.cssText =
        "width:100%;height:100%;display:block;touch-action:none;cursor:grab";
      renderer.domElement.setAttribute("aria-hidden", "true");
      host.appendChild(renderer.domElement);
      const scene = new Scene();
      scene.background = new Color("#bcc5b8");
      const camera = new PerspectiveCamera(57, 1, 0.06, 45);
      const room = buildRoom();
      releases.push(() => room.dispose());
      scene.add(room.root);
      const pmrem = new PMREMGenerator(renderer);
      const env = new RoomEnvironment();
      const environment = (() => {
        try {
          return pmrem.fromScene(env, 0.055);
        } finally {
          env.dispose();
          pmrem.dispose();
        }
      })();
      releases.push(() => environment.dispose());
      scene.environment = environment.texture;
      scene.environmentIntensity = 0.27;
      scene.add(new HemisphereLight("#d9e2dc", "#9b8061", 0.5));
      // Late-afternoon light enters the east-facing bay; the independent home has no story clock.
      const sun = new DirectionalLight("#ffe4af", 3.15);
      releases.push(() => sun.shadow.map?.dispose());
      sun.position.set(8, 5.1, 3.4);
      sun.target.position.set(-2, 1.4, -4.3);
      sun.castShadow = true;
      sun.shadow.mapSize.set(2048, 2048);
      sun.shadow.camera.left = -7;
      sun.shadow.camera.right = 7;
      sun.shadow.camera.top = 7;
      sun.shadow.camera.bottom = -7;
      sun.shadow.camera.near = 0.2;
      sun.shadow.camera.far = 22;
      sun.shadow.normalBias = 0.018;
      sun.shadow.bias = -0.00007;
      scene.add(sun, sun.target);
      const fill = new DirectionalLight("#d5dfd7", 0.92);
      fill.position.set(5, 3.2, 0.7);
      scene.add(fill);
      const lamp = new PointLight("#ffd39c", 3.6, 3.5, 2);
      lamp.position.copy(room.lamp);
      scene.add(lamp);
      const fire = new PointLight("#ffb966", 6, 4.3, 2);
      fire.position.set(0, 0.48, -3.8);
      scene.add(fire);
      // Small emissive embers, deliberately restrained; no animated screen-filling fire or fake room backdrop.
      const emberMat = new MeshBasicMaterial({ color: "#ffc283" });
      const embers = new Mesh(new PlaneGeometry(0.56, 0.045), emberMat);
      releases.push(() => {
        embers.geometry.dispose();
        emberMat.dispose();
      });
      embers.position.set(0, 0.19, -3.87);
      scene.add(embers);
      const post = makePost(renderer, scene, camera, { msaa: 4, bloom: true });
      releases.push(() => post.dispose());
      // Static architectural contact shadow: half-resolution AO, never a vignette painted onto surfaces.
      const occlusion = new GTAOPass(scene, camera, 256, 256);
      releases.push(() => {
        occlusion.dispose();
        // r186's GTAOPass.dispose omits these two owned materials.
        occlusion.gtaoMaterial.dispose();
        occlusion.blendMaterial.dispose();
      });
      occlusion.updateGtaoMaterial({
        radius: 0.36,
        thickness: 0.25,
        distanceExponent: 1.8,
        scale: 1,
        samples: 12,
      });
      occlusion.updatePdMaterial({ radius: 4, samples: 8, rings: 2 });
      occlusion.blendIntensity = 0.72;
      post.composer.insertPass(occlusion, 1);
      post.out.uniforms.uVig!.value = 0.1;
      post.out.uniforms.uWarm!.value = 0.025;
      post.out.uniforms.uContrast!.value = 1.02;
      post.out.uniforms.uSat!.value = 0.98;
      post.bloom.strength = 0.13;
      post.bloom.threshold = 3.5;

      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
      const view = new Vector3(0, 1.74, 4.6);
      const look = new Vector3(0, 1.6, -2.8);
      camera.position.copy(view);
      camera.lookAt(look);
      const targetView = view.clone(),
        targetLook = look.clone();
      const yaw = { x: 0, y: 0 };
      const pointer = { id: -1, x: 0, y: 0, downX: 0, downY: 0, moved: false };
      const ray = new Raycaster();
      const uv = new Vector2();
      let width = 1,
        height = 1,
        stopped = false,
        previous = 0,
        frame = 0,
        dirty = true;
      const resize = () => {
        dirty = true;
        width = Math.max(1, host.clientWidth);
        height = Math.max(1, host.clientHeight);
        const dpr = Math.min(
          window.devicePixelRatio || 1,
          width < 700 ? 1.5 : 1.75,
        );
        const pw = Math.round(width * dpr),
          ph = Math.round(height * dpr);
        renderer.setPixelRatio(1);
        renderer.setSize(pw, ph, false);
        post.setSize(pw, ph, 1);
        occlusion.setSize(
          Math.max(1, Math.round(pw / 2)),
          Math.max(1, Math.round(ph / 2)),
        );
        camera.aspect = width / height;
        camera.fov = width < 700 ? 69 : 57;
        camera.updateProjectionMatrix();
      };
      const observer = new ResizeObserver(resize);
      releases.push(() => observer.disconnect());
      observer.observe(host);
      resize();
      const hit = (event: PointerEvent): HomeTarget | undefined => {
        const rect = renderer.domElement.getBoundingClientRect();
        uv.set(
          ((event.clientX - rect.left) / rect.width) * 2 - 1,
          (-(event.clientY - rect.top) / rect.height) * 2 + 1,
        );
        ray.setFromCamera(uv, camera);
        return ray.intersectObjects(room.hits, false)[0]?.object.userData
          .homeTarget as HomeTarget | undefined;
      };
      const down = (event: PointerEvent) => {
        if (event.button !== 0 || destination.current !== "room") return;
        pointer.id = event.pointerId;
        pointer.x = pointer.downX = event.clientX;
        pointer.y = pointer.downY = event.clientY;
        pointer.moved = false;
        renderer.domElement.setPointerCapture(event.pointerId);
      };
      const move = (event: PointerEvent) => {
        if (pointer.id !== event.pointerId) {
          renderer.domElement.style.cursor = hit(event) ? "pointer" : "grab";
          return;
        }
        const dx = event.clientX - pointer.x,
          dy = event.clientY - pointer.y;
        if (
          Math.hypot(
            event.clientX - pointer.downX,
            event.clientY - pointer.downY,
          ) > 6
        )
          pointer.moved = true;
        yaw.x = Math.max(-2.3, Math.min(2.3, yaw.x - dx * 0.006));
        yaw.y = Math.max(-0.7, Math.min(0.9, yaw.y + dy * 0.004));
        pointer.x = event.clientX;
        pointer.y = event.clientY;
        renderer.domElement.style.cursor = "grabbing";
      };
      const up = (event: PointerEvent) => {
        if (pointer.id !== event.pointerId) return;
        if (!pointer.moved && event.type === "pointerup") {
          const selected = hit(event);
          if (selected === "books") actions.current.onSelectBook();
          if (selected === "memories") actions.current.onOpenMemories();
        }
        if (renderer.domElement.hasPointerCapture(event.pointerId))
          renderer.domElement.releasePointerCapture(event.pointerId);
        pointer.id = -1;
        renderer.domElement.style.cursor = "grab";
      };
      const contextLost = (event: Event) => {
        event.preventDefault();
        stopped = true;
        setFailed(true);
      };
      renderer.domElement.addEventListener("pointerdown", down);
      renderer.domElement.addEventListener("pointermove", move);
      renderer.domElement.addEventListener("pointerup", up);
      renderer.domElement.addEventListener("pointercancel", up);
      renderer.domElement.addEventListener("webglcontextlost", contextLost);
      releases.push(() => {
        stopped = true;
        cancelAnimationFrame(frame);
        renderer.domElement.removeEventListener("pointerdown", down);
        renderer.domElement.removeEventListener("pointermove", move);
        renderer.domElement.removeEventListener("pointerup", up);
        renderer.domElement.removeEventListener("pointercancel", up);
        renderer.domElement.removeEventListener(
          "webglcontextlost",
          contextLost,
        );
      });
      const render = (now: number) => {
        frame = requestAnimationFrame(render);
        if (stopped || document.hidden || now - previous < 1000 / 32) return;
        const dt = Math.min((now - previous) / 1000, 0.1);
        previous = now;
        const focus = destination.current;
        if (focus === "books") {
          targetView.set(-0.8, 1.78, 2.25);
          targetLook.set(-1.8, 1.4, -2.6);
        } else if (focus === "memories") {
          targetView.set(0.15, 1.72, 3.6);
          targetLook.set(1.5, 0.88, 1.2);
        } else {
          targetView.set(
            width < 700 ? -0.16 : 0,
            1.74,
            width < 700 ? 4.92 : 4.6,
          );
          targetLook.set(yaw.x, 1.6 + yaw.y, -2.8);
        }
        if (
          !dirty &&
          camera.position.distanceToSquared(targetView) < 0.000001 &&
          look.distanceToSquared(targetLook) < 0.000001
        )
          return;
        const k = reduced.matches ? 1 : 1 - Math.exp(-dt * 4.5);
        camera.position.lerp(targetView, k);
        look.lerp(targetLook, k);
        camera.lookAt(look);
        // Reduced-motion mode remains a stable room, with no camera sway or compulsory motion.
        renderer.info.reset();
        post.composer.render(dt);
        dirty = false;
        host.dataset.ready = "true";
        host.dataset.drawCalls = String(renderer.info.render.calls);
        host.dataset.triangles = String(renderer.info.render.triangles);
      };
      frame = requestAnimationFrame(render);
      return cleanup;
    } catch {
      cleanup();
      setFailed(true);
    }
  }, []);

  return (
    <div
      ref={mount}
      className="home-scene"
      style={{ width: "100%", height: "100%" }}
    >
      {failed && (
        <p className="home-scene-fallback" role="status">
          書斎の表示を休んでいます。本棚と回想録は下のボタンから開けます。
        </p>
      )}
    </div>
  );
}

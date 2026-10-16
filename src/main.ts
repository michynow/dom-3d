import * as THREE from "three";
import "./style.css";
import { PointerLockControls } from "three/addons/controls/PointerLockControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import hankaUrl from "./assets/hanka-3.glb?url";
import { batchStaticMeshes } from "./batch";
import { upgradeMaterials } from "./textures";
import { TouchControls } from "./touch-controls";

(() => {
  const canvas = document.querySelector(
    "canvas",
  ) as HTMLCanvasElement;
  const blocker = document.querySelector(
    "#blocker",
  ) as HTMLDivElement;
  const isTouch = window.matchMedia("(pointer: coarse)").matches;
  const dpr = window.devicePixelRatio;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x9eb6c9);
  scene.fog = new THREE.Fog(0x9eb6c9, 60, 220);
  const renderer = new THREE.WebGLRenderer({
    canvas,
    // High-DPI phones get little from MSAA but pay for it in fill rate.
    antialias: !isTouch || dpr < 2,
    powerPreference: "high-performance",
  });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(dpr, isTouch ? 1.5 : 2));
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  // The scene is static: render the shadow map once after load.
  renderer.shadowMap.autoUpdate = false;
  const camera = new THREE.PerspectiveCamera(
    75,
    window.innerWidth / window.innerHeight,
    0.1,
    1000,
  );

  const controls = new PointerLockControls(camera, document.body);
  const touch = new TouchControls(camera);
  const isActive = () => controls.isLocked || touch.enabled;
  let ready = false;
  let needsRender = true;
  const clock = new THREE.Clock();
  const raycaster = new THREE.Raycaster();
  const colliders: THREE.Object3D[] = [];
  const floors: THREE.Object3D[] = [];
  const movement = {
    forward: false,
    backward: false,
    left: false,
    right: false,
    sprint: false,
    jump: false,
  };
  const walkSpeed = 5;
  const sprintSpeed = 12;
  const eyeHeight = 1.6;
  const playerRadius = 0.35;
  const gravity = 22;
  const jumpSpeed = 7.5;
  const bodyOffsets = [0, -0.75];
  const down = new THREE.Vector3(0, -1, 0);
  const up = new THREE.Vector3(0, 1, 0);
  const front = new THREE.Vector3();
  const right = new THREE.Vector3();
  const moveDir = new THREE.Vector3();
  const origin = new THREE.Vector3();
  const probe = new THREE.Vector3();
  const axisDir = new THREE.Vector3();
  let velocityY = 0;
  let grounded = true;
  const floorName =
    /^(floor_|plinth_|lawn|driveway|terrace_deck|carport_paving|entry_court|entry_step)/;
  const skipCollider =
    /^(foliage|hedge_|lawn|driveway|terrace_deck|carport_paving|entry_court|entry_step|floor_|plinth_)/;

  camera.position.set(0, eyeHeight, 5);

  blocker.textContent = "Loading…";
  blocker.addEventListener("click", () => {
    if (!ready) return;
    if (isTouch) {
      document.documentElement.requestFullscreen?.().catch(() => {});
      touch.enable();
    } else {
      controls.lock();
    }
  });
  const onLock = () => {
    blocker.hidden = true;
  };
  const onUnlock = () => {
    blocker.hidden = false;
    needsRender = true;
  };
  controls.addEventListener("lock", onLock);
  controls.addEventListener("unlock", onUnlock);
  touch.addEventListener("lock", onLock);
  touch.addEventListener("unlock", onUnlock);

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    needsRender = true;
  });

  const onKey = (event: KeyboardEvent, pressed: boolean) => {
    switch (event.code) {
      case "KeyW":
      case "ArrowUp":
        movement.forward = pressed;
        break;
      case "KeyS":
      case "ArrowDown":
        movement.backward = pressed;
        break;
      case "KeyA":
      case "ArrowLeft":
        movement.left = pressed;
        break;
      case "KeyD":
      case "ArrowRight":
        movement.right = pressed;
        break;
      case "ShiftLeft":
      case "ShiftRight":
        movement.sprint = pressed;
        break;
      case "Space":
        if (pressed) movement.jump = true;
        event.preventDefault();
        break;
    }
  };

  document.addEventListener("keydown", (event) => {
    onKey(event, true);
  });
  document.addEventListener("keyup", (event) => {
    onKey(event, false);
  });

  // Image-based lighting gives every PBR material plausible reflections.
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.45;
  pmrem.dispose();

  const hemisphereLight = new THREE.HemisphereLight(
    0xddeeff,
    0x6b5a48,
    0.6,
  );
  scene.add(hemisphereLight);

  const sunDirection = new THREE.Vector3(8, 16, 10).normalize();
  const directionalLight = new THREE.DirectionalLight(0xfff1dc, 2.6);
  directionalLight.castShadow = true;
  directionalLight.shadow.mapSize.setScalar(isTouch ? 1024 : 2048);
  directionalLight.shadow.bias = -0.0004;
  directionalLight.shadow.normalBias = 0.03;
  scene.add(directionalLight, directionalLight.target);

  const fitSunShadow = (box: THREE.Box3) => {
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const r = sphere.radius;
    directionalLight.target.position.copy(sphere.center);
    directionalLight.position
      .copy(sphere.center)
      .addScaledVector(sunDirection, r * 2);
    const cam = directionalLight.shadow.camera;
    cam.left = -r;
    cam.right = r;
    cam.top = r;
    cam.bottom = -r;
    cam.near = r * 0.5;
    cam.far = r * 3.5;
    cam.updateProjectionMatrix();
    directionalLight.target.updateMatrixWorld();
    directionalLight.updateMatrixWorld();
  };

  const isMesh = (obj: THREE.Object3D): obj is THREE.Mesh =>
    (obj as THREE.Mesh).isMesh;

  const compactAttribute = (
    attr: THREE.BufferAttribute | THREE.InterleavedBufferAttribute,
    keep: number[],
  ) => {
    const itemSize = attr.itemSize;
    const dst = new Float32Array(keep.length * itemSize);
    for (let i = 0; i < keep.length; i++) {
      for (let k = 0; k < itemSize; k++) {
        dst[i * itemSize + k] = attr.getComponent(keep[i], k);
      }
    }
    return new THREE.BufferAttribute(dst, itemSize);
  };

  const stripBottomCap = (mesh: THREE.Mesh) => {
    const geometry = mesh.geometry.index
      ? mesh.geometry.toNonIndexed()
      : mesh.geometry.clone();
    const position = geometry.getAttribute("position");
    if (!position) return;
    let minY = Infinity;
    for (let i = 0; i < position.count; i++) {
      minY = Math.min(minY, position.getY(i));
    }
    const keep: number[] = [];
    for (let i = 0; i < position.count; i += 3) {
      const y0 = position.getY(i);
      const y1 = position.getY(i + 1);
      const y2 = position.getY(i + 2);
      if (
        y0 <= minY + 1e-3 &&
        y1 <= minY + 1e-3 &&
        y2 <= minY + 1e-3
      ) {
        continue;
      }
      keep.push(i, i + 1, i + 2);
    }
    if (keep.length === 0 || keep.length === position.count) {
      geometry.dispose();
      return;
    }
    for (const name of Object.keys(geometry.attributes)) {
      geometry.setAttribute(
        name,
        compactAttribute(geometry.getAttribute(name), keep),
      );
    }
    geometry.computeVertexNormals();
    geometry.computeBoundingBox();
    geometry.computeBoundingSphere();
    mesh.geometry.dispose();
    mesh.geometry = geometry;
  };

  const fixFloorWallZFighting = (house: THREE.Object3D) => {
    house.traverse((obj) => {
      if (!isMesh(obj)) return;
      if (/^floor_/.test(obj.name) && obj.name !== "floor_lamp") {
        obj.position.y += 0.004;
        const materials = Array.isArray(obj.material)
          ? obj.material
          : [obj.material];
        for (const material of materials) {
          material.polygonOffset = true;
          material.polygonOffsetFactor = -1;
          material.polygonOffsetUnits = -2;
        }
      }
      if (
        /^(ext_|int_)/.test(obj.name) &&
        /(_s\d+|_sill\d*)$/.test(obj.name)
      ) {
        stripBottomCap(obj);
      }
    });
  };

  const addHole = (
    shape: THREE.Shape,
    box: THREE.Box3,
    pad: number,
  ) => {
    const minX = box.min.x - pad;
    const maxX = box.max.x + pad;
    const minZ = box.min.z - pad;
    const maxZ = box.max.z + pad;
    if (maxX <= minX || maxZ <= minZ) return;
    const hole = new THREE.Path();
    hole.moveTo(minX, minZ);
    hole.lineTo(minX, maxZ);
    hole.lineTo(maxX, maxZ);
    hole.lineTo(maxX, minZ);
    hole.closePath();
    shape.holes.push(hole);
  };

  const addSlabRoof = (
    parent: THREE.Object3D,
    name: string,
    box: THREE.Box3,
    holes: THREE.Box3[],
    overhang: number,
    thickness: number,
    material: THREE.MeshStandardMaterial,
  ) => {
    const minX = box.min.x - overhang;
    const maxX = box.max.x + overhang;
    const minZ = box.min.z - overhang;
    const maxZ = box.max.z + overhang;
    const shape = new THREE.Shape();
    shape.moveTo(minX, minZ);
    shape.lineTo(maxX, minZ);
    shape.lineTo(maxX, maxZ);
    shape.lineTo(minX, maxZ);
    shape.closePath();
    for (const hole of holes) addHole(shape, hole, 0.04);

    const geometry = new THREE.ExtrudeGeometry(shape, {
      depth: thickness,
      bevelEnabled: false,
    });
    geometry.rotateX(Math.PI / 2);
    const roof = new THREE.Mesh(geometry, material);
    roof.name = name;
    roof.position.y = box.max.y + thickness;
    parent.add(roof);
  };

  const addHouseRoofs = (house: THREE.Object3D) => {
    const structure = house.getObjectByName("Structure");
    const joinery = house.getObjectByName("Joinery");
    if (!structure) return;

    const houseBox = new THREE.Box3();
    const chimneyHoles: THREE.Box3[] = [];
    const rooflightHoles: THREE.Box3[] = [];
    const carportBox = new THREE.Box3();
    const terraceBox = new THREE.Box3();
    let hasHouse = false;
    let hasCarport = false;
    let hasTerrace = false;

    structure.traverse((obj) => {
      if (!isMesh(obj)) return;
      if (/^(floor_|ext_|plinth_)/.test(obj.name)) {
        houseBox.expandByObject(obj);
        hasHouse = true;
      }
      if (obj.name === "chimney") {
        chimneyHoles.push(new THREE.Box3().setFromObject(obj));
      }
      if (obj.name.startsWith("carport_post")) {
        carportBox.expandByObject(obj);
        hasCarport = true;
      }
      if (obj.name.startsWith("terrace_post")) {
        terraceBox.expandByObject(obj);
        hasTerrace = true;
      }
    });

    joinery?.traverse((obj) => {
      if (isMesh(obj) && obj.name.startsWith("rooflight")) {
        rooflightHoles.push(new THREE.Box3().setFromObject(obj));
      }
    });

    if (hasHouse) {
      addSlabRoof(
        house,
        "roof_house",
        houseBox,
        [...rooflightHoles, ...chimneyHoles],
        0.45,
        0.28,
        new THREE.MeshStandardMaterial({
          color: 0x2c2c2a,
          roughness: 0.55,
          metalness: 0.12,
          side: THREE.DoubleSide,
        }),
      );
    }

    const timber = new THREE.MeshStandardMaterial({
      color: 0x8a6236,
      roughness: 0.72,
      metalness: 0,
      side: THREE.DoubleSide,
    });
    if (hasCarport) {
      addSlabRoof(
        house,
        "roof_carport",
        carportBox,
        [],
        0.7,
        0.14,
        timber,
      );
    }
    if (hasTerrace) {
      addSlabRoof(
        house,
        "roof_terrace",
        terraceBox,
        [],
        0.55,
        0.12,
        timber,
      );
    }
  };

  const collectColliders = (house: THREE.Object3D) => {
    house.traverse((obj) => {
      if (!isMesh(obj)) return;
      if (floorName.test(obj.name) && obj.name !== "floor_lamp") {
        floors.push(obj);
      } else if (!skipCollider.test(obj.name)) {
        colliders.push(obj);
      }
    });
  };

  const hitsWall = (
    from: THREE.Vector3,
    direction: THREE.Vector3,
    distance: number,
  ) => {
    if (distance <= 0 || colliders.length === 0) return false;
    raycaster.far = distance + playerRadius;
    for (const offset of bodyOffsets) {
      probe.set(from.x, from.y + offset, from.z);
      raycaster.set(probe, direction);
      const hits = raycaster.intersectObjects(colliders, false);
      if (
        hits.length > 0 &&
        hits[0].distance < distance + playerRadius
      ) {
        return true;
      }
    }
    return false;
  };

  const floorHit = (far: number) => {
    if (floors.length === 0) return null;
    probe.copy(camera.position);
    raycaster.set(probe, down);
    raycaster.far = far;
    const hits = raycaster.intersectObjects(floors, false);
    return hits[0] ?? null;
  };

  const snapToFloor = () => {
    const hit = floorHit(eyeHeight + 1.5);
    if (!hit) return;
    camera.position.y = hit.point.y + eyeHeight;
  };

  const applyVertical = (delta: number) => {
    if (grounded && movement.jump) {
      velocityY = jumpSpeed;
      grounded = false;
    }
    movement.jump = false;

    if (grounded) {
      const hit = floorHit(eyeHeight + 0.35);
      if (!hit || hit.distance > eyeHeight + 0.2) {
        grounded = false;
        return;
      }
      camera.position.y = hit.point.y + eyeHeight;
      velocityY = 0;
      return;
    }

    velocityY -= gravity * delta;
    const dy = velocityY * delta;
    if (dy > 0) {
      origin.copy(camera.position);
      if (hitsWall(origin, up, dy + 0.1)) velocityY = 0;
      else camera.position.y += dy;
      return;
    }

    const hit = floorHit(eyeHeight - dy + 0.25);
    if (hit && hit.distance <= eyeHeight) {
      camera.position.y = hit.point.y + eyeHeight;
      velocityY = 0;
      grounded = true;
      return;
    }
    camera.position.y += dy;
  };

  const gltfLoader = new GLTFLoader();
  gltfLoader.load(hankaUrl, async (gltf) => {
    const house = gltf.scene;
    scene.add(house);
    addHouseRoofs(house);
    fixFloorWallZFighting(house);
    collectColliders(house);
    await upgradeMaterials(house, {
      size: isTouch ? 256 : 512,
      anisotropy: Math.min(
        renderer.capabilities.getMaxAnisotropy(),
        isTouch ? 4 : 8,
      ),
    });
    const batches = batchStaticMeshes(house, scene);
    batches.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = !/^batch_(lawn|terrace_decking|kostka|concrete_paving)/.test(mesh.name);
      mesh.receiveShadow = true;
    });
    house.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (mesh.isMesh && mesh.visible) {
        mesh.castShadow = !(mesh.material as THREE.Material).transparent;
        mesh.receiveShadow = true;
      }
    });

    const box = new THREE.Box3().setFromObject(house);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const radius = size.length() * 0.6;

    camera.position.set(center.x, box.min.y + eyeHeight, box.min.z);
    camera.lookAt(center.x, box.min.y + eyeHeight, center.z);
    camera.near = Math.max(radius / 100, 0.1);
    camera.far = radius * 20;
    camera.updateProjectionMatrix();
    snapToFloor();

    fitSunShadow(box);
    renderer.shadowMap.needsUpdate = true;
    renderer.compile(scene, camera);
    ready = true;
    needsRender = true;
    blocker.innerHTML = isTouch
      ? "<p><strong>Tap to enter</strong><br>Left thumb: move · Right thumb: look</p>"
      : "<p><strong>Click to enter</strong><br>WASD: move · Mouse: look · Shift: run · Space: jump · Esc: exit</p>";
  });

  const planeGeometry = new THREE.PlaneGeometry(10, 10);
  const planeMaterial = new THREE.MeshBasicMaterial({
    color: "lightgray",
    side: THREE.DoubleSide,
  });
  const plane = new THREE.Mesh(planeGeometry, planeMaterial);
  plane.rotation.x = -Math.PI / 2;
  plane.position.y = -1;
  scene.add(plane);
  floors.push(plane);

  function animate() {
    requestAnimationFrame(animate);
    const delta = Math.min(clock.getDelta(), 0.05);

    const active = isActive();
    if (active) {
      if (touch.jump) {
        movement.jump = true;
        touch.jump = false;
      }
      const sprinting = movement.sprint || touch.sprint;
      const speed = sprinting ? sprintSpeed : walkSpeed;
      front.setFromMatrixColumn(camera.matrix, 0);
      front.crossVectors(camera.up, front);
      front.y = 0;
      front.normalize();
      right.setFromMatrixColumn(camera.matrix, 0);
      right.y = 0;
      right.normalize();

      moveDir.set(0, 0, 0);
      if (movement.forward) moveDir.add(front);
      if (movement.backward) moveDir.sub(front);
      if (movement.right) moveDir.add(right);
      if (movement.left) moveDir.sub(right);
      // Analog stick: magnitude scales speed, so a light push walks slowly.
      let throttle = 1;
      if (touch.move.lengthSq() > 0) {
        moveDir.addScaledVector(front, touch.move.y);
        moveDir.addScaledVector(right, touch.move.x);
        throttle = Math.min(touch.move.length(), 1);
      }

      if (moveDir.lengthSq() > 0) {
        moveDir.normalize().multiplyScalar(speed * throttle * delta);
        origin.copy(camera.position);
        if (moveDir.x !== 0) {
          axisDir.set(Math.sign(moveDir.x), 0, 0);
          if (!hitsWall(origin, axisDir, Math.abs(moveDir.x))) {
            camera.position.x += moveDir.x;
          }
        }
        origin.copy(camera.position);
        if (moveDir.z !== 0) {
          axisDir.set(0, 0, Math.sign(moveDir.z));
          if (!hitsWall(origin, axisDir, Math.abs(moveDir.z))) {
            camera.position.z += moveDir.z;
          }
        }
      }

      applyVertical(delta);
    }

    // Idle behind the overlay: skip redundant frames to save battery.
    if (!active && !needsRender) return;
    needsRender = false;
    renderer.render(scene, camera);
  }
  animate();
})();

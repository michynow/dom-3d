import * as THREE from "three";

const LOOK_SPEED = 0.005;
const STICK_RADIUS = 56;
const HALF_PI = Math.PI / 2 - 0.01;

/**
 * Twin-stick touch controls: a floating joystick on the left part of the
 * screen moves, dragging anywhere else looks around, and on-screen buttons
 * jump, toggle running and pause.
 */
export class TouchControls extends EventTarget {
  /** Analog movement: x = strafe right, y = forward, length 0..1. */
  readonly move = new THREE.Vector2();
  sprint = false;
  jump = false;
  enabled = false;

  private readonly root: HTMLDivElement;
  private readonly stick: HTMLDivElement;
  private readonly knob: HTMLDivElement;
  private readonly runButton: HTMLButtonElement;
  private readonly euler = new THREE.Euler(0, 0, 0, "YXZ");
  private stickId: number | null = null;
  private lookId: number | null = null;
  private readonly stickOrigin = new THREE.Vector2();
  private readonly lookLast = new THREE.Vector2();

  private readonly camera: THREE.Camera;

  constructor(camera: THREE.Camera) {
    super();
    this.camera = camera;
    this.root = document.createElement("div");
    this.root.id = "touch-ui";
    this.root.hidden = true;
    this.root.innerHTML = `
      <div class="stick" hidden><div class="knob"></div></div>
      <button type="button" class="touch-btn pause" aria-label="Pause">❚❚</button>
      <button type="button" class="touch-btn run" aria-pressed="false">Run</button>
      <button type="button" class="touch-btn jump">Jump</button>
    `;
    document.body.appendChild(this.root);
    this.stick = this.root.querySelector(".stick") as HTMLDivElement;
    this.knob = this.root.querySelector(".knob") as HTMLDivElement;
    this.runButton = this.root.querySelector(".run") as HTMLButtonElement;

    const press = (selector: string, action: () => void) => {
      const button = this.root.querySelector(selector) as HTMLButtonElement;
      button.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
        event.preventDefault();
        action();
      });
    };
    press(".jump", () => {
      this.jump = true;
    });
    press(".run", () => {
      this.sprint = !this.sprint;
      this.runButton.setAttribute("aria-pressed", String(this.sprint));
    });
    press(".pause", () => this.disable());

    this.root.addEventListener("pointerdown", this.onDown);
    this.root.addEventListener("pointermove", this.onMove);
    this.root.addEventListener("pointerup", this.onUp);
    this.root.addEventListener("pointercancel", this.onUp);
    this.root.addEventListener("contextmenu", (event) => event.preventDefault());
  }

  enable() {
    this.enabled = true;
    this.root.hidden = false;
    this.dispatchEvent(new Event("lock"));
  }

  disable() {
    this.enabled = false;
    this.root.hidden = true;
    this.releaseStick();
    this.lookId = null;
    this.dispatchEvent(new Event("unlock"));
  }

  private readonly onDown = (event: PointerEvent) => {
    if (!this.enabled) return;
    event.preventDefault();
    const leftZone = event.clientX < window.innerWidth * 0.45;
    if (leftZone && this.stickId === null) {
      this.stickId = event.pointerId;
      this.stickOrigin.set(event.clientX, event.clientY);
      this.stick.style.transform = `translate(${event.clientX}px, ${event.clientY}px)`;
      this.knob.style.transform = "translate(0px, 0px)";
      this.stick.hidden = false;
    } else if (this.lookId === null) {
      this.lookId = event.pointerId;
      this.lookLast.set(event.clientX, event.clientY);
    } else {
      return;
    }
    this.root.setPointerCapture(event.pointerId);
  };

  private readonly onMove = (event: PointerEvent) => {
    if (event.pointerId === this.stickId) {
      let dx = event.clientX - this.stickOrigin.x;
      let dy = event.clientY - this.stickOrigin.y;
      const length = Math.hypot(dx, dy);
      if (length > STICK_RADIUS) {
        dx *= STICK_RADIUS / length;
        dy *= STICK_RADIUS / length;
      }
      this.knob.style.transform = `translate(${dx}px, ${dy}px)`;
      this.move.set(dx / STICK_RADIUS, -dy / STICK_RADIUS);
      // Small dead zone so a resting thumb does not drift.
      if (this.move.length() < 0.12) this.move.set(0, 0);
    } else if (event.pointerId === this.lookId) {
      const dx = event.clientX - this.lookLast.x;
      const dy = event.clientY - this.lookLast.y;
      this.lookLast.set(event.clientX, event.clientY);
      this.euler.setFromQuaternion(this.camera.quaternion);
      this.euler.y -= dx * LOOK_SPEED;
      this.euler.x = THREE.MathUtils.clamp(this.euler.x - dy * LOOK_SPEED, -HALF_PI, HALF_PI);
      this.camera.quaternion.setFromEuler(this.euler);
    }
  };

  private readonly onUp = (event: PointerEvent) => {
    if (event.pointerId === this.stickId) this.releaseStick();
    if (event.pointerId === this.lookId) this.lookId = null;
  };

  private releaseStick() {
    this.stickId = null;
    this.move.set(0, 0);
    this.stick.hidden = true;
  }
}

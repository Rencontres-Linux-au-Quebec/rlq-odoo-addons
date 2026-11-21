/** @odoo-module **/

const TAU = Math.PI * 2;

// Wheel disc radius (world units); its height (diameter) is 2 * WHEEL_RADIUS.
const WHEEL_RADIUS = 2;
// The pointer cone pivots just outside the rim and is 0.5 long, so it reaches
// about 0.6 past the rim. Both are needed wherever it sits: the pivot to place
// it, the reach to keep it inside the camera frame and clear of Tux.
const POINTER_PIVOT = WHEEL_RADIUS + 0.28;
const POINTER_REACH = WHEEL_RADIUS + 0.6;
// Tux is normalized so its height stays within 25%-40% of the wheel height.
// 0.33 sits in the middle of that band.
const TUX_HEIGHT_FRACTION = 0.33;
// Resting pose of the flipper-arm pivots. The arms pivot AT the shoulder
// (their top is at the pivot, on the body surface), so raising them never
// detaches the shoulder. X = forward tilt, Z = outward splay (per side) kept
// at rest so the flippers stay outside the belly and visible.
const REST_ARM_X = 0.3;
const REST_ARM_Z = 0.5;

// Beyond 2 the extra device pixels are invisible on a spinning wheel and only
// cost memory: a projector at dpr 3 asks for nine times the drawing buffer.
const MAX_PIXEL_RATIO = 2;

// What drawing buffer to allocate for a canvas measured at `width` x `height`
// CSS px. Pure, and exported, because this is the whole of the sizing policy
// that _resize() applies and the only part of it worth testing:
//  - a canvas not laid out yet (0x0) gives null: skipped rather than given an
//    invented size, whose aspect ratio would be wrong. The ResizeObserver
//    calls back as soon as there is a real size to use.
//  - `runaway` marks a height nobody could look at -- one viewport and a bit.
//    Reaching it means some stylesheet has put the canvas back into its own
//    height computation (see the backstop in _resize()). The limit is set on
//    the symptom, not on the GPU: a runaway adds a few pixels per frame, so a
//    ceiling of several thousand px takes half a minute to reach and by then
//    the wheel has long scrolled out of sight.
//  - the pixel ratio is capped so the buffer stays inside the GPU's maximum
//    texture size (8192 with software WebGL): past it the context is lost and
//    nothing renders at all.
export function computeCanvasSize({
    width, height, viewportHeight, devicePixelRatio, maxTextureSize,
}) {
    const w = Math.round(width);
    const measuredHeight = Math.round(height);
    if (!(w >= 1) || !(measuredHeight >= 1)) {
        return null;
    }
    const maxH = Math.max(1200, Math.round((viewportHeight || 0) * 1.2));
    const runaway = measuredHeight > maxH;
    const h = runaway ? maxH : measuredHeight;
    const pixelRatio = Math.min(
        devicePixelRatio || 1,
        MAX_PIXEL_RATIO,
        (maxTextureSize || 4096) / Math.max(w, h)
    );
    return { w, h, measuredHeight, pixelRatio, runaway };
}

// Where the pointer sits, as a world angle in radians, from the raffle's
// `pointer_angle` setting. That setting is DEGREES CLOCKWISE FROM THE TOP, the
// way a clock face reads: 0 up, 90 right, 180 down, -90 left. World angles run
// counter-clockwise from +X, which is why the sign flips.
export function pointerWorldAngle(deg) {
    return Math.PI / 2 - ((Number(deg) || 0) * Math.PI) / 180;
}

// The wheel texture is drawn on a canvas and applied to a CircleGeometry with
// the default flipY, which MIRRORS the angular direction: segment `index`
// (canvas arc [index*seg, (index+1)*seg]) ends up centered at mesh-local angle
// -(index + 0.5) * seg. To bring segment `index` under a pointer sitting at
// world angle φ the wheel must rotate by R such that
// -(index+0.5)*seg + R ≡ φ, i.e. R = φ + (index+0.5)*seg  (plus `turns` full
// turns for the spin effect). φ defaults to π/2, the top of the wheel.
export function computeTargetAngle(
    index, total, turns, pointerAngle = Math.PI / 2
) {
    const seg = TAU / total;
    return turns * TAU + pointerAngle + (index + 0.5) * seg;
}

// Absolute wheel rotation to reach after a spin: congruent (mod 2π) to the
// angle that puts segment `index` under the pointer, and at least `turns`
// full turns forward from `startRotation` (so the animation always spins
// forward regardless of accumulated rotation).
export function computeAbsoluteTarget(
    startRotation, index, total, turns, pointerAngle = Math.PI / 2
) {
    const TAU = Math.PI * 2;
    const landing =
        ((computeTargetAngle(index, total, turns, pointerAngle) % TAU) + TAU) %
        TAU;
    const startMod = ((startRotation % TAU) + TAU) % TAU;
    let target = startRotation - startMod + landing;
    while (target < startRotation + turns * TAU) {
        target += TAU;
    }
    return target;
}

const PALETTE = [
    "#e63946", "#f1a208", "#2a9d8f", "#457b9d",
    "#8338ec", "#ff7b00", "#06d6a0", "#ef476f",
];

function disposeTree(obj) {
    if (!obj) return;
    obj.traverse((node) => {
        if (node.geometry) node.geometry.dispose();
        const mats = Array.isArray(node.material)
            ? node.material
            : node.material
            ? [node.material]
            : [];
        for (const m of mats) {
            if (m.map) m.map.dispose();
            m.dispose();
        }
    });
}

// Wrap a segment label onto up to `maxLines` lines, shrinking the font to
// fit `maxW`; ellipsize if it still overflows.
function labelLines(ctx, text, maxW, maxLines, minFont, maxFont) {
    const words = (text || "").trim().split(/\s+/).filter(Boolean);
    if (!words.length) {
        return { lines: [""], fontSize: maxFont };
    }
    const wrap = (fs) => {
        ctx.font = `bold ${fs}px sans-serif`;
        const lines = [];
        let cur = "";
        for (const w of words) {
            const trial = cur ? cur + " " + w : w;
            if (!cur || ctx.measureText(trial).width <= maxW) {
                cur = trial;
            } else {
                lines.push(cur);
                cur = w;
            }
        }
        if (cur) {
            lines.push(cur);
        }
        return lines;
    };
    for (let fs = maxFont; fs >= minFont; fs -= 2) {
        const lines = wrap(fs);
        if (
            lines.length <= maxLines &&
            lines.every((l) => ctx.measureText(l).width <= maxW)
        ) {
            return { lines, fontSize: fs };
        }
    }
    // Still too long: cap to maxLines and ellipsize the last one.
    const lines = wrap(minFont).slice(0, maxLines);
    let last = lines[lines.length - 1] || "";
    while (last && ctx.measureText(last + "…").width > maxW) {
        last = last.slice(0, -1);
    }
    lines[lines.length - 1] = last + "…";
    return { lines, fontSize: minFont };
}

function segmentTexture(names) {
    const THREE = window.THREE;
    const size = 1024;
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext("2d");
    const n = Math.max(names.length, 1);
    const seg = TAU / n;
    const cx = size / 2;
    const cy = size / 2;
    const r = size / 2;
    for (let i = 0; i < n; i++) {
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, r, i * seg, (i + 1) * seg);
        ctx.closePath();
        ctx.fillStyle = PALETTE[i % PALETTE.length];
        ctx.fill();
        // label (wrapped onto up to 4 lines for long names)
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(i * seg + seg / 2);
        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "right";
        ctx.textBaseline = "middle";
        const { lines, fontSize } = labelLines(
            ctx, names[i] || "", r - 90, 4, 16, 34
        );
        ctx.font = `bold ${fontSize}px sans-serif`;
        const lineH = fontSize * 1.12;
        const startY = -((lines.length - 1) * lineH) / 2;
        lines.forEach((ln, k) =>
            ctx.fillText(ln, r - 30, startY + k * lineH)
        );
        ctx.restore();
    }
    const tex = new THREE.CanvasTexture(canvas);
    tex.needsUpdate = true;
    return tex;
}

// Word-wrap `text` onto a flag cloth: shrink the font until the wrapped lines
// fit within maxW x maxH. Returns {lines, fontSize, lineH}.
function fitFlagLines(ctx, text, maxW, maxH) {
    const words = (text || "").trim().split(/\s+/).filter(Boolean);
    for (let fontSize = 96; fontSize >= 28; fontSize -= 6) {
        ctx.font = `bold ${fontSize}px sans-serif`;
        const lines = [];
        let cur = "";
        for (const wd of words) {
            const trial = cur ? cur + " " + wd : wd;
            if (!cur || ctx.measureText(trial).width <= maxW) {
                cur = trial;
            } else {
                lines.push(cur);
                cur = wd;
            }
        }
        if (cur) lines.push(cur);
        const lineH = fontSize * 1.15;
        const fits = lines.length * lineH <= maxH &&
            lines.every((l) => ctx.measureText(l).width <= maxW);
        if (fits) {
            return { lines, fontSize, lineH };
        }
    }
    return { lines: words.length ? words : [""], fontSize: 28, lineH: 32 };
}

// Soft radial flame gradient for a realistic (additive) candle flame.
function flameTexture() {
    const THREE = window.THREE;
    const s = 128;
    const c = document.createElement("canvas");
    c.width = c.height = s;
    const ctx = c.getContext("2d");
    const g = ctx.createRadialGradient(
        s / 2, s * 0.62, 2, s / 2, s * 0.62, s * 0.46
    );
    g.addColorStop(0, "rgba(255,255,238,1)");
    g.addColorStop(0.22, "rgba(255,232,130,0.96)");
    g.addColorStop(0.5, "rgba(255,150,40,0.7)");
    g.addColorStop(0.78, "rgba(205,45,12,0.25)");
    g.addColorStop(1, "rgba(120,10,0,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, s, s);
    const tex = new THREE.CanvasTexture(c);
    tex.needsUpdate = true;
    return tex;
}

// Side-view cherub playing a trumpet, no halo (theater theme decoration).
// An elegant classical herald angel in profile, playing a gilded trumpet,
// no halo. `flip=true` mirrors it (trumpet points the other way).
function angelTexture(flip) {
    const THREE = window.THREE;
    const w = 360;
    const h = 500;
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const ctx = c.getContext("2d");
    if (flip) {
        ctx.translate(w, 0);
        ctx.scale(-1, 1);
    }
    const ivory = ctx.createLinearGradient(60, 60, 300, 480);
    ivory.addColorStop(0, "#fcf7ec");
    ivory.addColorStop(0.5, "#eee4cf");
    ivory.addColorStop(1, "#d3c7a8");
    const shadow = "rgba(120,105,72,0.22)";
    const gold = ctx.createLinearGradient(230, 60, 346, 180);
    gold.addColorStop(0, "#f0d075");
    gold.addColorStop(1, "#b8860b");

    // ---- Wing (behind), elegant with layered feathers ----
    ctx.fillStyle = ivory;
    ctx.beginPath();
    ctx.moveTo(150, 300);
    ctx.bezierCurveTo(60, 250, 30, 120, 70, 70);
    ctx.bezierCurveTo(120, 120, 152, 200, 176, 300);
    ctx.closePath();
    ctx.fill();
    for (let i = 0; i < 6; i++) {
        const t = i / 5;
        const bx = 150 - t * 90;
        const by = 300 - t * 42;
        const tx = 72 + t * 28;
        const ty = 92 + t * 28;
        ctx.beginPath();
        ctx.moveTo(bx, by);
        ctx.quadraticCurveTo((bx + tx) / 2 - 16, (by + ty) / 2, tx, ty);
        ctx.quadraticCurveTo((bx + tx) / 2 + 8, (by + ty) / 2 + 14, bx + 10, by + 4);
        ctx.closePath();
        ctx.fillStyle = i % 2 ? "#f4ecd8" : "#e6dbc0";
        ctx.fill();
        ctx.strokeStyle = shadow;
        ctx.lineWidth = 1.4;
        ctx.stroke();
    }

    // ---- Flowing gown with folds ----
    ctx.fillStyle = ivory;
    ctx.beginPath();
    ctx.moveTo(182, 250);
    ctx.bezierCurveTo(150, 330, 120, 420, 110, 486);
    ctx.lineTo(258, 486);
    ctx.bezierCurveTo(250, 400, 236, 320, 224, 250);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = shadow;
    ctx.lineWidth = 6;
    ctx.lineCap = "round";
    for (const [x0, x1] of [[168, 150], [196, 190], [214, 228]]) {
        ctx.beginPath();
        ctx.moveTo(x0, 272);
        ctx.quadraticCurveTo(x0 - 6, 382, x1, 480);
        ctx.stroke();
    }
    ctx.strokeStyle = "rgba(255,255,245,0.5)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(184, 268);
    ctx.quadraticCurveTo(178, 382, 170, 480);
    ctx.stroke();
    // gold sash
    ctx.strokeStyle = gold;
    ctx.lineWidth = 12;
    ctx.beginPath();
    ctx.moveTo(176, 258);
    ctx.quadraticCurveTo(205, 278, 234, 262);
    ctx.stroke();

    // ---- Torso ----
    ctx.fillStyle = ivory;
    ctx.beginPath();
    ctx.ellipse(202, 216, 44, 54, -0.1, 0, Math.PI * 2);
    ctx.fill();

    // ---- Arm raising the trumpet ----
    ctx.strokeStyle = ivory;
    ctx.lineWidth = 24;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(214, 208);
    ctx.quadraticCurveTo(250, 188, 270, 150);
    ctx.stroke();

    // ---- Head (serene profile) with flowing hair, no halo ----
    ctx.fillStyle = "#d9b878";
    ctx.beginPath();
    ctx.arc(196, 140, 46, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#f6ead2";
    ctx.beginPath();
    ctx.moveTo(214, 106);
    ctx.bezierCurveTo(244, 114, 248, 140, 236, 150);
    ctx.bezierCurveTo(246, 156, 240, 167, 231, 168);
    ctx.bezierCurveTo(236, 178, 227, 187, 213, 184);
    ctx.bezierCurveTo(195, 182, 183, 160, 185, 138);
    ctx.bezierCurveTo(188, 118, 200, 106, 214, 106);
    ctx.closePath();
    ctx.fill();
    // waves of golden hair over the crown + falling down the back
    ctx.fillStyle = "#e6c489";
    for (let i = 0; i < 6; i++) {
        const a = Math.PI * (0.5 + i * 0.14);
        ctx.beginPath();
        ctx.arc(
            196 + Math.cos(a) * 44, 132 + Math.sin(a) * 44, 14, 0, Math.PI * 2
        );
        ctx.fill();
    }
    ctx.beginPath();
    ctx.moveTo(160, 150);
    ctx.quadraticCurveTo(140, 210, 168, 250);
    ctx.quadraticCurveTo(186, 214, 178, 160);
    ctx.closePath();
    ctx.fill();
    // soft cheek shading
    ctx.fillStyle = "rgba(180,140,90,0.16)";
    ctx.beginPath();
    ctx.ellipse(212, 158, 9, 13, 0, 0, Math.PI * 2);
    ctx.fill();

    // ---- Gilded herald trumpet with a small banner ----
    // Drawn in a local frame rotated to the trumpet axis so the bell is a
    // real funnel (its mouth rim stays perpendicular to the tube).
    const goldC = "#cd9b1d";
    ctx.save();
    ctx.translate(262, 150); // at the raised hand
    ctx.rotate(-0.8); // point up toward the wheel; +x = tube axis
    // straight tube
    ctx.strokeStyle = goldC;
    ctx.lineWidth = 12;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(72, 0);
    ctx.stroke();
    // three little valve caps on the tube
    ctx.fillStyle = goldC;
    for (const vx of [30, 42, 54]) {
        ctx.fillRect(vx - 2.5, -11, 5, 9);
    }
    // small pennant banner hanging under the tube
    ctx.fillStyle = "#f3ead4";
    ctx.beginPath();
    ctx.moveTo(28, 6);
    ctx.lineTo(58, 6);
    ctx.lineTo(58, 32);
    ctx.lineTo(43, 24);
    ctx.lineTo(28, 32);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = goldC;
    ctx.lineWidth = 2;
    ctx.stroke();
    // funnel bell: flares from the throat (x=72) to the mouth (x=106)
    const bellGrad = ctx.createLinearGradient(72, -26, 108, 26);
    bellGrad.addColorStop(0, "#b8860b");
    bellGrad.addColorStop(0.5, "#f7e08a");
    bellGrad.addColorStop(1, "#c8960d");
    ctx.fillStyle = bellGrad;
    ctx.beginPath();
    ctx.moveTo(72, -7);
    ctx.quadraticCurveTo(94, -12, 106, -27); // upper wall flares out
    ctx.quadraticCurveTo(114, 0, 106, 27); // around the mouth rim
    ctx.quadraticCurveTo(94, 12, 72, 7); // lower wall back to throat
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#8a6508";
    ctx.lineWidth = 2;
    ctx.stroke();
    // mouth opening: rim ellipse + dark interior, perpendicular to the axis
    ctx.fillStyle = goldC;
    ctx.beginPath();
    ctx.ellipse(106, 0, 8, 27, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(80,54,8,0.6)";
    ctx.beginPath();
    ctx.ellipse(106, 0, 4.5, 22, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    const tex = new THREE.CanvasTexture(c);
    tex.needsUpdate = true;
    return tex;
}

// One webbed, 3-toed orange foot (like a duck's / penguin's), laid flat.
function buildTuxFoot(THREE, footMat, side) {
    const s = new THREE.Shape();
    // 2D outline in the XY plane; +y is "forward". Heel at the back, three
    // rounded toe lobes with webbing dips at the front.
    // Shorter front-to-back (less elongated) than a real webbed foot.
    s.moveTo(-0.14, -0.12);
    s.lineTo(0.14, -0.12);
    s.lineTo(0.2, 0.06);
    s.quadraticCurveTo(0.22, 0.24, 0.1, 0.21); // toe 1 + web dip
    s.quadraticCurveTo(0.03, 0.28, -0.02, 0.21); // toe 2
    s.quadraticCurveTo(-0.09, 0.28, -0.13, 0.2); // toe 3
    s.quadraticCurveTo(-0.22, 0.14, -0.2, 0.06);
    s.closePath();
    const geo = new THREE.ExtrudeGeometry(s, {
        depth: 0.06, bevelEnabled: true, bevelThickness: 0.02,
        bevelSize: 0.02, bevelSegments: 2,
    });
    const foot = new THREE.Mesh(geo, footMat);
    // Lay the shape flat with the toes pointing forward (+z, toward the
    // camera) and the sole facing down.
    foot.rotation.x = Math.PI / 2;
    const pivot = new THREE.Group();
    pivot.add(foot);
    pivot.scale.setScalar(1.2);
    pivot.rotation.y = side * 0.28; // splay the toes outward
    return pivot;
}

// A flat, bird-wing flipper: a rounded, ELONGATED shoulder at the top that
// blends smoothly into the body (no hard rectangular cut), sweeping down and
// tapering to a rounded tip. Broad flat face toward +Z. Its top region sits
// above y=0 so it can be embedded in the body for a seamless join.
function buildFlipper(THREE, mat) {
    const w = 0.14; // half-width
    const len = 1.02;
    const s = new THREE.Shape();
    // rounded, elongated shoulder over the top
    s.moveTo(-w * 0.85, 0.06);
    s.quadraticCurveTo(0, 0.24, w * 0.95, 0.1); // long rounded shoulder crest
    // outer edge sweeping down to the tip
    s.quadraticCurveTo(w * 1.12, -len * 0.42, w * 0.5, -len * 0.86);
    // rounded tip
    s.quadraticCurveTo(w * 0.05, -len * 1.02, -w * 0.42, -len * 0.82);
    // inner edge back up to the shoulder
    s.quadraticCurveTo(-w * 0.82, -len * 0.42, -w * 0.85, 0.06);
    s.closePath();
    const geo = new THREE.ExtrudeGeometry(s, {
        depth: 0.1, bevelEnabled: true, bevelThickness: 0.035,
        bevelSize: 0.035, bevelSegments: 3,
    });
    geo.translate(0, 0, -0.05); // center the thickness on z=0
    return new THREE.Mesh(geo, mat);
}

// A heraldic fleur-de-lys (Québec) drawn on a transparent canvas, to sit on
// Tux's white belly. Blue on transparent.
function fleurDeLysTexture() {
    const THREE = window.THREE;
    const s = 256;
    const c = document.createElement("canvas");
    c.width = s;
    c.height = s;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, s, s);
    ctx.fillStyle = "#0d3b78"; // Québec blue
    const cx = s / 2;
    const petal = (dir) => {
        // dir = 0 central, -1 left, +1 right
        ctx.beginPath();
        if (dir === 0) {
            ctx.moveTo(cx, 24);
            ctx.bezierCurveTo(cx + 44, 72, cx + 40, 150, cx + 16, 180);
            ctx.bezierCurveTo(cx + 6, 190, cx - 6, 190, cx - 16, 180);
            ctx.bezierCurveTo(cx - 40, 150, cx - 44, 72, cx, 24);
        } else {
            const k = dir;
            ctx.moveTo(cx + k * 8, 122);
            ctx.bezierCurveTo(
                cx + k * 74, 78, cx + k * 100, 132, cx + k * 70, 176
            );
            ctx.bezierCurveTo(
                cx + k * 54, 198, cx + k * 28, 192, cx + k * 14, 174
            );
            ctx.bezierCurveTo(
                cx + k * 26, 150, cx + k * 22, 134, cx + k * 8, 122
            );
        }
        ctx.closePath();
        ctx.fill();
    };
    petal(-1);
    petal(1);
    petal(0);
    // horizontal band
    ctx.beginPath();
    if (ctx.roundRect) {
        ctx.roundRect(cx - 56, 180, 112, 22, 9);
    } else {
        ctx.rect(cx - 56, 180, 112, 22);
    }
    ctx.fill();
    // base foot + two small side flares
    const foot = (k) => {
        ctx.beginPath();
        if (k === 0) {
            ctx.moveTo(cx, 202);
            ctx.bezierCurveTo(cx + 17, 218, cx + 18, 244, cx, 252);
            ctx.bezierCurveTo(cx - 18, 244, cx - 17, 218, cx, 202);
        } else {
            ctx.moveTo(cx + k * 30, 202);
            ctx.bezierCurveTo(
                cx + k * 42, 216, cx + k * 42, 232, cx + k * 30, 238
            );
            ctx.bezierCurveTo(
                cx + k * 24, 226, cx + k * 24, 214, cx + k * 30, 202
            );
        }
        ctx.closePath();
        ctx.fill();
    };
    foot(-1);
    foot(1);
    foot(0);
    const tex = new THREE.CanvasTexture(c);
    tex.needsUpdate = true;
    return tex;
}

function buildProceduralTux() {
    const THREE = window.THREE;
    const g = new THREE.Group();
    const black = new THREE.MeshStandardMaterial({
        color: 0x181818, roughness: 0.45,
    });
    const white = new THREE.MeshStandardMaterial({
        color: 0xfbfbfb, roughness: 0.4,
    });
    // Beak: two-tone mandibles like the reference — a bright yellow upper and
    // a darker golden lower. Emissive keeps the pointed tip out of shadow.
    const upperBeakMat = new THREE.MeshStandardMaterial({
        color: 0xf5d130, roughness: 0.32, metalness: 0.05,
        emissive: new THREE.Color(0x6a5200), emissiveIntensity: 0.45,
    });
    const lowerBeakMat = new THREE.MeshStandardMaterial({
        color: 0xcf9012, roughness: 0.4, metalness: 0.05,
        emissive: new THREE.Color(0x3a2600), emissiveIntensity: 0.45,
    });
    const footMat = new THREE.MeshStandardMaterial({
        color: 0xf59a1e, roughness: 0.45,
        emissive: new THREE.Color(0x3a2200), emissiveIntensity: 0.35,
    });
    const pupilMat = new THREE.MeshStandardMaterial({
        color: 0x0d0d0d, roughness: 0.25,
    });
    const mouthMat = new THREE.MeshStandardMaterial({
        color: 0xb06a10, roughness: 0.6,
    });
    // slightly lighter than the head so the brows read against the black.
    const browMat = new THREE.MeshStandardMaterial({
        color: 0x333333, roughness: 0.5,
    });
    const nostrilMat = new THREE.MeshStandardMaterial({
        color: 0x8a5510, roughness: 0.6,
    });

    // ---- Body + neck + head as ONE continuous, SMOOTH silhouette (a single
    // lathe through a Catmull-Rom spline), so there is no step/deformation at
    // the neck: the outline from the head down to the shoulders is one direct
    // curve (a rounded-top head, a gentle neck pinch, a pear body).
    const bodyCtrl = [
        [0.02, -0.95], [0.3, -0.88], [0.5, -0.68], [0.58, -0.42],
        [0.56, -0.1], [0.48, 0.18], [0.4, 0.42], [0.35, 0.6],
        [0.3, 0.78], [0.29, 0.9], [0.33, 1.06], [0.36, 1.26],
        [0.36, 1.46], [0.34, 1.62], [0.3, 1.75], [0.22, 1.85],
        [0.12, 1.91], [0.03, 1.94],
    ].map(([r, y]) => new THREE.Vector2(r, y));
    const bodyPts = new THREE.SplineCurve(bodyCtrl).getPoints(80);
    const body = new THREE.Mesh(new THREE.LatheGeometry(bodyPts, 48), black);
    body.scale.set(1, 1, 0.92); // slightly egg cross-section
    g.add(body);

    // ---- White front as ONE continuous PEAR (not two circles): wide rounded
    // belly tapering up through the chest to a point under the chin. A single
    // lathe, flattened front-to-back and pushed forward so it wraps the front
    // + centre, leaving black flanks on the sides.
    // Bottom stops mid-body (rounded), leaving the lower torso + feet black,
    // as in the reference; tapers up to a point under the chin.
    const whiteCtrl = [
        [0.02, -0.52], [0.26, -0.44], [0.38, -0.22], [0.44, -0.02],
        [0.43, 0.2], [0.37, 0.42], [0.29, 0.62], [0.21, 0.8],
        [0.15, 0.95], [0.09, 1.08], [0.02, 1.14],
    ].map(([r, y]) => new THREE.Vector2(r, y));
    const whitePts = new THREE.SplineCurve(whiteCtrl).getPoints(72);
    const belly = new THREE.Mesh(new THREE.LatheGeometry(whitePts, 44), white);
    belly.scale.set(1.0, 1, 0.72); // flatten front-to-back
    belly.position.set(0, 0, 0.3); // push forward -> white front, black flanks
    g.add(belly);
    // A discreet crease line between the chest (thorax) and the belly (navel).
    const creaseMat = new THREE.MeshStandardMaterial({
        color: 0xd4d4d4, roughness: 0.55,
    });
    const crease = new THREE.Mesh(
        new THREE.TorusGeometry(0.18, 0.013, 8, 26, Math.PI), creaseMat
    );
    crease.rotation.x = Math.PI * 0.42;
    crease.rotation.z = Math.PI; // opening downward -> a smile-shaped crease
    crease.position.set(0, 0.14, 0.6);
    g.add(crease);

    // ---- Eyes: white sclera + pupil (cross-eyed Tux look) + an eyebrow.
    // Stored so the idle loop can blink them (squash on Y).
    const eyes = [];
    const eyeGroup = (side) => {
        const eg = new THREE.Group();
        const sclera = new THREE.Mesh(
            new THREE.SphereGeometry(0.1, 24, 24), white
        );
        sclera.scale.set(0.82, 1.2, 0.5);
        eg.add(sclera);
        const pupil = new THREE.Mesh(
            new THREE.SphereGeometry(0.045, 18, 18), pupilMat
        );
        pupil.position.set(0, 0, 0.06); // centered -> looks straight forward
        eg.add(pupil);
        eg.rotation.z = 0; // level (no cross-eyed tilt)
        // raised, leaving clear space above the beak
        eg.position.set(side * 0.14, 1.42, 0.4);
        eyes.push(eg);
        return eg;
    };
    g.add(eyeGroup(-1));
    g.add(eyeGroup(1));
    g.userData.eyes = eyes;
    // Eyebrows: raised well above the eyes (not in front of them), angled.
    const brow = (side) => {
        const b = new THREE.Mesh(
            new THREE.BoxGeometry(0.15, 0.034, 0.05), browMat
        );
        b.position.set(side * 0.14, 1.57, 0.4);
        b.rotation.z = side * 0.3;
        return b;
    };
    g.add(brow(-1), brow(1));

    // ---- Beak: wider, bright upper + darker lower mandible, a mouth line and
    // nostrils, pointing essentially straight forward.
    const beak = new THREE.Group();
    const upper = new THREE.Mesh(
        new THREE.ConeGeometry(0.2, 0.46, 24), upperBeakMat
    );
    upper.rotation.x = Math.PI / 2;
    upper.scale.set(1, 1, 0.5); // wide + flat
    upper.position.y = 0.035;
    beak.add(upper);
    const lower = new THREE.Mesh(
        new THREE.ConeGeometry(0.17, 0.4, 24), lowerBeakMat
    );
    lower.rotation.x = Math.PI / 2;
    lower.scale.set(1, 1, 0.48);
    lower.position.y = -0.055;
    beak.add(lower);
    // thin seam between the two mandibles
    const mouth = new THREE.Mesh(
        new THREE.BoxGeometry(0.18, 0.01, 0.28), mouthMat
    );
    mouth.position.set(0, -0.01, 0.12);
    beak.add(mouth);
    // two nostril holes near the base of the upper mandible
    const nostril = (side) => {
        const n = new THREE.Mesh(
            new THREE.SphereGeometry(0.016, 10, 10), nostrilMat
        );
        n.position.set(side * 0.05, 0.06, -0.02);
        return n;
    };
    beak.add(nostril(-1), nostril(1));
    beak.rotation.x = 0.07; // essentially straight forward (slight dip)
    beak.position.set(0, 1.16, 0.46);
    g.add(beak);

    // ---- Arms: bird-wing flippers whose rounded, elongated shoulder crest is
    // embedded in the body so it blends smoothly (no hard rectangular cut).
    // The crest sits just above the pivot; the pivot is on the body surface,
    // so raising the arm rotates it about the shoulder without detaching. The
    // outward splay lives on the pivot's Z so the wing stays visible.
    const makeArm = (side) => {
        const pivot = new THREE.Group();
        const flip = buildFlipper(THREE, black);
        flip.position.set(0, -0.16, 0); // crest just above the pivot (embeds)
        pivot.add(flip);
        pivot.position.set(side * 0.3, 0.58, 0.16);
        pivot.rotation.set(REST_ARM_X, 0, side * REST_ARM_Z);
        return pivot;
    };
    const armL = makeArm(-1);
    const armR = makeArm(1);
    g.add(armL, armR);
    g.userData.armL = armL;
    g.userData.armR = armR;

    // ---- Webbed, 3-toed orange feet, at the very bottom, toes forward and
    // in front of the belly so they stay visible.
    const footL = buildTuxFoot(THREE, footMat, -1);
    footL.position.set(-0.26, -0.92, 0.42);
    g.add(footL);
    const footR = buildTuxFoot(THREE, footMat, 1);
    footR.position.set(0.26, -0.92, 0.42);
    g.add(footR);
    return g;
}

export class RaffleScene {
    constructor(canvas, { onReady } = {}) {
        const THREE = window.THREE;
        this.THREE = THREE;
        this.canvas = canvas;
        this.rotation = 0;
        this._raf = null;
        this._spinRaf = null;
        this._animRaf = null;
        this._disposed = false;
        this._particles = null;
        this._animProps = [];
        this.tuxBase = null;
        this._ro = null;
        // Last size applied to the renderer, in CSS px, and its pixel
        // ratio (see _resize()).
        this._sizeW = 0;
        this._sizeH = 0;
        this._sizePixelRatio = 0;
        this._sizeWarned = false;
        this.theme = "light";
        this.tuxHalfWidth = 0.5;
        this._contentMinX = -WHEEL_RADIUS;
        this._contentMaxX = WHEEL_RADIUS;
        this._tuxSide = -1; // -1 = left of the wheel, +1 = right (linux theme)
        this._tuxVisible = true; // hidden by default via setTuxVisible()
        this._spinning = false;
        this._flapVel = 0;
        // Pointer world angle; π/2 is the top. setPointerAngle() moves it.
        this._pointerAngle = Math.PI / 2;
        this.renderer = new THREE.WebGLRenderer({
            canvas, antialias: true, alpha: true,
        });
        this._resize();
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(
            50, this._aspect(), 0.1, 100
        );
        this.camera.position.set(0, 0.5, 6);
        this.camera.lookAt(0, 0, 0);
        this.ambient = new THREE.AmbientLight(0xffffff, 0.9);
        this.scene.add(this.ambient);
        const dir = new THREE.DirectionalLight(0xffffff, 0.8);
        dir.position.set(2, 4, 5);
        this.scene.add(dir);
        // wheel
        this.wheelMat = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
        this.wheel = new THREE.Mesh(
            new THREE.CircleGeometry(WHEEL_RADIUS, 64), this.wheelMat
        );
        this.scene.add(this.wheel);
        // wooden rim around the wheel
        this.woodRim = new THREE.Mesh(
            new THREE.TorusGeometry(WHEEL_RADIUS + 0.06, 0.13, 16, 80),
            new THREE.MeshStandardMaterial({
                color: 0x8b5a2b, roughness: 0.8, metalness: 0.1,
            })
        );
        this.woodRim.position.z = -0.02;
        this.scene.add(this.woodRim);
        // pins at each segment boundary (rotate with the wheel)
        this.pinsGroup = new THREE.Group();
        this.scene.add(this.pinsGroup);
        // pointer / flapper - color adapts to the theme, position to the
        // raffle's pointer_angle (top by default)
        this.pointerMat = new THREE.MeshStandardMaterial({ color: 0x333333 });
        this.pointer = new THREE.Mesh(
            new THREE.ConeGeometry(0.16, 0.5, 16), this.pointerMat
        );
        this.scene.add(this.pointer);
        this._placePointer();
        // tux placeholder (procedural until glb loads)
        this.tux = buildProceduralTux();
        this.scene.add(this.tux);
        this._placeTux(this.tux);
        this._loop();
        // Keep the render buffer and framing in sync with the canvas size so
        // the scene never stretches and stays fully visible on any window.
        if (window.ResizeObserver) {
            this._ro = new ResizeObserver(() => {
                this._resize();
                this._fitCamera();
            });
            this._ro.observe(this.canvas);
        }
        if (onReady) onReady();
    }

    _aspect() {
        // Ratio of the size actually applied to the renderer rather than a
        // fresh DOM read: it keeps the framing and the projection matrix in
        // agreement, and avoids a forced reflow inside the observer below.
        return this._sizeH ? this._sizeW / this._sizeH : 1;
    }

    // The canvas is measured here and its drawing buffer (the width/height
    // ATTRIBUTES, since setSize is called with updateStyle=false) is written
    // from that measurement, while the ResizeObserver watches the very same
    // element. Writing only on a real change keeps that loop at zero gain.
    _resize() {
        const caps = this.renderer.capabilities || {};
        const size = computeCanvasSize({
            width: this.canvas.clientWidth,
            height: this.canvas.clientHeight,
            viewportHeight: window.innerHeight,
            devicePixelRatio: window.devicePixelRatio,
            maxTextureSize: caps.maxTextureSize,
        });
        if (!size) return;
        const { w, h, pixelRatio } = size;
        // Backstop, never expected to fire. Keeping the canvas out of its own
        // height computation is the stylesheet's job (`.o_raffle_canvas` has a
        // definite `flex-basis` precisely so the drawing buffer written below
        // can never come back as a layout input). If another stylesheet ever
        // reopens that loop, pin the box from here so the evening is not lost
        // to a blank wheel, and say so once instead of failing in silence.
        if (size.runaway && !this._sizeWarned) {
            this._sizeWarned = true;
            console.warn(
                `event_raffle: canvas measured at ${w}x${size.measuredHeight} ` +
                `px, clamped to ${h} px — a stylesheet feeds the canvas size ` +
                `back into the layout.`
            );
            const style = this.canvas.style;
            style.setProperty("flex", "1 1 0", "important");
            style.setProperty("min-height", "0", "important");
            style.setProperty("height", "auto", "important");
        }
        // Idempotent: with nothing to change we write nothing, so the
        // ResizeObserver above is not woken again by our own write. The pixel
        // ratio is part of the comparison so that dragging the window to a
        // screen of another density still redraws sharp.
        if (w === this._sizeW && h === this._sizeH &&
                pixelRatio === this._sizePixelRatio) {
            return;
        }
        this._sizeW = w;
        this._sizeH = h;
        this._sizePixelRatio = pixelRatio;
        this.renderer.setPixelRatio(pixelRatio);
        this.renderer.setSize(w, h, false);
        if (this.camera) {
            this.camera.aspect = w / h;
            this.camera.updateProjectionMatrix();
        }
    }

    // Frame the whole scene (wheel + pointer + Tux) for the current aspect
    // ratio, so nothing is ever cut off and the picture is never distorted.
    // Show / hide Tux (hidden by default). When hidden the camera reframes to
    // the wheel alone so it stays centered.
    setTuxVisible(visible) {
        this._tuxVisible = visible !== false;
        if (this.tux) this.tux.visible = this._tuxVisible;
        this._fitCamera();
    }

    // Move the pointer around the rim. `deg` is the raffle's pointer_angle:
    // degrees clockwise from the top, so 0 up, 90 right, 180 down, -90 left.
    // The wheel lands the winner under wherever it now sits, Tux steps aside
    // if it came to his side, and the camera reframes to keep it visible.
    setPointerAngle(deg) {
        const angle = pointerWorldAngle(deg);
        if (angle === this._pointerAngle) return;
        this._pointerAngle = angle;
        this._placePointer();
        if (this.tux) this._placeTux(this.tux);
        this._fitCamera();
    }

    // Seat the cone on the rim at the pointer angle, apex toward the centre.
    // A cone points +Y by default (world angle π/2), so aiming it inwards --
    // along φ + π -- is a rotation of φ + π/2 about Z. The flapper deflection
    // in _updateFlapper() is applied on top of that base.
    _placePointer() {
        if (!this.pointer) return;
        const a = this._pointerAngle;
        this.pointer.position.set(
            Math.cos(a) * POINTER_PIVOT, Math.sin(a) * POINTER_PIVOT, 0.15
        );
        this.pointerZBase = a + Math.PI / 2;
        this.pointer.rotation.z = this.pointerZBase;
        this._flapVel = 0;
    }

    // Add / remove a logo on Tux's belly (a child of the Tux group, so it
    // follows every move). Only "fleur_de_lys" is supported for now.
    setBellyLogo(logo) {
        const THREE = this.THREE;
        if (!this.tux) return;
        const want = logo === "fleur_de_lys";
        if (want && !this._bellyLogo) {
            const tex = fleurDeLysTexture();
            const mat = new THREE.MeshBasicMaterial({
                map: tex, transparent: true, depthWrite: false,
            });
            const plane = new THREE.Mesh(
                new THREE.PlaneGeometry(0.42, 0.5), mat
            );
            plane.position.set(0, 0.02, 0.64); // on the belly front, facing +z
            this._bellyLogo = plane;
            this.tux.add(plane);
        } else if (!want && this._bellyLogo) {
            this.tux.remove(this._bellyLogo);
            if (this._bellyLogo.material.map) {
                this._bellyLogo.material.map.dispose();
            }
            this._bellyLogo.material.dispose();
            this._bellyLogo.geometry.dispose();
            this._bellyLogo = null;
        }
    }

    _fitCamera() {
        if (!this.camera) return;
        let minX = this._tuxVisible ? this._contentMinX : -WHEEL_RADIUS;
        let maxX = this._tuxVisible
            ? this._contentMaxX !== undefined
                ? this._contentMaxX
                : WHEEL_RADIUS
            : WHEEL_RADIUS;
        if (this._angels) {
            // keep both side angels fully in frame
            minX = Math.min(minX, -(WHEEL_RADIUS + 1.45));
            maxX = WHEEL_RADIUS + 1.45;
        }
        // The pointer sticks out past the rim wherever it sits, so it is the
        // frame's business on whichever side that is -- not the top only.
        const ptrX = Math.cos(this._pointerAngle) * POINTER_REACH;
        const ptrY = Math.sin(this._pointerAngle) * POINTER_REACH;
        minX = Math.min(minX, ptrX);
        maxX = Math.max(maxX, ptrX);
        if (this._isLinuxTheme) {
            // Reserve empty space on the LEFT for the background terminal, so
            // the wheel + penguin shift to the right half of the canvas and
            // the terminal is no longer hidden behind them.
            minX -= (maxX - minX) * 0.85;
        }
        // a little headroom below for Tux's feet and the wheel's wooden rim
        const minY = Math.min(-WHEEL_RADIUS - 0.3, ptrY);
        const maxY = Math.max(WHEEL_RADIUS + 0.25, ptrY);
        const cx = (minX + maxX) / 2;
        const cy = (minY + maxY) / 2;
        const halfW = (maxX - minX) / 2;
        const halfH = (maxY - minY) / 2;
        const margin = 1.12;
        const vFov = (this.camera.fov * Math.PI) / 180;
        const aspect = this._aspect();
        const distV = (halfH * margin) / Math.tan(vFov / 2);
        const distH = (halfW * margin) / (Math.tan(vFov / 2) * aspect);
        const dist = Math.max(distV, distH);
        this.camera.position.set(cx, cy, dist);
        this.camera.lookAt(cx, cy, 0);
        this.camera.updateProjectionMatrix();
        // In the Linux themes the camera is panned left (to reveal the
        // terminal); yaw Tux so it still faces the viewer ("de face").
        this._tuxYaw = 0;
        if (this._isLinuxTheme && this.tuxBase) {
            const t = this.tuxBase.position;
            this._tuxYaw = Math.atan2(cx - t.x, dist - t.z);
        }
    }

    setSegments(names) {
        this.segCount = Math.max(names.length, 1);
        if (this.wheelMat.map) this.wheelMat.map.dispose();
        this.wheelMat.map = segmentTexture(names);
        this.wheelMat.needsUpdate = true;
        this._buildPins(this.segCount);
    }

    // A metal pin at each segment boundary; the pins rotate with the wheel and
    // the flapper (pointer) reacts as each pin passes under it.
    _buildPins(n) {
        const THREE = this.THREE;
        while (this.pinsGroup.children.length) {
            const c = this.pinsGroup.children.pop();
            if (c.geometry) c.geometry.dispose();
            if (c.material) c.material.dispose();
        }
        const seg = TAU / n;
        for (let i = 0; i < n; i++) {
            const a = i * seg;
            const pin = new THREE.Mesh(
                new THREE.SphereGeometry(0.075, 12, 12),
                new THREE.MeshStandardMaterial({
                    color: 0xe0e0e0, metalness: 0.8, roughness: 0.25,
                })
            );
            pin.position.set(
                Math.cos(a) * WHEEL_RADIUS,
                Math.sin(a) * WHEEL_RADIUS,
                0.09
            );
            this.pinsGroup.add(pin);
        }
        this.pinCount = n;
    }

    // Rotate the pins with the wheel and deflect the flapper as a pin nears
    // the pointer (rides over the peg, then rests in the gap). A pin sits
    // under the pointer when (rotation - pointer angle) is a whole number of
    // segments, so the pointer angle is what the phase is measured against.
    _updateFlapper() {
        if (!this.pointer) return;
        this.pinsGroup.rotation.z = this.rotation;
        if (this._spinning) {
            const n = this.pinCount || this.segCount || 1;
            const seg = TAU / n;
            const d = (this.rotation - this._pointerAngle) / seg;
            const frac = d - Math.floor(d);
            const nearest = Math.min(frac, 1 - frac);
            const closeness = 1 - nearest / 0.5;
            const lift = Math.pow(closeness, 6);
            // deflect away from the incoming pin (reversed direction)
            this.pointer.rotation.z = this.pointerZBase - lift * 0.45;
            this._flapVel = 0;
        } else {
            // spring the flapper back to straight with a little overshoot
            const disp = this.pointerZBase - this.pointer.rotation.z;
            this._flapVel = this._flapVel * 0.6 + disp * 0.25;
            this.pointer.rotation.z += this._flapVel;
        }
    }

    // Normalize the Tux object so its
    // height is TUX_HEIGHT_FRACTION of the wheel height, then stand it just
    // left of the wheel with its feet on the wheel's bottom line. Records
    // tuxWheelRatio for verification.
    _placeTux(obj) {
        const THREE = this.THREE;
        obj.position.set(0, 0, 0);
        obj.scale.setScalar(1);
        obj.updateMatrixWorld(true);
        let box = new THREE.Box3().setFromObject(obj);
        let size = box.getSize(new THREE.Vector3());
        const wheelHeight = WHEEL_RADIUS * 2;
        const targetHeight = wheelHeight * TUX_HEIGHT_FRACTION;
        const scale = targetHeight / (size.y || 1);
        obj.scale.setScalar(scale);
        obj.updateMatrixWorld(true);
        box = new THREE.Box3().setFromObject(obj);
        size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        // Stand Tux just outside the wheel on its side (right for the Linux
        // theme, left otherwise), feet on -WHEEL_RADIUS.
        const side = this._tuxSide || -1;
        // When the pointer has been moved to Tux's side it occupies that gap,
        // so step him out past its tip instead of letting the cone cross him.
        const ptrX = Math.cos(this._pointerAngle) * POINTER_REACH;
        const gap = 0.3 + Math.max(0, side * ptrX - WHEEL_RADIUS);
        obj.position.x =
            side * (WHEEL_RADIUS + size.x / 2 + gap) - center.x;
        obj.position.y = -WHEEL_RADIUS - box.min.y;
        obj.position.z = 0.5 - center.z;
        this.wheelHeight = wheelHeight;
        this.tuxHeight = size.y;
        this.tuxHalfWidth = size.x / 2;
        // Content extents in world X, used to frame the camera symmetrically.
        this._contentMinX = Math.min(
            -WHEEL_RADIUS, side * (WHEEL_RADIUS + size.x + gap)
        );
        this._contentMaxX = Math.max(
            WHEEL_RADIUS, side * (WHEEL_RADIUS + size.x + gap)
        );
        this.tuxWheelRatio = size.y / wheelHeight;
        // Base transform the animations offset from and restore to.
        this.tuxBase = {
            position: obj.position.clone(),
            scale: obj.scale.clone(),
        };
        this._fitCamera(); // also computes this._tuxYaw (faces camera in Linux)
        obj.rotation.y = this._tuxYaw || 0;
    }

    // ---- Tux animations ---------------------------------------------------
    // Each returns a Promise resolving when the choreography ends; the caller
    // then spins the wheel. All are procedural so they work on both the GLTF
    // model and the procedural fallback penguin.

    static get ANIMATIONS() {
        return ["peace", "jump", "flag", "dance"];
    }

    _runAnim(durationMs, frameFn) {
        return new Promise((resolve) => {
            const t0 = performance.now();
            const step = (now) => {
                if (this._disposed) {
                    resolve();
                    return;
                }
                const t = Math.min((now - t0) / durationMs, 1);
                frameFn(t);
                if (t < 1) {
                    this._animRaf = requestAnimationFrame(step);
                } else {
                    resolve();
                }
            };
            this._animRaf = requestAnimationFrame(step);
        });
    }

    _resetTux() {
        if (this.tux && this.tuxBase) {
            this.tux.position.copy(this.tuxBase.position);
            this.tux.scale.copy(this.tuxBase.scale);
            this.tux.rotation.set(0, this._tuxYaw || 0, 0);
            this._setArms(0, 0);
        }
    }

    // Raise the flipper arms about their shoulder pivots. `left`/`right` are
    // the extra lift beyond the resting outward splay (0 = resting). The
    // shoulder (pivot) never moves, so the arm stays attached.
    _setArms(left, right) {
        const u = this.tux && this.tux.userData;
        if (!u) return;
        if (u.armL) u.armL.rotation.set(REST_ARM_X, 0, -(REST_ARM_Z + left));
        if (u.armR) u.armR.rotation.set(REST_ARM_X, 0, REST_ARM_Z + right);
    }

    // Small physical keyboard Tux "types" on during the Linux themes.
    _makeKeyboard() {
        const THREE = this.THREE;
        const g = new THREE.Group();
        const board = new THREE.Mesh(
            new THREE.BoxGeometry(1.0, 0.06, 0.42),
            new THREE.MeshStandardMaterial({ color: 0x23232a, roughness: 0.6 })
        );
        g.add(board);
        const keyMat = new THREE.MeshStandardMaterial({
            color: 0x51515e, roughness: 0.5,
        });
        for (let r = 0; r < 3; r++) {
            for (let c = 0; c < 9; c++) {
                const k = new THREE.Mesh(
                    new THREE.BoxGeometry(0.08, 0.03, 0.08), keyMat
                );
                k.position.set(-0.4 + c * 0.1, 0.045, -0.11 + r * 0.11);
                g.add(k);
            }
        }
        g.rotation.x = -0.4; // tilt the deck up toward Tux/camera
        return g;
    }

    // Bring out the keyboard in front of Tux (Linux themes only).
    startTyping() {
        if (this._disposed || !this.tux || !this.tuxBase) return;
        if (!this._tuxVisible) return; // no Tux -> no keyboard
        this._typing = true;
        if (!this._keyboard) {
            this._keyboard = this._makeKeyboard();
            this.scene.add(this._keyboard);
        }
        const base = this.tuxBase.position;
        this._keyboard.scale.setScalar(Math.max(this.tuxHalfWidth * 2.1, 0.5));
        this._keyboard.position.set(
            base.x,
            base.y + this.tuxHeight * 0.2, // a bit lower, at hand height
            base.z + this.tuxHalfWidth + 0.12
        );
    }

    stopTyping() {
        this._typing = false;
        if (this._keyboard) {
            this.scene.remove(this._keyboard);
            disposeTree(this._keyboard);
            this._keyboard = null;
        }
        if (this.tux && this.tuxBase && !this._tuxBusy) this._resetTux();
    }

    // Per-frame idle behaviour: random blinking always; a keyboard-typing pose
    // while typing; occasional head-scratch when nothing else is happening.
    _updateIdle(now) {
        const tux = this.tux;
        const u = tux && tux.userData;
        if (!u) return;

        // ---- Blink (any time) ----
        if (u.eyes) {
            if (this._nextBlink == null) {
                this._nextBlink = now + 1200 + Math.random() * 2500;
            }
            let open = 1;
            const dt = now - this._nextBlink;
            if (dt >= 0) {
                const dur = 150;
                if (dt < dur) {
                    open = Math.abs(dt / dur - 0.5) * 2; // 1 -> 0 -> 1
                } else {
                    this._nextBlink = now + 1800 + Math.random() * 3500;
                }
            }
            const sy = 0.06 + 0.94 * open;
            for (const e of u.eyes) e.scale.y = sy;
        }

        // ---- Typing pose ----
        if (this._typing) {
            const tp = now / 110;
            const bendL = 0.95 + Math.max(0, Math.sin(tp)) * 0.3;
            const bendR = 0.95 + Math.max(0, Math.sin(tp + 1.7)) * 0.3;
            if (u.armL) u.armL.rotation.set(bendL, 0, 0.42);
            if (u.armR) u.armR.rotation.set(bendR, 0, -0.42);
            tux.rotation.set(0.16, this._tuxYaw || 0, 0); // lean, facing camera
            return;
        }

        // ---- Wheel is spinning: Tux turns on the vertical axis to show its
        // 3D form (except in the Linux themes, where it stays facing forward).
        if (this._spinning) {
            tux.rotation.y = this._isLinuxTheme
                ? this._tuxYaw || 0
                : Math.sin(now / 320) * 1.4;
            tux.position.y =
                this.tuxBase.position.y + Math.abs(Math.sin(now / 260)) * 0.08;
            return;
        }

        // ---- Head-scratch (only when fully idle) ----
        if (this._tuxBusy) return;
        if (this._nextScratch == null) {
            this._nextScratch = now + 4000 + Math.random() * 6000;
        }
        if (this._scratchUntil && now < this._scratchUntil) {
            const p = 1 - (this._scratchUntil - now) / 1500;
            const wig = Math.sin(p * Math.PI * 6) * 0.22;
            // right flipper up toward the head (rotates about the shoulder)
            if (u.armR) u.armR.rotation.set(-0.1, 0, 2.5 + wig);
            if (u.armL) u.armL.rotation.set(REST_ARM_X, 0, -REST_ARM_Z);
            tux.rotation.z = -0.05;
        } else {
            if (now >= this._nextScratch) {
                this._scratchUntil = now + 1500;
                this._nextScratch = now + 7000 + Math.random() * 8000;
            } else {
                this._setArms(0, 0); // resting splay
                tux.rotation.z = 0;
                tux.rotation.y = this._tuxYaw || 0;
            }
        }
    }

    _labelSprite(text, { fg = "#ffffff", bg = "rgba(0,0,0,0.55)" } = {}) {
        const THREE = this.THREE;
        const w = 512;
        const h = 256;
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = bg;
        const r = 40;
        ctx.beginPath();
        ctx.moveTo(r, 10);
        ctx.arcTo(w - 10, 10, w - 10, h - 10, r);
        ctx.arcTo(w - 10, h - 10, 10, h - 10, r);
        ctx.arcTo(10, h - 10, 10, 10, r);
        ctx.arcTo(10, 10, w - 10, 10, r);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = fg;
        ctx.font = "bold 110px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(text, w / 2, h / 2);
        const tex = new THREE.CanvasTexture(canvas);
        tex.needsUpdate = true;
        const sprite = new THREE.Sprite(
            new THREE.SpriteMaterial({ map: tex, transparent: true })
        );
        sprite.scale.set(2, 1, 1);
        return sprite;
    }

    _addProp(obj) {
        this._animProps.push(obj);
        this.scene.add(obj);
        return obj;
    }

    _clearAnimProps() {
        for (const p of this._animProps) {
            this.scene.remove(p);
            disposeTree(p);
            if (p.material && p.material.map) p.material.map.dispose();
            if (p.material) p.material.dispose();
        }
        this._animProps = [];
    }

    _makeFlag(text) {
        const THREE = this.THREE;
        const group = new THREE.Group();
        const pole = new THREE.Mesh(
            new THREE.CylinderGeometry(0.03, 0.03, 2.2, 8),
            new THREE.MeshStandardMaterial({ color: 0x8b5a2b })
        );
        pole.position.y = 1.1;
        group.add(pole);
        const w = 1024;
        const h = 384;
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#e63946";
        ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const { lines, fontSize, lineH } = fitFlagLines(
            ctx, text || "Vive le logiciel libre", w - 80, h - 60
        );
        ctx.font = `bold ${fontSize}px sans-serif`;
        const startY = h / 2 - ((lines.length - 1) * lineH) / 2;
        lines.forEach((ln, i) => ctx.fillText(ln, w / 2, startY + i * lineH));
        const tex = new THREE.CanvasTexture(canvas);
        const cloth = new THREE.Mesh(
            new THREE.PlaneGeometry(1.6, 0.6),
            new THREE.MeshBasicMaterial({
                map: tex, side: THREE.DoubleSide, transparent: true,
            })
        );
        cloth.position.set(0.83, 1.7, 0);
        group.add(cloth);
        group.userData.cloth = cloth;
        return group;
    }

    async playTuxAnimation(name, opts = {}) {
        if (this._disposed || !this.tux || !this.tuxBase) return;
        if (!this._tuxVisible) return; // Tux hidden: skip its animation
        this._tuxBusy = true;
        try {
            switch (name) {
                case "peace":
                    await this._animPeace();
                    break;
                case "jump":
                    await this._animJump();
                    break;
                case "flag":
                    await this._animFlag(opts.flagText);
                    break;
                case "dance":
                    await this._animDance();
                    break;
                default:
                    break;
            }
        } catch (e) {
            console.warn("event_raffle: tux animation failed", e);
        } finally {
            this._clearAnimProps();
            this._resetTux();
            this._tuxBusy = false;
        }
    }

    _animPeace() {
        const base = this.tuxBase.position;
        const label = this._addProp(this._labelSprite("✌"));
        label.position.set(base.x, base.y + this.tuxHeight + 0.5, base.z);
        return this._runAnim(1800, (t) => {
            // two little hops + a nod, right arm raised for the peace sign
            this.tux.position.y =
                base.y + Math.abs(Math.sin(t * Math.PI * 2)) * 0.4;
            this.tux.rotation.x = Math.sin(t * Math.PI * 4) * 0.12;
            this._setArms(0.35, 1.7 + Math.sin(t * Math.PI * 6) * 0.12);
            label.material.opacity = t < 0.8 ? 1 : (1 - t) / 0.2;
        });
    }

    _animJump() {
        const base = this.tuxBase.position;
        const s = this.tuxBase.scale.x;
        const label = this._addProp(this._labelSprite(":)"));
        label.position.set(base.x, base.y + this.tuxHeight + 0.5, base.z);
        return this._runAnim(1600, (t) => {
            const jump = Math.sin(t * Math.PI) * 1.3;
            this.tux.position.y = base.y + jump;
            // squash on takeoff/landing, stretch mid-air
            const stretch = 1 + Math.sin(t * Math.PI) * 0.18;
            this.tux.scale.set(s / stretch, s * stretch, s / stretch);
            // arms fling up during the jump, small mid-air turn
            this._setArms(Math.sin(t * Math.PI) * 1.6, Math.sin(t * Math.PI) * 1.6);
            this.tux.rotation.y = Math.sin(t * Math.PI * 2) * 0.4;
            label.material.opacity = Math.sin(t * Math.PI);
        });
    }

    _animFlag(flagText) {
        const base = this.tuxBase.position;
        const flag = this._addProp(this._makeFlag(flagText));
        const cloth = flag.userData.cloth;
        return this._runAnim(2200, (t) => {
            // flag rises next to Tux, then waves
            const rise = Math.min(t / 0.3, 1);
            flag.position.set(base.x + 0.4, base.y - 0.2 + rise * 0.1, base.z);
            flag.scale.setScalar(0.6 + rise * 0.4);
            if (cloth) cloth.rotation.y = Math.sin(t * Math.PI * 8) * 0.25;
            // Tux holds the flag high in the right hand and leans proudly
            this._setArms(0.25, 1.3 + Math.sin(t * Math.PI * 8) * 0.12);
            this.tux.rotation.z = Math.sin(t * Math.PI) * 0.1;
        });
    }

    // Showcase move: little jumps while swinging the arms and swaying / turning
    // left-right-left so the belly shows off in 3D.
    _animDance() {
        const base = this.tuxBase.position;
        const label = this._addProp(this._labelSprite("♪"));
        label.position.set(base.x, base.y + this.tuxHeight + 0.5, base.z);
        return this._runAnim(2800, (t) => {
            const beat = t * Math.PI * 6;
            const sway = Math.sin(t * Math.PI * 3);
            // little hops
            this.tux.position.y = base.y + Math.abs(Math.sin(beat)) * 0.28;
            // sway left-right-left
            this.tux.position.x = base.x + sway * 0.22;
            this.tux.rotation.z = Math.sin(beat) * 0.14;
            // wide turn on the VERTICAL axis (spins left<->right) so the 3D
            // form is obvious: front -> profile -> back -> profile -> front.
            this.tux.rotation.y = Math.sin(t * Math.PI * 3) * 1.9;
            // arms swing up alternately on the beat
            const up = 0.7 + Math.abs(Math.sin(beat)) * 0.7;
            this._setArms(up + Math.sin(beat) * 0.35, up - Math.sin(beat) * 0.35);
            label.material.opacity = 0.6 + 0.4 * Math.sin(beat);
        });
    }

    get _isLinuxTheme() {
        return this.theme === "linux" || this.theme === "linux_light";
    }

    setTheme(theme) {
        const known = [
            "light", "dark", "spectacle", "theatre",
            "linux", "linux_light", "rave",
        ];
        this.theme = known.includes(theme) ? theme : "light";
        // Tux stands on the right for the Linux themes (so it does not cover
        // the background terminal), on the left for every other theme.
        const side = this._isLinuxTheme ? 1 : -1;
        if (side !== this._tuxSide && this.tux) {
            this._tuxSide = side;
            this._placeTux(this.tux);
        } else {
            this._tuxSide = side;
        }
        const ptr = {
            light: 0x333333, dark: 0xffffff, spectacle: 0xffffff,
            theatre: 0xffd700, linux: 0x8bffab, linux_light: 0x1a7f37,
            rave: 0x33ffff,
        };
        const amb = {
            light: [0xffffff, 0.9], dark: [0xffffff, 0.7],
            spectacle: [0xffffff, 0.35], theatre: [0xffe9b0, 0.85],
            linux: [0xbfffd0, 0.85], linux_light: [0xffffff, 1.0],
            rave: [0xffffff, 0.35],
        };
        if (this.pointerMat) {
            this.pointerMat.color.set(ptr[this.theme]);
        }
        if (this.ambient) {
            this.ambient.color.set(amb[this.theme][0]);
            this.ambient.intensity = amb[this.theme][1];
        }
        this._applySpotlight(this.theme === "spectacle");
        this._applyAngels(this.theme === "theatre");
        this._applyRave(this.theme === "rave");
    }

    _applySpotlight(on) {
        const THREE = this.THREE;
        if (on && !this._spot) {
            this._spot = new THREE.SpotLight(
                0xffffff, 8, 24, 0.5, 0.4, 1.2
            );
            this._spot.position.set(0, 6, 6);
            this._spot.target.position.set(0, 0, 0);
            this.scene.add(this._spot);
            this.scene.add(this._spot.target);
        } else if (!on && this._spot) {
            this.scene.remove(this._spot);
            this.scene.remove(this._spot.target);
            this._spot = null;
        }
    }

    _applyRave(on) {
        const THREE = this.THREE;
        if (on && !this._rave) {
            this._rave = [];
            const colors = [
                0xff1e6e, 0x1eff8f, 0x1e8bff, 0xffe11e, 0xff2fd0, 0x22e3ff,
            ];
            for (const c of colors) {
                const light = new THREE.PointLight(c, 3, 16);
                this.scene.add(light);
                this._rave.push(light);
            }
            // 3D laser beams fanning from a rig above the wheel
            this._raveBeams = new THREE.Group();
            this._raveBeams.position.set(0, WHEEL_RADIUS + 1.4, -0.6);
            const beamColors = [0xff2fd0, 0x22e3ff, 0x7cff2f, 0xffe11e];
            for (let i = 0; i < 10; i++) {
                const geo = new THREE.CylinderGeometry(
                    0.012, 0.06, 10, 6, 1, true
                );
                geo.translate(0, -5, 0); // pivot at the top
                const beam = new THREE.Mesh(
                    geo,
                    new THREE.MeshBasicMaterial({
                        color: beamColors[i % beamColors.length],
                        transparent: true,
                        opacity: 0.5,
                        blending: THREE.AdditiveBlending,
                        depthWrite: false,
                        side: THREE.DoubleSide,
                    })
                );
                beam.userData.base = -0.95 + (i / 9) * 1.9;
                this._raveBeams.add(beam);
            }
            this.scene.add(this._raveBeams);
        } else if (!on && this._rave) {
            for (const l of this._rave) {
                this.scene.remove(l);
            }
            this._rave = null;
            if (this._raveBeams) {
                this.scene.remove(this._raveBeams);
                disposeTree(this._raveBeams);
                this._raveBeams = null;
            }
        }
    }

    _makeCandle() {
        const THREE = this.THREE;
        const g = new THREE.Group();
        const body = new THREE.Mesh(
            new THREE.CylinderGeometry(0.06, 0.07, 0.5, 12),
            new THREE.MeshStandardMaterial({ color: 0xfff2cc })
        );
        body.position.y = 0.25;
        g.add(body);
        const wick = new THREE.Mesh(
            new THREE.CylinderGeometry(0.012, 0.012, 0.06, 6),
            new THREE.MeshStandardMaterial({ color: 0x222222 })
        );
        wick.position.y = 0.53;
        g.add(wick);
        // Realistic flame: soft additive glow + bright core + flickering light.
        const outer = new THREE.Sprite(
            new THREE.SpriteMaterial({
                map: flameTexture(),
                blending: THREE.AdditiveBlending,
                transparent: true,
                depthWrite: false,
            })
        );
        outer.scale.set(0.26, 0.5, 1);
        outer.position.y = 0.66;
        g.add(outer);
        const core = new THREE.Sprite(
            new THREE.SpriteMaterial({
                map: flameTexture(),
                blending: THREE.AdditiveBlending,
                transparent: true,
                depthWrite: false,
            })
        );
        core.scale.set(0.12, 0.26, 1);
        core.position.y = 0.62;
        g.add(core);
        const light = new THREE.PointLight(0xffa64d, 1.4, 3.5);
        light.position.set(0, 0.66, 0.1);
        g.add(light);
        g.userData.flame = { outer, core, light };
        return g;
    }

    // Cinematic flicker: layered noise on the flame scale, offset and light.
    _flickerFlame(candle, t) {
        const f = candle.userData.flame;
        if (!f) return;
        const n =
            Math.sin(t * 91) * 0.5 +
            Math.sin(t * 47.3 + 1.3) * 0.3 +
            Math.sin(t * 23.7 + 0.6) * 0.2;
        const s = 1 + n * 0.22;
        f.outer.scale.set(0.26 * (1 + n * 0.08), 0.5 * s, 1);
        f.outer.position.x = n * 0.02;
        f.core.scale.set(0.12 * (1 - n * 0.05), 0.26 * s, 1);
        f.core.position.x = n * 0.015;
        f.light.intensity = 1.4 + n * 0.7;
    }

    // Dispatch the configured winner celebration.
    celebrate(type) {
        if (this._disposed || !this.tux || !this.tuxBase) {
            return Promise.resolve();
        }
        // Tux-centric celebrations need the penguin; when it is hidden fall
        // back to a confetti burst.
        if (!this._tuxVisible && ["candles", "trumpet", "diabolo"].includes(type)) {
            type = "confetti";
        }
        this._tuxBusy = true;
        let p;
        switch (type) {
            case "confetti":
                p = this._celebrateConfetti();
                break;
            case "fireworks":
                p = this._celebrateFireworks();
                break;
            case "trumpet":
                p = this._celebrateTrumpet();
                break;
            case "diabolo":
                p = this._celebrateDiabolo();
                break;
            case "candles":
            default:
                p = this.celebrateWithCandles();
                break;
        }
        return Promise.resolve(p).finally(() => {
            this._tuxBusy = false;
        });
    }

    // Victory dance: Tux dances holding a lit candle in each hand.
    celebrateWithCandles() {
        const base = this.tuxBase.position;
        const hw = this.tuxHalfWidth;
        const midY = base.y + this.tuxHeight * 0.45;
        const leftX = base.x - hw - 0.15;
        const rightX = base.x + hw + 0.15;
        const left = this._addProp(this._makeCandle());
        const right = this._addProp(this._makeCandle());
        left.position.set(leftX, midY, base.z + 0.3);
        right.position.set(rightX, midY, base.z + 0.3);
        return this._runAnim(2600, (t) => {
            const beat = t * Math.PI * 6;
            const sway = Math.sin(t * Math.PI * 4);
            const hop = Math.abs(Math.sin(beat)) * 0.22;
            this.tux.rotation.z = sway * 0.2;
            this.tux.position.x = base.x + sway * 0.16;
            this.tux.position.y = base.y + hop;
            // gentle turn to show off the belly while dancing
            this.tux.rotation.y = sway * 0.35;
            // raise the candles overhead on each beat
            const lift = 0.6 + Math.abs(Math.sin(beat)) * 0.6;
            this._setArms(lift, lift);
            const candleY = midY + hop + Math.abs(Math.sin(beat)) * 0.22;
            left.position.set(leftX + sway * 0.16, candleY, base.z + 0.3);
            right.position.set(rightX + sway * 0.16, candleY, base.z + 0.3);
            this._flickerFlame(left, t * 2600);
            this._flickerFlame(right, t * 2600 + 40);
        }).then(() => {
            this._clearAnimProps();
            this._resetTux();
        });
    }

    _celebrateFireworks() {
        const base = this.tuxBase.position;
        let last = -1;
        return this._runAnim(2800, (t) => {
            this.tux.position.y =
                base.y + Math.abs(Math.sin(t * Math.PI * 4)) * 0.2;
            const burst = Math.floor(t * 5);
            if (burst !== last) {
                last = burst;
                this.fireworks();
            }
        }).then(() => this._resetTux());
    }

    _celebrateConfetti() {
        const THREE = this.THREE;
        const n = 400;
        const geo = new THREE.BufferGeometry();
        const pos = new Float32Array(n * 3);
        const col = new Float32Array(n * 3);
        const vel = [];
        const colors = [
            [0.9, 0.2, 0.3], [0.2, 0.6, 0.9], [0.95, 0.75, 0.1],
            [0.5, 0.2, 0.9], [0.1, 0.8, 0.5],
        ];
        for (let i = 0; i < n; i++) {
            pos[i * 3] = 0;
            pos[i * 3 + 1] = WHEEL_RADIUS + 0.5;
            pos[i * 3 + 2] = 0.6;
            const a = Math.random() * Math.PI - Math.PI / 2;
            const sp = 0.04 + Math.random() * 0.09;
            vel.push([
                Math.cos(a) * sp,
                Math.abs(Math.sin(a)) * sp * 1.4 + 0.03,
                (Math.random() - 0.5) * 0.02,
            ]);
            const c = colors[i % colors.length];
            col[i * 3] = c[0];
            col[i * 3 + 1] = c[1];
            col[i * 3 + 2] = c[2];
        }
        geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
        const conf = new THREE.Points(
            geo,
            new THREE.PointsMaterial({
                size: 0.13, vertexColors: true, transparent: true,
            })
        );
        this._addProp(conf);
        const p = conf.geometry.attributes.position;
        return this._runAnim(2800, (t) => {
            for (let i = 0; i < p.count; i++) {
                const v = vel[i];
                p.array[i * 3] += v[0];
                p.array[i * 3 + 1] += v[1];
                p.array[i * 3 + 2] += v[2];
                v[1] -= 0.0016;
            }
            p.needsUpdate = true;
            conf.material.opacity = t < 0.85 ? 1 : (1 - t) / 0.15;
        }).then(() => this._clearAnimProps());
    }

    _makeTrumpet() {
        const THREE = this.THREE;
        const g = new THREE.Group();
        const gold = new THREE.MeshStandardMaterial({
            color: 0xd4af37, metalness: 0.85, roughness: 0.25,
        });
        const tube = new THREE.Mesh(
            new THREE.CylinderGeometry(0.035, 0.035, 0.5, 10), gold
        );
        tube.rotation.z = Math.PI / 2;
        g.add(tube);
        const bell = new THREE.Mesh(
            new THREE.CylinderGeometry(0.14, 0.05, 0.22, 18, 1, true), gold
        );
        bell.rotation.z = -Math.PI / 2;
        bell.position.x = 0.34;
        g.add(bell);
        return g;
    }

    _celebrateTrumpet() {
        const base = this.tuxBase.position;
        const trumpet = this._addProp(this._makeTrumpet());
        this._playFanfare();
        const tx = base.x + this.tuxHalfWidth * 0.6 + 0.3;
        const ty = base.y + this.tuxHeight * 0.72;
        return this._runAnim(2600, (t) => {
            trumpet.position.set(
                tx, ty + Math.sin(t * Math.PI * 8) * 0.03, base.z + 0.5
            );
            trumpet.rotation.z = -0.55;
            this.tux.rotation.x = -0.14;
            this.tux.rotation.z = Math.sin(t * Math.PI * 10) * 0.05;
        }).then(() => {
            this._clearAnimProps();
            this._resetTux();
        });
    }

    _makeDiabolo() {
        const THREE = this.THREE;
        const g = new THREE.Group();
        const mat = new THREE.MeshStandardMaterial({
            color: 0xd11149, metalness: 0.2, roughness: 0.5,
        });
        const c1 = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.18, 20), mat);
        c1.position.y = 0.09;
        g.add(c1);
        const c2 = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.18, 20), mat);
        c2.rotation.z = Math.PI;
        c2.position.y = -0.09;
        g.add(c2);
        const axle = new THREE.Mesh(
            new THREE.CylinderGeometry(0.03, 0.03, 0.07, 10),
            new THREE.MeshStandardMaterial({ color: 0x333333 })
        );
        g.add(axle);
        return g;
    }

    _celebrateDiabolo() {
        const base = this.tuxBase.position;
        const diab = this._addProp(this._makeDiabolo());
        const cx = base.x + 0.1;
        const baseY = base.y + this.tuxHeight * 0.7;
        return this._runAnim(3000, (t) => {
            const toss = Math.abs(Math.sin(t * Math.PI * 3));
            diab.position.set(
                cx + Math.sin(t * Math.PI * 3) * 0.22,
                baseY + toss * 0.9,
                base.z + 0.5
            );
            diab.rotation.y += 0.5;
            diab.rotation.x = 0.2;
            this.tux.rotation.z = Math.sin(t * Math.PI * 6) * 0.12;
        }).then(() => {
            this._clearAnimProps();
            this._resetTux();
        });
    }

    _playFanfare() {
        try {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return;
            if (!this._audio) this._audio = new Ctx();
            const ac = this._audio;
            if (ac.state === "suspended") ac.resume();
            const now = ac.currentTime;
            const notes = [523.25, 659.25, 783.99, 1046.5];
            const step = 0.2;
            notes.forEach((f, i) => {
                const osc = ac.createOscillator();
                const gain = ac.createGain();
                const last = i === notes.length - 1;
                osc.type = "triangle";
                osc.frequency.value = f;
                const start = now + i * step;
                const len = last ? step * 2.6 : step * 0.9;
                gain.gain.setValueAtTime(0.0001, start);
                gain.gain.exponentialRampToValueAtTime(0.25, start + 0.03);
                gain.gain.exponentialRampToValueAtTime(0.0001, start + len);
                osc.connect(gain).connect(ac.destination);
                osc.start(start);
                osc.stop(start + len + 0.02);
            });
        } catch (e) {
            console.warn("event_raffle: fanfare failed", e);
        }
    }

    _applyAngels(on) {
        const THREE = this.THREE;
        if (on && !this._angels) {
            this._angels = new THREE.Group();
            const mk = (flip, x) => {
                const s = new THREE.Sprite(
                    new THREE.SpriteMaterial({
                        map: angelTexture(flip), transparent: true,
                    })
                );
                s.scale.set(1.28, 1.78, 1);
                s.position.set(x, 0.3, 0.4);
                return s;
            };
            // left angel faces right; right angel is mirrored so its trumpet
            // points left -> both trumpets aim at the wheel.
            const left = mk(false, -(WHEEL_RADIUS + 0.9));
            const right = mk(true, WHEEL_RADIUS + 0.9);
            this._angels.add(left, right);
            this.scene.add(this._angels);
            this._fitCamera();
        } else if (!on && this._angels) {
            this.scene.remove(this._angels);
            disposeTree(this._angels);
            this._angels = null;
            this._fitCamera();
        }
    }

    spinTo(index, total, { durationS = 6, turns = 5 } = {}) {
        const start = this.rotation;
        const target = computeAbsoluteTarget(
            start, index, total, turns, this._pointerAngle
        );
        const t0 = performance.now();
        const dur = durationS * 1000;
        this._spinning = true;
        return new Promise((resolve) => {
            const step = (now) => {
                if (this._disposed) {
                    this._spinning = false;
                    resolve();
                    return;
                }
                const p = Math.min((now - t0) / dur, 1);
                const ease = 1 - Math.pow(1 - p, 3); // ease-out cubic
                this.rotation = start + (target - start) * ease;
                this.tux.rotation.z = Math.sin(p * Math.PI * 8) * 0.2 *
                    (1 - p);
                if (p < 1) {
                    this._spinRaf = requestAnimationFrame(step);
                } else {
                    // let the flapper spring back to straight
                    this._spinning = false;
                    resolve();
                }
            };
            this._spinRaf = requestAnimationFrame(step);
        });
    }

    fireworks() {
        const THREE = this.THREE;
        const count = 300;
        const geo = new THREE.BufferGeometry();
        const pos = new Float32Array(count * 3);
        this._vel = [];
        for (let i = 0; i < count; i++) {
            pos[i * 3] = 0;
            pos[i * 3 + 1] = 0.5;
            pos[i * 3 + 2] = 0.5;
            const a = Math.random() * TAU;
            const s = 0.02 + Math.random() * 0.06;
            this._vel.push([Math.cos(a) * s, Math.sin(a) * s + 0.04,
                (Math.random() - 0.5) * s]);
        }
        geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        const mat = new THREE.PointsMaterial({
            size: 0.08, vertexColors: false, color: 0xffd166,
            transparent: true,
        });
        if (this._particles) this.scene.remove(this._particles);
        this._particles = new THREE.Points(geo, mat);
        this._particleLife = 1;
        this.scene.add(this._particles);
    }

    _loop() {
        const render = () => {
            this.wheel.rotation.z = this.rotation;
            this._updateFlapper();
            this._updateIdle(performance.now());
            if (this._spot) {
                const tt = performance.now() * 0.001;
                this._spot.position.set(
                    Math.sin(tt) * 4, 5, 5 + Math.cos(tt * 0.7) * 2
                );
            }
            if (this._rave) {
                const tt = performance.now() * 0.0016;
                this._rave.forEach((l, i) => {
                    const a = tt * (1 + i * 0.4) + (i * Math.PI) / 2;
                    l.position.set(
                        Math.cos(a) * 3.5,
                        Math.sin(a * 1.3) * 2.5,
                        2.5 + Math.sin(a) * 1.5
                    );
                    l.intensity = 2.5 + Math.sin(tt * 6 + i) * 1.5;
                });
                if (this._raveBeams) {
                    const bt = performance.now() * 0.001;
                    this._raveBeams.children.forEach((b, i) => {
                        b.rotation.z =
                            b.userData.base +
                            Math.sin(bt * (1.5 + i * 0.2) + i) * 0.4;
                        b.material.opacity =
                            0.3 + 0.3 * (0.5 + 0.5 * Math.sin(bt * 8 + i));
                    });
                }
            }
            if (this._particles && this._particleLife > 0) {
                const p = this._particles.geometry.attributes.position;
                for (let i = 0; i < p.count; i++) {
                    const v = this._vel[i];
                    p.array[i * 3] += v[0];
                    p.array[i * 3 + 1] += v[1];
                    p.array[i * 3 + 2] += v[2];
                    v[1] -= 0.001; // gravity
                }
                p.needsUpdate = true;
                this._particleLife -= 0.01;
                this._particles.material.opacity = Math.max(
                    this._particleLife, 0
                );
            }
            this.renderer.render(this.scene, this.camera);
            this._raf = requestAnimationFrame(render);
        };
        this._raf = requestAnimationFrame(render);
    }

    dispose() {
        this._disposed = true;
        if (this._ro) this._ro.disconnect();
        if (this._raf) cancelAnimationFrame(this._raf);
        if (this._spinRaf) cancelAnimationFrame(this._spinRaf);
        if (this._animRaf) cancelAnimationFrame(this._animRaf);
        if (this._audio) {
            try {
                this._audio.close();
            } catch (e) {
                // ignore
            }
        }
        disposeTree(this.scene);
        this.renderer.dispose();
        // r128's dispose() does not release the WebGL context; without this
        // every remount (record navigation, fullscreen round trip) leaves one
        // alive and the browser starts dropping the oldest after ~16.
        this.renderer.forceContextLoss();
    }
}

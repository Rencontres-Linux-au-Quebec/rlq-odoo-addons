/** @odoo-module **/
import {
    computeTargetAngle,
    computeAbsoluteTarget,
    computeCanvasSize,
    pointerWorldAngle,
} from "@event_raffle/wheel/three_scene";
import { expect, test, describe } from "@odoo/hoot";

const TAU = Math.PI * 2;
const norm = (a) => ((a % TAU) + TAU) % TAU;

describe("computeTargetAngle", () => {
    test("adds full turns", () => {
        const a0 = computeTargetAngle(0, 4, 0);
        const a2 = computeTargetAngle(0, 4, 2);
        expect(Math.abs(a2 - a0 - 2 * TAU) < 1e-9).toBe(true);
    });

    test("places each segment under the top pointer", () => {
        const total = 6;
        const seg = TAU / total;
        for (let i = 0; i < total; i++) {
            const rot = computeTargetAngle(i, total, 3);
            // Mirrored texture: segment i center sits at mesh angle
            // -(i+0.5)*seg; after rotation it must reach the top pointer (π/2).
            const world = norm(-(i + 0.5) * seg + rot);
            const d = Math.abs(world - Math.PI / 2);
            expect(Math.min(d, TAU - d) < 1e-6).toBe(true);
        }
    });
});

describe("computeAbsoluteTarget", () => {
    test("lands correctly across accumulating spins", () => {
        const TAU = Math.PI * 2;
        const norm = (a) => ((a % TAU) + TAU) % TAU;
        let rot = 0;
        for (const [i, total, turns] of [[2, 5, 5], [0, 4, 5], [3, 7, 5], [1, 3, 0]]) {
            const target = computeAbsoluteTarget(rot, i, total, turns);
            const seg = TAU / total;
            // mirrored segment center must land under the top pointer (π/2)
            const landed = norm(-(i + 0.5) * seg + target);
            const d = Math.abs(landed - Math.PI / 2);
            expect(Math.min(d, TAU - d) < 1e-9).toBe(true);
            expect(target >= rot + turns * TAU - 1e-9).toBe(true);
            rot = target;
        }
    });
});

describe("computeCanvasSize", () => {
    const box = (o) => ({
        width: 1502, height: 545, viewportHeight: 757,
        devicePixelRatio: 1, maxTextureSize: 16384, ...o,
    });

    test("a canvas not laid out yet is skipped, not invented", () => {
        expect(computeCanvasSize(box({ width: 0, height: 0 }))).toBe(null);
        expect(computeCanvasSize(box({ height: 0 }))).toBe(null);
    });

    // The bug this module shipped with: _resize() writes the measured box into
    // the canvas width/height ATTRIBUTES, and in the embedded form view those
    // attributes were what sized the element. Any growth per call compounds.
    test("the buffer it asks for never exceeds the box it measured", () => {
        for (const dpr of [1, 1.25, 1.5, 2, 3]) {
            const s = computeCanvasSize(box({ devicePixelRatio: dpr }));
            expect(s.w).toBe(1502);
            expect(s.h).toBe(545);
            expect(s.pixelRatio <= 2).toBe(true);
        }
    });

    test("a height no one could look at is clamped and flagged", () => {
        // Small viewport: the 1200 px floor is the limit, so a short laptop
        // screen does not make the backstop trigger-happy.
        const laptop = computeCanvasSize(box({ height: 4000 }));
        expect(laptop.runaway).toBe(true);
        expect(laptop.h).toBe(1200);
        expect(laptop.measuredHeight).toBe(4000);
        // Tall screen: the viewport term takes over, so a legitimately tall
        // wheel on a portrait panel is still drawn at full size.
        const panel = computeCanvasSize(
            box({ viewportHeight: 2000, height: 3000 })
        );
        expect(panel.h).toBe(2400);
        expect(computeCanvasSize(box({ viewportHeight: 2000, height: 2000 }))
            .runaway).toBe(false);
        // A normal box is never flagged, at any viewport size.
        expect(computeCanvasSize(box()).runaway).toBe(false);
        expect(computeCanvasSize(box({ viewportHeight: 200 })).runaway)
            .toBe(false);
    });

    test("the pixel ratio keeps the buffer inside the GPU texture limit", () => {
        // Software WebGL reports 8192; a 3840 px wide canvas at dpr 2 would
        // ask for 7680 and, with the height, blow past it.
        const s = computeCanvasSize(
            box({ width: 3840, height: 1200, devicePixelRatio: 2,
                  maxTextureSize: 4096 })
        );
        expect(s.pixelRatio).toBe(4096 / 3840);
        expect(Math.floor(s.w * s.pixelRatio) <= 4096).toBe(true);
    });
});

describe("pointerWorldAngle", () => {
    // The setting reads like a clock face: degrees clockwise from the top.
    // World angles run counter-clockwise from +X, so the two disagree in sign
    // and this mapping is the only place that reconciles them.
    const at = (deg) => {
        const a = pointerWorldAngle(deg);
        return [Math.round(Math.cos(a) * 1e9) / 1e9,
                Math.round(Math.sin(a) * 1e9) / 1e9];
    };

    test("the four settings are the four compass points, clockwise", () => {
        expect(at("0")).toEqual([0, 1]);      // top
        expect(at("90")).toEqual([1, 0]);     // right
        expect(at("180")).toEqual([0, -1]);   // bottom
        expect(at("-90")).toEqual([-1, 0]);   // left
    });

    test("a missing setting means the top", () => {
        // Odoo hands the value over as a string; an unsaved record hands over
        // false, and the wheel must still point somewhere sensible.
        expect(pointerWorldAngle(90)).toBe(pointerWorldAngle("90"));
        expect(pointerWorldAngle(false)).toBe(Math.PI / 2);
        expect(pointerWorldAngle(undefined)).toBe(Math.PI / 2);
    });
});

describe("computeTargetAngle with a moved pointer", () => {
    // This is the assertion that guards the DRAW itself: whatever the pointer
    // angle, the segment the server picked has to come to rest under it.
    test("the chosen segment lands under the pointer, at every angle", () => {
        for (const deg of ["0", "90", "180", "-90"]) {
            const phi = pointerWorldAngle(deg);
            const target = norm(phi);
            for (const total of [1, 2, 3, 5, 12, 37]) {
                const seg = TAU / total;
                for (let i = 0; i < total; i++) {
                    const rot = computeTargetAngle(i, total, 3, phi);
                    const world = norm(-(i + 0.5) * seg + rot);
                    const d = Math.abs(world - target);
                    expect(Math.min(d, TAU - d) < 1e-9).toBe(true);
                }
            }
        }
    });

    test("accumulating spins stay forward at every angle", () => {
        for (const deg of ["0", "90", "180", "-90"]) {
            const phi = pointerWorldAngle(deg);
            let rot = 0;
            for (const [i, total, turns] of [[2, 5, 5], [0, 4, 5], [1, 3, 0]]) {
                const t = computeAbsoluteTarget(rot, i, total, turns, phi);
                const seg = TAU / total;
                const d = Math.abs(norm(-(i + 0.5) * seg + t) - norm(phi));
                expect(Math.min(d, TAU - d) < 1e-9).toBe(true);
                expect(t >= rot + turns * TAU - 1e-9).toBe(true);
                rot = t;
            }
        }
    });

    test("omitting the angle keeps the historic top-pointer behaviour", () => {
        for (const total of [3, 4, 7]) {
            for (let i = 0; i < total; i++) {
                expect(computeTargetAngle(i, total, 3))
                    .toBe(computeTargetAngle(i, total, 3, Math.PI / 2));
                expect(computeAbsoluteTarget(1.234, i, total, 5))
                    .toBe(computeAbsoluteTarget(1.234, i, total, 5, Math.PI / 2));
            }
        }
    });
});

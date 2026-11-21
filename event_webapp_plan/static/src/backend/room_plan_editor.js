/**
 * Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
 * Copyright (C) 2026 Rencontres Linux au Québec contributors
 * License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
 *
 * Visual editor of the room areas, a field widget for the one2many
 * `room_ids` of `event.webapp`.
 *
 * It shows the plan image with every room area over it. The user selects
 * a room (side list or click on its area), then drags on the image to
 * draw its area. The selected area carries a frame with eight resize
 * handles and a rotation knob: a drag inside the frame moves the area, a
 * drag on a handle resizes it, a drag on the knob turns it around its
 * centre. Buttons and an angle field under the selected room turn it too.
 *
 * Coordinates are percents of the image (0..100, two decimals) and the
 * angle is in degrees, clockwise, in (-180, 180]. The rectangle before it
 * turns always stays inside the image, the invariant checked by the
 * server; the corners of a turned area may leave the image and the
 * surface clips them. Values are written into the sub-record with
 * `record.update()` when the drag ends, so they are saved with the form
 * like any other x2many change; during the drag a preview is drawn.
 *
 * Pointer events cover mouse, pen and touch. The element under the press
 * picks the action: a handle or the knob of the selected area resizes or
 * turns it, its frame moves it, anything else draws. A move, resize or turn
 * starts once the pointer has gone MOVE_THRESHOLD_PX away from the press;
 * a shorter press writes nothing. A press draws an area only when the
 * rectangle reaches MIN_SIZE percent along BOTH axes; anything smaller,
 * such as a click or a sideways swipe, keeps the saved area and acts as a
 * click: it selects the topmost room under the pointer. A drag that starts
 * on the area of another room therefore draws the area of the selected
 * room, and a click there selects the other room. A click inside the
 * selected area selects the topmost OTHER room under the pointer, so a
 * room drawn inside or under the selected one stays reachable from the
 * plan; with no other room there, the selection stays.
 */
import {Component, useRef, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {isBinarySize} from "@web/core/utils/binary";
import {imageUrl} from "@web/core/utils/urls";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

const MIN_SIZE = 1;
// A move or turn shorter than this, in screen pixels along both axes, is
// a click.
const MOVE_THRESHOLD_PX = 4;
// Steps of the rotation: the knob and the buttons, then with Shift held.
const ROTATE_STEP = 15;
const ROTATE_FINE_STEP = 1;
const DEFAULT_COLOR = "#2A9D8F";
// First character of a base64 image -> its type, as the image field of the
// web client guesses it for an image not saved yet.
const BASE64_MAGIC = {"/": "jpeg", R: "gif", i: "png", P: "svg+xml", U: "webp"};
const AREA_FIELDS = ["pos_x", "pos_y", "pos_width", "pos_height", "pos_rotation"];
// Keys of a box, in the order of AREA_FIELDS.
const AREA_KEYS = ["x", "y", "width", "height", "rotation"];
// Resize handles: key -> [hx, hy], the side of the area each one drags in
// the frame of the area (-1 left or top, 1 right or bottom, 0 neither),
// and the direction it points to at rest, in degrees clockwise from up.
export const HANDLES = {
    nw: [-1, -1, 315],
    n: [0, -1, 0],
    ne: [1, -1, 45],
    e: [1, 0, 90],
    se: [1, 1, 135],
    s: [0, 1, 180],
    sw: [-1, 1, 225],
    w: [-1, 0, 270],
};
const RESIZE_CURSORS = ["ns-resize", "nesw-resize", "ew-resize", "nwse-resize"];

function clampPercent(value) {
    return Math.min(100, Math.max(0, value));
}

function round2(value) {
    return Math.round(value * 100) / 100;
}

/**
 * Angle in degrees brought into (-180, 180] with two decimals, as the
 * server stores it: 270 gives -90, -180 gives 180. A value that is not a
 * finite number gives 0.
 */
export function normalizeAngle(value) {
    if (!Number.isFinite(value)) {
        return 0;
    }
    let angle = round2(value % 360);
    if (angle <= -180) {
        angle += 360;
    } else if (angle > 180) {
        angle -= 360;
    }
    // + 0 turns -0 into 0.
    return round2(angle) + 0;
}

/**
 * Box {x, y, width, height, rotation} brought inside the image and
 * rounded to two decimals: the size stays within 100, the position moves
 * the box back inside 0..100 without changing its size, and the right and
 * bottom edges stay inside the image after rounding.
 */
export function clampBox(box) {
    const width = Math.min(Math.max(box.width, 0), 100);
    const height = Math.min(Math.max(box.height, 0), 100);
    const x = round2(Math.min(Math.max(box.x, 0), 100 - width));
    const y = round2(Math.min(Math.max(box.y, 0), 100 - height));
    return {
        x,
        y,
        width: round2(Math.min(width, 100 - x)),
        height: round2(Math.min(height, 100 - y)),
        rotation: normalizeAngle(box.rotation || 0),
    };
}

/**
 * Pixel frame of a box on a surface of `size` {width, height} pixels:
 * centre (cx, cy), size (w, h), and the unit vectors of its own axes, u
 * along its width and v along its height, turned with the box.
 */
export function boxFrame(box, size) {
    const angle = ((box.rotation || 0) * Math.PI) / 180;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    return {
        cx: ((box.x + box.width / 2) * size.width) / 100,
        cy: ((box.y + box.height / 2) * size.height) / 100,
        w: (box.width * size.width) / 100,
        h: (box.height * size.height) / 100,
        u: {x: cos, y: sin},
        v: {x: -sin, y: cos},
    };
}

/** Pixel position of the handle `key` of a box, on the surface. */
export function handlePoint(box, key, size) {
    const frame = boxFrame(box, size);
    const [hx, hy] = HANDLES[key];
    const du = (hx * frame.w) / 2;
    const dv = (hy * frame.h) / 2;
    return {
        x: frame.cx + du * frame.u.x + dv * frame.v.x,
        y: frame.cy + du * frame.u.y + dv * frame.v.y,
    };
}

/**
 * Margins of a box (percent) to the edges of the image: left, top, right,
 * bottom, all >= 0 for a box inside 0..100.
 */
function boxMargins(box) {
    return [box.x, box.y, 100 - box.x - box.width, 100 - box.y - box.height];
}

/**
 * Largest t in [0, 1] for which the box `sized(from + t * (to - from))`
 * keeps every margin >= 0, `from` and `to` being pixel sizes {w, h}. Each
 * margin is affine in the size, so it is affine in t and the bound of each
 * one is read from its values at both ends; a margin already below 0 at
 * `from` (a rounding of the saved box) bounds t at 0 only if it decreases.
 */
function largestStep(sized, from, to) {
    const start = boxMargins(sized(from));
    const end = boxMargins(sized(to));
    let t = 1;
    start.forEach((a, index) => {
        const b = end[index];
        if (b < 0 && b < a) {
            t = Math.min(t, a > 0 ? a / (a - b) : 0);
        }
    });
    return t;
}

/**
 * Box `box` resized by its handle `key` dragged to `point` (pixels of a
 * surface of `size`). The work happens in the frame of the box, so a
 * turned box keeps its angle: the opposite corner or side stays where it
 * is on screen, the dragged one follows the pointer along the axes of the
 * box, never below MIN_SIZE percent.
 *
 * The box before it turns stays inside the image by its size, not by its
 * position: from the size of `box` (inside) toward the size the pointer
 * asks for, the size grows as far as the edges allow, first along both
 * axes together, then along each one alone. A handle dragged past an edge
 * therefore stops the area at that edge and the anchor never moves.
 * clampBox() only rounds the result.
 */
export function resizeBox(box, key, point, size) {
    const frame = boxFrame(box, size);
    const [hx, hy] = HANDLES[key];
    const {u, v} = frame;
    const anchor = handlePoint(box, oppositeHandle(key), size);
    const dx = point.x - anchor.x;
    const dy = point.y - anchor.y;
    const along = dx * u.x + dy * u.y;
    const across = dx * v.x + dy * v.y;
    const minW = (MIN_SIZE * size.width) / 100;
    const minH = (MIN_SIZE * size.height) / 100;
    // Box of pixel size {w, h} with the anchor in place, in percent. The
    // anchor of a side handle is the middle of the opposite side: the
    // centre stays on the same line across that side.
    const sized = ({w, h}) => {
        const cx = anchor.x + ((hx * w) / 2) * u.x + ((hy * h) / 2) * v.x;
        const cy = anchor.y + ((hx * w) / 2) * u.y + ((hy * h) / 2) * v.y;
        const width = (w / size.width) * 100;
        const height = (h / size.height) * 100;
        return {
            x: (cx / size.width) * 100 - width / 2,
            y: (cy / size.height) * 100 - height / 2,
            width,
            height,
            rotation: box.rotation,
        };
    };
    const wanted = {
        w: hx ? Math.max(hx * along, minW) : frame.w,
        h: hy ? Math.max(hy * across, minH) : frame.h,
    };
    const step = (from, to) => {
        const t = largestStep(sized, from, to);
        return {w: from.w + t * (to.w - from.w), h: from.h + t * (to.h - from.h)};
    };
    let reached = step({w: frame.w, h: frame.h}, wanted);
    reached = step(reached, {w: wanted.w, h: reached.h});
    reached = step(reached, {w: reached.w, h: wanted.h});
    return clampBox(sized(reached));
}

/** Handle across the centre from `key`: "ne" gives "sw", "n" gives "s". */
function oppositeHandle(key) {
    const [hx, hy] = HANDLES[key];
    return Object.keys(HANDLES).find(
        (other) => HANDLES[other][0] === -hx && HANDLES[other][1] === -hy
    );
}

export class RoomPlanEditor extends Component {
    static template = "event_webapp_plan.RoomPlanEditor";
    static props = {...standardFieldProps};

    setup() {
        this.surfaceRef = useRef("surface");
        this.state = useState({
            selectedId: null,
            // Draw in progress: the corners of the rectangle, in percent.
            draft: null,
            // Move, resize or turn in progress: {mode, box}, the box
            // drawn in place of the saved one of the selected room.
            edit: null,
        });
        this.pointerId = null;
        // Start of the move, resize or turn: what the pointer grabbed and
        // where, kept out of the state since nothing renders it.
        this.grab = null;
        this.handles = Object.keys(HANDLES);
    }

    get rooms() {
        return this.props.record.data[this.props.name].records;
    }

    get selectedRoom() {
        return this.rooms.find((room) => room.id === this.state.selectedId) || null;
    }

    get canEdit() {
        return !this.props.readonly;
    }

    /** URL of the plan: the saved image, or the base64 one not saved yet. */
    get planUrl() {
        const record = this.props.record;
        const value = record.data.plan_image;
        if (!value) {
            return null;
        }
        if (isBinarySize(value)) {
            if (!record.resId) {
                return null;
            }
            return imageUrl(record.resModel, record.resId, "plan_image", {
                unique: record.data.write_date,
            });
        }
        const type = BASE64_MAGIC[value[0]] || "png";
        return `data:image/${type};base64,${value}`;
    }

    roomName(room) {
        return room.data.name || _t("Unnamed room");
    }

    roomColor(room) {
        return room.data.color || DEFAULT_COLOR;
    }

    hasArea(room) {
        return room.data.pos_width > 0 && room.data.pos_height > 0;
    }

    /** Saved box of a room: {x, y, width, height, rotation}. */
    savedBox(room) {
        const data = room.data;
        return {
            x: data.pos_x,
            y: data.pos_y,
            width: data.pos_width,
            height: data.pos_height,
            rotation: data.pos_rotation || 0,
        };
    }

    /**
     * Box drawn for a room: the draft of a draw or the preview of a move,
     * resize or turn for the selected room, else its saved box; null
     * when there is nothing to draw.
     */
    shownBox(room) {
        if (room.id === this.state.selectedId) {
            if (this.state.draft) {
                return {...this.toRect(this.state.draft), rotation: 0};
            }
            if (this.state.edit) {
                return this.state.edit.box;
            }
        }
        return this.hasArea(room) ? this.savedBox(room) : null;
    }

    boxStyle(box, color) {
        return [
            `left: ${box.x}%`,
            `top: ${box.y}%`,
            `width: ${box.width}%`,
            `height: ${box.height}%`,
            `--ewp-room-rotate: ${box.rotation || 0}deg`,
            `--ewp-room-color: ${color}`,
        ].join("; ");
    }

    roomStyle(room) {
        return this.boxStyle(this.shownBox(room), this.roomColor(room));
    }

    /** Box of the frame with the handles: the selected area, when editable. */
    get frameBox() {
        const room = this.selectedRoom;
        if (!this.canEdit || !room || this.state.draft) {
            return null;
        }
        return this.shownBox(room);
    }

    get frameStyle() {
        const room = this.selectedRoom;
        return this.boxStyle(this.frameBox, room ? this.roomColor(room) : DEFAULT_COLOR);
    }

    /** Resize cursor of a handle, after the angle of the area. */
    handleCursor(key) {
        const turned = HANDLES[key][2] + (this.frameBox?.rotation || 0);
        const index = Math.round((((turned % 180) + 180) % 180) / 45) % 4;
        return `cursor: ${RESIZE_CURSORS[index]}`;
    }

    /** Angle of the selected area, as the angle field shows it. */
    get selectedAngle() {
        const room = this.selectedRoom;
        if (!room) {
            return 0;
        }
        return this.state.edit ? this.state.edit.box.rotation : room.data.pos_rotation || 0;
    }

    get canRotate() {
        const room = this.selectedRoom;
        return Boolean(this.canEdit && room && this.hasArea(room));
    }

    selectRoom(room) {
        this.state.selectedId = this.state.selectedId === room.id ? null : room.id;
    }

    /** Size of the surface in pixels, null while it has none. */
    surfaceSize() {
        const box = this.surfaceRef.el.getBoundingClientRect();
        return box.width && box.height ? {width: box.width, height: box.height} : null;
    }

    /** Pointer position in pixels from the top left corner of the surface. */
    toPixels(ev) {
        const box = this.surfaceRef.el.getBoundingClientRect();
        return {x: ev.clientX - box.left, y: ev.clientY - box.top};
    }

    /** Pointer position in percent of the surface, clamped to 0..100. */
    toPercent(ev) {
        const box = this.surfaceRef.el.getBoundingClientRect();
        if (!box.width || !box.height) {
            return {x: 0, y: 0};
        }
        return {
            x: clampPercent(((ev.clientX - box.left) / box.width) * 100),
            y: clampPercent(((ev.clientY - box.top) / box.height) * 100),
        };
    }

    /**
     * Rectangle between the two corners of a draft, rounded to two
     * decimals with right and bottom edges kept inside the image, the
     * invariant checked by the server.
     */
    toRect({x0, y0, x1, y1}) {
        const x = round2(Math.min(x0, x1));
        const y = round2(Math.min(y0, y1));
        return {
            x,
            y,
            width: round2(Math.min(Math.abs(x1 - x0), 100 - x)),
            height: round2(Math.min(Math.abs(y1 - y0), 100 - y)),
        };
    }

    /**
     * Topmost room whose area contains the point (percent), or null; the
     * room whose id is `skipId` is left out. The point is turned back by
     * the angle of each area, in pixels, so a turned area answers for its
     * turned shape.
     */
    roomAt({x, y}, skipId = null) {
        const size = this.surfaceSize() || {width: 100, height: 100};
        const px = (x * size.width) / 100;
        const py = (y * size.height) / 100;
        const hits = this.rooms.filter((room) => {
            if (room.id === skipId || !this.hasArea(room)) {
                return false;
            }
            const frame = boxFrame(this.savedBox(room), size);
            const dx = px - frame.cx;
            const dy = py - frame.cy;
            const along = dx * frame.u.x + dy * frame.u.y;
            const across = dx * frame.v.x + dy * frame.v.y;
            return Math.abs(along) <= frame.w / 2 && Math.abs(across) <= frame.h / 2;
        });
        return hits.length ? hits[hits.length - 1] : null;
    }

    capture(ev) {
        this.pointerId = ev.pointerId;
        // Capture keeps the drag alive when the pointer leaves the image.
        // It is best effort: the browser refuses it for a pointer it does
        // not consider active, and the drag still works inside the image.
        try {
            this.surfaceRef.el.setPointerCapture(ev.pointerId);
        } catch {
            // The drag goes on without capture.
        }
    }

    onPointerDown(ev) {
        if (!this.canEdit || (ev.pointerType === "mouse" && ev.button !== 0)) {
            return;
        }
        ev.preventDefault();
        const size = this.surfaceSize();
        const handle = ev.target.closest && ev.target.closest("[data-ewp-handle]");
        const room = this.selectedRoom;
        if (handle && size && room && this.hasArea(room)) {
            const key = handle.dataset.ewpHandle;
            const box = this.savedBox(room);
            const start = this.toPixels(ev);
            const frame = boxFrame(box, size);
            const grabbed = key in HANDLES ? handlePoint(box, key, size) : start;
            this.grab = {
                key,
                box,
                size,
                start,
                // Offset between the pointer and the handle it grabbed: the
                // handle keeps it, so the area does not jump on the press.
                offset: {x: grabbed.x - start.x, y: grabbed.y - start.y},
                startAngle: Math.atan2(start.y - frame.cy, start.x - frame.cx),
                moved: false,
            };
            const mode = key === "move" ? "move" : key === "rotate" ? "rotate" : "resize";
            this.capture(ev);
            this.state.edit = {mode, box: {...box}};
            return;
        }
        const point = this.toPercent(ev);
        this.capture(ev);
        this.state.draft = {x0: point.x, y0: point.y, x1: point.x, y1: point.y};
    }

    /**
     * Box of the move, resize or turn in progress, for the pointer `ev`.
     * A move or a turn keeps the saved box until the pointer has gone
     * MOVE_THRESHOLD_PX away from the press: a click on the frame or on the
     * knob writes nothing, even for an angle the knob would snap.
     */
    editedBox(ev) {
        const grab = this.grab;
        const point = this.toPixels(ev);
        const {box, size} = grab;
        const mode = this.state.edit.mode;
        const dx = point.x - grab.start.x;
        const dy = point.y - grab.start.y;
        if (
            mode !== "resize" &&
            !grab.moved &&
            Math.abs(dx) < MOVE_THRESHOLD_PX &&
            Math.abs(dy) < MOVE_THRESHOLD_PX
        ) {
            return box;
        }
        grab.moved = true;
        if (mode === "move") {
            return clampBox({
                ...box,
                x: box.x + (dx / size.width) * 100,
                y: box.y + (dy / size.height) * 100,
            });
        }
        if (mode === "rotate") {
            const frame = boxFrame(box, size);
            const angle = Math.atan2(point.y - frame.cy, point.x - frame.cx);
            const turned = box.rotation + ((angle - grab.startAngle) * 180) / Math.PI;
            const step = ev.shiftKey ? ROTATE_FINE_STEP : ROTATE_STEP;
            return {...box, rotation: normalizeAngle(Math.round(turned / step) * step)};
        }
        return resizeBox(
            box,
            grab.key,
            {x: point.x + grab.offset.x, y: point.y + grab.offset.y},
            size
        );
    }

    onPointerMove(ev) {
        if (ev.pointerId !== this.pointerId) {
            return;
        }
        if (this.state.edit) {
            this.state.edit.box = this.editedBox(ev);
            return;
        }
        if (!this.state.draft) {
            return;
        }
        const point = this.toPercent(ev);
        this.state.draft.x1 = point.x;
        this.state.draft.y1 = point.y;
    }

    async onPointerUp(ev) {
        if (ev.pointerId !== this.pointerId) {
            return;
        }
        if (this.state.edit) {
            await this.endEdit(ev);
            return;
        }
        const draft = this.state.draft;
        if (!draft) {
            return;
        }
        // The release point ends the rectangle: a fast drag can end farther
        // than the last pointermove the browser delivered.
        const end = this.toPercent(ev);
        draft.x1 = end.x;
        draft.y1 = end.y;
        this.onPointerCancel();
        // Measured after rounding and clamping: a drag pushed past the right
        // or bottom edge can still give a zero width or height.
        const rect = this.toRect(draft);
        if (rect.width < MIN_SIZE || rect.height < MIN_SIZE) {
            const hit = this.roomAt({x: draft.x0, y: draft.y0});
            if (hit) {
                this.state.selectedId = hit.id;
            }
            return;
        }
        await this.writeBox({...rect, rotation: 0});
    }

    /**
     * Ends a move, resize or turn: writes the box it reached, if any. A
     * press inside the selected area that did not move is a click: it
     * selects the topmost other room under the pointer, if any.
     */
    async endEdit(ev) {
        const box = this.editedBox(ev);
        const room = this.selectedRoom;
        const {mode} = this.state.edit;
        const {moved, start, size} = this.grab;
        this.onPointerCancel();
        if (room && mode === "move" && !moved) {
            const point = {x: (start.x / size.width) * 100, y: (start.y / size.height) * 100};
            const hit = this.roomAt(point, room.id);
            if (hit) {
                this.state.selectedId = hit.id;
            }
            return;
        }
        const saved = room && this.savedBox(room);
        if (!room || AREA_KEYS.every((key) => box[key] === saved[key])) {
            return;
        }
        await this.writeBox(box);
    }

    onPointerCancel() {
        if (this.pointerId !== null && this.surfaceRef.el?.hasPointerCapture(this.pointerId)) {
            this.surfaceRef.el.releasePointerCapture(this.pointerId);
        }
        this.pointerId = null;
        this.grab = null;
        this.state.draft = null;
        this.state.edit = null;
    }

    /** Writes `box` into the area fields of the selected room. */
    async writeBox(box) {
        const room = this.selectedRoom;
        if (!room) {
            return;
        }
        await room.update({
            pos_x: box.x,
            pos_y: box.y,
            pos_width: box.width,
            pos_height: box.height,
            pos_rotation: normalizeAngle(box.rotation),
        });
    }

    /**
     * Turns the selected area by ROTATE_STEP degrees, ROTATE_FINE_STEP
     * with Shift held, clockwise for `direction` 1, the other way for -1.
     */
    async rotateBy(ev, direction) {
        const room = this.selectedRoom;
        if (!this.canRotate) {
            return;
        }
        const step = ev.shiftKey ? ROTATE_FINE_STEP : ROTATE_STEP;
        await room.update({
            pos_rotation: normalizeAngle((room.data.pos_rotation || 0) + direction * step),
        });
    }

    /** Sets the angle typed in the angle field, once it changes. */
    async onAngleChange(ev) {
        const room = this.selectedRoom;
        if (!this.canRotate) {
            return;
        }
        const typed = parseFloat(String(ev.target.value).replace(",", "."));
        const angle = Number.isFinite(typed) ? normalizeAngle(typed) : room.data.pos_rotation || 0;
        // The field shows the normalised angle even when the record keeps
        // its value, which renders nothing again.
        ev.target.value = angle;
        await room.update({pos_rotation: angle});
    }

    async straighten() {
        const room = this.selectedRoom;
        if (this.canRotate) {
            await room.update({pos_rotation: 0});
        }
    }

    async clearArea() {
        const room = this.selectedRoom;
        if (room) {
            await room.update(Object.fromEntries(AREA_FIELDS.map((name) => [name, 0])));
        }
    }
}

export const roomPlanEditor = {
    component: RoomPlanEditor,
    displayName: _t("Room plan editor"),
    supportedTypes: ["one2many"],
    isEmpty: () => false,
    // A function, so that each view gets its own objects: the web client
    // marks them readonly in place when the key is missing.
    relatedFields: () => [
        {name: "name", type: "char"},
        {name: "color", type: "char"},
        ...AREA_FIELDS.map((name) => ({name, type: "float", readonly: false})),
    ],
    fieldDependencies: [
        {name: "plan_image", type: "binary"},
        {name: "write_date", type: "datetime"},
    ],
};

registry.category("fields").add("ewp_room_plan_editor", roomPlanEditor);

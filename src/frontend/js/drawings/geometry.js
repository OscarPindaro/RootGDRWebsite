/* Geometry for the drawing editor: 2x3 affine matrices, polygon tests and
   bounds. Pure functions on plain arrays and [x, y] points, so the same code
   runs in the controller, the renderer and the tests.

   A matrix is [a, b, c, d, e, f], the SVG matrix() order: x' = a·x + c·y + e,
   y' = b·x + d·y + f. */

export const IDENTITY = [1, 0, 0, 1, 0, 0];

/** m ∘ n: apply n first, then m. */
export function multiply(m, n) {
  return [
    m[0] * n[0] + m[2] * n[1],
    m[1] * n[0] + m[3] * n[1],
    m[0] * n[2] + m[2] * n[3],
    m[1] * n[2] + m[3] * n[3],
    m[0] * n[4] + m[2] * n[5] + m[4],
    m[1] * n[4] + m[3] * n[5] + m[5],
  ];
}

export function apply(m, point) {
  return [m[0] * point[0] + m[2] * point[1] + m[4], m[1] * point[0] + m[3] * point[1] + m[5]];
}

export function invert(m) {
  const det = m[0] * m[3] - m[1] * m[2];
  if (Math.abs(det) < 1e-12) return null;
  const [a, b, c, d, e, f] = m;
  return [d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det];
}

export function translation(tx, ty) {
  return [1, 0, 0, 1, tx, ty];
}

export function scaling(sx, sy) {
  return [sx, 0, 0, sy, 0, 0];
}

export function rotation(radians) {
  const c = Math.cos(radians);
  const s = Math.sin(radians);
  return [c, s, -s, c, 0, 0];
}

/** Scale about a fixed world point. */
export function scaleAbout(fixed, sx, sy) {
  return multiply(translation(fixed[0], fixed[1]), multiply(scaling(sx, sy), translation(-fixed[0], -fixed[1])));
}

/** Rotate about a fixed world point. */
export function rotateAbout(fixed, radians) {
  return multiply(translation(fixed[0], fixed[1]), multiply(rotation(radians), translation(-fixed[0], -fixed[1])));
}

export function transformPoints(m, points) {
  return points.map((point) => apply(m, point));
}

export function polygonArea(points) {
  let total = 0;
  for (let index = 0; index < points.length; index += 1) {
    const [x1, y1] = points[index];
    const [x2, y2] = points[(index + 1) % points.length];
    total += x1 * y2 - x2 * y1;
  }
  return Math.abs(total) / 2;
}

/** Ray casting: is the point inside the polygon? */
export function pointInPolygon(point, points) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i, i += 1) {
    const [xi, yi] = points[i];
    const [xj, yj] = points[j];
    const crosses = yi > point[1] !== yj > point[1];
    if (crosses && point[0] < ((xj - xi) * (point[1] - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

export function distanceToSegment(point, a, b) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared < 1e-12) return Math.hypot(point[0] - a[0], point[1] - a[1]);
  let t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / lengthSquared;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy));
}

export function bounds(points) {
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  };
}

export function centerOf(points) {
  const box = bounds(points);
  return [(box.minX + box.maxX) / 2, (box.minY + box.maxY) / 2];
}

export function resizeFrame(corners, corner, point) {
  if (corners.length !== 4 || !Number.isInteger(corner) || corner < 0 || corner > 3 || !point.every(Number.isFinite)) return null;
  const fixed = corners[(corner + 2) % 4];
  let u = [corners[1][0] - corners[0][0], corners[1][1] - corners[0][1]];
  let v = [corners[3][0] - corners[0][0], corners[3][1] - corners[0][1]];
  const width = Math.hypot(...u), height = Math.hypot(...v);
  if (!width && !height) return null;
  if (!width) u = [v[1] / height, -v[0] / height];
  if (!height) v = [-u[1] / width, u[0] / width];
  const basis = [u[0], u[1], v[0], v[1], fixed[0], fixed[1]];
  const inverse = invert(basis);
  if (!inverse) return null;
  const start = apply(inverse, corners[corner]), wanted = apply(inverse, point);
  return { basis, inverse, fixed, sx:start[0] ? wanted[0] / start[0] : 1, sy:start[1] ? wanted[1] / start[1] : 1 };
}

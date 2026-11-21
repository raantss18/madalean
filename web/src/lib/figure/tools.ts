// The named tools of the figure, grouped like Fikajiana's toolbox (ADR 0019): what each one asks for, in order,
// and the construction kind it makes.
export type Group = 'base' | 'points' | 'lines' | 'circles' | 'polygons' | 'conics' | 'transforms' | 'measures' | 'advanced';
export type Want = 'point' | 'point_existing' | 'glider' | 'line' | 'circle_or_conic' | 'curve' | 'polygon' | 'object'
  | 'vector' | 'length' | 'point_or_line' | 'surface';
export interface Tool { id: string; group: Group; kind?: string; wants: Want[]; number?: 'radius' | 'angle' | 'ratio' | 'sides'; freeOrder?: boolean }

export const GROUPS: Group[] = ['base', 'points', 'lines', 'circles', 'polygons', 'conics', 'transforms', 'measures', 'advanced'];
const T = (id: string, group: Group, wants: Want[], kind: string | undefined = id, extra: Partial<Tool> = {}): Tool => ({ id, group, kind, wants, ...extra });

export const TOOLS: Tool[] = [
  T('move', 'base', [], undefined), T('delete', 'base', ['object'], undefined),
  T('point', 'points', ['point'], 'point'), T('midpoint', 'points', ['point', 'point']), T('intersection', 'points', ['curve', 'curve']),
  T('center', 'points', ['circle_or_conic']), T('centroid', 'points', ['polygon']),
  T('segment', 'lines', ['point', 'point']), T('line', 'lines', ['point', 'point']), T('ray', 'lines', ['point', 'point']),
  T('vector', 'lines', ['point', 'point']), T('parallel', 'lines', ['line', 'point'], 'parallel', { freeOrder: true }),
  T('perpendicular', 'lines', ['line', 'point'], 'perpendicular', { freeOrder: true }), T('perp_bisector', 'lines', ['point', 'point']),
  T('angle_bisector', 'lines', ['point', 'point', 'point']), T('tangent', 'lines', ['circle_or_conic', 'point'], 'tangent', { freeOrder: true }),
  T('circle_center_point', 'circles', ['point', 'point']), T('circle_center_radius', 'circles', ['point'], 'circle_center_radius', { number: 'radius' }),
  T('circle_3_points', 'circles', ['point', 'point', 'point']), T('arc', 'circles', ['point', 'point', 'point']),
  T('arc_3_points', 'circles', ['point', 'point', 'point']), T('semicircle', 'circles', ['point', 'point']),
  T('polygon', 'polygons', ['point']), T('regular_polygon', 'polygons', ['point', 'point'], 'regular_polygon', { number: 'sides' }),
  T('ellipse', 'conics', ['point', 'point', 'point']), T('hyperbola', 'conics', ['point', 'point', 'point']),
  T('parabola', 'conics', ['point', 'line'], 'parabola', { freeOrder: true }), T('conic_5_points', 'conics', ['point', 'point', 'point', 'point', 'point']),
  T('point_reflection', 'transforms', ['object', 'point']), T('line_reflection', 'transforms', ['object', 'line']),
  T('translation', 'transforms', ['object', 'vector']), T('rotation', 'transforms', ['object', 'point'], 'rotation', { number: 'angle' }),
  T('homothety', 'transforms', ['object', 'point'], 'homothety', { number: 'ratio' }),
  T('distance', 'measures', ['length', 'point_or_line']), T('angle', 'measures', ['point', 'point', 'point']),
  T('area', 'measures', ['surface']), T('slope', 'measures', ['line']),
  T('slider', 'advanced', [], 'slider'), T('locus', 'advanced', ['point_existing', 'glider']), T('relation', 'advanced', ['object', 'object'], undefined),
];
export const toolById = (id: string) => TOOLS.find((t) => t.id === id) ?? TOOLS[0]!;

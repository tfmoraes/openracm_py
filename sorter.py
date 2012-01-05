import copy
import corner_table

FIFO=1
CONTROLLABLE=2

BUFFER_SIZE = 20

K1 = 1.0
K2 = 0.5
K3 = 1.3

def _count_degree(ct, v_id):
    c = ct.get_corner_v(v_id)
    t = ct.get_triangle(c)
    cc = c
    d = 1
    while 1:
        cc = ct.swing(cc)
        nt = ct.get_triangle(cc)
        if nt == t:
            break
        else:
            d += 1
    return d


def _get_minimun_degree_vertex(ct, v_w):
    minimun = v_w[0]
    for v in v_w:
        if _count_degree(v) < minimun:
            minimun = v
    return minimun


def _get_bounding_faces(ct, v_id):
    c = ct.get_corner_v(v_id)
    ti = ct.get_triangle(c)
    yield ti
    cc = c
    while 1:
        cc = ct.swing(cc)
        nt = ct.get_triangle(cc)
        if nt == ti:
            break
        else:
            yield nt


def _get_white_bounding_vertices(ct, v_w, t_id):
    for c_id in ct.iterate_triangle_corner(t_id):
        v_id = ct.V[c_id]
        if v_id in v_w:
            yield v_id


def _get_renderable_faces_in_buffer(ct, v_g):
    output = []
    for v_id in v_g:
        for t_id in _get_bounding_faces(ct, v_id):
            for c_id in ct.iterate_triangle_corner(t_id):
                if ct.V[c_id] not in v_g:
                    break
            else:
                if t_id not in output:
                    output.append(t_id)
    return output


def _get_unrenderable_faces_in_buffer(ct, v_g, v_w):
    output = []
    for v_id in v_g:
        for t_id in _get_bounding_faces(ct, v_id):
            for c_id in ct.iterate_triangle_corner(t_id):
                if ct.V[c_id] not in v_w:
                    break
            else:
                output.append(t_id)
    return output


def _get_unrenderable_faces_in_buffer_connected_v(ct, vfocus, v_g, v_w):
    output = []
    for t_id in _get_bounding_faces(ct, vfocus):
        for c_id in ct.iterate_triangle_corner(t_id):
            if ct.V[c_id] not in v_w:
                break
        else:
            output.append(t_id)
    return output


def _calc_c2(ct, vfocus, v_w, v_g):
    return len(_get_unrenderable_faces_in_buffer_connected_v(ct, vfocus, v_g, v_w))


def _calc_c1_c3(ct, vfocus, v_w, v_g, F_output):
    v_ws = v_w[:]
    v_gs = v_g[:]
    F_output_s = F_output[:]
    c1 = 0
    for f in _get_bounding_faces(ct, vfocus):
        if f in F_output_s:
            break
        for vl in _get_white_bounding_vertices(ct, v_ws, f):
            if len(v_gs) == BUFFER_SIZE:
                v_gs.pop(0)
            v_ws.remove(vl)
            v_gs.append(vl)
            c1 += 1

            F_output_s.extend([i for i in _get_renderable_faces_in_buffer(ct, v_gs) if (i != f) and (i not in F_output_s)])
        
        F_output.append(f)

    v_b.append(v_focus)

    c3 = v_gs.index(vfocus)

    return c1, c3


def get_minimun_cost_vertex(ct, v_w, v_g, F_output):
    minimun = None
    for v in v_g:
        c2 = _calc_c2(ct, v, v_w, v_g)
        c1, c3 = _calc_c1_c3(ct, v, v_w, v_g, F_output)
        c = c1*K1 + c2*K2 + c3*K3
        if (minimun is None) or (c < minimun):
            minimun = c
            vmin = v
    return vmin


def k_cache_reorder(ct, model=FIFO):
    v_w = ct.vertices.keys()
    v_w.sort(key=lambda x: _count_degree(ct, x))

    v_g = []
    v_b = []

    F = range(len(v_w)/3)
    F_output = []

    while len(v_b) < len(ct.vertices):
        if v_g:
            vfocus = get_minimun_cost_vertex(ct, v_w, v_g, F_output)
        else:
            vfocus = v_w[0]

        for f in _get_bounding_faces(ct, vfocus):
            if f in F_output:
                break
            for vl in _get_white_bounding_vertices(ct, v_w, f):
                if len(v_g) == BUFFER_SIZE:
                    v_g.pop(0)
                v_w.remove(vl)
                v_g.append(vl)

                F_output.extend([i for i in _get_renderable_faces_in_buffer(ct, v_g) if (i != f) and (i not in F_output)])

            F_output.append(f)

        v_b.append(vfocus)

        if v_g:
            v_g.remove(vfocus)

        for vi in v_g[:]:
            if len(_get_unrenderable_faces_in_buffer(ct, v_g, v_w)) == 0 and v_g[0] == vi:
                v_b.append(v_g.pop(0))

    return F_output



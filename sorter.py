import copy
import corner_table

FIFO=1
CONTROLLABLE=2

BUFFER_SIZE = 20

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

def _get_white_bounding_vertices(ct, f, v_w):
    output = []
    for c in ct.iterate_triangle_corner(f):
        if ct.V[c] in v_w:
            output.append(ct.V[c])
    return output


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
        v_id = ct.get_vertex(c_id)
        if v_id not in v_w:
            yield v_id


def _get_renderable_faces_in_buffer(ct, v_g):
    output = []
    for v_id in v_g:
        for t_id in _get_bounding_faces(ct, v_id):
            for c_id in ct.iterate_triangle_corner(t_id):
                if ct.get_vertex(c_id) not in v_g:
                    break
            else:
                output.append(t_id)
    return output


def _get_unrenderable_faces_in_buffer(ct, v_g, v_w):
    output = []
    for v_id in v_g:
        for t_id in _get_bounding_faces(ct, v_id):
            for c_id in ct.iterate_triangle_corner(t_id):
                if ct.get_vertex(c_id) not in v_w:
                    break
            else:
                output.append(t_id)
    return output


def _calc_c2(ct, v_g, v_w):
    return len(_get_unrenderable_faces_in_buffer(ct, v_g, v_w)


def k_cache_reoder(ct, model=FIFO):
    v_w = ct.vertices.keys()
    v_w.sort(key=lambda x: _count_degree(ct, x))

    v_g = []
    v_b = []

    F = range(len(v_w/3))
    F_output = []

    while len(v_b) < len(ct.V):
        if v_g:
            pass
        else:
            vfocus = v_w.pop(0)

        for f in _get_bounding_faces(ct, vfocus):
            if f in F_output:
                break
            for vl in _get_white_bounding_vertices(ct, v_w, f):
                if len(v_g) == BUFFER_SIZE:
                    v_g.pop(0)
                v_w.remove(vl)
                v_g.append(vl)

                F_output.extend([i for i in _get_renderable_faces_in_buffer(ct, v_g) if i != f])

            F_output.append(f)

        v_b.append(v_focus)

        if v_g:
            v_g.remove(vfocus)

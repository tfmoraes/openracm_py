import copy
import cy_corner_table
import sys

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
        if ct.get_vertex_degree(v) < minimun:
            minimun = v
    return minimun

cdef _get_white_bounding_vertices(ct, v_w, t_id):
    cdef int c_id, v_id
    output = []
    for c_id in ct.iterate_triangle_corner(t_id):
        v_id = ct.V[c_id]
        if v_id in v_w:
            output.append(v_id)
    return output


cdef _get_renderable_faces_in_buffer(ct, v_g, v_w, v_status):
    cdef int t_id, c_id
    output = set()
    for v_id in v_g:
        for t_id in ct.get_faces_connected_to_v(v_id):
            for c_id in ct.iterate_triangle_corner(t_id):
                if v_status[ct.V[c_id]] != 1:
                    break
            else:
                #if t_id not in output:
                output.add(t_id)
    return output


cdef  _get_unrenderable_faces_in_buffer(ct, v_g, v_w):
    cdef int t_id, c_id, cg
    output = []
    for v_id in v_g:
        for t_id in ct.get_faces_connected_to_v(v_id):
            cg = 0
            for c_id in ct.iterate_triangle_corner(t_id):
                if ct.V[c_id] in v_g:
                    cg += 1
            if cg != 3:
                output.append(t_id)
    return output


def _get_unrenderable_faces_in_buffer_connected_v(ct, vfocus, v_g, v_w):
    """
    Unrenderable face is that ones whose not all it vertices are in buffer.
    """
    output = []
    for t_id in ct.get_faces_connected_to_v(vfocus):
        cg = 0
        for c_id in ct.iterate_triangle_corner(t_id):
            if ct.V[c_id] in v_g:
                cg += 1
        if cg != 3:
            output.append(t_id)
    return output


def _calc_c2(ct, vfocus, v_w, v_g):
    return len(_get_unrenderable_faces_in_buffer_connected_v(ct, vfocus, v_g, v_w))


def _calc_c1_c3(ct, vfocus, v_w, v_g, F_output, v_status):
    v_ws = v_w[:]
    v_gs = v_g[:]
    v_status_s = v_status.copy()
    F_output_s = F_output[:]
    c1 = 0
    for f in ct.get_faces_connected_to_v(vfocus):
        if f in F_output_s:
            break
        for vl in _get_white_bounding_vertices(ct, v_ws, f):
            if len(v_gs) == BUFFER_SIZE:
                va = v_gs.pop(0)
                v_ws.append(va)
            v_ws.remove(vl)
            v_gs.append(vl)
            c1 += 1

            F_output_s.extend([i for i in _get_renderable_faces_in_buffer(ct, v_gs, v_ws, v_status_s) if (i != f) and (i not in F_output_s)]) 
        F_output_s.append(f)

    #v_b.append(v_focus)

    try:
        c3 = v_gs.index(vfocus)
    except ValueError:
        c3 = 0

    return c1, c3


def get_minimun_cost_vertex(ct, v_w, v_g, F_output, v_status):
    minimun = None
    for v in v_g:
        c2 = _calc_c2(ct, v, v_w, v_g)
        c1, c3 = _calc_c1_c3(ct, v, v_w, v_g, F_output, v_status)
        c = c1*K1 + c2*K2 + c3*K3
        if (minimun is None) or (c < minimun):
            minimun = c
            vmin = v
    return vmin


def k_cache_reorder(ct, model=FIFO):
    v_w = ct.vertices.keys()
    v_w.sort(key=lambda x: ct.get_vertex_degree(x))

    v_g = []
    v_b = []

    F = range(len(ct.V)/3)
    F_output = []

    v_status = dict([(i, 0) for i in xrange(len(v_w))])
    f_status = dict([(i, 0) for i in xrange(len(F))])

    while len(v_b) < len(ct.vertices):
        if v_g:
            vfocus = get_minimun_cost_vertex(ct, v_w, v_g, F_output, v_status)
        else:
            vfocus = v_w[0]

        for f in ct.get_faces_connected_to_v(vfocus):
            if f in F_output:
                break
            for vl in _get_white_bounding_vertices(ct, v_w, f):
                if len(v_g) == BUFFER_SIZE:
                    va = v_g.pop(0)
                    v_w.append(va)
                    v_status[va] = 0
                v_w.remove(vl)
                v_g.append(vl)
                v_status[vl] = 1

                for fr in _get_renderable_faces_in_buffer(ct, v_g, v_w,
                                                          v_status):
                    if (fr != f) and f_status[fr] == 0:
                        F_output.append(fr)
                        f_status[fr] = 1
                #F_output.extend([i for i in _get_renderable_faces_in_buffer(ct, v_g) if (i != f) and (i not in F_output)])

            F_output.append(f)
            f_status[f] = 1

        v_b.append(vfocus)

        if v_g:
            try:
                v_g.remove(vfocus)
            except ValueError:
                pass

        for vi in v_g[:]:
            if len(_get_unrenderable_faces_in_buffer_connected_v(ct, vi, v_g, v_w)) == 0:
                v_b.append(v_g.pop(0))
            else:
                break



        sys.stdout.write('\rSorting: %.2f' % ((100.0*len(F_output))/(len(F))))
        sys.stdout.flush()

    print 

    counter = set()
    for vi in v_b:
        for fb in ct.get_faces_connected_to_v(vi):
            if fb not in F_output:
                counter.add(fb)
    print len(F_output), len(F), len(counter), len(v_b), len(v_g), len(v_w)
    return F_output

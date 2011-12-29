import copy
import corner_table

FIFO=1
CONTROLLABLE=2

BUFFER_SIZE = 20

def _count_degree(ct, v_id):
    c = ct.get_corner_v(v_id)
    t = ct.get_triangle(c)
    cc = c
    d = 2
    while 1:
        cc = ct.swing(cc)
        nt = ct.get_triangle(cc)
        d += 1

        if nt == t:
            break
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


def k_cache_reoder(ct, model=FIFO):
    v_w = ct.vertices.keys()
    v_w.sort(key=lambda x: _count_degree(ct, x))

    for i in v_w:
        print i, _count_degree(ct,i)
    v_g = []
    v_b = []
    f_output = []

    #while len(v_b) < len(ct.V):
    #    if v_g:
    #        pass
    #    else:
    #        vfocus = _get_minimun_degree_vertex(ct, v_w)
    #        v_w.pop(vfocus)
            
         


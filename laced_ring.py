#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import random
import sys
import ply_reader
import cy_corner_table
import ply_writer
import colour_clusters

class LacedRing(object):
    def __init__(self, vertices):
        self.vertices = vertices
        #self.faces = faces
        #self.edge_ring = edge_ring
        #self.m_t = m_t
        self.L = {}
        self.R = {}
        self.O = {}
        self.V = {}

    def make_lr(self, ct, edge_ring, m_t):
        self.edge_ring = edge_ring
        self.ct = ct
        for e in xrange(len(edge_ring)-1):
            c = edge_ring[e]
            cn = edge_ring[e+1]

            if ct.next_corner(c) == cn:
                l = ct.previous_corner(c)
                self.L[e] = ct.get_vertex(l)
                self.R[e] = ct.get_vertex(ct.get_oposite_corner(l))
            else:
                r = ct.next_corner(c)
                self.R[e] = ct.get_vertex(r)
                self.L[e] = ct.get_vertex(ct.get_oposite_corner(r))

        
        print "OOO", edge_ring[0], ct.get_oposite_corner(edge_ring[ len(edge_ring) - 1 ])

        print self.R

    def to_vertices_faces(self):
        faces = []
        colours = {}
        lines = []
        cl = {}
        for e in xrange(len(self.edge_ring)-1):
            v = self.edge_ring[e]
            vn = self.edge_ring[self.next_vertex(e)]
            #print e, self.next_vertex(e)
            faces.append((self.ct.get_vertex(v), self.L[e],
                         self.ct.get_vertex(vn)))
            faces.append((self.ct.get_vertex(vn), self.R[e],
                         self.ct.get_vertex(v)))

            colours[self.ct.get_vertex(v)]= 255, 0, 0
            colours[self.ct.get_vertex(vn)]= 255, 0, 0
            colours[self.ct.get_vertex(self.L[e])]= 0, 255, 0
            colours[self.ct.get_vertex(self.R[e])]= 0, 0, 255

            lines.append((self.ct.get_vertex(v), self.ct.get_vertex(vn),
                          self.ct.get_vertex(v)))

            cl[self.ct.get_vertex(v)]=  255,255,255
            cl[self.ct.get_vertex(vn)]= 255,255,255
            cl[self.ct.get_vertex(v)]=  255,255,255

        cl[lines[0][0]] = 255, 0, 255
        cl[lines[0][1]] = 255, 0, 255
        cl[lines[0][2]] = 255, 0, 255

        cl[lines[-1][0]] = 0, 255, 0
        cl[lines[-1][1]] = 0, 255, 0
        cl[lines[-1][2]] = 0, 255, 0


        writer = ply_writer.PlyWriter('/tmp/saida_linhas.ply')
        writer.from_faces_vertices_list(lines, self.vertices, cl)

        print "Faces", len(faces), len(self.edge_ring)
        return self.vertices, faces, colours
                         

    def next_vertex(self, v):
        return (v + 1) % len(self.edge_ring)

    def previous_ring(self, v):
        return (v + len(self.edge_ring) - 1) % self.len(self.edge_ring)
            


def read_ply(ply_filename):
    vertices = {}
    faces = []
    reader = ply_reader.PlyReader(ply_filename)
    v_id = 0
    for evt, data in reader.read():
        if evt == ply_reader.EVENT_VERTEX:
            current_vertex = data
            vertices[v_id] = current_vertex
            v_id += 1

        elif evt == ply_reader.EVENT_FACE:
            faces.append(data)

    return vertices, faces


def ring_expander(ct):
    s = 0 #random.randint(0, len(ct.V))
    c = s
    m_v = {ct.get_vertex(ct.previous_corner(c)): 1,
           ct.get_vertex(ct.next_corner(c)): 1}
    m_t = {}

    while 1:
        if not m_v.get(ct.get_vertex(c), 0):
            m_v[ct.get_vertex(c)] = 1
            m_t[ct.get_triangle(c)] = 1
        elif not m_t.get(ct.get_triangle(c), 0):
            c = ct.get_oposite_corner(c)
        c = ct.get_right_corner(c)

        if c == ct.get_oposite_corner(s):
            break

    return m_v


def clusterize_ct(ct, cluster_size):
    number_cluster = (len(ct.V)/3) / cluster_size
    if (len(ct.V)/3) % cluster_size:
        number_cluster += 1

    clusters = {}
    for n in xrange(number_cluster):
        clusters[n] = range(n * cluster_size,
                            (n + 1) * cluster_size)
    return clusters
    

def make_vertex_faces(vertices, faces):
    vertices_faces = {}
    for f_id, face in enumerate(faces):
        for v in face:
            try:
                vertices_faces[v].append(f_id)
            except KeyError:
                vertices_faces[v] = [f_id,]
    return vertices_faces

def _expand_ring(ct, s, cluster, min_, max_):
    c = s
    m_v = {ct.get_vertex(ct.previous_corner(c)): 1,
           ct.get_vertex(ct.next_corner(c)): 1}
    m_t = {}
    edge_ring = [ct.previous_corner(c), ct.next_corner(c)]

    n = 0
    while 1:
        if not m_v.get(ct.get_vertex(c), 0):
            if min_ <= ct.get_triangle(c) < max_:
                m_v[ct.get_vertex(c)] = 1
                m_t[ct.get_triangle(c)] = 1
                edge_ring.append(c)
                n = 0
            else:
                c = ct.get_oposite_corner(c)
                if n > 100:
                    return m_v, m_t, edge_ring
                n += 1

        elif not m_t.get(ct.get_triangle(c), 0):
            c = ct.get_oposite_corner(c)

        #elif (not min_ <= ct.get_triangle(c) < max_) and (not m_t.get(ct.get_triangle(c), 0)) :
            ##print n, ct.get_triangle(c), min_, max_
            #c = ct.get_oposite_corner(c)
            ##c = ct.get_right_corner(c)
            ##print n, ct.get_triangle(c), min_, max_
        c = ct.get_right_corner(c)
        if c == ct.get_oposite_corner(s):
            return m_v, m_t, edge_ring

def expand_ring_into_cluster(ct, cluster, pmin):
    #s = ct.get_corner_f(random.randint(min(clusters[ncluster]),
                                       #max(clusters[ncluster])))
    n_too_little = 0
    min_, max_ = min(cluster), max(cluster)
    vertices = set()
    for i in xrange(min_, max_):
        for c in ct.iterate_triangle_corner(i):
            vertices.add(ct.get_vertex(c))

    nvertices = len(vertices)

    gt_t = -1
    gt = None

    print "Cluster size", len(cluster)
    for i in xrange(min_, max_):
        for c in ct.iterate_triangle_corner(i):
            s = c
            m_v, m_t, edge_ring = _expand_ring(ct, s, cluster, min_, max_)
            if len(m_v) > gt_t or gt is None:
                gt_t = len(m_v)
                gt = s
        #if (float(len(m_t)) / (max_ - min_)) > pmin:
            #break
        #else:
            ##print "\tjust a little", len(m_v), len(m_t), float(len(m_t)) / (max_ - min_)
            #if n_too_little == 1000:
                #break
            #n_too_little += 1

    m_v, m_t, edge_ring = _expand_ring(ct, gt, cluster, min_, max_)
    print nvertices, len(m_v)

    edge_ring_t = []
    for c in edge_ring:
        for ci in ct.iterate_triangle_corner(ct.get_triangle(c)):
            edge_ring_t.append(ci)

    return m_v, m_t, edge_ring_t

def hybrid_expand_ring_into_cluster(ct, ncluster, clusters):
    min_, max_ = min(clusters[ncluster]), max(clusters[ncluster])
    s = ct.get_corner_f(random.randint(min_, max_))
    c = s
    k = 99999

    m_v = {ct.get_vertex(ct.previous_corner(c)): 1,
           ct.get_vertex(ct.next_corner(c)): 1}
    m_t = {}
    d = []
    n = 0
    while 1:
        if (not m_v.get(ct.get_vertex(c), 0)) and (min_ <= ct.get_triangle(c) < max_):
            m_v[ct.get_vertex(c)] = 1
            m_t[ct.get_triangle(c)] = 1

            d.append(ct.get_left_corner(c))
            d.append(ct.get_right_corner(c))
            n += 1

        if not d:
            break
        if n % k == 0:
            c = d.pop(0)
        else:
            c = d.pop()
        
    return m_v


def test_laced_ring(vertices, faces, cluster_size, pmin):
    vertices_faces = make_vertex_faces(vertices, faces)
    ct = cy_corner_table.CornerTable()
    ct.create_corner_from_vertex_face(vertices, faces, vertices_faces)
    clusters = colour_clusters.clusterize(faces, cluster_size) # clusterize_ct(ct, cluster_size)
    #print clusters.keys()
    ecluster = {}
    #for i, cluster in enumerate(clusters):
        #if len(cluster) > 1:
            #ncluster, m_t = expand_ring_into_cluster(ct, cluster, pmin)
            #print i, len(ncluster), len(m_t) / float(len(cluster))
            #ecluster.update(ncluster)

    #colours = {}
    #for v in xrange(len(vertices)):
        #if ecluster.get(v, 0):
            #colours[v] = (255, 0, 0)
        #else:
            #colours[v] = (255, 255, 255)
    #writer = ply_writer.PlyWriter('/tmp/saida.ply')
    #writer.from_faces_vertices_list(faces, vertices, colours)
    ncluster, m_t, edge_ring = expand_ring_into_cluster(ct, clusters[0], pmin)
    lr = LacedRing(vertices)
    lr.make_lr(ct, edge_ring, m_t)
    vertices, faces, colours = lr.to_vertices_faces()
    writer = ply_writer.PlyWriter('/tmp/saida.ply')
    writer.from_faces_vertices_list(faces, vertices, colours)


def main():
    vertices, faces = read_ply(sys.argv[1])
    test_laced_ring(vertices, faces, int(sys.argv[2]), float(sys.argv[3]))

if __name__ == '__main__':
    main()



#!/usr/bin/env python
# -*- coding: UTF-8 -*-

EVENT_VERTEX = 1
EVENT_FACE = 2

class PlyReader(object):
    def __init__(self, filename):
        self.filename = filename
        
    def read(self):
        with open(self.filename, 'r') as ply_file:
            for line in ply_file:
                # reading header
                if line.startswith('element vertex'):
                    n_vertex = int(line.split()[2])
                elif line.startswith('element face'):
                    n_faces = int(line.split()[2])
                elif line.startswith('end_header'):
                    break

            # reading vertex
            v_id = 0
            for line in ply_file:
                vertex = [float(v.replace(',', '.')) for v in line.split()][:3]
                yield (EVENT_VERTEX, vertex)
                v_id += 1
                if v_id == n_vertex:
                    break

            # reading faces
            f_id = 0
            for line in ply_file:
                face = [int(v) for v in line.split()][1:4]
                yield (EVENT_FACE, face)
                f_id += 1
                if f_id == n_faces:
                    break
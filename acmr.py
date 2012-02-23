import sys
import ply_reader
import ply_writer

class Buffer(object):
    """
    It's a buffer Fifo.
    """
    def __init__(self, size):
        """
        size - The size of the buffer.
        """
        self.size = size
        self._buffer = []

    def push(self, v):
        """
        Append the given vertex v to the buffer object. If the buffer is full,
        it drops the first vertex in the buffer.
        """
        if v in self._buffer:
            return False
        
        if len(self._buffer) == self.size:
            self._buffer.pop(0)
        self._buffer.append(v)
        return True

def count_acmr(ply_filename, buffer_size):
    """
    This function returns the Average Cache Miss Ratio (ACMR) of a given mesh
    file taking into account the buffer size. The mesh file must be in ply
    format.
    """
    reader = ply_reader.PlyReader(ply_filename)
    buffer = Buffer(buffer_size)
    misses = 0
    for evt, data in reader.read():
        if evt == ply_reader.EVENT_HEADER:
            n_vertex, n_faces = data
        if evt == ply_reader.EVENT_FACE:
            for v in data:
                if buffer.push(v):
                    misses += 1
            
    print u"Number of vertex: %d" % n_vertex
    print u"Number of faces: %d" % n_faces
    print u"Number of misses: %d" % misses
    print u"ACMR: %f" % (float(misses) / n_faces)

def main():
    count_acmr(sys.argv[1], int(sys.argv[2]))

if __name__ == '__main__':
    main()

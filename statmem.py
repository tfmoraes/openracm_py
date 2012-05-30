import numpy
import sys

def get_stat_mem(f):
    measures = []
    with file(f, 'r') as f_mem:
        for line in f_mem:
            measures.append(float(line.split()[1]))

        mem = numpy.array(measures)
        print mem.max(),
        print mem.mean(),
        print mem.std()


def main():
    get_stat_mem(sys.argv[1])

if __name__ == '__main__':
    main()

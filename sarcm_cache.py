import math

from cluster_loader import cluster_loader

from blist import blist
import collections

NOTFOUND=0
RANDOM=1
SEQ=2

PPREF=0.5

class LRU(object):
    def __init__(self):
        self._values = {}
        self._time = collections.OrderedDict()

    def __contains__(self, key):
        return self._values.__contains__(key)

    def __delitem__(self, key):
        if self._values.has_key(key):
            del self._values[key]
            del self._time[key]

    def __setitem__(self, key, value):
        self.__delitem__(key)
        self._values[key] = value
        self._time[key] = value

    def __getitem__(self, key):
        return self._values[key]

    def __len__(self):
        return self._time.__len__()

    def get_lru(self):
        return self._time.keys()[0]

    def get_mru(self):
        return self._time.keys()[-1]

    def pop(self, key):
        del self._values[key]
        return self._time.pop(key)

class SarcItem(object):
    def __init__(self, value, timestamp):
        self.value = value
        self.bit = 0
        self.timestamp = timestamp

    def __cmp__(self, o):
        try:
            return self.value.__cmp__(o)
        except TypeError:
            return self.value.__cmp__(o.value)

    def __repr__(self):
        return "%s" % self.value

    def __str__(self):
        return "%s" % self.value

class SarcMeshCache(object):
    def __init__(self, cache_size, threshold=2):
        self._cache_size = cache_size

        self.to_bench = False
        self.crandom = LRU()
        self.cseq = LRU()

        self.timestamp = 0

        self.desiredSeqListSize = 0.0
        self.adapt = 0.0
        self.seqMiss = 0
        self.largeRatio = 20

        self.seqcounter = 0
        self.seqThreshold = threshold

        self.dL = self._cache_size * 0.2

    @property
    def cache_size(self):
        return self._cache_size

    @cache_size.setter
    def cache_size(self, value):
        self._cache_size = value
        self.dL = self._cache_size * 0.2


    def update_usage(self, clmrg, cl):
        cl = int(cl)
        crandom = self.crandom
        cseq = self.cseq
        try:
            self.ratio = (2.0 * self.seqMiss * self.dL)/len(cseq)
        except ZeroDivisionError:
            self.ratio = 0.0

        LR = len(crandom)
        LS = len(cseq)

        ## FINDING where is the cl
        #try:
            #index = crandom.index(cl)
            #where = RANDOM
        #except ValueError:
            #try:
                #index = cseq.index(cl)
                #where = SEQ
            #except ValueError:
                #where = NOTFOUND

        if cl in crandom:
            where = RANDOM
            hit = crandom[cl]
        elif cl in cseq:
            where = SEQ
            hit = cseq[cl]
        else:
            where = NOTFOUND
        

        # it's in random cache
        if where == RANDOM:
            #lru = crandom[-1]
            #mru = crandom[0]
            #hit = crandom.pop(index)
            lru = crandom.get_lru()
            t_lru = crandom[lru]
            mru = crandom.get_mru()
            t_mru = crandom[mru]


            # it's in random bottom
            if hit - t_lru <= (self.dL/LR)* (t_mru - t_lru):
                self.seqMiss = 0
                self.adapt = max(-1, min(self.ratio - 1, 1))

            #hit.timestamp = self.timestamp
            #crandom.insert(0, hit)
            crandom[cl] = self.timestamp

        elif where == SEQ:
            lru = cseq.get_lru()
            t_lru = cseq[lru]
            mru = cseq.get_mru()
            t_mru = cseq[mru]
            
            if hit - t_lru <= (self.dL/LS)*(t_mru - t_lru):
                if self.ratio > self.largeRatio:
                    self.adapt = 1.0

            #hit.timestamp = self.timestamp
            #cseq.insert(0, hit)
            cseq[cl] = self.timestamp

            if (cl - 1) in crandom or (cl - 1) in cseq:
                #if not self.seqcounter.get(cl - 1, 0):
                    #self.seqcounter[cl] = max(self.seqThreshold,
                                          #self.seqcounter.get(cl-1, 0) + 1)
                self.seqcounter += 1
            else:
                self.seqcounter -= 1

        self.timestamp += 1

    def replace(self, cl_usage, etype=RANDOM):
        LR = len(self.crandom)
        LS = len(self.cseq)
        if etype == SEQ and LS <= PPREF*self._cache_size:
            try:
                k = self.crandom.get_lru()
                del self.crandom[k]
            except IndexError:
                k = self.cseq.get_lru()
                del self.cseq[k]
        elif LS < self.dL or LR < self.dL:
            if not self.crandom or (self.cseq and self.cseq[self.cseq.get_lru()] < self.crandom[self.crandom.get_lru()]):
                t = 1
                #k = self.cseq.pop()
                k = self.cseq.get_lru()
                del self.cseq[k]
            else:
                t= 2
                #k = self.crandom.pop()
                k = self.crandom.get_lru()
                del self.crandom[k]

        else:
            if LS > self.desiredSeqListSize:
                t= 3
                if self.cseq[self.cseq.get_lru()] == cl_usage:
                    print "OIOI", 
                    print "k", self.cseq[-1]
                    print "cseq", self.cseq
                    print "crandom", self.crandom
                    print "dL", self.dL
                    print "derideseqlist", self.desiredSeqListSize
                    print "cachesize", self.cache_size
                    print "adapt", self.adapt
                    print "tipo", t
                    print "ratio", self.ratio
                #k = self.cseq.pop()
                k = self.cseq.get_lru()
                del self.cseq[k]
            else:
                t= 4
                #k = self.crandom.pop()
                k = self.crandom.get_lru()
                del self.crandom[k]

                
        #self._adapt()
        return k

    def _adapt(self):
        if self.desiredSeqListSize > 0:
            self.desiredSeqListSize += self.adapt / 2.0
        else:
            self.desiredSeqListSize = len(self.cseq)


    # NOT found (MISS)
    def load_cluster(self, clmrg, cl):
        icl = int(cl)
        LR = len(self.crandom)
        LS = len(self.cseq)
        #if LS + LR >= self._cache_size:
            #k = str(self.replace(icl))
            #del clmrg._vertices[k]
            #del clmrg._L[k]
            #del clmrg._R[k]
            #del clmrg._VOs[k]
            #del clmrg._O[k]
            #del clmrg._V[k]
            #del clmrg._C[k]

            #clmrg.last_removed = k

            #if k == clmrg.last_loaded:
                #clmrg.wastings.append(k)

            #try:
                #clmrg._n_unload_clusters[k] += 1
            #except KeyError:
                #clmrg._n_unload_clusters[k] = 1

        if self.seqcounter >= self.seqThreshold \
           and ((icl -1) in self.cseq or (icl - 1) in self.crandom) \
           and  icl in clmrg.map_cluster_dependency:

            deps = clmrg.map_cluster_dependency[icl]
            load = [icl, ]
            for i in xrange(icl - 1, icl - len(deps), -1):
                if i not in deps:
                    break
                load.append(i)

            for i in xrange(icl + 1, icl + len(deps), 1):
                if i not in deps:
                    break
                load.append(i)

            load = load[:int(math.ceil(PPREF*self._cache_size))]
            load.sort()

            if not self.to_bench:
                if len(load) > 1:
                    init_cluster0, cluster_size0, iface0, eface0 = [int(i) for i in
                                                                    clmrg.index_clusters[str(load[0])].split()]
                    init_cluster1, cluster_size1, iface1, eface1 = [int(i) for i in
                                                                    clmrg.index_clusters[str(load[-1])].split()]
                    clmrg.cfile.seek(init_cluster0)
                    str_cluster = clmrg.cfile.read((init_cluster1 - init_cluster0) + cluster_size1)

                else:
                    init_cluster, cluster_size, iface, eface = [int(i) for i in clmrg.index_clusters[cl].split()]
                    clmrg.cfile.seek(init_cluster)
                    str_cluster = clmrg.cfile.read(cluster_size)

            init = 0
            for c in load:
                str_c = str(c)
                if self.to_bench:
                    vertices, L, R, VOs, V, C, O = range(7)
                else:
                    init_cluster, cluster_size, iface, eface = [int(i) for i in
                                                                clmrg.index_clusters[str_c].split()]
                    scluster = str_cluster[init: init + cluster_size]
                    init += cluster_size

                    vertices, L, R, VOs, V, C, O = cluster_loader(scluster)
                
                if str_c not in clmrg._L:
                    clmrg._vertices[str_c] = vertices
                    clmrg._L[str_c] = L
                    clmrg._R[str_c] = R
                    clmrg._VOs[str_c] = VOs
                    clmrg._V[str_c] = V
                    clmrg._C[str_c] = C
                    clmrg._O[str_c] = O


                    LR = len(self.crandom)
                    LS = len(self.cseq)

                    to_adapt = 0
                    if LS + LR > self._cache_size:
                        k = str(self.replace(icl, SEQ))
                        del clmrg._vertices[k]
                        del clmrg._L[k]
                        del clmrg._R[k]
                        del clmrg._VOs[k]
                        del clmrg._O[k]
                        del clmrg._V[k]
                        del clmrg._C[k]

                        to_adapt = 1
                        
                        if k == cl:
                            print "Load", load
                    #print self.desiredSeqListSize, len(self.cseq), len(self.crandom), self.cache_size

                    #sitem = SarcItem(c, self.timestamp)
                    #self.cseq.insert(0, sitem)
                    self.cseq[c] = self.timestamp

                    if to_adapt:
                        self._adapt()

                else:
                    #try:
                        #index = self.cseq.index(c)
                        #hit = self.cseq.pop(index)
                        #hit.timestamp = self.timestamp
                        #self.cseq.insert(0, hit)
                    #except ValueError:
                        #index = self.crandom.index(c)
                        #hit = self.crandom.pop(index)
                        #hit.timestamp = self.timestamp
                        #self.cseq.insert(0, hit)

                    if c in self.cseq:
                        self.cseq[c] = self.timestamp
                    else:
                        self.crandom[c] = self.timestamp


                self.timestamp += 1

            self.seqMiss += 1
            self.seqcounter = self.seqThreshold

        else:
            if self.to_bench:
                vertices, L, R, VOs, V, C, O = range(7)
            else:
                init_cluster, cluster_size, iface, eface = [int(i) for i in clmrg.index_clusters[cl].split()]
                clmrg.cfile.seek(init_cluster)
                str_cluster = clmrg.cfile.read(cluster_size)

                vertices, L, R, VOs, V, C, O = cluster_loader(str_cluster)

            LS = len(self.cseq)
            LR = len(self.crandom)

            to_adapt = 0
            if LS + LR > self._cache_size:
                k = str(self.replace(icl))
                del clmrg._vertices[k]
                del clmrg._L[k]
                del clmrg._R[k]
                del clmrg._VOs[k]
                del clmrg._O[k]
                del clmrg._V[k]
                del clmrg._C[k]
                to_adapt = 1

            clmrg._vertices[cl] = vertices
            clmrg._L[cl] = L
            clmrg._R[cl] = R
            clmrg._VOs[cl] = VOs
            clmrg._V[cl] = V
            clmrg._C[cl] = C
            clmrg._O[cl] = O

            #sitem = SarcItem(icl, self.timestamp)
            self.crandom[icl] = self.timestamp

            if to_adapt:
                self._adapt()

            self.timestamp += 1
            
            if self.seqcounter:
                self.seqcounter += 1
            else:
                self.seqcounter = 1

        try:
            clmrg._n_load_clusters[cl] += 1
        except KeyError:
            clmrg._n_load_clusters[cl] = 1
            clmrg._n_unload_clusters[cl] = 0

        clmrg.last_loaded = cl
        if clmrg.last_removed == cl:
            clmrg.wastings.append(cl)

        clmrg.misses += 1

    def bench(self, clmrg, filename):
        clmrg.to_bench = True
        self.to_bench = True
        n = 0
        with open(filename) as f:
            clmrg.misses = 0
            clmrg.access = 0
            for l in f:
                cl = l.strip()
                if cl:
                    if cl not in clmrg._L:
                        self.load_cluster(clmrg, cl)
                    else:
                        clmrg.hits += 1
                    self.update_usage(clmrg, cl)
                    clmrg.access += 1

                if n % 100000 == 0:
                    print n
                n += 1

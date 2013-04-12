import math

from cluster_loader import cluster_loader

NOTFOUND=0
RANDOM=1
SEQ=2

PPREF=0.5
M=2

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

class SarcMesh2Cache(object):
    def __init__(self, cache_size, threshold=2):
        self._cache_size = cache_size
        
        self.to_bench = False

        self.crandom = []
        self.cseq = []

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
        try:
            self.ratio = (2.0 * self.seqMiss * self.dL)/len(self.cseq)
        except ZeroDivisionError:
            self.ratio = 0.0

        LR = len(self.crandom)
        LS = len(self.cseq)

        # FINDING where is the cl
        try:
            index = self.crandom.index(cl)
            where = RANDOM
        except ValueError:
            try:
                index = self.cseq.index(cl)
                where = SEQ
            except ValueError:
                where = NOTFOUND
        

        # it's in random cache
        if where == RANDOM:
            lru = self.crandom[-1]
            mru = self.crandom[0]
            hit = self.crandom.pop(index)

            # it's in random bottom
            if hit.timestamp - lru.timestamp <= (self.dL/LR)*(mru.timestamp - lru.timestamp):
                self.seqMiss = 0
                self.adapt = max(-1, min(self.ratio - 1, 1))

            hit.timestamp = self.timestamp
            self.crandom.insert(0, hit)

        elif where == SEQ:
            lru = self.cseq[-1]
            mru = self.cseq[0]
            hit = self.cseq.pop(index)
            
            if hit.timestamp - lru.timestamp <= (self.dL/LS)*(mru.timestamp - lru.timestamp):
                if self.ratio > self.largeRatio:
                    self.adapt = 1.0

            hit.timestamp = self.timestamp
            self.cseq.insert(0, hit)

            if (cl - 1) in self.crandom or (cl - 1) in self.cseq:
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
                k = self.crandom.pop()
            except IndexError:
                k = self.cseq.pop()
        elif LS < self.dL or LR < self.dL:
            if not self.crandom or (self.cseq and self.cseq[-1].timestamp < self.crandom[-1].timestamp):
                t = 1
                k = self.cseq.pop()
            else:
                t= 2
                k = self.crandom.pop()
        else:
            if LS > self.desiredSeqListSize:
                t= 3
                if self.cseq[-1] == cl_usage:
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
                k = self.cseq.pop()
            else:
                t= 4
                k = self.crandom.pop()

                
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

        if ((icl -1) in self.cseq or (icl - 1) in self.crandom) \
           and  icl in clmrg.map_cluster_dependency:

            deps = clmrg.map_cluster_dependency[icl]
            self.seqMiss += 1

            load = [i for i in xrange(icl, icl + M)]
            #for i in xrange(icl - 1, icl - len(deps), -1):
                #if i not in deps:
                    #break
                #load.append(i)

            #for i in xrange(icl + 1, icl + len(deps), 1):
                #if i not in deps:
                    #break
                #load.append(i)

            load = load[:int(math.ceil(PPREF*self._cache_size))]
            #load.sort()


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
                        self._adapt()
                        
                        if k == cl:
                            print "Load", load
                    #print self.desiredSeqListSize, len(self.cseq), len(self.crandom), self.cache_size

                    sitem = SarcItem(c, self.timestamp)
                    self.cseq.insert(0, sitem)

                    #if to_adapt:
                        #self._adapt()

                else:
                    try:
                        index = self.cseq.index(c)
                        hit = self.cseq.pop(index)
                        hit.timestamp = self.timestamp
                        self.cseq.insert(0, hit)
                    except ValueError:
                        index = self.crandom.index(c)
                        hit = self.crandom.pop(index)
                        hit.timestamp = self.timestamp
                        self.cseq.insert(0, hit)


                self.timestamp += 1

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
                self._adapt()

            clmrg._vertices[cl] = vertices
            clmrg._L[cl] = L
            clmrg._R[cl] = R
            clmrg._VOs[cl] = VOs
            clmrg._V[cl] = V
            clmrg._C[cl] = C
            clmrg._O[cl] = O

            sitem = SarcItem(icl, self.timestamp)
            self.crandom.insert(0, sitem)

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

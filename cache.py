import pickle
from collections import defaultdict
from functools import partial

from cachetools import FIFOCache


class MyFIFOCache(FIFOCache):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_data(self):
        """获取缓存数据"""
        return self._FIFOCache__order


class Cache:
    """缓存"""

    def __init__(self, maxsize=100):
        self.caches = defaultdict(partial(MyFIFOCache, maxsize=maxsize))

    def put(self, cache_name, item):
        self.caches[cache_name][item] = None

    def is_in_cache(self, cache_name, item):
        return item in self.caches[cache_name]

    def save(self, path):
        """保存缓存数据到本地"""
        tmp = {k: cache.get_data() for k, cache in self.caches.items()}
        with open(path, 'wb') as f:
            pickle.dump(tmp, f)

    def save(self, path, group_name):
        """保存缓存数据到本地"""
        tmp = {k: cache.get_data() for k, cache in self.caches.items() if k == group_name}
        with open(path, 'wb') as f:
            pickle.dump(tmp, f)

    def load(self, path):
        """加载本地缓存数据"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            for k, d in data.items():
                for kk in d.keys():
                    self.put(k, kk)


if __name__ == "__main__":
    from pprint import pprint

    # MAX_SIZE = 3
    # cache = Cache(MAX_SIZE)
    # cache.put("aa", 333)
    # cache.put("aa", 345)
    # cache.put("aa", 0)
    # pprint(cache.caches)
    # cache.put("aa", 789)
    # pprint(cache.caches)
    # cache.put("22", 892)
    # cache.put("22", "ab")
    # pprint(cache.caches)

    # cache.save("tmp_cache.pkl")

    new_cache = Cache(500)
    new_cache.load("myCache.pkl")
    new_cache.put("aa", 333)
    pprint(new_cache.caches)

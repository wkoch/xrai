import warnings,unittest.mock
from cachetools import cachedmethod
class C:
 def __init__(self):self.cache={}
 @cachedmethod(lambda self:self.cache)
 def f(self,x):return x
with warnings.catch_warnings(record=True) as recorded:
 warnings.simplefilter('always');unittest.mock.create_autospec(C,instance=True)
assert not recorded, [str(w.message) for w in recorded]

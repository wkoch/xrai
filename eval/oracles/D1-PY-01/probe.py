from cachetools import cachedmethod
import threading
for info in [False, True]:
 for mode in ['unlocked','locked','condition']:
  mutex=threading.RLock(); cond=threading.Condition(mutex)
  opts={'info':info}
  if mode=='locked': opts['lock']=lambda s:s.mutex
  if mode=='condition': opts['condition']=lambda s:s.cond
  class C:
   def __init__(self): self.cache={};self.label='owner';self.mutex=mutex;self.cond=cond;self.calls=0
   @cachedmethod(lambda s:s.cache,key=lambda s,x:(s.label,x),**opts)
   def f(self,x): self.calls+=1;return x*2
  c=C();assert c.f.cache_key(21)==('owner',21),(mode,info)
  assert c.f(21)==42;assert c.f(21)==42;assert c.calls==1
  assert ('owner',21) in c.cache
  c.f.cache_clear();assert not c.cache

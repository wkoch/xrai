#!/private/tmp/xrai-l4-measurement/bin/python
import json,os,struct,sys,time
from pathlib import Path
r=sys.stdin.buffer;w=sys.stdout.buffer
h=r.read(47); n=struct.unpack('<Q',h[7:15])[0];body=r.read(n)
inc=b'1'*32
w.write(b'XRW2'+struct.pack('<H',2)+b'\x02'+struct.pack('<Q',len(body))+inc+body);w.flush()
h=r.read(47)
Path('/private/tmp/xrai-review-xrw2-peer-receipt.json').write_text(json.dumps({'pid':os.getpid(),'parse_header_received':len(h),'advertised_parse_bytes':struct.unpack('<Q',h[7:15])[0]}))
# Unexpected READY before draining an 8MiB source body. Parent must retire before joining writer.
w.write(b'XRW2'+struct.pack('<H',2)+b'\x02'+struct.pack('<Q',0)+inc);w.flush()
time.sleep(60)

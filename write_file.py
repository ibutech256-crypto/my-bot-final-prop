import base64,sys
p=sys.argv[1]
b=sys.argv[2]
c=base64.b64decode(b).decode("utf-8")
open(p,"w",encoding="utf-8").write(c)
print("OK:"+p)


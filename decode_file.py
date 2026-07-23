import base64,sys
p=sys.argv[1]
b64_file=sys.argv[2] if len(sys.argv)>2 else p+".b64"
with open(b64_file,"r") as f:
    c=base64.b64decode(f.read().strip()).decode("utf-8")
with open(p,"w",encoding="utf-8") as f:
    f.write(c)
print("OK:"+p)


import base64,sys; 
p=sys.argv[1]; 
with open(p+.b64) as f: c=base64.b64decode(f.read().strip()).decode(utf-8); 
with open(p,w,encoding=utf-8) as f: f.write(c); 
print(OK:+p) 

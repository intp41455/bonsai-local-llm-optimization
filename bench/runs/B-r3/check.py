import re
p = "results/pelican.svg"
s = open(p, encoding="utf-8").read()
lines = s.splitlines()
print("lines:", len(lines))
print("external refs:", bool(re.search(r'http|https|file://|data:', s)))
print("svg ok:", s.startswith("<svg"))

from pathlib import Path
import io,re,base64
from PIL import Image
p=Path('dist/CorridorKey2.0-hp-beta-User-Book.html');s=p.read_text();b=io.BytesIO();Image.open('.build/evidence/guide-screenshots/controls-0.9.7.jpg').convert('RGB').save(b,format='PNG');encoded=base64.b64encode(b.getvalue()).decode();pat=r'(<img\b[^>]*src=")data:image/png;base64,[^"<>]+(" alt="Actual Fusion keyer and controls beside a keyed green-screen subject")';s,n=re.subn(pat,lambda m:m[1]+'data:image/png;base64,'+encoded+m[2],s);assert n==1
s=s.replace('A real keyed frame, the Inspector groups, and the Fusion flow on this Mac.','Final installed 0.9.7: a real keyed frame, compact Inspector groups, and the Fusion flow on this Mac.')
s=s.replace('Native 1080p has extensive real MPS and Resolve evidence; that does not establish every required release gate.','Native 1080p has completed real MPS and Resolve tests. Clean-account installation, whole-Mac offline first use, and restart checks still need their recorded physical handoff.')
s=s.replace('Read QA-37 and QA-38 in the accompanying report for the actual repair and uninstall test results. Workflow availability by itself is not a passed native maintenance test.','The installed 0.9.7 Manager passed graphical missing-file repair, interrupted-component recovery, Keep Models and Remove All tests. The final package was then reinstalled and fresh MPS inference verified. Read QA-37 and QA-38 in the accompanying report for the exact scope.')
s=s.replace('<a href="NATIVE_QUALIFICATION.md">the acceptance report</a>','<a href="Native-Qualification.html">the acceptance report</a>')
p.write_text(s)
p=Path('dist/USER_GUIDE.md');s=p.read_text();intro='''For the illustrated, bookmarked offline guide, open
[CorridorKey2.0 hp beta — User Book](CorridorKey2.0-hp-beta-User-Book.html).

Documentation update for installed 0.9.7: the real acquisition-edit safety test,
graphical repair and both installed removal workflows passed. The overall beta
still needs clean-account/offline first use and restart evidence. A new or changed
temporal shot requires matching captures in separate render requests; if prompted,
keep inputs stable and request another frame or repeat native pre-render. Do not
click Analyze Shot again merely to acknowledge verification. Safe source-identity
refresh retries can occur even with unchanged visible pixels.

''';p.write_text(intro+s)
print('Final installed controls added to the offline book.')

"""Find and fix the remaining OpenPosition.update_or_create."""
import paramiko, time

HOST = '194.37.80.107'
USER = 'Administrator'
PASS = '3634#Dt@123456'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=10, banner_timeout=5)

sftp = c.open_sftp()

# Read engine file
f = sftp.open('C:\\prop-frim-bot\\backend\\apps\\trading\\management\\commands\\run_mt5_engine.py')
content = f.read().decode('utf-8')
f.close()

lines = content.split('\n')
print(f"Total lines: {len(lines)}")
for i, line in enumerate(lines):
    if i >= 750 and i <= 770:
        print(f"  {i+1}: {line[:120]}")

# Find update_or_create on OpenPosition
for i, line in enumerate(lines):
    stripped = line.strip()
    if 'OpenPosition.objects.update_or_create' in stripped:
        print(f"\nFound at line {i+1}")
        # Show the full block
        for j in range(i-1, min(len(lines), i+20)):
            print(f"  {j+1}: {lines[j][:120]}")

c.close()

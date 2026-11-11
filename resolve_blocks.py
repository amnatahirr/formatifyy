import sys
path, choices = sys.argv[1], sys.argv[2].split(',')
raw = open(path, encoding='utf-8', newline='').read().split('\n')
out, state, idx, ch = [], 0, 0, None
for line in raw:
    s = line.rstrip('\r')
    if s.startswith('<<<<<<<'):
        state, ch, idx = 1, choices[idx], idx + 1
        if ch == 'skip': out.append(line)
        continue
    if state == 1 and s == '=======':
        state = 2
        if ch == 'skip': out.append(line)
        continue
    if state == 2 and s.startswith('>>>>>>>'):
        state = 0
        if ch == 'skip': out.append(line)
        continue
    if state == 0 or ch == 'skip' or (state == 1 and ch in ('ours', 'both')) or (state == 2 and ch in ('theirs', 'both')):
        out.append(line)
assert idx == len(choices), f'{path}: found {idx} blocks, gave {len(choices)} choices'
open(path, 'w', encoding='utf-8', newline='').write('\n'.join(out))

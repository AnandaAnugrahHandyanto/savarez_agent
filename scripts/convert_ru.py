"""Convert old flat-key ru.ts to new defineLocale() format."""
import re
import json

OLD_PATH = 'apps/desktop/src/i18n/ru.ts'
NEW_PATH = 'apps/desktop/src/i18n/ru_new.ts'

with open(OLD_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract key-value pairs
pairs = {}
key_order = []
for line in content.split('\n'):
    line = line.strip()
    if not line or line == '});':
        continue
    if line.startswith('import') or line.startswith('registerTranslations'):
        continue
    if line.startswith('//') or line.startswith('/*') or line.startswith('*'):
        continue
    if line.endswith(','):
        line = line[:-1]
    m = re.match(r"'([^']+)':\s*'(.+)'$", line)
    if m:
        key = m.group(1)
        val = m.group(2).replace("'", "\\'")
        pairs[key] = val
        key_order.append(key)

print(f'Found {len(pairs)} keys')

# Build nested dict, sorting shallowest-first to handle prefix conflicts
def set_nested(d, path, value):
    parts = path.split('.')
    for part in parts[:-1]:
        part = part.replace('-', '_')
        if part not in d:
            d[part] = {}
        if not isinstance(d[part], dict):
            print(f'  WARN: "{path}" — "{part}" was string, converting to dict')
            d[part] = {}
        d = d[part]
    last = parts[-1].replace('-', '_')
    d[last] = value

nested = {}
sorted_keys = sorted(key_order, key=lambda k: len(k.split('.')))
for key in sorted_keys:
    set_nested(nested, key, pairs[key])

def format_val(val):
    if '{0}' in val or '{1}' in val or '{2}' in val:
        indices = sorted(set(int(m) for m in re.findall(r'\{(\d+)\}', val)))
        params = ', '.join('abcdefghijklmnopqrstuvwxyz'[i] if i < 26 else f'p{i}' for i in indices)
        result = val
        for idx in reversed(indices):
            pn = 'abcdefghijklmnopqrstuvwxyz'[idx] if idx < 26 else f'p{idx}'
            result = result.replace(f'{{{idx}}}', f'${{{pn}}}')
        return f"({params}) => `{result}`"
    else:
        return f"'{val}'"

def dump_dict(d, indent=2):
    p = '  ' * indent
    lines = []
    for key in sorted(d.keys()):
        val = d[key]
        if isinstance(val, dict):
            lines.append(f'{p}{key}: {{')
            lines.extend(dump_dict(val, indent + 1))
            lines.append(f'{p}}},')
        else:
            lines.append(f'{p}{key}: {format_val(val)},')
    return lines

lines = dump_dict(nested, 2)
output = f"""import {{ defineLocale }} from './define-locale'

export const ru = defineLocale({{
{chr(10).join(lines)}
}})
"""

with open(NEW_PATH, 'w', encoding='utf-8') as f:
    f.write(output)

print(f'Wrote {len(lines)} lines to {NEW_PATH}')
print('First 10 lines of output:')
for line in output.split('\n')[:15]:
    print(f'  {line}')

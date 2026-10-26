"""Independent terminal callback traces; freeze before native execution."""
import json


def tokens(items):
    return [str(value) for text, offset, length in items for value in (text.encode().hex(), offset, length)]


def expected():
    rows=[]
    for kind in ('pattern','any'):
        for scenario in range(7):
            if scenario==0:trace=tokens([('a',0,1)])
            elif scenario==4:trace=tokens([('a',0,1),('v',2,1),('w',4,1)])
            elif scenario==5:trace=tokens([('a',0,1)])
            else:trace=tokens([('a',0,1),('b',2,1),('c',4,1)])
            if scenario==3:
                for text,offset in [('q',0),('r',2)]:trace+=['nested',text.encode().hex(),str(offset),'1']
            if scenario<=4:trace+=['deleted']
            if scenario in (2,5):trace+=['terminal-marker','same-exception']
            trace+=['calls='+str(1 if scenario in (0,5) else 3),'dead' if scenario<=4 else 'alive']
            rows.append(dict(id=f'{kind}-{scenario}',value=trace))
    return rows


def canon(rows):
    return ''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows).encode()


def check(data):
    actual=[json.loads(line) for line in data.splitlines()]
    if actual!=expected():raise ValueError('terminal callback trace/exception/lifetime mismatch')
    return 14

"""Typed boundary between raw framebuffer envelopes and validated metadata.

Zstd's independent decoder is process-backed. Its semantic acceptance remains
at acquisition; this adapter validates only raw envelope/image integrity.
"""
from dataclasses import dataclass
from pathlib import Path
import copy
import json
import behavior_lab as lab

@dataclass(frozen=True)
class Envelope:
    metadata: dict
    file: str
    width: int
    height: int

    @classmethod
    def parse(cls, raw, name):
        if (not isinstance(raw, dict) or raw.get('name') != name
                or raw.get('file') != name+'.png'
                or not isinstance(raw.get('metadata'), dict)
                or raw['metadata'].get('scenario') not in lab.SCENARIOS
                or raw['metadata'].get('inWorld') is not True
                or type(raw.get('width')) is not int or raw['width'] <= 0
                or type(raw.get('height')) is not int or raw['height'] <= 0
                or not isinstance(raw.get('capture'), dict)
                or raw['capture'].get('source') != 'final-default-framebuffer'
                or raw['capture'].get('stage') != 'after-imgui-before-swap'):
            raise ValueError('invalid raw framebuffer envelope '+name)
        return cls(copy.deepcopy(raw['metadata']),raw['file'],raw['width'],raw['height'])


def admit(directory):
    directory=Path(directory)
    jsons={p.stem:p for p in directory.glob('*.json') if p.name!='manifest.json'}
    pngs={p.stem:p for p in directory.glob('*.png')}
    if jsons.keys()!=pngs.keys() or len(jsons)!=3:
        raise ValueError('three paired frame envelopes required')
    result={}
    for name,p in jsons.items():
        envelope=Envelope.parse(json.loads(p.read_bytes()),name)
        im=lab.image(pngs[name])
        if list(im.size)!=[envelope.width,envelope.height]:
            raise ValueError('frame envelope/image dimensions differ')
        result[name]=envelope
    return result


def controls():
    raw={'name':'state','file':'state.png','width':1000,'height':600,
         'metadata':{'scenario':'ttl-room','inWorld':True},
         'capture':{'source':'final-default-framebuffer','stage':'after-imgui-before-swap'}}
    Envelope.parse(raw,'state')
    rejected=[]
    for field,value in [('metadata',{}),('file','wrong.png'),('width',True),('capture',{})]:
        bad=copy.deepcopy(raw);bad[field]=value
        try:Envelope.parse(bad,'state')
        except ValueError:rejected.append(field);continue
        raise ValueError('schema control accepted '+field)
    return rejected

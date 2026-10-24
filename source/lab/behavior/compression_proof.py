"""Independent fixed Gzip/PNG anchor plus actual native producer/consumer receipts."""
import base64
import io
import zlib
from PIL import Image

COLOR = [96,192,224,255]
PNG = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000100000001008060000001ff3ff610000001a4944415478da634838f0e03f259861d4805103460d182e06000058cbff1f6e548d410000000049454e44ae426082')
GZIP = bytes.fromhex('1f8b08000000000002ffeb0cf073e7e592e2626060e0f5f4700902d20220ccc10624e53fff4f0452529e2e8e2115b7923d2c3e3cb0579d9178a52190d98d57420fa824e2f47ff9bc905e47a02a064f573f97754e094d00d52fea1d53000000')
GZIP_PATH = '/opensb_data;bin;gzip;H4sIAAAAAAAC_-sM8HPn5ZLiYmBg4PX0cAkC0gIgzMEGJOU__08EUlKeLo4hFbeSPSw-PLBXnZF4pSGQ2Y1XQg-oJOL0f_m8kF5HoCoGT1c_l3VOCU0A1S_qHVMAAAA='
MAX_PNG = 65536


def same(a,b):
    if type(a) is not type(b): return False
    if isinstance(b,list): return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    if isinstance(b,dict): return a.keys()==b.keys() and all(same(a[k],b[k]) for k in b)
    return a==b


def keys(value,names):
    if not isinstance(value,dict) or set(value)!=set(names.split()): raise ValueError('invalid compression proof schema')


def unhex(value):
    if not isinstance(value,str) or len(value)>MAX_PNG*2: raise ValueError('invalid compression byte length')
    try: data=bytes.fromhex(value)
    except ValueError as e: raise ValueError('invalid compression hex') from e
    if data.hex()!=value: raise ValueError('noncanonical compression hex')
    return data


def inflate(wire,bits):
    try:
        decoder=zlib.decompressobj(bits)
        data=decoder.decompress(wire,MAX_PNG+1)
    except zlib.error as e: raise ValueError('independent compressed payload rejected') from e
    if len(data)>MAX_PNG or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('invalid compressed PNG extent')
    return data


def png_pixels(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format!='PNG' or image.size!=(16,16): raise ValueError('invalid compression PNG dimensions')
            if image.convert('RGBA').tobytes()!=bytes(COLOR)*256: raise ValueError('compression PNG literal pixels differ')
    except (OSError,SyntaxError) as e: raise ValueError('independent PNG decoder rejected bytes') from e


def validate(receipt):
    p=receipt.get('compressionProof');keys(p,'version operations visual')
    if type(p['version']) is not int or p['version']!=1: raise ValueError('invalid compression proof version')
    ops=p['operations'];keys(ops,'embed zlib gzip');normalized={}
    backends=[]
    for kind,name in enumerate(('embed','zlib','gzip')):
        row=ops[name];keys(row,'backend path compressedHex pngHex calls');backend=row['backend'];backends.append(backend)
        if backend not in ('cpp','rust'): raise ValueError('invalid compression backend')
        vector=[int(i==kind) for i in range(3)] if backend=='rust' else [0]*3
        if not same(row['calls'],{'attempt':vector,'success':vector,'exception':[0]*3}): raise ValueError('compression native invocation/exit receipts differ')
        wire,png=unhex(row['compressedHex']),unhex(row['pngHex']);png_pixels(png)
        if name=='gzip':
            if row['path']!=GZIP_PATH or wire!=GZIP or png!=PNG: raise ValueError('independent fixed Gzip/PNG bytes differ')
        else:
            path=row['path']
            if not isinstance(path,str) or not path.startswith('/opensb_data;bin;zlib;') or len(path)>MAX_PNG*2: raise ValueError('invalid actual Zlib embedded path')
            payload=path.split(';',3)[3]
            try: path_wire=base64.b64decode(payload+'='*((-len(payload))%4),altchars=b'-_',validate=True)
            except (ValueError,base64.binascii.Error) as e: raise ValueError('invalid Zlib path payload') from e
            if path_wire!=wire: raise ValueError('actual Zlib path/wire differ')
        if inflate(wire,31 if name=='gzip' else 15)!=png: raise ValueError('independent decode differs from actual native PNG')
        normalized[name]={k:v for k,v in row.items() if k not in ('backend','calls')}
    if len(set(backends))!=1: raise ValueError('mixed compression backends')
    if normalized['embed']!=normalized['zlib']: raise ValueError('actual producer/Zlib consumer observations differ')
    visual={'imagePath':'/behaviorlab/compression-result.png','color':COLOR,'scale':4,'label':'COMPRESS'}
    if not same(p['visual'],visual): raise ValueError('compression actual returned image/visual differs')
    return {'version':1,'operations':normalized,'visual':p['visual']}


def visible(frame,receipt):
    if receipt.get('cameraPosition')!=[64,48] or receipt.get('cameraPixelRatio')!=2 or min(frame.size)<200: raise ValueError('invalid compression camera/viewport')
    x,y=frame.width//2,frame.height//2
    pixels=list(frame.crop((x-40,y-40,x+40,y+40)).convert('RGBA').getdata())
    if pixels.count(tuple(COLOR))<16: raise ValueError('actual compressed image has no visible cyan ink')
    rgba=frame.convert('RGBA')
    ink=[(i%rgba.width,i//rgba.width) for i,p in enumerate(rgba.getdata()) if p==tuple(COLOR)]
    bounds=(min(px for px,py in ink),min(py for px,py in ink),max(px for px,py in ink)+1,max(py for px,py in ink)+1)
    if len(ink)!=64*64 or bounds!=(x-32,y-32,x+32,y+32): raise ValueError('actual compressed image geometry differs from 64x64')
    label=list(frame.crop((x-100,y-100,x+100,y-40)).convert('RGBA').getdata())
    if label.count((255,255,255,255))<8: raise ValueError('compression normal Font label has no visible ink')

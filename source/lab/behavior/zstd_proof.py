"""Literal PNG/packet anchors plus genuine native TCP and Zstd invocation receipts."""
import base64
import io
import subprocess
from PIL import Image

COLOR=[224,160,64,255]
MAX_BYTES=65536
CLI='/opt/homebrew/bin/zstd'

def same(a,b):
    if type(a) is not type(b):return False
    if isinstance(b,list):return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    if isinstance(b,dict):return a.keys()==b.keys() and all(same(a[k],b[k]) for k in b)
    return a==b

def keys(value,names):
    if type(value) is not dict or set(value)!=set(names.split()):raise ValueError('invalid Zstd proof schema')

def unhex(value):
    if type(value) is not str or len(value)>MAX_BYTES*2:raise ValueError('invalid Zstd byte extent')
    try:data=bytes.fromhex(value)
    except ValueError as error:raise ValueError('invalid Zstd hex') from error
    if data.hex()!=value:raise ValueError('noncanonical Zstd hex')
    return data

def frame_size(wire):
    # Parse framing independently before calling a separate decoder artifact;
    # reject unknown sizes, concatenated frames and unbounded output up front.
    if len(wire)<6 or wire[:4]!=bytes.fromhex('28b52ffd'):raise ValueError('invalid Zstd frame magic')
    descriptor=wire[4];single=bool(descriptor&32)
    if descriptor&24:raise ValueError('reserved Zstd descriptor')
    position=5+(not single)+(0,1,2,4)[descriptor&3]
    width=((1 if single else 0),2,4,8)[descriptor>>6]
    if not width or position+width>len(wire):raise ValueError('unknown/truncated Zstd frame size')
    size=int.from_bytes(wire[position:position+width],'little')+(256 if width==2 else 0)
    if size>MAX_BYTES:raise ValueError('unbounded Zstd frame size')
    position+=width
    while True:
        if position+3>len(wire):raise ValueError('truncated Zstd block')
        header=int.from_bytes(wire[position:position+3],'little');position+=3
        kind=(header>>1)&3;length=header>>3
        if kind==3 or length>131072:raise ValueError('invalid Zstd block')
        position+=1 if kind==1 else length
        if position>len(wire):raise ValueError('truncated Zstd payload')
        if header&1:break
    position+=4 if descriptor&4 else 0
    if position!=len(wire):raise ValueError('trailing/concatenated Zstd frame')
    return size

def inflate(wire):
    expected=frame_size(wire)
    try:result=subprocess.run([CLI,'-d','-q','-c','-M1MB'],input=wire,capture_output=True,timeout=5)
    except (OSError,subprocess.TimeoutExpired) as error:raise ValueError('external Zstd decoder unavailable') from error
    if result.returncode or len(result.stdout)!=expected:raise ValueError('external Zstd decode differs')
    return result.stdout

def png_pixels(png):
    try:
        with Image.open(io.BytesIO(png)) as image:
            if image.format!='PNG' or image.size!=(16,16) or image.convert('RGBA').tobytes()!=bytes(COLOR)*256:raise ValueError('Zstd PNG literal pixels differ')
    except (OSError,SyntaxError) as error:raise ValueError('invalid Zstd PNG') from error

def calls(value,backend,kind):
    vector=[int(i==kind) for i in range(4)] if backend=='rust' else [0]*4
    if not same(value,{'attempt':vector,'success':vector,'exception':[0]*4}):raise ValueError('Zstd native call receipts differ')

def bulk_text():
    state=0x12345678;out=[]
    for _ in range(16384):
        state^=(state<<13)&0xffffffff;state^=state>>17;state^=(state<<5)&0xffffffff
        out.append('0123456789abcdef'[(state>>28)&15])
    return ''.join(out).encode()

def vlq(value):
    parts=[value&127];value>>=7
    while value:parts.append(128|(value&127));value>>=7
    return bytes(reversed(parts))

def packet(text):
    # ChatSend=18, Broadcast=0, protocol5 empty JsonObject count=0.
    body=vlq(len(text))+text+b'\0\0'
    return b'\x12'+vlq(2*len(body))+body

def validate(receipt):
    proof=receipt.get('zstdProof');keys(proof,'version backend image network visual')
    if type(proof['version']) is not int or proof['version']!=1:raise ValueError('invalid Zstd proof version')
    backend=proof['backend']
    if backend not in ('cpp','rust'):raise ValueError('invalid Zstd backend')
    image=proof['image'];keys(image,'embed decode size rgbaHex');rows={}
    for kind,name in [(2,'embed'),(3,'decode')]:
        row=image[name];keys(row,'path compressedHex pngHex calls');calls(row['calls'],backend,kind)
        wire,png=unhex(row['compressedHex']),unhex(row['pngHex']);png_pixels(png)
        path=row['path']
        if type(path) is not str or not path.startswith('/opensb_data;bin;zstd;') or len(path)>MAX_BYTES*2:raise ValueError('invalid actual Zstd embedded path')
        payload=path.split(';',3)[3]
        try:encoded=base64.b64decode(payload+'='*((-len(payload))%4),altchars=b'-_',validate=True)
        except (ValueError,base64.binascii.Error) as error:raise ValueError('invalid Zstd path payload') from error
        if encoded!=wire or inflate(wire)!=png:raise ValueError('actual Zstd source/wire/PNG differ')
        rows[name]={key:value for key,value in row.items() if key!='calls'}
    if rows['embed']!=rows['decode']:raise ValueError('Zstd actual producer/consumer differ')
    if not same(image['size'],[16,16]) or unhex(image['rgbaHex'])!=bytes(COLOR)*256:raise ValueError('actual decoded Zstd image differs')
    network=proof['network'];keys(network,'transport address streamEnabled rulesVersion rounds')
    if not same({k:network[k] for k in ('transport','address','streamEnabled','rulesVersion')},{'transport':'tcp','address':'127.0.0.1','streamEnabled':True,'rulesVersion':5}):raise ValueError('real loopback stream transport required')
    rounds=network['rounds']
    if type(rounds) is not list or len(rounds)!=3:raise ValueError('missing Zstd TCP rounds')
    expected_texts=[rows['embed']['path'].encode(),b'ZSTD',bulk_text()];normalized=[]
    for index,(row,text) in enumerate(zip(rounds,expected_texts)):
        keys(row,'direction textHex receivedHex sendMode receivedMode receivedData events')
        if row['direction']!=('b-to-a' if index==1 else 'a-to-b') or unhex(row['textHex'])!=text or unhex(row['receivedHex'])!=text:raise ValueError('actual decoded TCP label/path/payload differs')
        if not same([row['sendMode'],row['receivedMode'],row['receivedData']],[0,0,{}]):raise ValueError('actual native ChatSend fields differ')
        events=row['events']
        if type(events) is not list or not 2<=len(events)<=64:raise ValueError('actual native TCP codec events required')
        streams=[[],[],[],[]]
        for number,event in enumerate(events):
            keys(event,'kind inputHex outputHex calls');kind=event['kind']
            if type(kind) is not int or kind!=(0 if number==0 else 1):raise ValueError('invalid TCP codec event order')
            calls(event['calls'],backend,kind);before=unhex(event['inputHex']);after=unhex(event['outputHex'])
            if not before or len(before)>32768 or len(after)>32768 or kind==1 and len(before)>1024:raise ValueError('invalid native TCP event extent')
            streams[kind*2].append(before);streams[kind*2+1].append(after)
        compress_input,compress_output,decompress_input,decompress_output=[b''.join(parts) for parts in streams]
        expected=packet(text)
        if compress_input!=expected or decompress_output!=expected or not compress_output or compress_output!=decompress_input:raise ValueError('independent typed packet/coalesced native wire differs')
        if index==2 and (len(compress_output)<=1024 or len(events)<3):raise ValueError('bulk TCP receive boundary not exercised')
        normalized.append({k:row[k] for k in ('direction','textHex','receivedHex','sendMode','receivedMode','receivedData')}|{'streams':[part.hex() for part in (compress_input,compress_output,decompress_input,decompress_output)]})
    visual={'imagePath':rows['embed']['path'],'color':COLOR,'scale':4,'label':'ZSTD'}
    if not same(proof['visual'],visual):raise ValueError('actual TCP/image-driven visual differs')
    # Only OS read partition and backend-specific counters are projected out,
    # AFTER each native record and all coalesced bytes have been validated.
    return {'version':1,'image':rows,'network':normalized,'visual':visual}

def visible(frame,receipt):
    if receipt.get('cameraPosition')!=[64,48] or receipt.get('cameraPixelRatio')!=2 or min(frame.size)<200:raise ValueError('invalid Zstd camera/viewport')
    rgba=frame.convert('RGBA');x,y=frame.width//2,frame.height//2
    ink=[(i%rgba.width,i//rgba.width) for i,p in enumerate(rgba.getdata()) if p==tuple(COLOR)]
    if not ink:raise ValueError('actual Zstd image has no visible ink')
    bounds=(min(px for px,py in ink),min(py for px,py in ink),max(px for px,py in ink)+1,max(py for px,py in ink)+1)
    if len(ink)!=4096 or bounds!=(x-32,y-32,x+32,y+32):raise ValueError('actual Zstd image geometry differs from64x64')
    if list(frame.crop((x-100,y-100,x+100,y-40)).convert('RGBA').getdata()).count((255,255,255,255))<8:raise ValueError('Zstd normal Font label missing')

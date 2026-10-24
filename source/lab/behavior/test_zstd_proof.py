"""Synthetic records exercise the verifier, never substitute for real captures."""
import base64,copy,struct,unittest,zlib
from PIL import Image
import zstd_proof as proof

def png(color):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',16,16,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes(color)*16)*16))+chunk(b'IEND',b'')

def raw_frame(data):
    header=b'\x20'+bytes([len(data)]) if len(data)<256 else b'\x60'+(len(data)-256).to_bytes(2,'little')
    return bytes.fromhex('28b52ffd')+header+((len(data)<<3)|1).to_bytes(3,'little')+data

def calls(backend,kind):
    vector=[int(i==kind) for i in range(4)] if backend=='rust' else [0]*4
    return {'attempt':vector.copy(),'success':vector.copy(),'exception':[0]*4}

def fixture(backend='rust',color=None,partition=1024):
    color=color or proof.COLOR;data=png(color);wire=raw_frame(data);path='/opensb_data;bin;zstd;'+base64.urlsafe_b64encode(wire).decode()
    image={name:{'path':path,'compressedHex':wire.hex(),'pngHex':data.hex(),'calls':calls(backend,kind)} for kind,name in [(2,'embed'),(3,'decode')]}
    image.update(size=[16,16],rgbaHex=(bytes(color)*256).hex());rounds=[]
    for index,text in enumerate([path.encode(),b'ZSTD',proof.bulk_text()]):
        native=proof.packet(text);compressed=raw_frame(native);parts=[compressed[i:i+partition] for i in range(0,len(compressed),partition)]
        width=(len(native)+len(parts)-1)//len(parts)
        events=[{'kind':0,'inputHex':native.hex(),'outputHex':compressed.hex(),'calls':calls(backend,0)}]
        for number,part in enumerate(parts):events.append({'kind':1,'inputHex':part.hex(),'outputHex':native[number*width:(number+1)*width].hex(),'calls':calls(backend,1)})
        rounds.append({'direction':'b-to-a' if index==1 else 'a-to-b','textHex':text.hex(),'receivedHex':text.hex(),'sendMode':0,'receivedMode':0,'receivedData':{},'events':events})
    return {'zstdProof':{'version':1,'backend':backend,'image':image,'network':{'transport':'tcp','address':'127.0.0.1','streamEnabled':True,'rulesVersion':5,'rounds':rounds},'visual':{'imagePath':path,'color':color,'scale':4,'label':'ZSTD'}}}

class ZstdProofTests(unittest.TestCase):
    def test_raw_frame_and_typed_literal(self):
        self.assertEqual(proof.frame_size(bytes.fromhex('28b52ffd2003190000616263')),3)
        self.assertEqual(proof.inflate(bytes.fromhex('28b52ffd2003190000616263')),b'abc')
        self.assertEqual(proof.packet(b'ZSTD').hex(),'120e045a5354440000')

    def test_native_backends_and_os_partition_normalize(self):
        self.assertEqual(proof.validate(fixture()),proof.validate(fixture('cpp')))
        self.assertEqual(proof.validate(fixture()),proof.validate(fixture(partition=601)))

    def test_paired_wrong_png_not_a_roundtrip_anchor(self):
        with self.assertRaisesRegex(ValueError,'literal pixels'):proof.validate(fixture(color=[1,2,3,255]))

    def test_genuine_transport_and_native_events_required(self):
        for key,value in [('transport','local'),('streamEnabled',False),('address','0.0.0.0')]:
            receipt=fixture();receipt['zstdProof']['network'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):proof.validate(receipt)
        receipt=fixture();receipt['zstdProof']['network']['rounds'][0]['events']=[]
        with self.assertRaisesRegex(ValueError,'native TCP'):proof.validate(receipt)

    def test_native_receipt_suppression_rejected(self):
        for kind in (0,1):
            receipt=fixture();event=receipt['zstdProof']['network']['rounds'][0]['events'][kind];event['calls']['success']=[0]*4
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'receipts'):proof.validate(receipt)
        receipt=fixture();receipt['zstdProof']['image']['embed']['calls']['attempt'][2]=True
        with self.assertRaises(ValueError):proof.validate(receipt)

    def test_altered_received_fields_wire_and_missing_round(self):
        for key,value in [('receivedHex','424144'),('receivedMode',True),('receivedData',{'wrong':1})]:
            receipt=fixture();receipt['zstdProof']['network']['rounds'][1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):proof.validate(receipt)
        receipt=fixture();receipt['zstdProof']['network']['rounds'][0]['events'][0]['inputHex']='00'
        with self.assertRaisesRegex(ValueError,'typed packet'):proof.validate(receipt)
        receipt=fixture();receipt['zstdProof']['network']['rounds'].pop()
        with self.assertRaisesRegex(ValueError,'missing'):proof.validate(receipt)

    def test_framing_extent_checks_before_decoder(self):
        wire=raw_frame(b'abc')
        for bad in [wire[:-1],wire+wire,wire+b'x',bytes.fromhex('28b52ffd0000010000')]:
            with self.subTest(bad=bad.hex()),self.assertRaises(ValueError):proof.frame_size(bad)
        with self.assertRaisesRegex(ValueError,'unbounded'):proof.frame_size(bytes.fromhex('28b52ffde0')+(65537).to_bytes(8,'little'))

    def test_visible_geometry_and_font(self):
        receipt={'cameraPosition':[64,48],'cameraPixelRatio':2};frame=Image.new('RGBA',(1000,600),(0,0,0,255))
        frame.paste(tuple(proof.COLOR),(436,236,564,364))
        with self.assertRaisesRegex(ValueError,'geometry'):proof.visible(frame,receipt)
        frame=Image.new('RGBA',(1000,600),(0,0,0,255));frame.paste(tuple(proof.COLOR),(468,268,532,332))
        with self.assertRaisesRegex(ValueError,'Font'):proof.visible(frame,receipt)
        frame.paste((255,255,255,255),(465,215,535,220));proof.visible(frame,receipt)

if __name__=='__main__':unittest.main()

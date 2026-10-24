import base64
import copy
import io
import unittest
import zlib
from PIL import Image
import compression_proof as proof


def fixture(backend='rust'):
    wire=zlib.compress(proof.PNG,5)
    path='/opensb_data;bin;zlib;'+base64.urlsafe_b64encode(wire).decode()
    rows={}
    for index,name in enumerate(('embed','zlib','gzip')):
        v=[int(i==index) for i in range(3)] if backend=='rust' else [0]*3
        rows[name]={'backend':backend,'path':proof.GZIP_PATH if name=='gzip' else path,
            'compressedHex':(proof.GZIP if name=='gzip' else wire).hex(),'pngHex':proof.PNG.hex(),
            'calls':{'attempt':v.copy(),'success':v.copy(),'exception':[0]*3}}
    return {'compressionProof':{'version':1,'operations':rows,'visual':{'imagePath':'/behaviorlab/compression-result.png','color':proof.COLOR.copy(),'scale':4,'label':'COMPRESS'}}}


class CompressionProofTests(unittest.TestCase):
    def test_native_backends_normalize(self):
        self.assertEqual(proof.validate(fixture()),proof.validate(fixture('cpp')))

    def test_independent_gzip_png_literal(self):
        self.assertEqual(proof.inflate(proof.GZIP,31),proof.PNG)
        proof.png_pixels(proof.PNG)
        self.assertEqual(base64.urlsafe_b64decode(proof.GZIP_PATH.split(';',3)[3]),proof.GZIP)

    def test_matched_wrong_roundtrip_is_insufficient(self):
        stream=io.BytesIO();Image.new('RGBA',(16,16),(1,2,3,255)).save(stream,format='PNG')
        png=stream.getvalue();wire=zlib.compress(png)
        p=fixture()
        for name in ('embed','zlib'):
            p['compressionProof']['operations'][name].update(pngHex=png.hex(),compressedHex=wire.hex(),path='/opensb_data;bin;zlib;'+base64.urlsafe_b64encode(wire).decode())
        with self.assertRaisesRegex(ValueError,'literal pixels'):proof.validate(p)

    def test_all_three_actual_call_exit_vectors_required(self):
        for name in ('embed','zlib','gzip'):
            for event in ('attempt','success'):
                p=fixture();p['compressionProof']['operations'][name]['calls'][event]=[0]*3
                with self.subTest(name=name,event=event),self.assertRaisesRegex(ValueError,'receipts'):proof.validate(p)

    def test_native_path_payload_must_equal_observed_wire(self):
        p=fixture();p['compressionProof']['operations']['embed']['path']+='_'
        with self.assertRaises(ValueError):proof.validate(p)
        p=fixture();p['compressionProof']['operations']['zlib']['pngHex']=proof.PNG[:-1].hex()
        with self.assertRaises(ValueError):proof.validate(p)

    def test_fixed_gzip_not_an_unanchored_second_roundtrip(self):
        p=fixture();p['compressionProof']['operations']['gzip']['compressedHex']=proof.GZIP[:-1].hex()
        with self.assertRaisesRegex(ValueError,'fixed Gzip'):proof.validate(p)

    def test_types_schema_backend_and_size(self):
        p=fixture();p['compressionProof']['operations']['embed']['calls']['attempt'][0]=True
        with self.assertRaises(ValueError):proof.validate(p)
        p=fixture();p['compressionProof']['operations']['gzip']['backend']='cpp'
        p['compressionProof']['operations']['gzip']['calls']={k:[0]*3 for k in ('attempt','success','exception')}
        with self.assertRaisesRegex(ValueError,'mixed'):proof.validate(p)
        p=fixture();p['compressionProof']['inferred']=True
        with self.assertRaises(ValueError):proof.validate(p)
        with self.assertRaises(ValueError):proof.inflate(zlib.compress(bytes(proof.MAX_PNG+1)),15)

    def test_wrong_projection_scale_is_detected(self):
        frame=Image.new('RGBA',(1000,600),(0,0,0,255))
        frame.paste(tuple(proof.COLOR),(436,236,564,364))
        with self.assertRaisesRegex(ValueError,'geometry differs'):proof.visible(frame,{'cameraPosition':[64,48],'cameraPixelRatio':2})

    def test_real_visible_image_and_label_required(self):
        frame=Image.new('RGBA',(1000,600),(0,0,0,255));receipt={'cameraPosition':[64,48],'cameraPixelRatio':2}
        with self.assertRaisesRegex(ValueError,'cyan ink'):proof.visible(frame,receipt)
        frame.paste(tuple(proof.COLOR),(468,268,532,332))
        with self.assertRaisesRegex(ValueError,'Font label'):proof.visible(frame,receipt)
        frame.paste((255,255,255,255),(465,215,535,220));proof.visible(frame,receipt)


if __name__=='__main__':unittest.main()
